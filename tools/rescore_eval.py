"""Re-score the saved raw model answers in docs/vision_eval.json with the current scorer (no API calls)."""
import json, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from eval_describe import score  # noqa: E402

p = ROOT / "docs/vision_eval.json"
data = json.loads(p.read_text())
truth = json.loads((ROOT / "sample_wardrobe/ground_truth.json").read_text())
lines = ["| Model | failures | median s | p90 s | category | type | colour | warmth ±1 | formality ±1 | material |", "|---|---|---|---|---|---|---|---|---|---|"]
for m, r in data["results"].items():
    for row in r["rows"]:
        if "pred" in row:
            row.update(score(row["pred"], truth[row["id"]]))
    ok = [x for x in r["rows"] if "pred" in x]
    r["accuracy"] = {k: round(sum(x[k] for x in ok) / r["n"], 3) for k in ("cat", "type", "color", "warmth1", "form1", "material")}
    a = r["accuracy"]
    lines.append(f"| {m} | {r['failures']}/{r['n']} | {r['latency_median_s']} | {r['latency_p90_s']} | {a['cat']:.0%} | {a['type']:.0%} | {a['color']:.0%} | {a['warmth1']:.0%} | {a['form1']:.0%} | {a['material']:.0%} |")
p.write_text(json.dumps(data, indent=1, ensure_ascii=False))
(ROOT / "docs/vision_eval.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
