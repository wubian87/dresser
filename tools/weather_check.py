"""Compare the app's forecast numbers with a plain HTTP request to the same Open-Meteo URL (no key, needs network).

    python tools/weather_check.py "Shanghai" > docs/weather_check.md
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from todays_outfit import weather as wx  # noqa: E402


def main(city: str) -> None:
    now = datetime.now().astimezone()
    with tempfile.TemporaryDirectory() as d:
        svc = wx.WeatherService(Path(d) / "w.json")
        loc = wx.geocode(city)[0]
        fc = svc.today(loc, now.date(), refresh=True)
    params = {"latitude": loc.lat, "longitude": loc.lon, "timezone": "auto", "forecast_days": 1,
              "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum"}
    raw = httpx.get(wx.FORECAST_URL, params=params, timeout=15).json()
    daily = raw["daily"]
    same = (daily["time"][0] == fc.day and daily["temperature_2m_max"][0] == fc.high and daily["temperature_2m_min"][0] == fc.low
            and daily["precipitation_probability_max"][0] == fc.rain_prob)
    print(f"# Open-Meteo check: the app's numbers vs a plain request to the same URL\n")
    print(f"Run at {now:%Y-%m-%d %H:%M} (local time of the machine, UTC{now:%z}); city searched: `{city}` -> {loc.name} ({loc.lat}, {loc.lon}).\n")
    print("Plain request (`httpx.get`, same URL and parameters, no app code), `daily` part:\n\n```json\n" + json.dumps(daily) + "\n```\n")
    print(f"The app (`WeatherService.today`, cache bypassed): day {fc.day}, high {fc.high}, low {fc.low}, rain probability {fc.rain_prob}%.\n")
    print(f"Label shown by the app: `{fc.label(loc.name.split(',')[0])}`; temperature the rules dress for (midpoint, rounded to 0.5): {fc.temp} °C; rain = {fc.rain}.\n")
    print(f"**Same numbers: {'yes' if same else 'NO'}.** (Two requests a moment apart; the forecast can change between them.)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Shanghai")
