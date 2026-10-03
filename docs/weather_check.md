# Open-Meteo check: the app's numbers vs a plain request to the same URL

Run at 2026-10-04 00:17 (local time of the machine, UTC+0800); city searched: `Shanghai` -> Shanghai, Shanghai Municipality, China (31.22222, 121.45806).

Plain request (`httpx.get`, same URL and parameters, no app code), `daily` part:

```json
{"time": ["2026-10-04"], "temperature_2m_max": [22.1], "temperature_2m_min": [18.7], "precipitation_probability_max": [100], "precipitation_sum": [27.8]}
```

The app (`WeatherService.today`, cache bypassed): day 2026-10-04, high 22.1, low 18.7, rain probability 100%.

Label shown by the app: `Today in Shanghai: 19-22 °C, rain 100%`; temperature the rules dress for (midpoint, rounded to 0.5): 20.5 °C; rain = True.

**Same numbers: yes.** (Two requests a moment apart; the forecast can change between them.)

Same URL with `curl` (run right after):

```
{"time": ["2026-10-04"], "temperature_2m_max": [22.1], "temperature_2m_min": [18.7], "precipitation_probability_max": [100], "precipitation_sum": [27.8]}
```
