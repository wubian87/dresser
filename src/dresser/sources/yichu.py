"""Bring your own wardrobe: import from a "yichu"-style wardrobe app (FastAPI + SQLite + uploads folder).

"yichu" is the author's own self-hosted wardrobe app. This adapter is deliberately small and
schema-agnostic: you tell it the table and column names, it copies the rows into a wardrobe.json
that the rest of Dresser understands. Photos are *referenced*, never uploaded anywhere.

    python -m dresser import-yichu --db /path/db.sqlite --uploads /path/uploads \
        --table items --image-col image_path --name-col name --out my_wardrobe/wardrobe.json

NOTE: the defaults below are guesses; they were NOT verified against a real yichu database
(no private data was touched while building this project). The importer is tested with a
synthetic SQLite file in tests/test_yichu.py. Override the column names to fit your database.
Everything is opened read-only.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def import_yichu(db: str, uploads: str, out: str, table: str = "items", image_col: str = "image_path",
                 name_col: str = "name", id_col: str = "id", extra_cols: dict[str, str] | None = None) -> int:
    """Write `out` (wardrobe.json) and return the number of items. `extra_cols` maps wardrobe field -> db column
    for optional manual overrides, e.g. {"category": "category", "warmth": "warmth"}."""
    for ident in [table, image_col, name_col, id_col, *(extra_cols or {}).values()]:
        if not ident.replace("_", "").isalnum():
            raise ValueError(f"suspicious SQL identifier: {ident!r}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cols = [id_col, image_col, name_col, *(extra_cols or {}).values()]
    rows = con.execute(f"SELECT {', '.join(dict.fromkeys(cols))} FROM {table}").fetchall()
    con.close()
    out_p = Path(out).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    items = []
    for r in rows:
        img = r[image_col]
        if not img:
            continue
        src = Path(img) if Path(img).is_absolute() else Path(uploads) / img
        if not src.is_file():
            continue
        it = {"id": str(r[id_col]), "name": r[name_col] or str(r[id_col]), "image": str(src.resolve())}
        for field, col in (extra_cols or {}).items():
            if r[col] not in (None, ""):
                it[field] = r[col]
        items.append(it)
    out_p.write_text(json.dumps({"items": items}, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(items)
