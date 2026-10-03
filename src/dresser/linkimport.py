"""Import a piece from a public product link: fetch the page, read its title/description/image, download the picture.

Honest scope: this reads what a shop puts in the *HTML it sends to anyone* (Open Graph tags, JSON-LD product data).
It does not log in, execute JavaScript, solve captchas or bypass blocks. Many shops (Taobao/Tmall, Xiaohongshu, ...)
answer with a block page, a login wall or an empty JavaScript shell; then you get a clear message and the fallback is
to save the product image and upload it. Pages that did and did not work when I tried: see README.

Safety: only http/https on ports 80/443/8080/8443; every host (including redirect targets and the image host) must
resolve only to public IP addresses; redirects are followed by hand (max 4); response sizes are capped; a short timeout.
Limit: the check happens before the request, so a hostile DNS server could in theory answer differently to the HTTP
client (DNS rebinding); this tool is meant for a personal single-user app, not as a public proxy.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

UA = "Mozilla/5.0 (compatible; Dresser/0.3; personal wardrobe app; single page fetch)"
MAX_HTML = 2 * 1024 * 1024
MAX_IMAGE = 12 * 1024 * 1024
TIMEOUT = 10.0
ALLOWED_PORTS = {None, 80, 443, 8080, 8443}
HARD_SITES = ("taobao.com", "tmall.com", "xiaohongshu.com", "xhslink.com", "1688.com", "pinduoduo.com", "douyin.com", "jd.com")


class LinkError(ValueError):
    """A problem the user can understand; `kind` is one of refused, bad-url, network, blocked, login, no-data, too-large."""

    def __init__(self, message: str, kind: str = "no-data"):
        super().__init__(message)
        self.kind = kind


# ---------------------------------------------------------------- SSRF guard
def _ip_ok(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_global and not a.is_multicast


def check_url(url: str, resolver=socket.getaddrinfo) -> str:
    """Return the cleaned URL or raise LinkError('bad-url'|'refused'). Resolves the host and requires public addresses only."""
    url = (url or "").strip()
    try:
        p = urlparse(url)
        port = p.port
    except ValueError:
        raise LinkError("That does not look like a web address.", "bad-url") from None
    if p.scheme not in ("http", "https") or not p.hostname:
        raise LinkError("Only http:// or https:// links are accepted.", "bad-url")
    if p.username or p.password:
        raise LinkError("Links with a username or password are not accepted.", "bad-url")
    if port not in ALLOWED_PORTS:
        raise LinkError("Only the standard web ports (80, 443, 8080, 8443) are accepted.", "refused")
    host = p.hostname
    try:
        ipaddress.ip_address(host)
        addrs = [host]
    except ValueError:
        try:
            addrs = [ai[4][0] for ai in resolver(host, port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)]
        except OSError:
            raise LinkError(f"I could not find the site {host}.", "network") from None
    if not addrs or not all(_ip_ok(a) for a in addrs):
        raise LinkError("That address points to a private or local network, which this tool refuses to contact.", "refused")
    return url


# ---------------------------------------------------------------- fetching
def make_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, follow_redirects=False,
                        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,image/*;q=0.8,*/*;q=0.5",
                                 "Accept-Language": "en,zh;q=0.8"})


def fetch(url: str, client: httpx.Client, max_bytes: int, resolver=socket.getaddrinfo, max_redirects: int = 4):
    """GET with manual, re-validated redirects and a hard size cap. Returns (final_url, content_type, bytes, charset)."""
    for _ in range(max_redirects + 1):
        url = check_url(url, resolver)
        try:
            with client.stream("GET", url) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    url = urljoin(url, r.headers["location"])
                    continue
                if r.status_code in (401, 403, 407, 429, 451):
                    raise LinkError(_blocked_msg(url, r.status_code), "blocked")
                if r.status_code == 404:
                    raise LinkError("The page was not found (HTTP 404): check the link.", "no-data")
                if r.status_code != 200:
                    raise LinkError(f"The site answered HTTP {r.status_code}.", "blocked" if r.status_code >= 500 else "no-data")
                ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                charset = (re.search(r"charset=([\w-]+)", r.headers.get("content-type", "")) or [None, None])[1]
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        raise LinkError("The page is larger than the size limit, so I stopped reading it.", "too-large")
                return url, ctype, bytes(buf), charset
        except httpx.TimeoutException:
            raise LinkError(f"{urlparse(url).hostname} did not answer within {TIMEOUT:g} seconds.", "network") from None
        except httpx.HTTPError as e:
            raise LinkError(f"Could not reach {urlparse(url).hostname} ({type(e).__name__}).", "network") from None
    raise LinkError("Too many redirects.", "network")


def _hard_site(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in HARD_SITES)


def _blocked_msg(url: str, status: int) -> str:
    host = urlparse(url).hostname
    extra = " Shops like this usually need JavaScript or a login." if _hard_site(url) else ""
    return f"{host} refused the automated request (HTTP {status}).{extra}"


# ---------------------------------------------------------------- parsing
class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.title = ""
        self.jsonld: list[str] = []
        self._in_title = False
        self._in_ld = False
        self._ld = ""

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "link" and a.get("rel", "").lower() == "image_src" and a.get("href"):
            self.links["image_src"] = a["href"]
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and "ld+json" in a.get("type", "").lower():
            self._in_ld, self._ld = True, ""

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld:
            self._in_ld = False
            self.jsonld.append(self._ld)

    def handle_data(self, data):
        if self._in_title and len(self.title) < 300:
            self.title += data
        elif self._in_ld:
            self._ld += data


@dataclass
class Product:
    url: str
    title: str = ""
    description: str = ""
    images: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)       # color, material, brand, category from JSON-LD when present


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _first_str(v) -> str:
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        for x in v:
            s = _first_str(x)
            if s:
                return s
    if isinstance(v, dict):
        return _first_str(v.get("name") or v.get("url") or "")
    return ""


def _image_urls(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [u for x in v for u in _image_urls(x)]
    if isinstance(v, dict):
        return _image_urls(v.get("url") or v.get("contentUrl") or "")
    return []


def parse_product(html: str, page_url: str) -> Product:
    pg = _Page()
    try:
        pg.feed(html)
    except Exception:       # a malformed page must not crash the app; use whatever was read so far
        pass
    prod = Product(page_url)
    ld: dict = {}
    for raw in pg.jsonld:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        for o in _walk(data):
            t = o.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Product" in types and not ld:
                ld = o
    prod.title = (_first_str(ld.get("name")) or pg.meta.get("og:title") or pg.meta.get("twitter:title") or pg.title).strip()
    prod.description = (_first_str(ld.get("description")) or pg.meta.get("og:description") or pg.meta.get("description")
                        or pg.meta.get("twitter:description") or "").strip()
    cands = [pg.meta.get("og:image:secure_url"), pg.meta.get("og:image"), pg.meta.get("twitter:image"),
             *_image_urls(ld.get("image")), pg.links.get("image_src")]
    seen: list[str] = []
    for c in cands:
        if c:
            u = urljoin(page_url, c.strip())
            if urlparse(u).scheme in ("http", "https") and u not in seen:
                seen.append(u)
    prod.images = seen
    for k in ("color", "material", "category"):
        v = _first_str(ld.get(k))
        if v:
            prod.extra[k] = v
    b = _first_str(ld.get("brand"))
    if b:
        prod.extra["brand"] = b
    prod.title = re.sub(r"\s+", " ", prod.title)[:120]
    prod.description = re.sub(r"\s+", " ", prod.description)[:400]
    return prod


def decode(body: bytes, charset: str | None) -> str:
    for enc in (charset, "utf-8"):
        if enc:
            try:
                return body.decode(enc)
            except (LookupError, UnicodeDecodeError):
                continue
    return body.decode("utf-8", "replace")


LOGIN_HINT = re.compile(r"(login|signin|sign-in|passport|captcha|verify|security-check|punish)", re.I)


def read_page(url: str, client: httpx.Client, resolver=socket.getaddrinfo) -> Product:
    """Fetch and parse one product page. Raises LinkError with a message the user can act on."""
    final, ctype, body, charset = fetch(url, client, MAX_HTML, resolver)
    redirected = final != url
    if LOGIN_HINT.search(urlparse(final).path) or (redirected and LOGIN_HINT.search(urlparse(final).hostname or "")):
        raise LinkError(f"{urlparse(final).hostname} sent me to a login or verification page; this tool does not log in. "
                        "Save the product image and upload it instead.", "login")
    if "html" not in ctype and "xml" not in ctype:
        if ctype.startswith("image/"):
            raise LinkError("That link is a picture, not a web page: upload the picture directly.", "no-data")
        raise LinkError(f"That link is not a web page (it is {ctype or 'unknown'}).", "no-data")
    prod = parse_product(decode(body, charset), final)
    if not prod.images:
        hard = " Shops like this render products with JavaScript or require a login." if _hard_site(final) else \
               " Many shops build the page with JavaScript, which this tool does not run."
        raise LinkError(f"I found no product picture in the HTML of {urlparse(final).hostname}.{hard} "
                        "Save the product image and upload it instead.", "no-data")
    return prod


MIN_SIDE, MIN_BYTES = 200, 8_000       # smaller than this is a logo / placeholder, not a product photo


def _big_enough(body: bytes) -> bool:
    if len(body) < MIN_BYTES:
        return False
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(body)) as im:
            return min(im.size) >= MIN_SIDE
    except Exception:       # undecodable here: let the later photo_to_jpeg step give the user-facing error
        return True


def download_image(prod: Product, client: httpx.Client, resolver=socket.getaddrinfo) -> tuple[str, bytes]:
    """Try the candidate pictures in order; return (url, raw bytes) of the first that downloads (decoding happens later)."""
    last: LinkError | None = None
    for u in prod.images[:4]:
        try:
            final, ctype, body, _ = fetch(u, client, MAX_IMAGE, resolver)
        except LinkError as e:
            last = e
            continue
        if body and _big_enough(body):
            return final, body
        if body:
            last = LinkError("The only picture on that page is tiny (a logo or placeholder, not a product photo).", "no-data")
    raise last or LinkError("The product picture could not be downloaded.", "no-data")


# ---------------------------------------------------------------- text-only guess (used when no vision model can run)
_TYPES = [  # (keywords, category, type, warmth, formality)
    (("t-shirt", "tee", "tank top", "polo", "t恤", "背心"), "top", "t-shirt", 1, 2),
    (("blouse", "shirt", "衬衫", "衬衣"), "top", "shirt", 2, 3),
    (("sweater", "jumper", "knit", "pullover", "毛衣", "针织"), "top", "sweater", 4, 3),
    (("hoodie", "sweatshirt", "卫衣"), "top", "hoodie", 3, 1),
    (("cardigan", "开衫"), "outer", "cardigan", 3, 3),
    (("blazer", "西装外套", "西服"), "outer", "blazer", 3, 4),
    (("puffer", "down jacket", "parka", "羽绒"), "outer", "puffer jacket", 4, 2),
    (("trench", "风衣"), "outer", "trench coat", 3, 4),
    (("coat", "大衣"), "outer", "coat", 4, 4),
    (("jacket", "夹克", "外套"), "outer", "jacket", 3, 3),
    (("jeans", "牛仔裤"), "bottom", "jeans", 3, 2),
    (("shorts", "短裤"), "bottom", "shorts", 1, 2),
    (("skirt", "半身裙", "裙"), "bottom", "skirt", 2, 3),
    (("trousers", "pants", "chinos", "leggings", "裤"), "bottom", "trousers", 3, 3),
    (("dress", "gown", "连衣裙"), "dress", "dress", 2, 4),
    (("sneaker", "trainer", "运动鞋", "板鞋"), "shoes", "sneakers", 2, 2),
    (("boot", "靴"), "shoes", "boots", 4, 3),
    (("sandal", "凉鞋"), "shoes", "sandals", 1, 2),
    (("heel", "pump", "高跟"), "shoes", "high heels", 2, 4),
    (("loafer", "flat", "ballet", "乐福", "平底"), "shoes", "flats", 2, 3),
    (("shoe", "鞋"), "shoes", "shoes", 2, 3),
]
_COLORS = {"black": "black", "white": "white", "grey": "grey", "gray": "grey", "beige": "beige", "cream": "cream", "navy": "navy",
           "blue": "blue", "red": "red", "green": "green", "yellow": "yellow", "pink": "pink", "brown": "brown", "tan": "tan",
           "khaki": "khaki", "olive": "olive", "burgundy": "burgundy", "orange": "orange", "purple": "purple", "camel": "camel",
           "黑": "black", "白": "white", "灰": "grey", "米": "beige", "蓝": "blue", "红": "red", "绿": "green", "黄": "yellow",
           "粉": "pink", "棕": "brown", "咖": "brown"}
_MATERIALS = ("cotton", "linen", "wool", "cashmere", "denim", "leather", "silk", "polyester", "nylon", "suede", "knit", "canvas",
              "fleece", "velvet", "satin", "rubber")


def _has(t: str, k: str) -> bool:
    return bool(re.search(rf"\b{re.escape(k)}\w*", t)) if k.isascii() else k in t


def guess_from_text(text: str) -> dict:
    """Deterministic fields from a product title/description. Only keys it is reasonably sure of are returned."""
    t = (text or "").lower()
    out: dict = {}
    for kws, cat, typ, w, f in _TYPES:
        if any(_has(t, k) for k in kws):
            out.update(category=cat, type=typ, warmth=w, formality=f)
            break
    for k, v in _COLORS.items():
        if _has(t, k) if k.isascii() else k in t:
            out["color"] = v
            break
    for m in _MATERIALS:
        if re.search(rf"\b{m}\b", t):
            out["material"] = m
            break
    return out
