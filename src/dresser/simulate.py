"""Synthetic histories and the rotation simulation.

EVERYTHING here is simulation on example data: the "habit" user is a made-up picker that mostly reaches for a few
favourite pieces; it is an assumption used to create a plausible 14-day starting history, not data about any person.
The rule-based part (no language model, no network) is the real code path of the app.
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

from .history import History
from .rotation import Rotation, RotationPolicy
from .rules import build_outfits

FAV_WEIGHT = 1.4     # default habit strength: each favourite piece in an outfit multiplies its pick probability by e**1.4 (~4x)


def make_weather(rng: random.Random, start: date, days: int) -> list[dict]:
    """Plausible autumn days: temperature wanders around 14 C, ~30 % rainy; weekdays commute, weekends casual,
    one date on the first Saturday."""
    out, t, did_date = [], rng.uniform(10, 18), False
    for k in range(days):
        d = start + timedelta(days=k)
        t = max(5.0, min(26.0, t + rng.gauss(0, 3.0) + (14 - t) * 0.15))
        occ = "commute" if d.weekday() < 5 else "casual"
        if d.weekday() == 5 and not did_date:
            occ, did_date = "date", True
        out.append({"date": d, "temp": round(t * 2) / 2, "rain": rng.random() < 0.3, "occasion": occ})
    return out


def pick_favourites(items: list[dict], rng: random.Random) -> set[str]:
    """A 'same few favourites' user: one favourite per category (two tops)."""
    fav: set[str] = set()
    for cat, n in (("top", 2), ("bottom", 1), ("shoes", 1), ("outer", 1), ("dress", 1)):
        pool = sorted(i["id"] for i in items if i["category"] == cat)
        fav.update(rng.sample(pool, min(n, len(pool))))
    return fav


HABIT_POOL = 6       # the made-up habit user only considers the 6 best-scoring rule-approved outfits (no absurd picks)


def habit_pick(rng: random.Random, cands, fav: set[str], strength: float = FAV_WEIGHT):
    cands = cands[:HABIT_POOL]
    w = [math.exp(strength * sum(i["id"] in fav for i in c.items)) for c in cands]
    return rng.choices(cands, weights=w, k=1)[0]


def seed_habit_history(items: list[dict], end_day: date, days: int = 14, seed: int = 7,
                       fav: set[str] | None = None, strength: float = FAV_WEIGHT) -> tuple[History, set[str], list[dict]]:
    """A synthetic `days`-day wear history ending the day before `end_day`. Returns (history, favourites, weather)."""
    rng = random.Random(seed)
    fav = fav or pick_favourites(items, rng)
    wx = make_weather(rng, end_day - timedelta(days=days), days)
    h = History()
    for w in wx:
        cands = build_outfits(items, w["temp"], w["rain"], w["occasion"])
        if cands:
            h.wear(w["date"], [i["id"] for i in habit_pick(rng, cands, fav, strength).items], w["occasion"])
    return h, fav, wx


def _metrics(items, picks: list[dict | None], window_wx: list[dict]) -> dict:
    """picks[k] = {"ids": [...], "score": rule score or None, "relaxed": bool} for window day k, or None if nothing fit."""
    worn = [p for p in picks if p is not None]
    counts: dict[str, int] = {}
    for p in worn:
        for i in p["ids"]:
            counts[i] = counts.get(i, 0) + 1
    reachable: set[str] = set()
    for w in window_wx:
        for c in build_outfits(items, w["temp"], w["rain"], w["occasion"], limit=10_000):
            reachable.update(c.ids)
    consec = sum(1 for a, b in zip(worn, worn[1:]) for i in b["ids"] if i in a["ids"])
    outfits = [frozenset(p["ids"]) for p in worn]
    scores = [p["score"] for p in worn if p["score"] is not None]
    return {
        "days_with_outfit": len(worn),
        "pieces_worn": len(counts),
        "wardrobe_size": len(items),
        "reachable_pieces": len(reachable),
        "unreachable_pieces": sorted({i["id"] for i in items} - reachable),
        "share_of_wardrobe_worn": len(counts) / len(items),
        "share_of_reachable_worn": len(set(counts) & reachable) / max(1, len(reachable)),
        "max_repeats_one_piece": max(counts.values(), default=0),
        "piece_repeats_vs_previous_day": consec,
        "repeated_identical_outfits": len(outfits) - len(set(outfits)),
        "mean_rule_score": sum(scores) / len(scores) if scores else None,
        "relaxed_days": sum(1 for p in worn if p["relaxed"]),
    }


def _pick(o) -> dict:
    return {"ids": o.ids, "score": o.base_score, "relaxed": o.relaxed}


def simulate(items: list[dict], seed: int, days: int = 14, policy: RotationPolicy = RotationPolicy(),
             strength: float = FAV_WEIGHT) -> dict:
    """One simulated month for one random seed: `days` days of habit history, then `days` more days under 3 policies.

      habit     the same made-up habit user keeps choosing as before
      no_rot    the app's top rule-based pick every day, history ignored
      rotation  the app's top pick with rotation (sees the habit history, then its own picks)
    The second period uses a different random weather sequence (same generator). Rules only: no model, no network."""
    start = date(2026, 9, 1)
    hist, fav, wx1 = seed_habit_history(items, start + timedelta(days=days), days, seed, strength=strength)
    wx2 = make_weather(random.Random(seed + 1000), start + timedelta(days=days), days)
    first_picks = []
    for w in wx1:
        e = hist.wear_on(w["date"])
        first_picks.append({"ids": e["items"], "score": None, "relaxed": False} if e else None)
    out = {"seed": seed, "favourites": sorted(fav), "habit_period": _metrics(items, first_picks, wx1), "arms": {}}
    for name in ("habit", "no_rot", "rotation"):
        rng = random.Random(seed + 5000)
        h = History()
        h.wears = [dict(w) for w in hist.wears]
        picks = []
        for w in wx2:
            adjust = Rotation(h, w["date"], policy=policy).adjust if name == "rotation" else None
            cands = build_outfits(items, w["temp"], w["rain"], w["occasion"], adjust=adjust)
            if not cands:
                picks.append(None)
                continue
            p = habit_pick(rng, cands, fav, strength) if name == "habit" else cands[0]
            picks.append(_pick(p))
            h.wear(w["date"], p.ids, w["occasion"])
        out["arms"][name] = _metrics(items, picks, wx2) | {"picks": [None if p is None else p["ids"] for p in picks]}
    out["weather2"] = [{**w, "date": w["date"].isoformat()} for w in wx2]
    return out
