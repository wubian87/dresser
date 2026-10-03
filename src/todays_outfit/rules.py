"""Step 2a - deterministic rule filter. No AI here: weather + occasion -> allowed outfit combos.

An outfit is: (top + bottom) or dress, + shoes, + optional outer layer.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

OCCASIONS = ("commute", "casual", "date", "formal")

# per-item formality bounds, and bounds on the mean formality of the whole outfit
OCCASION_RULES = {
    "commute": {"item": (1, 5), "mean": (2.5, 4.2), "ideal": 3.4},
    "casual": {"item": (1, 3), "mean": (1.0, 3.0), "ideal": 2.0},
    "date": {"item": (2, 5), "mean": (2.5, 4.4), "ideal": 3.4},
    "formal": {"item": (3, 5), "mean": (3.8, 5.0), "ideal": 4.6},
}

# materials that suffer in the rain
RAIN_BAD = ("suede", "canvas", "satin", "silk", "velvet", "mesh", "fabric", "felt")
RAIN_GOOD_SHOES = ("rain boot", "rubber", "wellington", "waterproof")
RAIN_GOOD_OUTER = ("trench", "water-resistant", "waterproof", "rain", "nylon", "puffer", "parka", "windbreaker")

NEUTRALS = ("black", "white", "grey", "gray", "beige", "cream", "navy", "brown", "tan", "khaki", "denim", "ivory", "camel")


@dataclass
class Outfit:
    items: list[dict]
    score: float
    notes: list[str] = field(default_factory=list)
    relaxed: bool = False

    @property
    def ids(self) -> list[str]:
        return [i["id"] for i in self.items]


def target_warmth(temp_c: float) -> float:
    """Desired total warmth level 1..5.5 for an air temperature (deg C)."""
    return max(1.0, min(5.5, 1 + (30 - temp_c) / 7))


def outfit_warmth(core: list[dict], outer: dict | None) -> float:
    base = sum(i["warmth"] for i in core) / len(core)
    return base + (0.5 * (outer["warmth"] - 1) if outer else 0.0)


def _text(item: dict) -> str:
    return " ".join(str(item.get(k, "")) for k in ("type", "material", "notes", "name")).lower()


def rain_unfriendly(item: dict) -> bool:
    """Shoes made of rain-sensitive material. 'Good' keywords are looked up in type/material only, so a note like
    'rubber sole' on a canvas sneaker does not make it rain-proof."""
    if item.get("category") != "shoes":
        return False
    core = f"{item.get('type', '')} {item.get('material', '')}".lower()
    return any(w in _text(item) for w in RAIN_BAD) and not any(w in core for w in RAIN_GOOD_SHOES)


def color_family(item: dict) -> str:
    c = str(item.get("color", "")).lower()
    for n in NEUTRALS:
        if n in c:
            return "neutral"
    return c or "unknown"


def _score(core, outer, shoes, temp_c, rain, occasion, band) -> tuple[float, list[str]]:
    notes = []
    pieces = core + ([outer] if outer else []) + [shoes]
    w = outfit_warmth(core, outer)
    tw = target_warmth(temp_c)
    score = 10.0 - 2.0 * abs(w - tw)
    mean_f = sum(i["formality"] for i in pieces) / len(pieces)
    score -= 1.5 * abs(mean_f - OCCASION_RULES[occasion]["ideal"])
    # colour: neutrals are safe; at most one loud colour looks intentional
    loud = {color_family(i) for i in pieces if color_family(i) != "neutral"}
    if len(loud) > 1:
        score -= 1.5 * (len(loud) - 1)
        notes.append("several loud colours")
    elif len(loud) == 1:
        score += 0.3
    if rain:
        if any(k in _text(shoes) for k in RAIN_GOOD_SHOES):
            score += 1.0
            notes.append("rain-proof shoes")
        if outer and any(k in _text(outer) for k in RAIN_GOOD_OUTER):
            score += 1.0
            notes.append("water-resistant layer")
    # sprung formality: a very formal shoe with a very casual top feels off
    spread = max(i["formality"] for i in pieces) - min(i["formality"] for i in pieces)
    if spread >= 3:
        score -= 0.8 * (spread - 2)
    return score, notes


def build_outfits(items: list[dict], temp_c: float, rain: bool, occasion: str,
                  limit: int = 12) -> list[Outfit]:
    """Return up to `limit` scored candidate outfits that obey the hard rules.

    If the hard rules leave nothing (small wardrobe), constraints are relaxed step by step and
    outfits are flagged `relaxed=True` so the UI can say so honestly.
    """
    if occasion not in OCCASIONS:
        raise ValueError(f"occasion must be one of {OCCASIONS}")
    by = lambda c: [i for i in items if i["category"] == c]  # noqa: E731
    tops, bottoms, dresses, outers, shoes = by("top"), by("bottom"), by("dress"), by("outer"), by("shoes")
    rules = OCCASION_RULES[occasion]
    tw = target_warmth(temp_c)

    for level in range(4):  # 0 = strict, then progressively relaxed
        lo_i, hi_i = rules["item"]
        lo_m, hi_m = rules["mean"]
        slack = (0.0, 0.5, 1.0, 2.0)[level]
        band = (0.9 + slack, 1.3 + slack)  # (colder-than-target tolerance, warmer-than-target tolerance)
        item_ok = lambda i: (lo_i - (level >= 2)) <= i["formality"] <= (hi_i + (level >= 2))  # noqa: E731
        outs: list[Outfit] = []
        cores = [[t, b] for t in tops for b in bottoms] + [[d] for d in dresses]
        for core in cores:
            if not all(item_ok(i) for i in core):
                continue
            # no single piece may be wildly wrong for the weather (e.g. shorts at 5 C, heavy knit at 30 C)
            if any(abs(i["warmth"] - tw) > 2.2 + slack for i in core):
                continue
            for outer in [None] + outers:
                if outer is not None and not item_ok(outer):
                    continue
                w = outfit_warmth(core, outer)
                if not (tw - band[0] <= w <= tw + band[1]):
                    continue
                # hard layering rules
                if temp_c < 12 and (outer is None or outer["warmth"] < 3) and level < 2:
                    continue
                if temp_c >= 24 and outer is not None and not (occasion == "formal" and outer["warmth"] <= 2):
                    continue
                for sh in shoes:
                    if not item_ok(sh):
                        continue
                    if rain and rain_unfriendly(sh) and level < 3:
                        continue
                    if temp_c >= 25 and sh["warmth"] >= 4 and level < 2:
                        continue
                    if temp_c <= 5 and sh["warmth"] <= 1 and level < 2:
                        continue
                    pieces = core + ([outer] if outer else []) + [sh]
                    mean_f = sum(i["formality"] for i in pieces) / len(pieces)
                    if not (lo_m - 0.3 * level <= mean_f <= hi_m + 0.3 * level):
                        continue
                    s, notes = _score(core, outer, sh, temp_c, rain, occasion, band)
                    if level:
                        s -= 2 * level
                    outs.append(Outfit(pieces, s, notes, relaxed=level > 0))
        if outs:
            return _diverse_top(sorted(outs, key=lambda o: -o.score), limit)
    return []


def _diverse_top(outs: list[Outfit], limit: int) -> list[Outfit]:
    """Greedy pick that avoids near-duplicates (>=3 shared pieces) so the model sees real alternatives."""
    chosen: list[Outfit] = []
    for o in outs:
        if all(len(set(o.ids) & set(c.ids)) < 3 or len(o.ids) <= 2 for c in chosen):
            chosen.append(o)
        if len(chosen) >= limit:
            break
    return chosen
