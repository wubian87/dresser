"""'Paste a product link': mocked shop pages (no real network), SSRF guard, honest failures, and the API."""
import io
import json
import random

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conftest import FakeVision, make_stylist
from dresser import api
from dresser import linkimport as li
from dresser.config import load_config
from conftest import ROOT


def noisy_jpeg(size=(320, 420)):
    rnd = random.Random(1)
    im = Image.frombytes("RGB", size, bytes(rnd.randrange(256) for _ in range(size[0] * size[1] * 3)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


IMG = noisy_jpeg()
PRIVATE = {"internal.example": "10.0.0.5", "loop.example": "127.0.0.1", "meta.example": "169.254.169.254", "v6.example": "::1",
           "localhost": "127.0.0.1", "2130706433": "127.0.0.1", "0x7f.0.0.1": "127.0.0.1"}      # what getaddrinfo answers for these


def resolver(host, port, *a, **k):
    ip = PRIVATE.get(host, "93.184.216.34")
    return [(10 if ":" in ip else 2, 1, 6, "", (ip, port))]


PAGE = """<!doctype html><html><head><title>Fallback title</title>
<meta property="og:title" content="Women's Navy Linen Blend Shirt">
<meta property="og:description" content="Relaxed fit shirt in breathable linen.">
<meta property="og:image" content="/img/shirt.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Linen Shirt","color":"Navy",
 "material":"Linen","image":["https://cdn.shop.example/other.jpg"],"brand":{"@type":"Brand","name":"Acme"}}</script>
</head><body><h1>Shirt</h1></body></html>"""


def shop(pages=None, image=IMG, status=200):
    """A fake web: path -> response."""
    seen = []

    def handler(req: httpx.Request):
        seen.append(str(req.url))
        pages_ = pages or {}
        if req.url.path in pages_:
            return pages_[req.url.path](req) if callable(pages_[req.url.path]) else pages_[req.url.path]
        if req.url.path.endswith(".jpg"):
            return httpx.Response(200, content=image, headers={"content-type": "image/jpeg"})
        return httpx.Response(status, text=PAGE, headers={"content-type": "text/html; charset=utf-8"})
    c = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    c.seen = seen
    return c


def wire(st, client=None):
    st.link_client_factory = lambda: client or shop()
    st.link_resolver = resolver
    return st


# ---------------- parsing ----------------
def test_parse_og_and_jsonld():
    p = li.parse_product(PAGE, "https://shop.example/p/shirt")
    assert p.title == "Linen Shirt" and "breathable linen" in p.description            # JSON-LD product name beats og:title
    assert li.parse_product(PAGE.replace("Linen Shirt", ""), "https://shop.example/").title == "Women's Navy Linen Blend Shirt"
    assert p.images[0] == "https://shop.example/img/shirt.jpg"                      # relative og:image resolved
    assert "https://cdn.shop.example/other.jpg" in p.images                         # JSON-LD image kept as a fallback candidate
    assert p.extra["color"] == "Navy" and p.extra["material"] == "Linen" and p.extra["brand"] == "Acme"


def test_parse_jsonld_graph_and_title_fallback():
    html = ('<title>Plain title</title><script type="application/ld+json">{"@graph":[{"@type":"WebSite"},'
            '{"@type":["Product"],"name":"Graph tee","image":{"url":"//cdn.x.example/t.png"}}]}</script>')
    p = li.parse_product(html, "https://x.example/a")
    assert p.title == "Graph tee" and p.images == ["https://cdn.x.example/t.png"]
    q = li.parse_product("<title>Just a title</title>", "https://x.example/")
    assert q.title == "Just a title" and q.images == []
    assert li.parse_product("<script type='application/ld+json'>{broken", "https://x.example/").images == []


def test_guess_from_text_en_zh_and_word_boundaries():
    g = li.guess_from_text("Women's Navy Linen Blend Shirt")
    assert (g["category"], g["type"], g["color"], g["material"]) == ("top", "shirt", "navy", "linen")
    z = li.guess_from_text("男士黑色牛仔裤 纯棉")
    assert z["type"] == "jeans" and z["color"] == "black"
    assert li.guess_from_text("steel wheelbarrow").get("type") is None             # 'tee'/'heel' inside other words don't match
    assert li.guess_from_text("") == {}


# ---------------- SSRF guard ----------------
@pytest.mark.parametrize("url,kind", [
    ("file:///etc/passwd", "bad-url"), ("ftp://shop.example/a", "bad-url"), ("gopher://shop.example", "bad-url"), ("javascript:alert(1)", "bad-url"),
    ("", "bad-url"), ("not a url", "bad-url"), ("https://user:pw@shop.example/", "bad-url"),
    ("http://127.0.0.1/", "refused"), ("http://127.0.0.1:8000/api/status", "refused"), ("http://localhost/", "refused"),
    ("http://10.1.2.3/", "refused"), ("http://192.168.1.1/", "refused"), ("http://172.16.0.9/", "refused"),
    ("http://169.254.169.254/latest/meta-data", "refused"), ("http://[::1]/", "refused"), ("http://[::ffff:127.0.0.1]/", "refused"),
    ("http://0.0.0.0/", "refused"), ("http://2130706433/", "refused"), ("http://0x7f.0.0.1/", "refused"),
    ("http://internal.example/", "refused"), ("http://loop.example/", "refused"), ("http://meta.example/", "refused"), ("http://v6.example/", "refused"),
    ("https://shop.example:22/", "refused"), ("http://shop.example:6379/", "refused")])
def test_ssrf_guard_rejects(url, kind):
    with pytest.raises(li.LinkError) as e:
        li.check_url(url, resolver)
    assert e.value.kind == kind


def test_ssrf_guard_accepts_public_http_and_https():
    assert li.check_url("https://shop.example/p?id=1", resolver) == "https://shop.example/p?id=1"
    assert li.check_url("http://shop.example:8080/p", resolver)


def test_redirect_to_private_address_is_refused_and_never_requested():
    client = shop({"/p": httpx.Response(302, headers={"location": "http://internal.example/admin"})})
    with pytest.raises(li.LinkError) as e:
        li.read_page("https://shop.example/p", client, resolver)
    assert e.value.kind == "refused" and not any("internal" in u for u in client.seen)


def test_redirect_chain_followed_and_capped():
    client = shop({"/a": httpx.Response(301, headers={"location": "/b"}), "/b": httpx.Response(302, headers={"location": "https://shop.example/p"})})
    assert li.read_page("https://shop.example/a", client, resolver).title == "Linen Shirt"
    loop = shop({"/a": httpx.Response(302, headers={"location": "/a"})})
    with pytest.raises(li.LinkError, match="redirects"):
        li.read_page("https://shop.example/a", loop, resolver)


def test_page_size_cap(monkeypatch):
    monkeypatch.setattr(li, "MAX_HTML", 2000)
    client = shop({"/big": httpx.Response(200, text="<html>" + "x" * 5000, headers={"content-type": "text/html"})})
    with pytest.raises(li.LinkError) as e:
        li.read_page("https://shop.example/big", client, resolver)
    assert e.value.kind == "too-large"


# ---------------- honest failures ----------------
@pytest.mark.parametrize("status,kind,word", [(403, "blocked", "refused the automated request"), (429, "blocked", "refused"),
                                              (404, "no-data", "not found"), (500, "blocked", "HTTP 500")])
def test_http_failures_have_clear_messages(status, kind, word):
    client = shop({"/p": httpx.Response(status, text="no")})
    with pytest.raises(li.LinkError) as e:
        li.read_page("https://shop.example/p", client, resolver)
    assert e.value.kind == kind and word in str(e.value)


def test_hard_sites_get_the_javascript_or_login_hint():
    client = shop({"/item.htm": httpx.Response(200, text="<html><title>淘宝</title><body><div id=app></div></body></html>", headers={"content-type": "text/html"})})
    with pytest.raises(li.LinkError) as e:
        li.read_page("https://item.taobao.com/item.htm?id=1", client, resolver)
    assert e.value.kind == "no-data" and "JavaScript" in str(e.value) and "upload" in str(e.value)
    with pytest.raises(li.LinkError) as e:
        li.read_page("https://item.taobao.com/item.htm?id=1", shop({"/item.htm": httpx.Response(403, text="x")}), resolver)
    assert "login" in str(e.value)


def test_js_only_page_without_image_and_non_html_and_login_redirect():
    empty = shop({"/p": httpx.Response(200, text="<html><title>App</title></html>", headers={"content-type": "text/html"})})
    with pytest.raises(li.LinkError, match="no product picture"):
        li.read_page("https://shop.example/p", empty, resolver)
    pdf = shop({"/p": httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})})
    with pytest.raises(li.LinkError, match="not a web page"):
        li.read_page("https://shop.example/p", pdf, resolver)
    login = shop({"/p": httpx.Response(302, headers={"location": "/account/login?next=/p"})})
    with pytest.raises(li.LinkError) as e:
        li.read_page("https://shop.example/p", login, resolver)
    assert e.value.kind == "login"


