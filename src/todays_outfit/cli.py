from __future__ import annotations

import argparse
import json
import sys

from .config import load_config
from .llm import PrivacyError
from .rules import OCCASIONS
from .service import Stylist


def _fmt(res: dict, temp, rain, occ) -> str:
    out = [f"{occ}, {temp:g} °C, {'rain' if rain else 'dry'}  ->  {res['mode']} mode ({res.get('candidates', 0)} rule-approved candidates)"]
    for n, s in enumerate(res["suggestions"], 1):
        out.append(f"\n  Outfit {n}: " + " + ".join(i["name"] for i in s.items))
        out.append(f"    {s.reason}")
    if res.get("warning"):
        out.append(f"\n  note: {res['warning']}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="todays-outfit", description="Outfit suggestions from clothes you already own.")
    ap.add_argument("--config", help="path to config.toml (default ./config.toml or $TODAYS_OUTFIT_CONFIG)")
    ap.add_argument("--wardrobe", default="sample_wardrobe/wardrobe.json")
    ap.add_argument("--cache", default="cache/descriptions.json")
    ap.add_argument("--privacy", choices=["off", "images-local", "local-only"], help="override privacy mode from config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("describe", help="run the vision model on every photo (cached)")
    s = sub.add_parser("suggest", help="suggest 1-3 outfits")
    s.add_argument("--temp", type=float, required=True, help="temperature in °C")
    s.add_argument("--rain", action="store_true")
    s.add_argument("--occasion", choices=OCCASIONS, required=True)
    s.add_argument("--rules-only", action="store_true", help="skip the language model")
    s.add_argument("--json", action="store_true")
    sv = sub.add_parser("serve", help="start the web app")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    y = sub.add_parser("import-yichu", help="import a yichu-style SQLite wardrobe (see sources/yichu.py)")
    y.add_argument("--db", required=True)
    y.add_argument("--uploads", required=True)
    y.add_argument("--out", required=True)
    y.add_argument("--table", default="items")
    y.add_argument("--image-col", default="image_path")
    y.add_argument("--name-col", default="name")
    y.add_argument("--id-col", default="id")
    a = ap.parse_args(argv)

    if a.cmd == "import-yichu":
        from .sources.yichu import import_yichu
        n = import_yichu(a.db, a.uploads, a.out, a.table, a.image_col, a.name_col, a.id_col)
        print(f"imported {n} items -> {a.out}")
        return 0

    cfg = load_config(a.config, a.privacy)
    if a.cmd == "serve":
        import os
        import uvicorn
        os.environ["TODAYS_OUTFIT_WARDROBE"] = a.wardrobe
        os.environ["TODAYS_OUTFIT_CACHE"] = a.cache
        if a.config:
            os.environ["TODAYS_OUTFIT_CONFIG"] = a.config
        if a.privacy:
            os.environ["TODAYS_OUTFIT_PRIVACY"] = a.privacy
        uvicorn.run("todays_outfit.api:app", host=a.host, port=a.port)
        return 0

    st = Stylist(cfg, a.wardrobe, a.cache)
    if a.cmd == "describe":
        todo = len(st.undescribed())
        print(f"{len(st.items)} photos, {todo} to describe with {cfg.vision.model} @ {cfg.vision.base_url} (privacy={cfg.privacy})")
        try:
            errs = st.describe(progress=lambda i, d, s: print(f"  {i}: {d['color']} {d['type']} (warmth {d['warmth']}, formality {d['formality']}) {s:.1f}s"))
        except PrivacyError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 2
        for k, v in errs.items():
            print(f"  FAILED {k}: {v}", file=sys.stderr)
        return 1 if errs else 0
    if a.cmd == "suggest":
        if st.undescribed():
            print(f"warning: {len(st.undescribed())} photos not described yet; run `describe` first.", file=sys.stderr)
        res = st.suggest(a.temp, a.rain, a.occasion, use_model=not a.rules_only)
        if a.json:
            print(json.dumps({**res, "suggestions": [{"items": [i["id"] for i in s.items], "reason": s.reason, "source": s.source}
                                                      for s in res["suggestions"]]}, ensure_ascii=False, indent=1))
        else:
            print(_fmt(res, a.temp, a.rain, a.occasion))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
