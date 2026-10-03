"""FastAPI app: one JSON API + one static, phone-friendly page."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import weather as wx
from .linkimport import LinkError
from .seasons import SEASONS
from .config import load_config
from .rules import OCCASIONS
from .service import NotFound, ReadOnlyError, Stylist

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 30 * 1024 * 1024
app = FastAPI(title="Today's Outfit")
_state: dict = {}


def stylist() -> Stylist:
    if "s" not in _state:
        cfg = load_config(os.environ.get("TODAYS_OUTFIT_CONFIG"), os.environ.get("TODAYS_OUTFIT_PRIVACY"))
        _state["s"] = Stylist(cfg, os.environ.get("TODAYS_OUTFIT_WARDROBE", "sample_wardrobe/wardrobe.json"),
                              os.environ.get("TODAYS_OUTFIT_CACHE", "cache/descriptions.json"))
    return _state["s"]


@app.exception_handler(NotFound)
async def _nf(_, e):
    return JSONResponse({"detail": f"not found: {e.args[0]}"}, status_code=404)


@app.exception_handler(ReadOnlyError)
async def _ro(_, e):
    return JSONResponse({"detail": str(e)}, status_code=403)


@app.exception_handler(LinkError)
async def _le(_, e):
    return JSONResponse({"detail": str(e), "kind": e.kind}, status_code=422)


@app.exception_handler(ValueError)
async def _ve(_, e):
    return JSONResponse({"detail": str(e)}, status_code=422)


class SuggestIn(BaseModel):
    temp: float = Field(ge=-40, le=55)
    rain: bool = False
    occasion: str


class WearIn(BaseModel):
    items: list[str]
    occasion: str | None = None
    date: str | None = None
    merge: bool = False


class SkipIn(BaseModel):
    items: list[str]
    occasion: str | None = None


class SeasonIn(BaseModel):
    season: str


class LinkIn(BaseModel):
    url: str = Field(max_length=2000)


class TagsIn(BaseModel):
    fields: dict
    model: bool = False


class LocationIn(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


def _card(i: dict) -> dict:
    return {"id": i["id"], "name": i["name"], "category": i["category"], "image": f"/images/{i['id']}"}


def _day(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise ValueError("date must look like 2026-10-03") from None


@app.get("/api/status")
def status():
    s = stylist()
    return {"vision_model": s.cfg.vision.model, "text_model": s.cfg.text.model, "vision_host": s.cfg.vision.base_url,
            "text_host": s.cfg.text.base_url, "privacy": s.cfg.privacy, "items": len(s.items),
            "undescribed": len(s.undescribed()), "occasions": OCCASIONS, "readonly": s.readonly,
            "today": s.today_date().isoformat()}


@app.get("/api/wardrobe")
def wardrobe(season: str | None = None):
    """The current season room (default), one named room, or season=all."""
    if season is not None and season != "all" and season not in SEASONS:
        raise HTTPException(422, f"season must be 'all' or one of {SEASONS}")
    return stylist().wardrobe_view(season)


@app.get("/api/rooms")
def rooms():
    return stylist().rooms_view()


@app.post("/api/describe")
def describe():
    s = stylist()
    errs = s.describe()
    return {"undescribed": len(s.undescribed()), "errors": errs}


@app.post("/api/suggest")
def api_suggest(body: SuggestIn):
    if body.occasion not in OCCASIONS:
        raise HTTPException(422, f"occasion must be one of {OCCASIONS}")
    res = stylist().suggest(body.temp, body.rain, body.occasion)
    return {"mode": res["mode"], "warning": res.get("warning"), "candidates": res.get("candidates", 0),
            "undescribed": res["undescribed"], "latency": res.get("latency"),
            "suggestions": [{"items": [_card(i) for i in x.items], "reason": x.reason, "note": x.note, "source": x.source,
                             "relaxed": x.relaxed} for x in res["suggestions"]]}


# ---- Today card ----
@app.get("/api/today")
def today(occasion: str | None = None, temp: float | None = None, rain: bool | None = None, refresh: bool = False,
          force: bool = False):
    if occasion is not None and occasion not in OCCASIONS:
        raise HTTPException(422, f"occasion must be one of {OCCASIONS}")
    if temp is not None and not -40 <= temp <= 55:
        raise HTTPException(422, "temp out of range")
    return stylist().today_view(occasion, temp, rain, refresh_weather=refresh, force=force)


@app.post("/api/wear")
def wear(body: WearIn):
    e = stylist().wear(body.items, body.occasion, _day(body.date), body.merge)
    return {"ok": True, "entry": e}


@app.delete("/api/wear")
def unwear(date: str | None = None):
    return {"ok": stylist().unwear(_day(date))}


@app.post("/api/skip")
def skip(body: SkipIn):
    stylist().skip(body.items, body.occasion)
    return {"ok": True}


# ---- settings / weather ----
@app.get("/api/settings")
def get_settings():
    return stylist().settings_view()


@app.put("/api/settings/season")
def set_season(body: SeasonIn):
    return stylist().set_season(body.season)


@app.put("/api/settings/location")
def set_location(body: LocationIn):
    stylist().set_location(wx.Location(body.name, body.lat, body.lon))
    return {"ok": True}


@app.delete("/api/settings/location")
def clear_location():
    stylist().set_location(None)
    return {"ok": True}


@app.get("/api/geocode")
def geocode(q: str):
    try:
        found = stylist().search_city(q)
    except wx.WeatherError as e:
        raise HTTPException(502, str(e)) from None
    return [{"name": f.name, "lat": f.lat, "lon": f.lon} for f in found]


# ---- adding / editing clothes ----
@app.post("/api/upload")
async def upload(request: Request, describe: bool = True):
    """Raw image bytes as the request body (one photo per call, so the page can show progress per photo)."""
    data = await request.body()
    if not data:
        raise ValueError("empty upload")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "photo is larger than 30 MB")
    return await run_in_threadpool(stylist().stage_photo, data, describe)


@app.post("/api/import-link")
async def import_link(body: LinkIn):
    """'Paste a product link': a public page only. Failures come back as 422 {detail, kind} with a message to show."""
    return await run_in_threadpool(stylist().import_link, body.url.strip())


@app.post("/api/tags/suggest")
async def suggest_tags(body: TagsIn):
    return await run_in_threadpool(stylist().suggest_tags, body.fields, body.model)


@app.delete("/api/staged/{sid}")
def discard(sid: str):
    stylist().discard_staged(sid)
    return {"ok": True}


@app.get("/staged/{sid}")
def staged_image(sid: str):
    p = stylist()._staged_path(sid)
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/items")
async def add_item(request: Request):
    body = await request.json()
    sid = str(body.get("staging_id", ""))
    it = stylist().add_item(sid, body.get("fields") or {})
    return {"id": it["id"]}


@app.put("/api/items/{item_id}")
async def update_item(item_id: str, request: Request):
    body = await request.json()
    stylist().update_item(item_id, body)
    return {"ok": True}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str):
    stylist().delete_item(item_id)
    return {"ok": True}


@app.get("/images/{item_id}")
def image(item_id: str):
    return FileResponse(stylist().find(item_id)["image_path"])


@app.get("/thumb/{item_id}")
def thumb(item_id: str):
    return FileResponse(stylist().thumb_path(item_id), headers={"Cache-Control": "max-age=3600"})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