def test_timeout_and_connection_errors_become_network_errors():
    def boom(req):
        raise httpx.ConnectTimeout("slow")
    with pytest.raises(li.LinkError) as e:
        li.read_page("https://shop.example/p", httpx.Client(transport=httpx.MockTransport(boom)), resolver)
    assert e.value.kind == "network" and "did not answer" in str(e.value)


def test_tiny_images_are_rejected_and_next_candidate_used():
    tiny = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(tiny, "PNG")
    html = '<meta property="og:image" content="/logo.png"><meta property="og:title" content="X"><meta name="twitter:image" content="/big.jpg">'
    client = shop({"/p": httpx.Response(200, text=html, headers={"content-type": "text/html"}),
                   "/logo.png": httpx.Response(200, content=tiny.getvalue(), headers={"content-type": "image/png"})})
    prod = li.read_page("https://shop.example/p", client, resolver)
    url, raw = li.download_image(prod, client, resolver)
    assert url.endswith("/big.jpg") and raw == IMG
    only_logo = li.Product(url="https://shop.example/p", title="X", images=["https://shop.example/logo.png"])
    with pytest.raises(li.LinkError, match="tiny"):
        li.download_image(only_logo, client, resolver)


def test_request_carries_an_honest_user_agent_and_no_cookies():
    seen = {}

    def handler(req):
        seen.update(req.headers)
        return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})
    c = li.make_client()
    c._transport = httpx.MockTransport(handler)
    li.read_page("https://shop.example/p", c, resolver)
    assert "Dresser" in seen["user-agent"] and "cookie" not in seen and "authorization" not in seen


