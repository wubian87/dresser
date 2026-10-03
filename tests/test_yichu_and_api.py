import sqlite3

from fastapi.testclient import TestClient
from PIL import Image

from todays_outfit import api
from todays_outfit.sources.yichu import import_yichu


def test_import_yichu_synthetic_db(tmp_path):
    up = tmp_path / "uploads"
    up.mkdir()
    Image.new("RGB", (8, 8), "red").save(up / "a.png")
    db = tmp_path / "db.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table items (id integer primary key, name text, image_path text, category text)")
    con.executemany("insert into items values (?,?,?,?)", [(1, "Red tee", "a.png", "top"), (2, "No photo", None, "top"),
                                                           (3, "Missing file", "zzz.png", "top")])
    con.commit()
    con.close()
    out = tmp_path / "w" / "wardrobe.json"
    assert import_yichu(str(db), str(up), str(out), extra_cols={"category": "category"}) == 1
    import json
    it = json.loads(out.read_text())["items"][0]
    assert it["id"] == "1" and it["name"] == "Red tee" and it["category"] == "top"


def test_import_rejects_sql_injection_identifiers(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        import_yichu("x", "y", "z", table="items; drop table items")


def test_web_api_rules_fallback(tmp_path):
    """API works end to end with a model that always fails: rules-only fallback, never a 500."""
    from conftest import make_stylist
    api._state["s"] = make_stylist(tmp_path)          # text model returns garbage -> rules fallback
    try:
        c = TestClient(api.app)
        assert c.get("/api/status").json()["occasions"] == ["commute", "casual", "date", "formal"]
        r = c.post("/api/suggest", json={"temp": 14, "rain": True, "occasion": "commute"})
        assert r.status_code == 200 and r.json()["mode"] == "rules" and r.json()["suggestions"]
        assert c.post("/api/suggest", json={"temp": 14, "rain": True, "occasion": "beach"}).status_code == 422
        assert c.get("/").status_code == 200
    finally:
        api._state.clear()
