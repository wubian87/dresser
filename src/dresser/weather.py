"""Today's forecast from Open-Meteo (free, no API key): https://open-meteo.com/

Location is set once (a city name resolved with Open-Meteo's geocoding API, or lat/lon in config). With no location
nothing is fetched and the app asks for the temperature by hand. If the network is down the last cached forecast for
today is used, and if there is none the app falls back to manual input; it never raises into the UI.

What is sent to Open-Meteo: the city name typed in settings (geocoding) and the latitude/longitude (forecast).
No photos, no wardrobe. Under privacy mode `local-only` nothing is sent at all and weather stays manual.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
RAIN_THRESHOLD = 50          # precipitation probability (%) at or above which the day counts as "rain"
CACHE_TTL_S = 3 * 3600       # a cached forecast younger than this is used without asking the network


class WeatherError(RuntimeError):
    pass


@dataclass
class Location:
    name: str
    lat: float
    lon: float

    def key(self) -> str:
        return f"{self.lat:.3f},{self.lon:.3f}"


@dataclass
class Forecast:
    day: str                 # ISO date the forecast is for
    high: float
    low: float
    rain_prob: int | None    # max precipitation probability of the day, %
    precip_mm: float | None
    source: str = "open-meteo"
    fetched_at: float = 0.0
    from_cache: bool = False
    stale: bool = False      # served from cache because the network failed

    @property
    def temp(self) -> float:
        """The single temperature the rules dress for: midpoint of the day's low and high, rounded to 0.5."""
        return round((self.high + self.low) / 2 * 2) / 2

    @property
    def rain(self) -> bool:
        if self.rain_prob is not None:
            return self.rain_prob >= RAIN_THRESHOLD
        return (self.precip_mm or 0) >= 1.0

    def label(self, city: str) -> str:
        lo, hi = round(self.low), round(self.high)
        rng = f"{lo} °C" if lo == hi else f"{lo}-{hi} °C"
        rain = f", rain {self.rain_prob}%" if self.rain_prob is not None else (", rain" if self.rain else ", dry")
        return f"Today in {city}: {rng}{rain}"

    def to_dict(self) -> dict:
        return {"day": self.day, "high": self.high, "low": self.low, "rain_prob": self.rain_prob, "precip_mm": self.precip_mm,
                "fetched_at": self.fetched_at}


def make_client() -> httpx.Client:
    return httpx.Client(timeout=6.0, headers={"User-Agent": "dresser/0.2 (personal wardrobe app)"})


RETRY_DELAY_S = 1.5


def _get_json(client: httpx.Client, url: str, params: dict) -> dict:
    """One GET, with a single retry after a short pause on HTTP 429 (rate limit) or 5xx; network errors are not retried."""
    for attempt in (1, 2):
        try:
            r = client.get(url, params=params)
        except httpx.HTTPError as e:
            raise WeatherError(f"could not reach Open-Meteo ({type(e).__name__})") from None
        if attempt == 1 and (r.status_code == 429 or r.status_code >= 500):
            time.sleep(RETRY_DELAY_S)
            continue
        break
    if r.status_code != 200:
        raise WeatherError(f"Open-Meteo answered HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise WeatherError("Open-Meteo sent something that is not JSON") from None


def geocode(city: str, client: httpx.Client | None = None, count: int = 5) -> list[Location]:
    city = city.strip()
    if not city:
        raise WeatherError("empty city name")
    own = client is None
    client = client or make_client()
    try:
        data = _get_json(client, GEOCODE_URL, {"name": city, "count": count, "language": "en", "format": "json"})
    finally:
        if own:
            client.close()
    out = []
    for r in data.get("results") or []:
        try:
            label = ", ".join(x for x in (r["name"], r.get("admin1"), r.get("country")) if x)
            out.append(Location(label, float(r["latitude"]), float(r["longitude"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def parse_forecast(data: dict) -> Forecast:
    try:
        d = data["daily"]
        hi, lo = d["temperature_2m_max"][0], d["temperature_2m_min"][0]
        if hi is None or lo is None:
            raise WeatherError("forecast has no temperatures")
        prob = d.get("precipitation_probability_max", [None])[0]
        mm = d.get("precipitation_sum", [None])[0]
        return Forecast(day=d["time"][0], high=float(hi), low=float(lo),
                        rain_prob=None if prob is None else int(round(prob)),
                        precip_mm=None if mm is None else float(mm), fetched_at=time.time())
    except (KeyError, IndexError, TypeError, ValueError):
        raise WeatherError("unexpected forecast format") from None


def fetch_forecast(loc: Location, client: httpx.Client | None = None) -> Forecast:
    own = client is None
    client = client or make_client()
    try:
        data = _get_json(client, FORECAST_URL, {
            "latitude": loc.lat, "longitude": loc.lon, "timezone": "auto", "forecast_days": 1,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum"})
    finally:
        if own:
            client.close()
    return parse_forecast(data)


class WeatherService:
    """Forecast with an on-disk cache (one entry per location, replaced daily)."""

    def __init__(self, cache_path=None, client_factory=None):
        self.cache_path = Path(cache_path) if cache_path else None
        self.client_factory = client_factory or make_client

    def _read(self) -> dict:
        if self.cache_path and self.cache_path.is_file():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {}

    def _write(self, data: dict) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.replace(tmp, self.cache_path)

    def today(self, loc: Location, day: date | None = None, refresh: bool = False) -> Forecast:
        """Forecast for `day` (default: today). Raises WeatherError only if neither network nor cache can answer."""
        day = day or date.today()
        cache = self._read()
        hit = cache.get(loc.key())
        cached: Forecast | None = None
        if hit and hit.get("day") == day.isoformat():
            try:
                cached = Forecast(day=hit["day"], high=hit["high"], low=hit["low"], rain_prob=hit.get("rain_prob"),
                                  precip_mm=hit.get("precip_mm"), fetched_at=hit.get("fetched_at", 0.0), from_cache=True)
            except KeyError:
                cached = None
        if cached and not refresh and time.time() - cached.fetched_at < CACHE_TTL_S:
            return cached
        client = self.client_factory()
        try:
            fc = fetch_forecast(loc, client)
        except WeatherError:
            if cached:
                cached.stale = True
                return cached
            raise
        finally:
            client.close()
        if fc.day == day.isoformat():
            cache[loc.key()] = fc.to_dict()
            self._write(cache)
        return fc


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")
