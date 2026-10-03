import json
import time
from datetime import date

import pytest

from conftest import ROOT, MockWeather, TODAY, forecast_json, make_stylist
from dresser import weather as wx
from dresser.config import load_config

SH = wx.Location("Shanghai, China", 31.22, 121.46)


def test_parse_and_label():
    fc = wx.parse_forecast(forecast_json(18.4, 12.6, 70))
    assert (fc.high, fc.low, fc.rain_prob, fc.rain) == (18.4, 12.6, 70, True)
    assert fc.temp == 15.5                       # midpoint of low and high, rounded to 0.5
    assert fc.label("Hangzhou") == "Today in Hangzhou: 13-18 °C, rain 70%"


def test_rain_threshold_and_fallback_to_precip_sum():
    assert not wx.parse_forecast(forecast_json(prob=49)).rain and wx.parse_forecast(forecast_json(prob=50)).rain
    f = forecast_json(prob=None, mm=2.0)
    assert wx.parse_forecast(f).rain and wx.parse_forecast(forecast_json(prob=None, mm=0.2)).rain is False


def test_bad_payloads_raise_weathererror():
    for bad in ({}, {"daily": {}}, {"daily": {"time": ["x"], "temperature_2m_max": [None], "temperature_2m_min": [1]}}):
        with pytest.raises(wx.WeatherError):
            wx.parse_forecast(bad)


def test_geocode_with_mocked_http():
    m = MockWeather()
    res = wx.geocode("Hangzhou", m.client())
    assert res[0].name == "Hangzhou, Zhejiang, China" and res[0].lat == 30.29
    assert "name=Hangzhou" in m.calls[0] and "geocoding-api.open-meteo.com" in m.calls[0]


def test_forecast_request_shape():
    m = MockWeather()
    wx.fetch_forecast(SH, m.client())
    url = m.calls[0]
    assert "api.open-meteo.com/v1/forecast" in url and "latitude=31.22" in url
    assert "precipitation_probability_max" in url and "temperature_2m_max" in url and "forecast_days=1" in url
    assert "apikey" not in url.lower() and "key=" not in url.lower()          # no key involved


def test_cache_avoids_second_request_and_survives_restart(tmp_path):
    m = MockWeather()
    svc = wx.WeatherService(tmp_path / "w.json", client_factory=m.client)
    a = svc.today(SH, TODAY)
    b = wx.WeatherService(tmp_path / "w.json", client_factory=m.client).today(SH, TODAY)   # new process, same file
    assert len(m.calls) == 1 and not a.from_cache and b.from_cache and b.high == a.high


def test_old_cache_is_refreshed_and_refresh_flag_forces(tmp_path):
    m = MockWeather()
    svc = wx.WeatherService(tmp_path / "w.json", client_factory=m.client)
    svc.today(SH, TODAY)
    data = json.loads((tmp_path / "w.json").read_text())
    data[SH.key()]["fetched_at"] = time.time() - 5 * 3600
    (tmp_path / "w.json").write_text(json.dumps(data))
    svc.today(SH, TODAY)
    assert len(m.calls) == 2
    svc.today(SH, TODAY, refresh=True)
    assert len(m.calls) == 3


def test_offline_uses_stale_cache_then_fails_cleanly(tmp_path):
    m = MockWeather()
    svc = wx.WeatherService(tmp_path / "w.json", client_factory=m.client)
    svc.today(SH, TODAY)
    m.offline = True
    fc = svc.today(SH, TODAY, refresh=True)
    assert fc.stale and fc.from_cache
    with pytest.raises(wx.WeatherError):
        wx.WeatherService(tmp_path / "other.json", client_factory=m.client).today(SH, TODAY)


def test_http_error_status_is_weathererror(monkeypatch):
    monkeypatch.setattr(wx, "RETRY_DELAY_S", 0)
    import httpx
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="oops")))
    with pytest.raises(wx.WeatherError):
        wx.fetch_forecast(SH, c)


# ---- through the Stylist (what the web page and `today` use) ----
def test_no_location_means_manual(tmp_path):
    st = make_stylist(tmp_path)
    info = st.weather_info()
    assert info["source"] == "none" and "No location" in info["error"] and st.mock.calls == []


