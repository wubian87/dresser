"""Try "Paste a link" on real public product pages and print what happened (page, picture, vision model, fields).

    python tools/link_import_probe.py URL [URL ...]     > docs/link_import_run.txt

Uses a throw-away wardrobe folder; needs the network, and SILICONFLOW_API_KEY for the vision step (without it the fields
come from the page title only). Prints one block per link. Nothing is saved to your own wardrobe.
"""
from __future__ import annotations

import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dresser import linkimport as li  # noqa: E402
from dresser.config import load_config  # noqa: E402
from dresser.service import Stylist  # noqa: E402
from dresser.wardrobe import save_wardrobe  # noqa: E402


def main(urls: list[str]) -> None:
    cfg = load_config(ROOT / "config.example.toml")
    print(f"link import probe, {date.today().isoformat()}, privacy={cfg.privacy}, vision={cfg.vision.model}\n")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "wardrobe.json"
        save_wardrobe(path, [])
        st = Stylist(cfg, path, Path(d) / "cache.json")
        for u in urls:
            t0 = time.time()
            try:
                r = st.import_link(u)
            except li.LinkError as e:
                print(f"FAILED  {u}\n  kind={e.kind}  ({time.time() - t0:.1f}s)\n  message shown to the user: {e}\n")
                continue
            f = r["fields"]
            print(f"WORKED  {u}  ({time.time() - t0:.1f}s)\n  page title : {r['source']['title']}\n"
                  f"  filled     : {f['category']} / {f['type']} / {f['color']} / {f['material'] or '-'} / warmth {f['warmth']} / formality {f['formality']}\n"
                  f"  rooms      : {', '.join(f['season'])}\n  tags       : {', '.join(f['tags'])}\n"
                  f"  vision note: {r['describe_error'] or 'vision model read the picture'}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