# ---------------- service flow ----------------
def test_import_link_end_to_end_with_vision_and_title(tmp_path):
    vis = FakeVision({"category": "top", "type": "shirt", "color": "blue", "material": "", "warmth": 2, "formality": 3, "season": [], "notes": ""})
    st = wire(make_stylist(tmp_path, demo=False, vision=vis))
    r = st.import_link("https://shop.example/p/shirt")
    f = r["fields"]
    assert r["source"]["host"] == "shop.example" and r["source"]["title"] == "Linen Shirt"
    assert f["name"] == "Linen Shirt" and f["category"] == "top" and f["color"] == "blue"     # vision wins for colour
    assert f["material"] == "linen"                                                                       # page data fills the blank
    assert f["season"] and f["tags"] and r["describe_error"] is None and vis.calls == 1
    assert (st.staging / f"{r['staging_id']}.jpg").is_file()
    it = st.add_item(r["staging_id"], f)                         # the user reviews, then saves
    assert it["name"] == "Linen Shirt" and st.described()[0]["tags"]


def test_hint_reaches_vision_prompt_and_bypasses_description_cache(tmp_path):
    prompts = []

    class V(FakeVision):
        def chat(self, messages, **k):
            prompts.append(messages[0]["content"][1]["text"])
            return super().chat(messages, **k)
    st = wire(make_stylist(tmp_path, demo=False, vision=V()))
    st.import_link("https://shop.example/p")
    st.import_link("https://shop.example/p")             # same picture again: a hinted call is not served from the plain-photo cache
    assert len(prompts) == 2 and "Linen Shirt" in prompts[0] and "trust the photo" in prompts[0]