def test_auto_weather_drives_today(tmp_path):
    st = make_stylist(tmp_path)
    st.set_location(wx.Location("Shanghai, China", 31.22, 121.46))
    v = st.today_view("commute", use_model=False)
    assert v["weather"]["source"] == "auto" and v["weather"]["label"] == "Today in Shanghai: 13-18 °C, rain 70%"
    assert v["weather"]["temp"] == 15.5 and v["weather"]["rain"] is True
    assert v["suggestions"]
    # rain => no rain-sensitive shoes among the suggestions
    for s in v["suggestions"]:
        assert not {i["id"] for i in s["items"]} & {"tan-suede-loafers", "white-sneakers"}


def test_manual_override_wins_and_keeps_forecast_visible(tmp_path):
    st = make_stylist(tmp_path)
    st.set_location(wx.Location("Shanghai, China", 31.22, 121.46))
    v = st.today_view("commute", temp=27, rain=False, use_model=False)
    assert v["weather"]["source"] == "manual" and v["weather"]["temp"] == 27
    assert v["weather"]["forecast_label"].startswith("Today in Shanghai")


def test_offline_without_cache_falls_back_to_manual(tmp_path):
    m = MockWeather()
    m.offline = True
    st = make_stylist(tmp_path, mock=m)
    st.set_location(wx.Location("Shanghai, China", 31.22, 121.46))
    v = st.today_view("commute", use_model=False)
    assert v["needs_weather"] and v["weather"]["source"] == "none" and "by hand" in v["weather"]["error"]
    assert v["suggestions"] == []
    assert st.today_view("commute", temp=14, rain=True, use_model=False)["suggestions"]   # manual still works


def test_offline_with_cache_says_so(tmp_path):
    st = make_stylist(tmp_path)
    st.set_location(wx.Location("Shanghai, China", 31.22, 121.46))
    st.weather_info()
    st.mock.offline = True
    info = st.weather_info(refresh=True)
    assert info["source"] == "auto" and "Offline" in info["note"]


def test_local_only_privacy_never_calls_open_meteo(tmp_path):
    cfg = load_config(ROOT / "config.example.toml", "local-only")
    st = make_stylist(tmp_path, cfg=cfg)
    st.set_location(wx.Location("Shanghai, China", 31.22, 121.46))
    info = st.weather_info()
    assert info["source"] == "none" and "local-only" in info["error"] and st.mock.calls == []
    with pytest.raises(wx.WeatherError):
        st.search_city("Hangzhou")
    assert st.mock.calls == []


def test_config_lat_lon_and_city_once(tmp_path):
    cfg = load_config(ROOT / "config.example.toml")
    cfg.weather = {"lat": 30.29, "lon": 120.16, "name": "Hangzhou"}
    st = make_stylist(tmp_path, cfg=cfg)
    assert st.weather_info()["label"].startswith("Today in Hangzhou")
    cfg2 = load_config(ROOT / "config.example.toml")
    cfg2.weather = {"city": "Hangzhou"}
    st2 = make_stylist(tmp_path / "b", cfg=cfg2)
    assert st2.weather_info()["source"] == "auto"
    assert st2.location().name == "Hangzhou, Zhejiang, China"            # resolved once, then remembered
    n = len(st2.mock.calls)
    st2.weather_info()
    assert not any("geocoding" in c for c in st2.mock.calls[n:])


def test_one_retry_on_rate_limit(monkeypatch):
    import httpx
    monkeypatch.setattr(wx, "RETRY_DELAY_S", 0)
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, text="slow down") if len(calls) == 1 else httpx.Response(200, json=forecast_json())

    fc = wx.fetch_forecast(SH, httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(calls) == 2 and fc.high == 18.0
    calls.clear()
    always = httpx.Client(transport=httpx.MockTransport(lambda r: (calls.append(1), httpx.Response(429))[1]))
    with pytest.raises(wx.WeatherError, match="429"):
        wx.fetch_forecast(SH, always)
    assert len(calls) == 2
