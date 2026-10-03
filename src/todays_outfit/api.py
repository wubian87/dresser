"""FastAPI app: one JSON API + one static, phone-friendly page."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import load_config
from .rules import OCCASIONS
from .service import Stylist

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Today's Outfit")
_state: dict = {}


def stylist() -> Stylist:
    if "s" not in _state:
        cfg = load_config(os.environ.get("TODAYS_OUTFIT_CONFIG"), os.environ.get("TODAYS_OUTFIT_PRIVACY"))
        _state["s"] = Stylist(cfg, os.environ.get("TODAYS_OUTFIT_WARDROBE", "sample_wardrobe/wardrobe.json"),
                              os.environ.get("TODAYS_OUTFIT_CACHE", "cache/descriptions.json"))
    return _state["s"]


class SuggestIn(BaseModel):
    temp: float = Field(ge=-40, le=55)
    rain: bool = False
    occasion: str


def _card(i: dict) -> dict:
    return {"id": i["id"], "name": i["name"], "category": i["category"], "image": f"/images/{i['id']}"}


@app.get("/api/status")
def status():
    s = stylist()
    return {"vision_model": s.cfg.vision.model, "text_model": s.cfg.text.model, "vision_host": s.cfg.vision.base_url,
            "text_host": s.cfg.text.base_url, "privacy": s.cfg.privacy, "items": len(s.items),
            "undescribed": len(s.undescribed()), "occasions": OCCASIONS}


@app.get("/api/wardrobe")
def wardrobe():
    return [_card(i) for i in stylist().described()]


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
            "suggestions": [{"items": [_card(i) for i in x.items], "reason": x.reason, "source": x.source, "relaxed": x.relaxed}
                            for x in res["suggestions"]]}


@app.get("/images/{item_id}")
def image(item_id: str):
    for i in stylist().items:
        if i["id"] == item_id:
            return FileResponse(i["image_path"])
    raise HTTPException(404)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
