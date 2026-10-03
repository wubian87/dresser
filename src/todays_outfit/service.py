"""Shared glue used by both the CLI and the web app."""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from datetime import date
from urllib.parse import urlparse
from pathlib import Path

from . import linkimport as li
from . import weather as wx
from .config import Config
from .describe import Cache, describe_all, describe_image, file_hash
from .history import History
from .llm import LLMClient, LLMError, PrivacyError
from .rotation import Rotation
from .rules import OCCASIONS
from .seasons import SEASONS, clean_seasons, hemisphere, in_room, infer_seasons, suggest_season
from .tags import infer_tags, suggest_with_model
from .style import suggest
from .wardrobe import (IMAGES_DIR, bytes_hash, clean_fields, is_described, is_example, load_wardrobe, merged, new_item,
                       photo_to_jpeg, read_extra, save_wardrobe, unique_id)

BADGE_DAYS = 7          # a "not worn in N days" badge appears from this many days
DEFAULT_OCCASION = "casual"


class ReadOnlyError(RuntimeError):
    """The bundled example wardrobe is read-only; use --demo (a writable copy) or your own data directory."""


class NotFound(KeyError):
    pass


class Settings:
    """Tiny JSON file: last-used occasion and the location chosen once."""

    def __init__(self, path):
        self.path = Path(path)
        self.data: dict = {}
        if self.path.is_file():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)


