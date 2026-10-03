"""One real call of the optional model tag stage on a few example pieces; prints stage-1 tags and the model's new ones.

    python tools/tag_check.py > docs/tag_suggestions_run.md      (needs SILICONFLOW_API_KEY)
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from todays_outfit.config import load_config  # noqa: E402
from todays_outfit.llm import LLMClient  # noqa: E402
from todays_outfit.service import Stylist  # noqa: E402
from todays_outfit.tags import infer_tags, suggest_with_model  # noqa: E402

PIECES = ["beige-trench", "grey-knit-sweater", "yellow-rain-boots", "navy-dress"]


def main() -> None:
    cfg = load_config(ROOT / "config.example.toml")
    st = Stylist(cfg, ROOT / "sample_wardrobe" / "wardrobe.json", ROOT / "cache" / "descriptions.json")
    items = {m["id"]: m for m in st.described()}
    client = LLMClient(cfg.text)
    print(f"# Tag suggestions: real model call, {datetime.now():%Y-%m-%d %H:%M} (UTC+8), `{cfg.text.model}`, example wardrobe (drawings)\n")
    print("| Piece | Stage 1 (rules, always) | Stage 2 (model, on request: only NEW tags) | Seconds |\n|---|---|---|---|")
    for pid in PIECES:
        m = items[pid]
        t0 = time.time()
        try:
            extra = ", ".join(suggest_with_model(client, m))
        except Exception as e:  # noqa: BLE001
            extra = f"(failed: {type(e).__name__})"
        print(f"| {m['name']} | {', '.join(infer_tags(m))} | {extra} | {time.time() - t0:.1f} |")


if __name__ == "__main__":
    main()
