"""Wardrobe file format and the helpers that edit it.

wardrobe.json:
{ "items": [ {"id": "white-tee", "image": "white-tee.png", "warmth": 1 /* optional manual override */ }, ... ] }
Image paths are relative to the wardrobe.json file.

Pieces added through the app (web "Add clothes" or `add`) carry *all* their fields in the item itself
(category, type, colour, ...), because the user reviewed and may have edited them before saving.
Pieces from the bundled example / importers carry only an image; their fields come from the cached
vision-model description, and any field written in wardrobe.json overrides it.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps

OVERRIDABLE = ("category", "type", "color", "material", "warmth", "formality", "season", "notes")
RUNTIME_KEYS = {"image_path", "hash", "desc"}   # never written back to wardrobe.json
IMAGES_DIR = "images"


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


def has_own_fields(item: dict) -> bool:
    """True for pieces whose description lives in wardrobe.json itself (added and reviewed by the user)."""
    return bool(item.get("category") and item.get("type"))


def is_described(item: dict) -> bool:
    return "desc" in item or has_own_fields(item)


def merged(item: dict) -> dict | None:
    """Final item = model description + manual overrides from wardrobe.json. None if not described yet."""
    desc = item.get("desc")
    if not desc and not has_own_fields(item):
        return None
    out = {"id": item["id"], "material": "", "warmth": 3, "formality": 3, "season": [], "notes": "", "color": "unknown",
           **(desc or {})}
    for k in OVERRIDABLE:
        if k in item:
            out[k] = item[k]
    out["name"] = item.get("name") or f"{out['color']} {out['type']}"
    if item.get("added"):
        out["added"] = item["added"]
    return out


def save_wardrobe(path, items: list[dict], extra: dict | None = None) -> None:
    """Atomic write. `items` are runtime dicts; runtime-only keys are dropped."""
    path = Path(path)
    data = dict(extra or {})
    data["items"] = [{k: v for k, v in it.items() if k not in RUNTIME_KEYS} for it in items]
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_extra(path) -> dict:
    """Top-level keys of wardrobe.json other than `items` (e.g. the '_note' on the example wardrobe)."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in d.items() if k != "items"}


def is_example(path) -> bool:
    """The bundled example wardrobe is marked "_readonly": true; the app never writes into it."""
    return read_extra(path).get("_readonly") is True


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "piece"


def unique_id(base: str, taken: set[str]) -> str:
    base = slugify(base)
    cand, n = base, 2
    while cand in taken:
        cand, n = f"{base}-{n}", n + 1
    return cand


def photo_to_jpeg(data: bytes, max_side: int = 1600) -> bytes:
    """Phone photo bytes -> upright JPEG without EXIF/GPS metadata, at most `max_side` px. Raises ValueError."""
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        raise ValueError("that file is not an image I can read") from None
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def bytes_hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def clean_fields(raw: dict) -> dict:
    """Validate user-submitted/edited fields (same rules as the vision model's output). Raises ValueError."""
    from .describe import normalize
    out = normalize(raw)
    name = str(raw.get("name", "")).strip()[:60]
    if name:
        out["name"] = name
    return out


def new_item(item_id: str, image_rel: str, fields: dict, today: date | None = None) -> dict:
    it = {"id": item_id, "image": image_rel}
    if fields.get("name"):
        it["name"] = fields["name"]
    for k in OVERRIDABLE:
        it[k] = fields[k]
    it["added"] = (today or date.today()).isoformat()
    return it
