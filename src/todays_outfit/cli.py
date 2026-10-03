from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .config import load_config
from .llm import PrivacyError
from .rules import OCCASIONS
from .seasons import SEASONS
from .service import NotFound, ReadOnlyError, Stylist
from .wardrobe import save_wardrobe

SAMPLE = "sample_wardrobe/wardrobe.json"


def _resolve_wardrobe(a, cfg, create: bool) -> str:
    """--demo > --wardrobe > --data-dir > ./data (if it exists, or `create`) > the bundled read-only example."""
    if a.demo:
        from .demo import init_demo
        return str(init_demo(a.data_dir or "demo_data", cfg, a.cache))
    if a.wardrobe:
        return a.wardrobe
    p = Path(a.data_dir or "data") / "wardrobe.json"
    if p.is_file():
        return str(p)
    if create or a.data_dir:
        p.parent.mkdir(parents=True, exist_ok=True)
        save_wardrobe(p, [])
        return str(p)
    return SAMPLE


def _fmt(res: dict, temp, rain, occ) -> str:
    out = [f"{occ}, {temp:g} °C, {'rain' if rain else 'dry'}  ->  {res['mode']} mode ({res.get('candidates', 0)} rule-approved candidates)"]
    for n, s in enumerate(res["suggestions"], 1):
        out.append(f"\n  Outfit {n}: " + " + ".join(i["name"] for i in s.items))
        out.append(f"    {s.reason}")
        if s.note:
            out.append(f"    Rotation: {s.note}")
    if res.get("warning"):
        out.append(f"\n  note: {res['warning']}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="todays-outfit", description="Outfit suggestions from clothes you already own.")
    ap.add_argument("--config", help="path to config.toml (default ./config.toml or $TODAYS_OUTFIT_CONFIG)")
    ap.add_argument("--wardrobe", help=f"path to wardrobe.json (default: ./data/wardrobe.json if it exists, else {SAMPLE})")
    ap.add_argument("--data-dir", help="folder holding wardrobe.json, images/, history.json, settings.json (default ./data)")
    ap.add_argument("--demo", action="store_true",
                    help="use a writable copy of the example wardrobe with a SYNTHETIC 14-day history (in ./demo_data)")
    ap.add_argument("--cache", default="cache/descriptions.json")
    ap.add_argument("--privacy", choices=["off", "images-local", "local-only"], help="override privacy mode from config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("describe", help="run the vision model on every photo (cached)")
    s = sub.add_parser("suggest", help="suggest 1-3 outfits")
    s.add_argument("--temp", type=float, required=True, help="temperature in °C")
    s.add_argument("--rain", action="store_true")
    s.add_argument("--occasion", choices=OCCASIONS, required=True)
    s.add_argument("--rules-only", action="store_true", help="skip the language model")
    s.add_argument("--no-rotation", action="store_true", help="ignore the wear history")
    s.add_argument("--json", action="store_true")
    s.add_argument("--season", choices=[*SEASONS, "all"], help="room to style from (default: the current season room)")
    t = sub.add_parser("today", help="today's pick: automatic forecast (Open-Meteo) + your last-used occasion")
    t.add_argument("--occasion", choices=OCCASIONS, help="default: the last one you used")
    t.add_argument("--temp", type=float, help="override the forecast with a temperature (°C)")
    t.add_argument("--rain", action="store_true", help="with --temp: it rains")
    t.add_argument("--rules-only", action="store_true")
    t.add_argument("--season", choices=[*SEASONS, "all"], help="room to style from (default: the current season room)")
    se = sub.add_parser("season", help="show the current season room, or set it (auto = follow the date)")
    se.add_argument("set", nargs="?", choices=[*SEASONS, "auto"])
    w = sub.add_parser("wear", help="record what you wore (default: today)")
    w.add_argument("items", nargs="*", help="piece ids (see `wardrobe`)")
    w.add_argument("--date", help="YYYY-MM-DD, default today")
    w.add_argument("--undo", action="store_true", help="remove the entry for that day")
    wd = sub.add_parser("wardrobe", help="list the pieces of the current room with last-worn date and wear count")
    wd.add_argument("--season", choices=[*SEASONS, "all"])
    ad = sub.add_parser("add", help="add clothes from photos: the vision model describes them, you can override fields")
    ad.add_argument("photos", nargs="+")
    ad.add_argument("--category", choices=["top", "bottom", "dress", "outer", "shoes", "accessory"])
    ad.add_argument("--type")
    ad.add_argument("--color")
    ad.add_argument("--name")
    ad.add_argument("--no-describe", action="store_true", help="do not call a vision model (needs --category)")
    sub.add_parser("init-demo", help="create ./demo_data (writable example wardrobe + synthetic 14-day history)")
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
    if a.cmd == "init-demo":
        from .demo import init_demo
        p = init_demo(a.data_dir or "demo_data", cfg, a.cache)
        print(f"demo wardrobe ready: {p} (example drawings + SYNTHETIC 14-day history)")
        return 0
    a.wardrobe = _resolve_wardrobe(a, cfg, create=a.cmd in ("serve", "add"))
    if a.cmd == "serve":
        import os
        import uvicorn
        os.environ["TODAYS_OUTFIT_WARDROBE"] = a.wardrobe
        os.environ["TODAYS_OUTFIT_CACHE"] = a.cache
        if a.config:
            os.environ["TODAYS_OUTFIT_CONFIG"] = a.config
        if a.privacy:
            os.environ["TODAYS_OUTFIT_PRIVACY"] = a.privacy
        print(f"wardrobe: {a.wardrobe}")
        uvicorn.run("todays_outfit.api:app", host=a.host, port=a.port)
        return 0

    st = Stylist(cfg, a.wardrobe, a.cache)
    try:
        return _run(a, cfg, st)
    except ReadOnlyError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except NotFound as e:
        print(f"no such piece: {e.args[0]} (see `todays-outfit wardrobe`)", file=sys.stderr)
        return 1


def _run(a, cfg, st: Stylist) -> int:
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
        res = st.suggest(a.temp, a.rain, a.occasion, use_model=not a.rules_only, rotate=not a.no_rotation, season=a.season)
        if a.json:
            print(json.dumps({**res, "suggestions": [{"items": [i["id"] for i in s.items], "reason": s.reason, "note": s.note,
                                                      "source": s.source} for s in res["suggestions"]]}, ensure_ascii=False, indent=1))
        else:
            print(_fmt(res, a.temp, a.rain, a.occasion))
        return 0
    if a.cmd == "today":
        v = st.today_view(a.occasion, a.temp, a.rain if a.temp is not None else None, use_model=not a.rules_only, season=a.season)
        w = v["weather"]
        if v.get("needs_weather"):
            print(f"{w.get('error', 'No weather.')}\nSet a city once in config.toml ([weather] city = \"...\") or the web page, "
                  "or run: today --temp 15 [--rain]", file=sys.stderr)
            return 1
        print(f"{w['label']}  ->  occasion: {v['occasion']}, room: {v['season']}" + (f"  ({w['note']})" if w.get("note") else ""))
        if v["worn_today"]:
            print("You already logged today: " + " + ".join(i["name"] for i in v["worn_today"]["items"]))
        if v["warning"]:
            print(f"note: {v['warning']}")
        for n, sg in enumerate(v["suggestions"], 1):
            print(f"\n  {'Top pick' if n == 1 else f'Alternative {n - 1}'}: " + " + ".join(i["name"] for i in sg["items"]))
            print(f"    {sg['reason']}")
            if sg["note"]:
                print(f"    Rotation: {sg['note']}")
        if v["suggestions"]:
            ids = " ".join(i["id"] for i in v["suggestions"][0]["items"])
            print(f"\nWearing the top pick? todays-outfit wear {ids}")
        return 0
    if a.cmd == "season":
        if a.set:
            st.set_season(a.set)
        i = st.season_info()
        print(f"room: {i['current']}" + (f"  (you chose it; the date suggests {i['auto']})" if i["override"] else f"  (from the date, {i['hemisphere']} hemisphere)"))
        return 0
    if a.cmd == "wear":
        day = date.fromisoformat(a.date) if a.date else None
        if a.undo:
            print("removed" if st.unwear(day) else "nothing logged for that day")
            return 0
        if not a.items:
            print("give piece ids (see `todays-outfit wardrobe`), or --undo", file=sys.stderr)
            return 1
        e = st.wear(a.items, None, day)
        print(f"logged {e['date']}: " + ", ".join(e["items"]))
        return 0
    if a.cmd == "wardrobe":
        room = a.season or st.season_info()["current"]
        rows = sorted(st.wardrobe_view(room), key=lambda r: (-r["unworn_days"], r["name"]))
        print(f"{len(rows)} pieces in the {room} room ({len(st.described())} in all)" + ("  (read-only example wardrobe)" if st.readonly else ""))
        for r in rows:
            last = r["last_worn"] or "never"
            print(f"  {r['id']:<22} {r['category']:<9} {r['name']:<28} last worn {last:<10} worn {r['wear_count']}x"
                  + (f"   [{r['badge']}]" if r["badge"] else ""))
        return 0
    if a.cmd == "add":
        fields = {"category": a.category, "type": a.type, "color": a.color, "name": a.name}
        if a.no_describe and not a.category:
            print("--no-describe needs --category", file=sys.stderr)
            return 1
        bad = 0
        for ph in a.photos:
            try:
                it = st.add_photo_file(Path(ph), fields, describe=not a.no_describe)
                print(f"  added {it['id']}: {it['color']} {it['type']} ({it['category']}, warmth {it['warmth']}, formality {it['formality']})")
            except (ValueError, OSError) as e:
                bad += 1
                print(f"  FAILED {ph}: {e}", file=sys.stderr)
        print(f"{len(a.photos) - bad} added -> {st.path}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
