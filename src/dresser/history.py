"""Wear history and feedback, stored in one small local JSON file (history.json next to wardrobe.json).

{ "wears": [ {"date": "2026-10-02", "items": ["white-tee", ...], "occasion": "commute"} ],   # one entry per day
  "skips": [ {"date": "2026-10-02", "items": [...], "occasion": "commute"} ] }               # "Show another" taps

Nothing here is inferred by a model: it is exactly what the user tapped.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


def _d(s: str) -> date:
    return date.fromisoformat(s)


@dataclass
class PieceStats:
    last_worn: date | None
    wear_count: int

    def days_since(self, today: date) -> int | None:
        return None if self.last_worn is None else (today - self.last_worn).days


class History:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.wears: list[dict] = []
        self.skips: list[dict] = []
        self.extra: dict = {}      # e.g. the "_note" that marks a synthetic demo history
        if self.path and self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}   # a damaged file must not stop the app; it just starts empty
            self.extra = {k: v for k, v in data.items() if k.startswith("_")}
            self.wears = [w for w in data.get("wears", []) if _valid(w)]
            self.skips = [s for s in data.get("skips", []) if _valid(s)]

    # ---- persistence ----
    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({**self.extra, "wears": sorted(self.wears, key=lambda w: w["date"]),
                                   "skips": self.skips[-500:]}, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    # ---- writes ----
    def wear(self, day: date, item_ids: list[str], occasion: str | None = None, merge: bool = False) -> dict:
        """Record what was worn on `day`. One entry per day: a new call replaces it (or adds to it if merge)."""
        ids = list(dict.fromkeys(item_ids))
        cur = self.wear_on(day)
        if cur is not None:
            self.wears.remove(cur)
            if merge:
                ids = list(dict.fromkeys(cur["items"] + ids))
                occasion = occasion or cur.get("occasion")
        entry = {"date": day.isoformat(), "items": ids, "occasion": occasion}
        self.wears.append(entry)
        return entry

    def unwear(self, day: date) -> bool:
        cur = self.wear_on(day)
        if cur is None:
            return False
        self.wears.remove(cur)
        return True

    def skip(self, day: date, item_ids: list[str], occasion: str | None = None) -> None:
        self.skips.append({"date": day.isoformat(), "items": sorted(set(item_ids)), "occasion": occasion})

    def forget_items(self, item_ids: set[str]) -> None:
        """Remove deleted pieces from the log (an outfit that becomes empty is dropped)."""
        for w in self.wears:
            w["items"] = [i for i in w["items"] if i not in item_ids]
        self.wears = [w for w in self.wears if w["items"]]
        self.skips = [s for s in self.skips if not (set(s["items"]) & item_ids)]

    # ---- reads ----
    def wear_on(self, day: date) -> dict | None:
        for w in self.wears:
            if w["date"] == day.isoformat():
                return w
        return None

    def first_day(self) -> date | None:
        return min((_d(w["date"]) for w in self.wears), default=None)

    def stats(self) -> dict[str, PieceStats]:
        out: dict[str, PieceStats] = {}
        for w in self.wears:
            day = _d(w["date"])
            for i in w["items"]:
                s = out.setdefault(i, PieceStats(None, 0))
                s.wear_count += 1
                if s.last_worn is None or day > s.last_worn:
                    s.last_worn = day
        return out

    def worn_ids_between(self, start: date, end: date) -> set[str]:
        return {i for w in self.wears if start <= _d(w["date"]) <= end for i in w["items"]}

    def version(self) -> int:
        return len(self.wears) * 1000003 + len(self.skips) + sum(len(w["items"]) for w in self.wears)


def _valid(e) -> bool:
    try:
        return isinstance(e, dict) and isinstance(e["items"], list) and bool(_d(e["date"]))
    except (KeyError, ValueError, TypeError):
        return False
