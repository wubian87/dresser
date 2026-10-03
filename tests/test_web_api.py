import pytest
from fastapi.testclient import TestClient

from conftest import FakeText, TODAY, make_stylist, photo_bytes
from dresser import api


@pytest.fixture
def client(tmp_path):
    st = make_stylist(tmp_path)
    api._state["s"] = st
    yield TestClient(api.app), st
    api._state.clear()


def test_today_needs_weather_then_city_then_auto(client):
    c, st = client
    v = c.get("/api/today").json()
    assert v["needs_weather"] and v["suggestions"] == [] and v["occasion"] == "casual"
    found = c.get("/api/geocode", params={"q": "Hangzhou"}).json()
    assert found[0]["name"].startswith("Hangzhou")
    assert c.put("/api/settings/location", json=found[0]).status_code == 200
    v = c.get("/api/today", params={"occasion": "commute"}).json()
    assert v["weather"]["source"] == "auto" and v["weather"]["label"] == "Today in Hangzhou: 13-18 °C, rain 70%"
    assert v["suggestions"] and v["suggestions"][0]["items"][0]["thumb"].startswith("/thumb/")
    # last-used occasion is remembered
    assert c.get("/api/settings").json()["occasion"] == "commute"
    assert c.get("/api/today").json()["occasion"] == "commute"
    assert c.delete("/api/settings/location").status_code == 200
    assert c.get("/api/today").json()["needs_weather"]


def test_wear_this_is_one_tap_and_shows_in_wardrobe(client):
    c, st = client
    v = c.get("/api/today", params={"temp": 15, "rain": "true", "occasion": "commute"}).json()
    ids = [i["id"] for i in v["suggestions"][0]["items"]]
    assert c.post("/api/wear", json={"items": ids, "occasion": "commute"}).status_code == 200
    w = {m["id"]: m for m in c.get("/api/wardrobe").json()}
    assert all(w[i]["last_worn"] == TODAY.isoformat() and w[i]["days_since"] == 0 for i in ids)
    again = c.get("/api/today", params={"temp": 15, "rain": "true", "occasion": "commute"}).json()
    assert again["worn_today"]["items"] and again["suggestions"] == []         # already logged: no new outfit computed
    forced = c.get("/api/today", params={"temp": 15, "rain": "true", "occasion": "commute", "force": "true"}).json()
    assert forced["suggestions"] and not {i["id"] for i in forced["suggestions"][0]["items"]} & set(ids)   # no repeat of today's pieces
    assert c.delete("/api/wear").json()["ok"] is True
    assert c.get("/api/today", params={"temp": 15, "occasion": "commute"}).json()["worn_today"] is None


def test_show_another_stores_skip_and_demotes_that_combo(client):
    c, st = client
    q = {"temp": 15, "rain": "false", "occasion": "commute"}
    first = c.get("/api/today", params=q).json()["suggestions"][0]
    ids = [i["id"] for i in first["items"]]
    assert c.post("/api/skip", json={"items": ids, "occasion": "commute"}).status_code == 200
    assert st.history.skips[-1]["items"] == sorted(ids)
    after = c.get("/api/today", params=q).json()["suggestions"]
    assert all(sorted(i["id"] for i in s["items"]) != sorted(ids) for s in after)


def test_wear_unknown_piece_and_bad_date(client):
    c, _ = client
    assert c.post("/api/wear", json={"items": ["ghost"]}).status_code == 404
    assert c.post("/api/wear", json={"items": ["white-tee"], "date": "yesterday"}).status_code == 422
    assert c.post("/api/wear", json={"items": []}).status_code == 422
    assert c.post("/api/wear", json={"items": ["white-tee"], "date": "2026-10-01"}).status_code == 200


def test_upload_review_save_edit_delete_over_http(client):
    c, st = client
    r = c.post("/api/upload", content=photo_bytes("red"), headers={"Content-Type": "image/png"})
    assert r.status_code == 200
    up = r.json()
    assert up["fields"]["type"] == "t-shirt" and up["describe_error"] is None
    assert c.get(f"/staged/{up['staging_id']}").status_code == 200
    r = c.post("/api/items", json={"staging_id": up["staging_id"], "fields": {**up["fields"], "name": "Red tee", "warmth": 1}})
    assert r.status_code == 200
    iid = r.json()["id"]
    w = {m["id"]: m for m in c.get("/api/wardrobe").json()}
    assert w[iid]["name"] == "Red tee" and w[iid]["warmth"] == 1 and w[iid]["wear_count"] == 0
    assert c.get(f"/thumb/{iid}").status_code == 200 and c.get(f"/images/{iid}").status_code == 200
    assert c.put(f"/api/items/{iid}", json={**up["fields"], "name": "Crimson tee", "color": "crimson"}).status_code == 200
    assert {m["id"]: m for m in c.get("/api/wardrobe").json()}[iid]["name"] == "Crimson tee"
    assert c.delete(f"/api/items/{iid}").status_code == 200
    assert iid not in {m["id"] for m in c.get("/api/wardrobe").json()}
    assert c.delete(f"/api/items/{iid}").status_code == 404


def test_upload_rejects_garbage_and_discard_works(client):
    c, st = client
    assert c.post("/api/upload", content=b"hello").status_code == 422
    assert c.post("/api/upload", content=b"").status_code == 422
    up = c.post("/api/upload?describe=false", content=photo_bytes()).json()
    assert up["describe_error"] and up["fields"]["type"] == ""
    assert c.delete(f"/api/staged/{up['staging_id']}").status_code == 200
    assert c.get(f"/staged/{up['staging_id']}").status_code == 404
    assert c.post("/api/items", json={"staging_id": up["staging_id"], "fields": up["fields"]}).status_code == 404


def test_readonly_example_returns_403(tmp_path):
    from conftest import ROOT
    from dresser.config import load_config
    from dresser.service import Stylist
    api._state["s"] = Stylist(load_config(ROOT / "config.example.toml"), ROOT / "sample_wardrobe" / "wardrobe.json",
                              tmp_path / "c.json")
    try:
        c = TestClient(api.app)
        assert c.get("/api/status").json()["readonly"] is True
        r = c.post("/api/wear", json={"items": ["white-tee"]})
        assert r.status_code == 403 and "read-only" in r.json()["detail"]
        assert c.get("/api/wardrobe").status_code == 200
    finally:
        api._state.clear()


def test_today_with_model_answer_includes_computed_note(tmp_path):
    st = make_stylist(tmp_path, text=FakeText('{"outfits":[{"candidate":0,"reason":"Easy, light layers."}]}'))
    api._state["s"] = st
    try:
        v = TestClient(api.app).get("/api/today", params={"temp": 15, "rain": "false", "occasion": "commute"}).json()
        s = v["suggestions"][0]
        assert v["mode"] == "model" and s["reason"] == "Easy, light layers." and s["source"] == "model"
        assert s["note"] and "Easy" not in s["note"]                  # note comes from the history, not the model
        assert [x["source"] for x in v["suggestions"]] == ["model", "rules", "rules"]
    finally:
        api._state.clear()
