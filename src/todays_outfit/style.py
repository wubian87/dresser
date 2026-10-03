"""Step 2b - 'style': a text model picks the best 1-3 candidates and explains why.

The model can only choose among rule-approved candidates, and any failure falls back to rules-only.
"""
from __future__ import annotations

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
        "Do not invent clothes that are not listed. Answer with ONE JSON object only, no prose:\n"
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


def rules_reason(o: Outfit, temp_c: float, rain: bool, occasion: str) -> str:
    names = ", ".join(i["name"] for i in o.items)
    bits = [f"{names}: warmth and dress code fit {occasion} at {temp_c:g} °C"]
    if rain:
        bits.append("and it avoids rain-sensitive shoes")
    bits.extend(o.notes)
    return "; ".join(bits) + " (rule-based pick)"


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
            return {"suggestions": [Suggestion(cands[i].items, r, "model", cands[i].relaxed) for i, r in picks],
                    "mode": "model", "candidates": len(cands), "warning": None,
                    "latency": client.last_latency}
        except PrivacyError as e:
            warning = f"{e} - used rules only."
        except (LLMError, ValueError) as e:
            warning = f"Model unavailable or invalid answer ({type(e).__name__}); used rules only."
    top = cands[:n]
    return {"suggestions": [Suggestion(o.items, rules_reason(o, temp_c, rain, occasion), "rules", o.relaxed) for o in top],
            "mode": "rules", "candidates": len(cands), "warning": warning}