def test_vision_failure_falls_back_to_page_text_and_says_so(tmp_path):
    class Down:
        ep = type("E", (), {"model": "m", "base_url": "http://x/v1"})()

        def chat(self, *a, **k):
            from dresser.llm import LLMError
            raise LLMError("request failed: ReadTimeout")
    st = wire(make_stylist(tmp_path, demo=False, vision=Down()))
    r = st.import_link("https://shop.example/p")
    assert r["fields"]["type"] == "shirt" and r["fields"]["color"] == "navy" and r["fields"]["material"] == "linen"
    assert "page title only" in r["describe_error"] and "ReadTimeout" in r["describe_error"]


def test_local_only_refuses_without_touching_the_network(tmp_path):
    cfg = load_config(ROOT / "config.example.toml", "local-only")
    st = make_stylist(tmp_path, demo=False, cfg=cfg)
    st.link_client_factory = lambda: pytest.fail("network client must not even be created")
    with pytest.raises(li.LinkError) as e:
        st.import_link("https://shop.example/p")
    assert e.value.kind == "refused" and "local-only" in str(e.value)


def test_images_local_fetches_the_page_but_never_sends_the_picture_to_the_cloud(tmp_path):
    from dresser.llm import LLMClient
    cfg = load_config(ROOT / "config.example.toml", "images-local")
    st = wire(make_stylist(tmp_path, demo=False, cfg=cfg))
    st.vision = LLMClient(cfg.vision, cfg.privacy)       # real client, cloud endpoint: must refuse before any request is sent
    r = st.import_link("https://shop.example/p")
    assert r["fields"]["type"] == "shirt" and "images-local" in r["describe_error"] and "page title only" in r["describe_error"]


def test_readonly_example_wardrobe_refuses_import(tmp_path):
    st = wire(make_stylist(tmp_path, demo=False))
    st.readonly = True
    from dresser.service import ReadOnlyError
    with pytest.raises(ReadOnlyError):
        st.import_link("https://shop.example/p")


# ---------------- API ----------------
@pytest.fixture
def web(tmp_path):
    st = wire(make_stylist(tmp_path, demo=False))
    api._state["s"] = st
    yield TestClient(api.app), st
    api._state.clear()


def test_api_import_link_ok_and_errors(web):
    c, st = web
    r = c.post("/api/import-link", json={"url": "https://shop.example/p"})
    assert r.status_code == 200 and r.json()["source"]["host"] == "shop.example" and r.json()["fields"]["tags"]
    bad = c.post("/api/import-link", json={"url": "http://127.0.0.1/api/status"})
    assert bad.status_code == 422 and bad.json()["kind"] == "refused" and "private" in bad.json()["detail"]
    assert c.post("/api/import-link", json={"url": "file:///etc/passwd"}).json()["kind"] == "bad-url"
    assert c.post("/api/import-link", json={}).status_code == 422


def test_api_season_rooms_and_tags(web, tmp_path):
    c, st = web
    s = c.get("/api/settings").json()
    assert s["season"]["current"] == "autumn" and s["details"]["privacy"] == "off" and "location" in s
    assert c.put("/api/settings/season", json={"season": "winter"}).json()["current"] == "winter"
    assert c.put("/api/settings/season", json={"season": "monsoon"}).status_code == 422
    assert c.get("/api/rooms").json()["current"] == "winter"
    assert c.get("/api/wardrobe", params={"season": "nope"}).status_code == 422
    assert c.get("/api/wardrobe", params={"season": "all"}).status_code == 200
    t = c.post("/api/tags/suggest", json={"fields": {"category": "outer", "type": "trench coat", "warmth": 3, "formality": 4, "color": "beige"}}).json()
    assert "rain-ready" in t["auto"] and t["seasons"] and t["model"] == []
    assert c.put("/api/settings/season", json={"season": "auto"}).json()["current"] == "autumn"