class Stylist:
    interactive_timeout = 75.0      # seconds the "Add clothes" form waits for the vision model before asking you to type

    def __init__(self, cfg: Config, wardrobe_path, cache_path="cache/descriptions.json", *, today=None,
                 weather: wx.WeatherService | None = None, readonly: bool | None = None):
        self.cfg = cfg
        self.path = Path(wardrobe_path)
        self.dir = self.path.parent
        self.readonly = is_example(self.path) if readonly is None else readonly
        self._extra = read_extra(self.path)
        self.items = load_wardrobe(self.path)
        self.cache = Cache(cache_path, seed=self.dir / "descriptions.cache.json")
        self.thumb_dir = Path(cache_path).parent / "thumbs"
        self.vision = LLMClient(cfg.vision, cfg.privacy)
        self.text = LLMClient(cfg.text, cfg.privacy)
        self.history = History(self.dir / "history.json")
        self.settings = Settings(self.dir / "settings.json")
        # the read-only example wardrobe must not be written to: keep its forecast cache under cache/ (gitignored)
        self.weather = weather or wx.WeatherService((Path(cache_path).parent if self.readonly else self.dir) / "weather_cache.json")
        self._today = today
        self.link_client_factory = li.make_client
        self.link_resolver = socket.getaddrinfo
        self.lock = threading.RLock()
        self.version = 0
        self._today_cache: dict = {}
        self.load_cached()

    # ---------- basics ----------
    def today_date(self) -> date:
        return self._today() if self._today else date.today()

    def _bump(self) -> None:
        self.version += 1
        self._today_cache.clear()

    def _writable(self) -> None:
        if self.readonly:
            raise ReadOnlyError("This is the bundled example wardrobe (read-only). Start with --demo for a writable copy "
                                "or --data-dir for your own wardrobe.")

    def load_cached(self):
        """Attach cached descriptions without calling any model."""
        for it in self.items:
            it["hash"] = file_hash(it["image_path"])
            rec = self.cache.get(it["hash"], self.cfg.vision.model)
            if rec:
                it["desc"] = rec["desc"]

    def undescribed(self):
        return [i for i in self.items if not is_described(i)]

    def describe(self, progress=None) -> dict:
        todo = self.undescribed()
        return describe_all(self.vision, todo, self.cache, progress=progress)

    def described(self) -> list[dict]:
        return [m for m in (merged(i) for i in self.items) if m]

    def find(self, item_id: str) -> dict:
        for i in self.items:
            if i["id"] == item_id:
                return i
        raise NotFound(item_id)

    # ---------- rotation / suggestions ----------
    def rotation(self) -> Rotation:
        added = {}
        for i in self.items:
            if i.get("added"):
                try:
                    added[i["id"]] = date.fromisoformat(i["added"])
                except ValueError:
                    pass
        return Rotation(self.history, self.today_date(), added)

    # ---------- season rooms ----------
    def season_info(self) -> dict:
        """The current room: the user's override if set, else suggested from today's date (and the location's hemisphere)."""
        loc = self.location()
        auto = suggest_season(self.today_date(), loc.lat if loc else None)
        over = self.settings.data.get("season")
        over = over if over in SEASONS else None
        return {"current": over or auto, "auto": auto, "override": over, "hemisphere": hemisphere(loc.lat if loc else None),
                "options": list(SEASONS)}

    def set_season(self, value: str) -> dict:
        """`value` is a season name, or "auto" to follow the date."""
        if value != "auto" and value not in SEASONS:
            raise ValueError(f"season must be 'auto' or one of {SEASONS}")
        self._writable()
        with self.lock:
            if value == "auto":
                self.settings.data.pop("season", None)
            else:
                self.settings.data["season"] = value
            self.settings.save()
            self._bump()
        return self.season_info()

    def room(self, season: str | None = None) -> list[dict]:
        """Described pieces in a room (default: the current one). season="all" returns everything."""
        items = self.described()
        season = season or self.season_info()["current"]
        return items if season == "all" else [m for m in items if in_room(m, season)]

    def suggest(self, temp_c: float, rain: bool, occasion: str, use_model: bool = True, rotate: bool = True,
                pad: bool = False, season: str | None = None) -> dict:
        """Styling uses only the pieces in the current season room (or `season`; "all" disables the room filter)."""
        res = suggest(self.room(season), temp_c, rain, occasion, self.text if use_model else None, self.cfg.language,
                      rotation=self.rotation() if rotate else None, pad_with_rules=pad)
        res["undescribed"] = len(self.undescribed())
        return res

    # ---------- wardrobe view with wear stats ----------
    def wardrobe_view(self, season: str | None = None) -> list[dict]:
        """Pieces of the current room (season="all": every room) with wear stats."""
        rot, today = self.rotation(), self.today_date()
        has_history = bool(self.history.wears)
        out = []
        for m in self.room(season):
            st = rot.stats.get(m["id"])
            days = st.days_since(today) if st else None
            unworn = rot.unworn_days(m["id"])
            badge = f"not worn in {unworn} days" if has_history and unworn >= BADGE_DAYS else None
            out.append({**{k: m.get(k) for k in ("id", "name", "category", "type", "color", "material", "warmth", "formality",
                                                 "season", "notes", "added", "tags", "season_auto", "tags_auto", "tags_edited")},
                        "image": f"/images/{m['id']}", "thumb": f"/thumb/{m['id']}",
                        "last_worn": st.last_worn.isoformat() if st and st.last_worn else None,
                        "wear_count": st.wear_count if st else 0, "days_since": days, "unworn_days": unworn,
                        "never_logged": st is None and has_history, "badge": badge,
                        "badge_level": None if not badge else ("long" if unworn >= 14 else "mid")})
        return out

    # ---------- history actions ----------
    def wear(self, ids: list[str], occasion: str | None = None, day: date | None = None, merge: bool = False) -> dict:
        self._writable()
        with self.lock:
            for i in ids:
                self.find(i)
            if not ids:
                raise ValueError("nothing to record")
            e = self.history.wear(day or self.today_date(), ids, occasion, merge=merge)
            self.history.save()
            self._bump()
            return e

    def unwear(self, day: date | None = None) -> bool:
        self._writable()
        with self.lock:
            ok = self.history.unwear(day or self.today_date())
            self.history.save()
            self._bump()
            return ok

    def skip(self, ids: list[str], occasion: str | None = None) -> None:
        self._writable()
        with self.lock:
            for i in ids:
                self.find(i)
            self.history.skip(self.today_date(), ids, occasion)
            self.history.save()
            self._bump()

    # ---------- settings / weather ----------
    def occasion(self) -> str:
        o = self.settings.data.get("occasion")
        return o if o in OCCASIONS else DEFAULT_OCCASION

    def set_occasion(self, occasion: str) -> None:
        if occasion not in OCCASIONS:
            raise ValueError(f"occasion must be one of {OCCASIONS}")
        self._writable()
        with self.lock:
            self.settings.data["occasion"] = occasion
            self.settings.save()

    def location(self) -> wx.Location | None:
        loc = self.settings.data.get("location")
        if isinstance(loc, dict):
            try:
                return wx.Location(loc["name"], float(loc["lat"]), float(loc["lon"]))
            except (KeyError, TypeError, ValueError):
                pass
        w = getattr(self.cfg, "weather", {}) or {}
        if "lat" in w and "lon" in w:
            return wx.Location(str(w.get("name") or w.get("city") or f"{w['lat']}, {w['lon']}"), float(w["lat"]), float(w["lon"]))
        return None

    def set_location(self, loc: wx.Location | None) -> None:
        self._writable()
        with self.lock:
            if loc is None:
                self.settings.data.pop("location", None)
            else:
                self.settings.data["location"] = {"name": loc.name, "lat": loc.lat, "lon": loc.lon}
            self.settings.save()
            self._bump()

    def search_city(self, query: str) -> list[wx.Location]:
        self._check_weather_privacy()
        client = self.weather.client_factory()
        try:
            return wx.geocode(query, client)
        finally:
            client.close()

    def _check_weather_privacy(self) -> None:
        if self.cfg.privacy == "local-only":
            raise wx.WeatherError("privacy=local-only: not contacting Open-Meteo; type the temperature by hand")

    def weather_info(self, refresh: bool = False) -> dict:
        """Today's weather for the UI. Never raises: on any problem returns source='none' with a reason."""
        loc = self.location()
        if loc is None:
            city = (getattr(self.cfg, "weather", {}) or {}).get("city")
            if city:   # config names a city only: resolve it once and remember the answer
                try:
                    self._check_weather_privacy()
                    found = self.search_city(city)
                    if found and not self.readonly:
                        self.set_location(found[0])
                        loc = found[0]
                except wx.WeatherError as e:
                    return {"source": "none", "error": str(e)}
            if loc is None:
                return {"source": "none", "error": "No location set yet: type today's temperature, or set your city once."}
        try:
            self._check_weather_privacy()
            fc = self.weather.today(loc, self.today_date(), refresh=refresh)
        except wx.WeatherError as e:
            return {"source": "none", "city": loc.name, "error": f"{e}. Type the temperature by hand."}
        city = loc.name.split(",")[0]
        info = {"source": "auto", "city": loc.name, "label": fc.label(city), "high": fc.high, "low": fc.low,
                "high_r": round(fc.high), "low_r": round(fc.low),        # the rounded numbers the label shows, so page and CLI agree
                "rain_prob": fc.rain_prob, "temp": fc.temp, "rain": fc.rain, "forecast_day": fc.day,
                "cached": fc.from_cache, "fetched": wx.fmt_time(fc.fetched_at) if fc.fetched_at else None}
        if fc.stale:
            info["note"] = f"Offline: showing the forecast saved at {info['fetched']}."
        return info

    def rooms_view(self) -> dict:
        """Piece counts per season room (for 'N pieces in other rooms') and tag counts in the current room."""
        items = self.described()
        cur = self.season_info()["current"]
        counts = {sea: sum(1 for m in items if in_room(m, sea)) for sea in SEASONS}
        tags: dict[str, int] = {}
        for m in items:
            if in_room(m, cur):
                for t in m.get("tags") or []:
                    tags[t] = tags.get(t, 0) + 1
        return {"current": cur, "counts": counts, "total": len(items), "in_room": counts[cur],
                "tags": [{"tag": t, "n": n} for t, n in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))]}

    def settings_view(self) -> dict:
        """Everything the Settings tab shows: the choices (season, city, occasion) and, folded away, the technical details."""
        from . import __version__
        loc = self.location()
        return {"season": self.season_info(), "occasion": self.occasion(),
                "location": None if loc is None else {"name": loc.name, "lat": loc.lat, "lon": loc.lon},
                "details": {"text_model": self.cfg.text.model, "text_host": self.cfg.text.base_url,
                            "vision_model": self.cfg.vision.model, "vision_host": self.cfg.vision.base_url,
                            "privacy": self.cfg.privacy, "pieces": len(self.items), "pieces_ready": len(self.items) - len(self.undescribed()),
                            "cached_descriptions": len(self.cache.data), "data_dir": str(self.dir), "readonly": self.readonly,
                            "version": __version__, "today": self.today_date().isoformat()}}

    # ---------- the Today card ----------
    def today_view(self, occasion: str | None = None, temp: float | None = None, rain: bool | None = None,
                   use_model: bool = True, refresh_weather: bool = False, force: bool = False,
                   season: str | None = None) -> dict:
        today = self.today_date()
        occ = occasion if occasion in OCCASIONS else self.occasion()
        if occasion in OCCASIONS and occasion != self.settings.data.get("occasion") and not self.readonly:
            self.set_occasion(occasion)           # remember the last-used occasion
        if temp is not None:
            w = {"source": "manual", "temp": temp, "rain": bool(rain),
                 "label": f"Manual: {temp:g} °C, {'rain' if rain else 'dry'}"}
            auto = self.weather_info(refresh_weather) if self.location() else None
            if auto and auto.get("source") == "auto":
                w["forecast_label"] = auto["label"]
        else:
            w = self.weather_info(refresh_weather)
        wt = self.history.wear_on(today)
        by_id = {m["id"]: m for m in self.described()}
        sea = season or self.season_info()["current"]
        room = {m["id"] for m in self.room(sea)}
        worn = None
        if wt:
            worn = {"items": [self._card(by_id[i]) for i in wt["items"] if i in by_id], "occasion": wt.get("occasion")}
        out = {"date": today.isoformat(), "occasion": occ, "weather": w, "worn_today": worn, "suggestions": [],
               "mode": "none", "warning": None, "candidates": 0, "undescribed": len(self.undescribed()),
               "wardrobe_size": len(room), "readonly": self.readonly, "has_location": self.location() is not None,
               "season": sea, "outside_room": len(by_id) - len(room)}
        if worn and not force:      # already logged today: no need to ask a model for another outfit
            return out
        if w["source"] == "none":
            out["needs_weather"] = True
            return out
        if not by_id:
            out["warning"] = "Your wardrobe is empty: add some clothes first."
            return out
        if not room:
            out["warning"] = (f"Nothing in your {sea} room yet ({len(by_id)} pieces live in other rooms). "
                              "Add clothes, or switch the season in Settings.")
            return out
        key = (today, occ, w["temp"], w["rain"], self.version, use_model, sea)
        res = self._today_cache.get(key)
        if res is None:
            res = self.suggest(w["temp"], w["rain"], occ, use_model=use_model, pad=True, season=sea)
            if len(self._today_cache) > 20:
                self._today_cache.clear()
            self._today_cache[key] = res
        out.update(mode=res["mode"], warning=res.get("warning"), candidates=res.get("candidates", 0),
                   latency=res.get("latency"),
                   suggestions=[{"items": [self._card(i) for i in s.items], "reason": s.reason, "note": s.note,
                                 "source": s.source, "relaxed": s.relaxed} for s in res["suggestions"]])
        return out

    @staticmethod
    def _card(i: dict) -> dict:
        return {"id": i["id"], "name": i["name"], "category": i["category"], "image": f"/images/{i['id']}",
                "thumb": f"/thumb/{i['id']}"}

    # ---------- adding / editing clothes ----------
    @property
    def staging(self) -> Path:
        return self.dir / "staging"

    def stage_photo(self, data: bytes, describe: bool = True, hint: str | None = None, guess: dict | None = None,
                    name: str = "") -> dict:
        """Save one uploaded photo as a re-encoded JPEG in staging and (optionally) auto-describe it.

        `hint` (text from a shop page) is given to the vision model; `guess` (deterministic fields from that text) fills
        what the model leaves empty, or everything if no model could run. Returns
        {"staging_id", "fields", "describe_error", "duplicate_of"}. `fields` is what the form shows for review."""
        self._writable()
        jpg = photo_to_jpeg(data)
        h = bytes_hash(jpg)
        self.staging.mkdir(parents=True, exist_ok=True)
        self._clean_staging()
        sid = uuid.uuid4().hex[:16]
        path = self.staging / f"{sid}.jpg"
        path.write_bytes(jpg)
        dup = next((i["id"] for i in self.items if i.get("hash") == h), None)
        fields, err = self._describe_path(path, h, hint) if describe else (None, "auto-describe skipped")
        base = {"category": "top", "type": "", "color": "", "material": "", "warmth": 3, "formality": 3, "season": [], "notes": ""}
        if fields is None:
            fields = base
            if guess:
                fields = {**base, **guess}
                err = (err or "").replace(" Fill the fields in by hand.", "") + " Filled from the page title only: please check."
        elif guess:
            for k in ("color", "material"):
                if guess.get(k) and (not fields.get(k) or fields.get(k) == "unknown"):
                    fields[k] = guess[k]
        fields = {**fields, "name": name}
        fields["season"] = infer_seasons(fields)          # rooms from the rule table, not from the model's guess
        fields["tags"] = infer_tags(fields)
        return {"staging_id": sid, "fields": fields, "describe_error": err, "duplicate_of": dup}

    def import_link(self, url: str, *, client=None, resolver=None) -> dict:
        """'Paste a product link': read the public page (title, description, picture), then behave like an upload.

        Raises linkimport.LinkError (message is safe to show) when the page cannot be used."""
        self._writable()
        if self.cfg.privacy == "local-only":
            raise li.LinkError("privacy=local-only: not contacting any web site. Save the product image and upload it instead.", "refused")
        resolver = resolver or self.link_resolver
        own = client is None
        client = client or self.link_client_factory()
        try:
            prod = li.read_page(url, client, resolver)
            img_url, raw = li.download_image(prod, client, resolver)
        finally:
            if own:
                client.close()
        guess = li.guess_from_text(" ".join([prod.title, prod.description, prod.extra.get("category", ""),
                                             prod.extra.get("color", ""), prod.extra.get("material", "")]))
        if prod.extra.get("color"):
            guess["color"] = prod.extra["color"].lower()[:30]
        if prod.extra.get("material"):
            guess["material"] = prod.extra["material"].lower()[:40]
        try:
            st = self.stage_photo(raw, True, hint=f"{prod.title}. {prod.description}"[:300], guess=guess, name=prod.title[:60])
        except ValueError:
            raise li.LinkError("The product picture is in a format I cannot read. Save it as JPG/PNG and upload it instead.", "no-data") from None
        host = (urlparse(prod.url).hostname or "")
        st["source"] = {"url": prod.url, "host": host, "title": prod.title, "description": prod.description}
        return st

    def suggest_tags(self, fields: dict, use_model: bool = False) -> dict:
        """Tag and room suggestions for a form's current fields. Stage 1 always; stage 2 (model) only if asked."""
        f = {k: fields.get(k) for k in ("category", "type", "color", "material", "warmth", "formality", "notes")}
        f["category"] = f["category"] or "top"
        out = {"auto": infer_tags(f), "seasons": infer_seasons(f), "model": [], "error": None}
        if use_model:
            client = self.text
            try:
                out["model"] = suggest_with_model(client, f, self.cfg.language)
            except PrivacyError as e:
                out["error"] = f"{e}"
            except (LLMError, ValueError) as e:
                out["error"] = f"The model could not suggest tags ({e})"[:200]
        return out

    def _describe_path(self, path: Path, h: str, hint: str | None = None) -> tuple[dict | None, str | None]:
        rec = None if hint else self.cache.get(h, self.cfg.vision.model)       # a hinted answer is not the plain photo's answer
        if rec:
            return dict(rec["desc"]), None
        client = self.vision
        if isinstance(client, LLMClient):     # someone is waiting on a phone: give up sooner than the batch `describe`
            client = LLMClient(client.ep, client.privacy, timeout=self.interactive_timeout)
        try:
            desc, secs = describe_image(client, path, hint) if hint else describe_image(client, path)
        except PrivacyError as e:
            return None, f"{e}. Fill the fields in by hand."
        except LLMError as e:
            return None, f"Auto-describe unavailable ({e}). Fill the fields in by hand."[:240]
        except ValueError as e:
            return None, f"{e}. Fill the fields in by hand."[:240]
        if not hint:
            with self.lock:
                self.cache.put(h, self.cfg.vision.model, {"desc": desc, "seconds": round(secs, 2)})
                self.cache.save()
        return desc, None

    def _clean_staging(self, max_age_s: int = 86400) -> None:
        now = time.time()
        for p in self.staging.glob("*.jpg"):
            try:
                if now - p.stat().st_mtime > max_age_s:
                    p.unlink()
            except OSError:
                pass

    def discard_staged(self, sid: str) -> None:
        p = self._staged_path(sid)
        if p.is_file():
            p.unlink()

    def _staged_path(self, sid: str) -> Path:
        if not sid.isalnum():
            raise NotFound(sid)
        return self.staging / f"{sid}.jpg"

    def add_item(self, sid: str, fields: dict) -> dict:
        self._writable()
        clean = clean_fields(fields)          # ValueError -> 422 in the API
        src = self._staged_path(sid)
        if not src.is_file():
            raise NotFound(sid)
        with self.lock:
            h = bytes_hash(src.read_bytes())
            iid = unique_id(clean.get("name") or f"{clean['color']} {clean['type']}", {i["id"] for i in self.items})
            (self.dir / IMAGES_DIR).mkdir(parents=True, exist_ok=True)
            dest = self.dir / IMAGES_DIR / f"{iid}.jpg"
            os.replace(src, dest)
            it = new_item(iid, f"{IMAGES_DIR}/{iid}.jpg", clean, self.today_date())
            it["image_path"], it["hash"] = dest.resolve(), h
            self.items.append(it)
            save_wardrobe(self.path, self.items, self._extra)
            self._bump()
            return it

    def add_photo_file(self, photo: Path, fields: dict | None = None, describe: bool = True) -> dict:
        """CLI helper: stage + (describe) + save in one go. `fields` override the described values."""
        st = self.stage_photo(Path(photo).read_bytes(), describe=describe)
        if st["describe_error"] and not fields:
            self.discard_staged(st["staging_id"])
            raise ValueError(st["describe_error"])
        merged_fields = {**st["fields"], **{k: v for k, v in (fields or {}).items() if v not in (None, "")}}
        if not merged_fields.get("type"):
            merged_fields["type"] = merged_fields["category"]
        try:
            return self.add_item(st["staging_id"], merged_fields)
        except Exception:
            self.discard_staged(st["staging_id"])
            raise

    def update_item(self, item_id: str, fields: dict) -> dict:
        self._writable()
        clean = clean_fields(fields)
        with self.lock:
            it = self.find(item_id)
            for k in ("category", "type", "color", "material", "warmth", "formality", "season", "notes", "tags"):
                it[k] = clean[k]
            if "name" in clean:
                it["name"] = clean["name"]
            elif "name" in fields:
                it.pop("name", None)
            save_wardrobe(self.path, self.items, self._extra)
            self._bump()
            return it

    def delete_item(self, item_id: str) -> None:
        self._writable()
        with self.lock:
            it = self.find(item_id)
            self.items.remove(it)
            save_wardrobe(self.path, self.items, self._extra)
            self.history.forget_items({item_id})
            self.history.save()
            img = Path(it["image_path"])
            try:   # only delete photos this app stored itself; imported/referenced photos stay where they are
                if img.is_file() and img.parent == (self.dir / IMAGES_DIR).resolve():
                    img.unlink()
            except OSError:
                pass
            self._bump()

    def thumb_path(self, item_id: str, width: int = 360) -> Path:
        from PIL import Image, ImageOps
        it = self.find(item_id)
        self.thumb_dir.mkdir(parents=True, exist_ok=True)
        t = self.thumb_dir / f"{it.get('hash') or file_hash(it['image_path'])}_{width}.jpg"
        if not t.is_file():
            im = ImageOps.exif_transpose(Image.open(it["image_path"])).convert("RGB")
            im.thumbnail((width, width))
            im.save(t, "JPEG", quality=82)
        return t
