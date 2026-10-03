"""Step 2b - 'style': a text model picks the best 1-3 candidates and explains why.

The model can only choose among rule-approved candidates, and any failure falls back to rules-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .jsonparse import extract_json
from .llm import LLMClient, LLMError, PrivacyError
from .rotation import Rotation, history_claims
from .rules import Outfit, build_outfits


@dataclass
class Suggestion:
    items: list[dict]
    reason: str
    source: str            # "model" | "rules"
    relaxed: bool = False
    note: str = ""         # rotation sentence computed from the wear history (never written by a model)


def _describe_item(i: dict) -> str:
    tags = f", tags: {', '.join(i['tags'][:6])}" if i.get("tags") else ""
    return f"{i['name']} [{i['category']}, warmth {i['warmth']}/5, formality {i['formality']}/5, {i.get('material') or 'material n/a'}{tags}]"


def build_prompt(cands: list[Outfit], temp_c: float, rain: bool, occasion: str, language: str, n: int) -> str:
    """Candidates are listed best-first (rules + wear-history rotation already applied). The model is not told the
    history, and is told not to talk about it."""
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
        "Only mention pieces that are part of that exact outfit; never mention other garments or alternatives, "
        "and do not mention what she wore before (you do not know it). Answer with ONE JSON object only, no prose:\n"
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


def _fresh(cands: list[Outfit], rot: Rotation, n: int) -> list[Outfit]:
    """Candidates shown to the model: prefer ones with nothing worn in the last 3 days; if that leaves fewer than
    two, nothing worn yesterday/today; if that still leaves fewer than two, all of them."""
    for min_days in (4, 2):
        ok = [c for c in cands if rot.min_days_since_worn(c.items) >= min_days]
        if len(ok) >= min(2, len(cands)):
            return ok
    return cands


def suggest(items: list[dict], temp_c: float, rain: bool, occasion: str,
            client: LLMClient | None, language: str = "English", n: int = 3,
            rotation: Rotation | None = None, pad_with_rules: bool = False) -> dict:
    """Main entry. Returns {"suggestions": [...], "mode": "model"|"rules"|"none", "warning": str|None}.

    `rotation` (optional): wear-history ranking. It only reorders candidates that already passed the rules.
    `pad_with_rules`: if the model returned fewer than `n` usable picks, fill up with the next-best rule-ranked
    candidates (each labelled source="rules"), so a "Show another" button has something to show."""
    cands = build_outfits(items, temp_c, rain, occasion, adjust=rotation.adjust if rotation else None)
    if not cands:
        return {"suggestions": [], "mode": "none", "candidates": 0,
                "warning": "No outfit in this wardrobe fits that weather and occasion. Try another occasion or add clothes."}
    warning = None
    note = (lambda o: rotation.facts(o.items)["note"]) if rotation else (lambda o: "")
    if client is not None:
        try:
            shown = _fresh(cands, rotation, n) if rotation else cands
            raw = client.chat([{"role": "user", "content": build_prompt(shown, temp_c, rain, occasion, language, n)}],
                              max_tokens=700, temperature=0.4)
            picks = parse_choice(raw, len(shown), n)
            good = [(i, r) for i, r in picks if not ungrounded_terms(r, shown[i].items) and not history_claims(r)]
            if not good:
                raise ValueError("every reason mentioned garments that are not in its outfit (or invented wear history)")
            sugg = [Suggestion(shown[i].items, r, "model", shown[i].relaxed, note(shown[i])) for i, r in good]
            if pad_with_rules and len(sugg) < n:
                have = {frozenset(x.ids) for x in (shown[i] for i, _ in good)}
                for o in shown:
                    if len(sugg) >= n:
                        break
                    if frozenset(o.ids) not in have:
                        have.add(frozenset(o.ids))
                        sugg.append(Suggestion(o.items, rules_reason(o, temp_c, rain, occasion), "rules", o.relaxed, note(o)))
            return {"suggestions": sugg,
                    "mode": "model", "candidates": len(cands), "dropped_ungrounded": len(picks) - len(good),
                    "warning": None, "latency": client.last_latency}
        except PrivacyError as e:
            warning = f"{e} - used rules only."
        except (LLMError, ValueError) as e:
            warning = f"Model unavailable or invalid answer ({e}); used rules only."[:240]
    top = cands[:n]
    return {"suggestions": [Suggestion(o.items, rules_reason(o, temp_c, rain, occasion), "rules", o.relaxed, note(o)) for o in top],
            "mode": "rules", "candidates": len(cands), "warning": warning}
