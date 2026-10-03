"""Compare text models on the 'style' step with the real described sample wardrobe.

For each (model, thinking on/off) and scenario: latency, did we get valid JSON with in-range candidates
(i.e. would the app NOT have had to fall back to rules-only)? Writes docs/style_eval.json / .md.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from todays_outfit.config import Endpoint, PRESETS  # noqa: E402
from todays_outfit.llm import LLMClient, LLMError  # noqa: E402
from todays_outfit.rules import build_outfits  # noqa: E402
from todays_outfit.service import Stylist  # noqa: E402
from todays_outfit.config import load_config  # noqa: E402
from todays_outfit.style import build_prompt, parse_choice  # noqa: E402

SCENARIOS = [(12, True, "commute"), (26, False, "date"), (5, False, "casual"), (20, False, "formal"), (30, False, "casual")]
# thinking ON gets a big token budget (reasoning tokens count against max_tokens); thinking OFF uses the app default
VARIANTS = [("Qwen/Qwen3.6-35B-A3B", {"enable_thinking": False}), ("Qwen/Qwen3.5-27B", {"enable_thinking": False}),
            ("Qwen/Qwen3.6-35B-A3B", {}), ("Qwen/Qwen3.5-27B", {})]


def main():
    st = Stylist(load_config(ROOT / "config.example.toml"), ROOT / "sample_wardrobe/wardrobe.json", ROOT / "cache/descriptions.json")
    items = st.described()
    out = {}
    for model, extra in VARIANTS:
        name = model + (" (thinking off)" if extra else " (thinking on, 4000 tokens)")
        c = LLMClient(Endpoint(PRESETS["siliconflow"]["base_url"], model, "SILICONFLOW_API_KEY", extra), timeout=180)
        rows = []
        for t, r, o in SCENARIOS:
            cands = build_outfits(items, t, r, o)
            prompt = build_prompt(cands, t, r, o, "English", 3)
            t0 = time.perf_counter()
            try:
                raw = c.chat([{"role": "user", "content": prompt}], max_tokens=700 if extra else 4000, temperature=0.4)
                dt = time.perf_counter() - t0
                try:
                    picks = parse_choice(raw, len(cands), 3)
                    rows.append({"scenario": [t, r, o], "s": round(dt, 1), "valid": True, "picks": picks})
                except ValueError as e:
                    rows.append({"scenario": [t, r, o], "s": round(dt, 1), "valid": False, "error": str(e), "raw": raw[:300]})
            except LLMError as e:
                rows.append({"scenario": [t, r, o], "s": round(time.perf_counter() - t0, 1), "valid": False, "error": str(e)[:150]})
            print(name, (t, r, o), rows[-1]["s"], rows[-1]["valid"], flush=True)
        out[name] = rows
    (ROOT / "docs/style_eval.json").write_text(json.dumps({"date": time.strftime("%Y-%m-%d %H:%M %Z"), "results": out}, indent=1, ensure_ascii=False))
    lines = ["| Text model | valid answers | median s | max s |", "|---|---|---|---|"]
    for name, rows in out.items():
        s = sorted(x["s"] for x in rows)
        lines.append(f"| {name} | {sum(x['valid'] for x in rows)}/{len(rows)} | {s[len(s)//2]} | {s[-1]} |")
    (ROOT / "docs/style_eval.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
