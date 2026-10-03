"""Simulate 14 days of rotation on the example wardrobe and print REAL computed numbers.

SIMULATION ON EXAMPLE DATA. No person is involved: the "habit" user is a simulated picker that mostly reaches for one
favourite per category, and the app arms always take the app's top pick (they never skip or override it). Rules-only
ranking (no language model, no network), so it is deterministic and reproducible:

    python tools/simulate_rotation.py            # writes docs/rotation_simulation.md and .json

Design of one run (seed s): 14 days of habit history -> then 14 more days of new weather under three policies that all
start from the same history: habit (keeps choosing as before), no_rot (app's top pick, history ignored),
rotation (app's top pick, rotation on, sees its own picks as it goes).
"""
from __future__ import annotations

import json
import statistics as stats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dresser.config import load_config  # noqa: E402
from dresser.rotation import RotationPolicy  # noqa: E402
from dresser.service import Stylist  # noqa: E402
from dresser.simulate import simulate  # noqa: E402

SEEDS = range(50)
STRENGTHS = {"mild habit (favourite piece ~4x as likely)": 1.4, "strong habit (~12x)": 2.5}
ARMS = [("habit", "simulated habit user keeps choosing as before"), ("no_rot", "app top pick, no rotation"),
        ("rotation", "app top pick, with rotation")]
METRICS = [("share_of_wardrobe_worn", "Pieces worn at least once in 14 days", "pieces"),
           ("share_of_reachable_worn", "... of the pieces the rules allow in that weather", "pct"),
           ("max_repeats_one_piece", "Most times one piece was worn in 14 days", "num"),
           ("piece_repeats_vs_previous_day", "Piece-days repeated from the previous day", "num"),
           ("repeated_identical_outfits", "Days wearing an outfit already worn in the window", "num"),
           ("mean_rule_score", "Mean rule score of the outfit worn (higher = better by the rules)", "score")]


def fmt(v, kind, size):
    if kind == "pieces":
        return f"{v * size:.1f}"
    return f"{v * 100:.0f}%" if kind == "pct" else f"{v:.1f}" if kind in ("num", "score") else str(v)


def main() -> None:
    cfg = load_config(ROOT / "config.example.toml")
    st = Stylist(cfg, ROOT / "sample_wardrobe" / "wardrobe.json", ROOT / "cache" / "descriptions.json")
    items = st.room("autumn")          # the simulated weather is autumn-like, so the app would style from the autumn room
    size = len(items)
    policy = RotationPolicy()
    out = {"note": "SIMULATION on the autumn room of the example wardrobe (example illustrations), rules-only, not data about any person",
           "wardrobe_size": size, "seeds": len(SEEDS), "policy": policy.__dict__, "results": {}}
    md = ["# Rotation simulation (example data, rules only)", "",
          f"**This is a simulation, not a user study.** The wardrobe is the autumn room ({size} of the 21 example illustrations in `sample_wardrobe/`; the weather below is autumn-like, and the app only styles from the current room); "
          "the \"habit user\" is a simulated picker; the app arms always accept the app's top pick. Reproduce: "
          "`python tools/simulate_rotation.py`. No language model and no network are used, so the numbers are exactly repeatable.", "",
          f"Setup per run: 14 days of habit history, then 14 new days of weather (random, autumn-like 5-26 °C, ~30% rainy days, "
          f"weekdays commute / weekends casual) under three policies that start from the same history. {len(SEEDS)} runs "
          f"(seeds 0-{len(SEEDS) - 1}) for each habit strength. Cells are the mean over runs, with [min - max] in brackets.", "",
          f"Rotation policy used: worn today/yesterday -{policy.yesterday_penalty}, worn 2-3 days ago -{policy.recent_penalty}, "
          f"long-unworn bonus up to +{policy.neglect_bonus} per piece (full at {policy.neglect_full_days} days). "
          "For scale, rule scores of the best candidates are typically within 1-3 points of each other.", "",
          "How to read it: `no_rotation` takes the same best-scoring outfit whenever the weather repeats, which is why it repeats a lot; "
          "that is the baseline the rotation changes, not a claim about how anyone dresses. The simulated habit user wore "
          "~70-80% of the pieces in a fortnight (weather and the rules already force some variety), so it did not reproduce a \"many clothes never worn\" "
          "pattern, and these numbers say nothing about how much of a real closet sits unused.", ""]
    for label, strength in STRENGTHS.items():
        runs = [simulate(items, s, strength=strength) for s in SEEDS]
        out["results"][label] = {"strength": strength, "runs": [{k: v for k, v in r.items() if k != "weather2"} for r in runs]}
        hp = [r["habit_period"]["share_of_wardrobe_worn"] for r in runs]
        md += [f"## {label}", "",
               f"Seed period (the 14 days of habit history before the comparison): {stats.mean(hp) * size:.1f} of {size} pieces worn "
               f"on average [{min(hp) * size:.0f} - {max(hp) * size:.0f}].", "",
               "| Measure (14 days) | " + " | ".join(d for _, d in ARMS) + " |", "|---|" + "---|" * len(ARMS)]
        for key, desc, kind in METRICS:
            cells = []
            for arm, _ in ARMS:
                vals = [r["arms"][arm][key] for r in runs]
                cells.append(f"{fmt(stats.mean(vals), kind, size)} [{fmt(min(vals), kind, size)} - {fmt(max(vals), kind, size)}]")
            md.append(f"| {desc} | " + " | ".join(cells) + " |")
        reach = [r["arms"]["rotation"]["reachable_pieces"] for r in runs]
        never = sorted(set.intersection(*[set(r["arms"]["rotation"]["unreachable_pieces"]) for r in runs]))
        md += ["", f"Pieces the rules allow at all in these 14-day weather windows: {stats.mean(reach):.1f} of {size} on average "
                   f"[{min(reach)} - {max(reach)}]. Never usable in any run: {', '.join(never) or 'none'} "
                   "(the vision model labelled it an accessory, so the outfit builder does not use it; this is a known misreading, see README).", ""]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "rotation_simulation.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    (ROOT / "docs" / "rotation_simulation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
