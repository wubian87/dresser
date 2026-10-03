import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def items():
    """Sample wardrobe with the hand-written ground truth as descriptions (no network needed)."""
    gt = json.loads((ROOT / "sample_wardrobe/ground_truth.json").read_text())
    return [dict(id=k, category=v["cat"], type=v["type"], color=v["color"], material=v["material"],
                 warmth=v["warmth"], formality=v["formality"], notes="", name=f"{v['color']} {v['type']}")
            for k, v in gt.items()]


# ---- helpers for the wardrobe / history / weather / web tests (no network anywhere) ----
import io
from datetime import date

import httpx
from PIL import Image

from todays_outfit import weather as wx
from todays_outfit.config import load_config
from todays_outfit.demo import init_demo
from todays_outfit.service import Stylist

TODAY = date(2026, 10, 3)


class FakeText:
    """Stands in for the text model. `answer=None` -> unusable output -> the app must fall back to rules."""
    last_latency = 0.1

    def __init__(self, answer=None):
        self.answer, self.prompts = answer, []

    def chat(self, messages, **k):
        self.prompts.append(messages[0]["content"])
        return self.answer or "no json here"


class FakeVision:
    def __init__(self, desc=None):
        self.desc = desc or {"category": "top", "type": "t-shirt", "color": "red", "material": "cotton", "warmth": 2,
                             "formality": 2, "season": ["summer"], "notes": "fake"}
        self.calls = 0
        self.ep = type("E", (), {"model": "fake-vision", "base_url": "http://localhost/v1"})()

    def chat(self, messages, **k):
        import json
        self.calls += 1
        return json.dumps(self.desc)


def photo_bytes(color="red", size=(60, 80), fmt="PNG", exif_orientation=None):
    im = Image.new("RGB", size, color)
    buf = io.BytesIO()
    if exif_orientation:
        ex = Image.Exif()
        ex[0x0112] = exif_orientation
        im.save(buf, "JPEG", exif=ex)
    else:
        im.save(buf, fmt)
    return buf.getvalue()


def forecast_json(hi=18.0, lo=13.0, prob=70, mm=3.2, day="2026-10-03"):
    return {"daily": {"time": [day], "temperature_2m_max": [hi], "temperature_2m_min": [lo],
                      "precipitation_probability_max": [prob], "precipitation_sum": [mm]}}


class MockWeather:
    """httpx.MockTransport that counts calls and can be switched offline."""

    def __init__(self, forecast=None):
        self.forecast = forecast or forecast_json()
        self.calls, self.offline = [], False

    def handler(self, request: httpx.Request):
        self.calls.append(str(request.url))
        if self.offline:
            raise httpx.ConnectError("down")
        if "geocoding" in request.url.host:
            return httpx.Response(200, json={"results": [
                {"name": "Hangzhou", "admin1": "Zhejiang", "country": "China", "latitude": 30.29, "longitude": 120.16}]})
        return httpx.Response(200, json=self.forecast)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def make_stylist(tmp_path, mock: MockWeather | None = None, text=None, vision=None, demo=True, cfg=None):
    cfg = cfg or load_config(ROOT / "config.example.toml")
    cache = tmp_path / "cache" / "descriptions.json"
    if demo:
        path = init_demo(tmp_path / "data", cfg, cache, today=TODAY, with_location=False)   # tests choose their own weather
    else:
        from todays_outfit.wardrobe import save_wardrobe
        path = tmp_path / "data" / "wardrobe.json"
        path.parent.mkdir(parents=True)
        save_wardrobe(path, [])
    mock = mock or MockWeather()
    svc = wx.WeatherService(tmp_path / "data" / "weather_cache.json", client_factory=mock.client)
    st = Stylist(cfg, path, cache, today=lambda: TODAY, weather=svc)
    st.text = text or FakeText()
    st.vision = vision or FakeVision()
    st.mock = mock
    return st
