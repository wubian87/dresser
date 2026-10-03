"""Wardrobe file format.

wardrobe.json:
{ "items": [ {"id": "white-tee", "image": "white-tee.png", "warmth": 1 /* optional manual override */ }, ... ] }
Image paths are relative to the wardrobe.json file.
"""
from __future__ import annotations

import json
from pathlib import Path

OVERRIDABLE = ("category", "type", "color", "material", "warmth", "formality", "season", "notes")


def load_wardrobe(path) -> list[dict]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for raw in data["items"]:
        it = dict(raw)
        it["image_path"] = (path.parent / raw["image"]).resolve()  # absolute paths work too
        if not it["image_path"].is_file():
            raise FileNotFoundError(f"missing photo for {raw['id']}: {raw['image']}")
        items.append(it)
    return items


def merged(item: dict) -> dict | None:
    """Final item = model description + manual overrides from wardrobe.json. None if not described yet."""
    desc = item.get("desc")
    if not desc:
        return None
    out = {"id": item["id"], **desc}
    for k in OVERRIDABLE:
        if k in item:
            out[k] = item[k]
    out["name"] = item.get("name") or f"{out['color']} {out['type']}"
    return out
