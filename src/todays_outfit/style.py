"""Step 2b - 'style': a text model picks the best 1-3 candidates and explains why.

The model can only choose among rule-approved candidates, and any failure falls back to rules-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .jsonparse import extract_json
from .llm import LLMClient, LLMError, PrivacyError
from .rules import Outfit, build_outfits


@dataclass
class Suggestion:
    items: list[dict]
    reason: str
    source: str            # "model" | "rules"
    relaxed: bool = False


def _describe_item(i: dict) -> str:
    return f"{i['name']} [{i['category']}, warmth {i['warmth']}/5, formality {i['formality']}/5, {i.get('material') or 'material n/a'}]"


def build_prompt(cands: list[Outfit], temp_c: float, rain: bool, occasion: str, language: str, n: int) -> str:
    lines = []
    for k, o in enumerate(cands):
        lines.append(f"{k}: " + " + ".join(_describe_item(i) for i in o.items))
    return (
        f"You are a friendly personal stylist. The user is dressing for: occasion = {occasion}; "
        f"temperature = {temp_c:g} C; rain = {'yes' if rain else 'no'}.\n"
        "These outfits were pre-approved by hard rules (weather and dress-code safe), all from clothes she already owns:\n"
        + "\n".join(lines)
        + f"\n\nPick the best {n} DIFFERENT outfits (fewer if fewer are good). For each, write a one or two sentence reason "
        f"(max 35 words) in {language}, naming concrete pieces and why they suit the weather/occasion and each other. "
        "Only mention pieces that are part of that exact outfit; never mention other garments or alternatives. Answer with ONE JSON object only, no prose:\n"
        '{"outfits": [{"candidate": <number from the list>, "reason": "<text>"}]}'
    )


def parse_choice(text: str, n_candidates: int, max_out: int = 3) -> list[tuple[int, str]]:
    """Validate model output -> [(candidate index, reason)]. Raises ValueError if unusable."""
    data = extract_json(text)
    arr = data.get("outfits") if isinstance(data, dict) else data
    if not isinstance(arr, list) or not arr:
        raise ValueError("no outfits array")
    picked, seen = [], set()
    for e in arr:
        if not isinstance(e, dict):
            continue
        try:
            idx = int(e.get("candidate"))
        except (TypeError, ValueError):
            continue
        reason = str(e.get("reason", "")).strip()
        if 0 <= idx < n_candidates and idx not in seen and reason:
            seen.add(idx)
            picked.append((idx, reason[:400]))
    if not picked:
        raise ValueError("no valid candidates chosen")
    return picked[:max_out]


# Words a reason may use only if the outfit really contains such a garment. Catches the typical small-model
# slip of praising a piece that is NOT in the outfit ("... better than heels", "cozy wool knit" for a shirt).
GARMENT_GROUPS = [
    ("sweater", "knit", "jumper", "pullover"), ("jeans", "denim"), ("cardigan",), ("hoodie", "sweatshirt"),
    ("blazer", "jacket", "coat", "trench", "puffer", "parka"), ("trousers", "pants", "slacks"), ("shorts",),
    ("skirt",), ("dress", "sundress"), ("shirt", "tee", "blouse", "button-down", "t-shirt"),
    ("sneaker", "trainer"), ("boot",), ("heel", "pump", "stiletto"), ("loafer", "moccasin"),
    ("flat", "ballet"), ("sandal",),
]


def ungrounded_terms(reason: str, items: list[dict]) -> list[str]:
    """Garment words in `reason` that no piece of the outfit accounts for."""
    have = " ".join(f"{i.get('name', '')} {i.get('type', '')}" for i in items).lower()
    text = re.sub(r"dress(ed|ing|y| code)", "", reason.lower())
    bad = []
    for group in GARMENT_GROUPS:
        mentioned = [w for w in group if re.search(rf"\b{re.escape(w)}(s|es)?\b", text)]
        if mentioned and not any(w in have for w in group):
            bad.append(mentioned[0])
    return bad


def rules_reason(o: Outfit, temp_c: float, rain: bool, occasion: str) -> str:
    bits = [f"Right weight for {temp_c:g} °C and within the {occasion} dress code"]
    if rain and "rain-proof shoes" not in o.notes:
        bits.append("no rain-sensitive shoes")
    bits.extend(o.notes)
    return "; ".join(bits) + " (rule-based pick)."


def suggest(items: list[dict], temp_c: float, rain: bool, occasion: str,
            client: LLMClient | None, language: str = "English", n: int = 3) -> dict:
    """Main entry. Returns {"suggestions": [...], "mode": "model"|"rules"|"none", "warning": str|None}."""
    cands = build_outfits(items, temp_c, rain, occasion)
    if not cands:
        return {"suggestions": [], "mode": "none", "candidates": 0,
                "warning": "No outfit in this wardrobe fits that weather and occasion. Try another occasion or add clothes."}
    warning = None
    if client is not None:
        try:
            raw = client.chat([{"role": "user", "content": build_prompt(cands, temp_c, rain, occasion, language, n)}],
                              max_tokens=700, temperature=0.4)
            picks = parse_choice(raw, len(cands), n)
            good = [(i, r) for i, r in picks if not ungrounded_terms(r, cands[i].items)]
            if not good:
                raise ValueError("every reason mentioned garments that are not in its outfit")
            return {"suggestions": [Suggestion(cands[i].items, r, "model", cands[i].relaxed) for i, r in good],
                    "mode": "model", "candidates": len(cands), "dropped_ungrounded": len(picks) - len(good),
                    "warning": None, "latency": client.last_latency}
        except PrivacyError as e:
            warning = f"{e} - used rules only."
        except (LLMError, ValueError) as e:
            warning = f"Model unavailable or invalid answer ({e}); used rules only."[:240]
    top = cands[:n]
    return {"suggestions": [Suggestion(o.items, rules_reason(o, temp_c, rain, occasion), "rules", o.relaxed) for o in top],
            "mode": "rules", "candidates": len(cands), "warning": warning}
