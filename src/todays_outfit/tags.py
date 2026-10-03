"""Auto tags for a piece.

Stage 1 (this file, deterministic, no model): tags from category, type, colour, material, warmth, formality.
Stage 2 (optional, in service/`suggest_with_model`): a text model proposes extra tags; they are merged with stage 1,
de-duplicated and shown as chips the user accepts or removes. Tags are plain lowercase words; users can add their own.
"""
from __future__ import annotations

import re

from .jsonparse import extract_json
from .rules import NEUTRALS, OCCASION_TAGS, RAIN_BAD, RAIN_GOOD_OUTER, RAIN_GOOD_SHOES  # noqa: F401

MAX_TAGS = 12

_LAYER_TYPES = ("cardigan", "hoodie", "vest", "blazer", "jacket", "coat", "trench", "puffer", "parka", "shawl", "sweatshirt")
_SPORTY = ("hoodie", "sneaker", "trainer", "track", "jogger", "sweatshirt", "athletic", "running")
_DRESSY_SHOES = ("heel", "pump", "stiletto", "loafer")


def _text(item: dict) -> str:
    return " ".join(str(item.get(k, "")) for k in ("type", "material", "notes", "name")).lower()


def clean_tag(t) -> str:
    t = re.sub(r"[^\w\- ]+", "", str(t).strip().lower().replace("_", "-"), flags=re.UNICODE)
    return re.sub(r"\s+", "-", t.strip())[:24]


def clean_tags(tags) -> list[str]:
    out: list[str] = []
    for t in tags if isinstance(tags, (list, tuple)) else []:
        c = clean_tag(t)
        if c and c not in out:
            out.append(c)
    return out[:MAX_TAGS]


def infer_tags(item: dict) -> list[str]:
    """Stage 1. Every tag below has a plain rule, listed in the comment next to it."""
    tags: list[str] = []
    add = lambda t: tags.append(t) if t not in tags else None  # noqa: E731
    cat, text = item.get("category", ""), _text(item)
    typ = str(item.get("type", "")).lower()
    core = f"{typ} {str(item.get('material', '')).lower()}"
    try:
        f, w = int(item.get("formality", 3)), int(item.get("warmth", 3))
    except (TypeError, ValueError):
        f, w = 3, 3
    # formality: 1-2 casual, 3 smart-casual, 4-5 work, 5 formal
    if f <= 2:
        add("casual")
    elif f == 3:
        add("smart-casual")
    else:
        add("work")
    if f >= 5:
        add("formal")
    if f >= 4 and (cat == "dress" or any(k in typ for k in _DRESSY_SHOES) or "skirt" in typ):
        add("dressy")
    # rain: rain-proof shoes/outer; shoes in rain-sensitive materials are flagged the other way
    if cat == "shoes":
        if any(k in core for k in RAIN_GOOD_SHOES):
            add("rain-ready")
        elif any(k in text for k in RAIN_BAD):
            add("not-for-rain")
    elif cat == "outer" and any(k in text for k in RAIN_GOOD_OUTER):
        add("rain-ready")
    # layering: outer layers and light cover-ups
    if cat == "outer" or any(k in typ for k in _LAYER_TYPES):
        add("layering")
    # colour
    color = str(item.get("color", "")).lower()
    if color and color != "unknown":
        add("neutral" if any(n in color for n in NEUTRALS) else "colourful")
    # warmth
    if w >= 4:
        add("warm")
    elif w <= 1 or (w == 2 and cat in ("top", "bottom", "dress")):
        add("light")
    # material / look
    for key, tag in (("denim", "denim"), ("knit", "knit"), ("wool", "wool"), ("leather", "leather"), ("linen", "linen"),
                     ("silk", "silk"), ("cotton", "cotton")):
        if key in core:
            add(tag)
    if any(k in typ for k in _SPORTY):
        add("sporty")
    return tags[:MAX_TAGS]


def merge_tags(*groups) -> list[str]:
    out: list[str] = []
    for g in groups:
        for t in clean_tags(g):
            if t not in out:
                out.append(t)
    return out[:MAX_TAGS]


def tag_prompt(item: dict, language: str = "English") -> str:
    return (
        "You tag clothes for a personal wardrobe app. Piece: "
        f"{item.get('color', '')} {item.get('type', '')} (category {item.get('category', '')}, material {item.get('material') or 'unknown'}, "
        f"warmth {item.get('warmth', '?')}/5, formality {item.get('formality', '?')}/5, notes: {item.get('notes') or 'none'}).\n"
        f"Already tagged: {', '.join(infer_tags(item)) or 'nothing'}.\n"
        "Suggest up to 5 NEW short tags (one or two words, lowercase, in English) about style, occasion, fit or how it is worn, "
        "e.g. 'preppy', 'weekend', 'office', 'cosy', 'evening', 'travel'. Do not repeat existing tags, do not invent colours "
        'or materials that are not listed. Answer with ONE JSON object only: {"tags": ["..."]}'
    )


def parse_model_tags(text: str, existing: list[str] | None = None) -> list[str]:
    data = extract_json(text)
    arr = data.get("tags") if isinstance(data, dict) else data
    if not isinstance(arr, list):
        raise ValueError("no tags array")
    have = set(existing or [])
    return [t for t in clean_tags(arr) if t not in have][:5]


def suggest_with_model(client, item: dict, language: str = "English") -> list[str]:
    """Stage 2. Returns only tags that are new relative to stage 1. Raises LLMError/PrivacyError/ValueError on failure."""
    raw = client.chat([{"role": "user", "content": tag_prompt(item, language)}], max_tokens=200, temperature=0.3)
    return parse_model_tags(raw, infer_tags(item))
