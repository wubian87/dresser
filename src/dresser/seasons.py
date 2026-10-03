"""Season rooms: the wardrobe is split into four rooms (spring, summer, autumn, winter) and only the current room is
shown and used for styling. A piece can live in several rooms.

Which room is "current" is a setting (auto = suggested from today's date, flipped in the southern hemisphere when the
location's latitude is known and negative; default north). Which rooms a piece belongs to is inferred from its warmth
and category by the table below, and is editable per piece.
"""
from __future__ import annotations

import re
from datetime import date

SEASONS = ("spring", "summer", "autumn", "winter")
_NORTH = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring", 6: "summer", 7: "summer",
          8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
_FLIP = {"spring": "autumn", "summer": "winter", "autumn": "spring", "winter": "summer"}


SUMMERY = ("shorts", "sandal", "sundress", "tank", "camisole", "flip.?flop", "swim", "sleeveless")
WINTERY = ("coat", "parka", "puffer", "padded", "fleece", "thermal", "scarf", "beanie", "glove", "down jacket")


def suggest_season(day: date, lat: float | None = None) -> str:
    """Meteorological season for `day`; southern hemisphere (lat < 0) is flipped; unknown latitude means north."""
    s = _NORTH[day.month]
    return _FLIP[s] if lat is not None and lat < 0 else s


def hemisphere(lat: float | None) -> str:
    return "south" if lat is not None and lat < 0 else "north"


def infer_seasons(item: dict) -> list[str]:
    """Rooms for a piece, from warmth (1 very light .. 5 heavy) and category. Deterministic, no model.

      warmth 1  -> spring, summer
      warmth 2  -> spring, summer, autumn
      warmth 3  -> spring, autumn, winter   (+ summer for bottoms, dresses and shoes)
      warmth 4  -> autumn, winter
      warmth 5  -> winter

    Then two keyword overrides on the piece's type/name: shorts, sandals, sundresses, tank tops and similar are
    spring+summer only; coats, parkas, puffers, fleece, thermals and similar are autumn+winter only.
    """
    try:
        w = int(item.get("warmth", 3))
    except (TypeError, ValueError):
        w = 3
    w = max(1, min(5, w))
    if w == 1:
        out = ["spring", "summer"]
    elif w == 2:
        out = ["spring", "summer", "autumn"]
    elif w == 3:
        out = ["spring", "autumn", "winter"]
        if item.get("category") in ("bottom", "dress", "shoes"):
            out.insert(1, "summer")
    elif w == 4:
        out = ["autumn", "winter"]
    else:
        out = ["winter"]
    text = f"{item.get('type', '')} {item.get('name', '')}".lower()
    if any(re.search(rf"\b{k}", text) for k in SUMMERY):
        return ["spring", "summer"]
    if any(re.search(rf"\b{k}", text) for k in WINTERY):
        return ["autumn", "winter"]
    return out


def clean_seasons(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [s for s in SEASONS if isinstance(value, (list, tuple, set)) and s in {str(v).lower() for v in value}]


def item_seasons(item: dict) -> list[str]:
    """The rooms a (merged) item is in: its own editable list if it has one, else the rule inference."""
    own = clean_seasons(item.get("season"))
    return own or infer_seasons(item)


def in_room(item: dict, season: str) -> bool:
    return season in item_seasons(item)
