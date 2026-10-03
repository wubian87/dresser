"""Benchmark vision models on the EXAMPLE wardrobe against ground_truth.json.

Usage: python tools/eval_describe.py [model ...]   (default: the four SiliconFlow candidates)
Latency = wall-clock seconds per single request, images sent one at a time (no concurrency).
Writes docs/vision_eval.json and docs/vision_eval.md. The API key is read from the environment by the client and never printed.
"""
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dresser.config import Endpoint, PRESETS  # noqa: E402
from dresser.describe import describe_image  # noqa: E402
from dresser.llm import LLMClient, LLMError  # noqa: E402

MODELS = ["Qwen/Qwen3-VL-8B-Instruct", "Qwen/Qwen3-VL-30B-A3B-Instruct", "Qwen/Qwen3-VL-32B-Instruct", "zai-org/GLM-4.5V"]
SYN = {"t-shirt": ["tee", "t shirt", "tshirt", "t-shirt"], "button-up shirt": ["shirt", "button", "oxford", "blouse"],
       "knit sweater": ["sweater", "jumper", "pullover", "knit"], "hoodie": ["hoodie", "sweatshirt"],
       "cardigan": ["cardigan"], "blazer": ["blazer", "jacket", "suit"], "trench coat": ["trench", "coat"],
       "puffer jacket": ["puffer", "padded", "down", "quilted", "jacket"], "denim jacket": ["denim", "jean jacket", "jacket"],
       "jeans": ["jeans", "denim"], "tailored trousers": ["trouser", "pants", "slacks"], "shorts": ["shorts"],
       "pleated midi skirt": ["skirt"], "dress": ["dress"], "sundress": ["dress", "sundress"],
       "sneakers": ["sneaker", "trainer"], "ankle boots": ["boot"], "high heels": ["heel", "pump", "stiletto"],
       "loafers": ["loafer", "moccasin", "slip-on"], "rain boots": ["rain", "wellington", "boot"],
       "ballet flats": ["flat", "ballet", "slip-on", "shoe"]}


COLOR_EQ = {"khaki": ("beige", "tan", "khaki"), "cream": ("beige", "cream", "ivory"), "tan": ("brown", "tan", "beige"),
            "white": ("white",), "mustard yellow": ("mustard", "yellow", "golden")}


def color_ok(pred, truth):
    p = pred.lower()
    if truth in COLOR_EQ and any(w in p for w in COLOR_EQ[truth]):
        return True
    return any(w in p for w in truth.lower().replace("light ", "").split()) or (truth == "mustard yellow" and "yellow" in p) \
        or (truth == "grey" and "gray" in p) or (truth == "blue" and "blue" in p) or (truth == "burgundy" and any(x in p for x in ("maroon", "wine", "red")))


def score(d, gt):
    return {"cat": d["category"] == gt["cat"],
            "type": any(w in d["type"] for w in SYN[gt["type"]]),
            "color": color_ok(d["color"], gt["color"]),
            "warmth1": abs(d["warmth"] - gt["warmth"]) <= 1,
            "form1": abs(d["formality"] - gt["formality"]) <= 1,
            "material": any(w in d["material"] for w in gt["material"].replace(",", "").split()[:2])}


def main():
    models = sys.argv[1:] or MODELS
    truth = json.loads((ROOT / "sample_wardrobe/ground_truth.json").read_text())
    results = {}
    for m in models:
        ep = Endpoint(PRESETS["siliconflow"]["base_url"], m, PRESETS["siliconflow"]["api_key_env"])
        client = LLMClient(ep)
        rows, lat, fails = [], [], 0
        for iid, gt in truth.items():
            t0 = time.perf_counter()
            try:
                d, _ = describe_image(client, ROOT / "sample_wardrobe" / f"{iid}.png")
            except (LLMError, ValueError) as e:
                fails += 1
                rows.append({"id": iid, "error": str(e)[:120]})
                continue
            lat.append(time.perf_counter() - t0)
            rows.append({"id": iid, "pred": d, "s": round(lat[-1], 2), **score(d, gt)})
            print(m, iid, "ok" if rows[-1]["cat"] else "CAT-MISS", f"{lat[-1]:.1f}s", flush=True)
        ok = [r for r in rows if "pred" in r]
        n = len(truth)
        agg = {k: round(sum(r[k] for r in ok) / n, 3) for k in ("cat", "type", "color", "warmth1", "form1", "material")}
        results[m] = {"n": n, "failures": fails, "latency_median_s": round(statistics.median(lat), 2) if lat else None,
                      "latency_p90_s": round(sorted(lat)[int(.9 * (len(lat) - 1))], 2) if lat else None,
                      "latency_mean_s": round(statistics.mean(lat), 2) if lat else None, "accuracy": agg, "rows": rows}
    out = ROOT / "docs"
    (out / "vision_eval.json").write_text(json.dumps({"date": time.strftime("%Y-%m-%d %H:%M %Z"), "results": results}, indent=1, ensure_ascii=False))
    lines = ["| Model | failures | median s | p90 s | category | type | colour | warmth ±1 | formality ±1 | material |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m, r in results.items():
        a = r["accuracy"]
        lines.append(f"| {m} | {r['failures']}/{r['n']} | {r['latency_median_s']} | {r['latency_p90_s']} | {a['cat']:.0%} | {a['type']:.0%} | {a['color']:.0%} | {a['warmth1']:.0%} | {a['form1']:.0%} | {a['material']:.0%} |")
    (out / "vision_eval.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
