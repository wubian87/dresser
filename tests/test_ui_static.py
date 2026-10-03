"""The page is one static file; these checks pin the structure the redesign promised (not a browser test)."""
import json
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "src/todays_outfit/static/index.html").read_text(encoding="utf-8")


def test_three_tabs_and_single_column():
    tabs = re.findall(r'<button data-tab="(\w+)">', HTML)
    assert tabs == ["today", "wardrobe", "settings"]
    assert "max-width:560px" in HTML and "@media (prefers-color-scheme:dark)" in HTML


def test_technical_info_is_not_on_the_main_screens():
    today_js = HTML[HTML.index("function renderToday"):HTML.index("function bindToday")]
    for word in ("privacy", "endpoint", "pieces_ready", "cached", "base_url", "vision_model"):
        assert word not in today_js.lower().replace("details", ""), word
    assert "<summary>Details</summary>" in today_js
    assert "Privacy mode" in HTML[HTML.index("async function renderSettings"):]       # ... but Settings has it


def test_add_sheet_offers_photos_and_paste_a_link():
    assert "Paste a link" in HTML and "/api/import-link" in HTML and "Upload a picture instead" in HTML


def test_all_api_routes_used_by_the_page_exist():
    from todays_outfit.api import app
    routes = {r.path for r in app.routes}
    for used in set(re.findall(r'["`](/api/[a-z\-/]+)', HTML)):
        assert used.rstrip("/") in routes or any(r.startswith(used.rstrip("/")) for r in routes), used


def test_page_and_command_line_round_the_temperature_the_same_way(tmp_path):
    """A forecast low of 18.5 is printed 18 by the CLI label (Python rounds half to even); the page must show the same."""
    from conftest import MockWeather, forecast_json, make_stylist
    st = make_stylist(tmp_path, mock=MockWeather(forecast_json(hi=22.8, lo=18.5, prob=98)))
    st.set_location(__import__("todays_outfit.weather", fromlist=["Location"]).Location("Shanghai, China", 31.2, 121.5))
    w = st.weather_info()
    assert w["label"] == "Today in Shanghai: 18-23 °C, rain 98%" and (w["low_r"], w["high_r"]) == (18, 23)
    assert "w.low_r ??" in HTML and "w.high_r ??" in HTML


def test_link_import_closes_keyboard_and_drops_old_failures():
    """Found on a real phone: the on-screen keyboard hid the result, and old failed cards piled up under a new one."""
    html = (Path(__file__).resolve().parent.parent / "src" / "todays_outfit" / "static" / "index.html").read_text(encoding="utf-8")
    assert '$("#url").blur()' in html
    assert '.draft.failed' in html and 'classList.add("failed")' in html


def test_add_sheet_text_follows_the_real_mode_not_the_config():
    """No vision key -> the page must not claim a photo is read by the cloud model."""
    assert '"nokey"' in HTML and "No vision key is set" in HTML
    assert 'd.vision_key_ready === false' in HTML


def test_touch_targets_are_at_least_40px_high():
    for rule in (".occ button{", ".pill{", "details.more summary{", ".filters summary{"):
        css = HTML[HTML.index(rule):].split("}")[0]
        assert "min-height:40px" in css, rule


def test_index_is_served_with_no_cache_and_status_reports_key_state(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from todays_outfit import api
    from conftest import make_stylist
    st = make_stylist(tmp_path)
    monkeypatch.delenv(st.cfg.vision.api_key_env, raising=False)
    assert st.settings_view()["details"]["vision_key_ready"] is False
    monkeypatch.setenv(st.cfg.vision.api_key_env, "not-a-real-key-4711")
    assert st.settings_view()["details"]["vision_key_ready"] is True
    assert "4711" not in json.dumps(st.settings_view())      # the value is never exposed
    r = TestClient(api.app).get("/")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
