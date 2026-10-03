# Today's Outfit

**Tell it the weather and where you're going. It builds an outfit from the clothes you already own, and says why.**

A real run on the bundled example wardrobe (12 °C, raining, commute):

```
$ todays-outfit suggest --temp 12 --rain --occasion commute

  Outfit 1: gray sweater + black trousers + yellow rain boots
    The warm gray wool knit sweater pairs perfectly with black trousers for a cozy, professional
    commute. Yellow rain boots keep feet dry in the rain while adding a cheerful pop of color.

  Outfit 2: light blue button-down shirt + black trousers + beige blazer + brown ankle boots
    ...Brown ankle boots offer superior warmth and stability for wet, chilly commuting conditions.

  Outfit 3: navy blue maxi dress + black blazer + yellow rain boots
    ...Yellow rain boots provide essential waterproof protection against the rain...
```

(Full output of four scenarios: [`docs/examples.txt`](docs/examples.txt). Phone-sized screenshots: [`docs/screenshot_rainy_commute.png`](docs/screenshot_rainy_commute.png), [`docs/screenshot_warm_date.png`](docs/screenshot_warm_date.png). Suede and canvas shoes are filtered out on rainy days by a hard rule before the model sees anything.)

## Who it's for

I built it for my wife, from the wardrobe she already has. It is not a shopping app and it never suggests buying anything. You photograph your clothes once, a vision model describes each piece, and from then on a morning question ("12 degrees, rain, I have to be at the office") gets 1-3 complete outfits. Anyone with a closet and an OpenAI-compatible endpoint can use it.

## What she said

> **TODO (owner fills in after she tries it): her actual words, good and bad. Left blank on purpose; nothing here is invented.**

## Verify it in one command

```bash
git clone <TODO repo url> && cd wardrobe-stylist
./demo.sh        # or: make demo
```

This installs into a local `.venv`, runs the tests, and prints two outfit suggestions from the **bundled example wardrobe** (21 synthetic illustrations in `sample_wardrobe/`, with the vision model's real descriptions already cached). It works **offline and without an API key**: with no key the app falls back to the deterministic rules and says so. To see the language model's picks too:

```bash
export SILICONFLOW_API_KEY=...        # your own key; the app only ever reads this variable
./demo.sh                              # now the reasons are written by an open-weight model
python -m todays_outfit serve          # web page on http://127.0.0.1:8000 (works on a phone on your LAN with --host 0.0.0.0)
```

## Cloud or local: one line

All model calls go through one OpenAI-compatible client. Copy `config.example.toml` to `config.toml`:

```toml
[llm]
preset = "siliconflow"   # cloud: open-weight Qwen models via SiliconFlow, key read from $SILICONFLOW_API_KEY
# preset = "local"       # Ollama / llama.cpp at http://localhost:11434/v1, no key at all
privacy = "off"          # "off" | "images-local" | "local-only"
```

| Preset | Endpoint | Key | Status in this repo |
|---|---|---|---|
| `siliconflow` | `https://api.siliconflow.cn/v1` | env var `SILICONFLOW_API_KEY` (the config stores only the *name*) | **Tested** end to end |
| `local` | `http://localhost:11434/v1` | none | **Not tested end to end**: no local runtime was available when I built this. The client, the privacy guard and the config switch are unit-tested; I have not measured a local vision model. |

You can mix: e.g. `[vision] preset = "local"` to read photos on your own machine and keep the cloud for the text-only styling step. Any other OpenAI-compatible server works by setting `base_url`, `model` and `api_key_env` in `[vision]` / `[text]`.

### Privacy mode

`--privacy images-local` refuses to send any photo to a non-localhost endpoint. `--privacy local-only` refuses to call any non-localhost endpoint at all (styling then falls back to rules). The check runs before the HTTP request is made; see `tests/test_privacy_config.py` and [`docs/privacy_demo.txt`](docs/privacy_demo.txt) for a real refusal. What goes to the cloud in the default mode: a 512-px JPEG of each photo (once, then cached) and, per question, a text list of rule-approved outfits plus the weather. The API key is read from the environment per request and is never logged or stored.

## How it works (short)

1. **describe**: a vision model turns each photo into JSON (category, type, colour, material, warmth 1-5, formality 1-5, season, notes). Cached by image hash + model in `cache/descriptions.json`. You can override any field per item in `wardrobe.json`.
2. **filter** (no AI): weather maps to a warmth target; rain removes rain-sensitive shoes; the occasion bounds formality; every outfit is top+bottom or dress, plus shoes, plus an optional outer layer. If a small wardrobe leaves nothing, constraints are relaxed in steps and the result is flagged "loosest match".
3. **style**: a text model picks the best 1-3 of those candidates and writes the reason. Its answer must be valid JSON, point at real candidates, and mention only garments that are in that outfit; otherwise that pick is dropped, and if nothing survives the app falls back to the rule-based ranking. The app never breaks because a model had a bad day.

## Models I measured

Everything below was measured on my run on **2026-10-03 (Beijing time)** against SiliconFlow, on the 21 bundled illustrations, one request at a time. Ground truth is what I drew (`sample_wardrobe/ground_truth.json`). Reproduce with `python tools/eval_describe.py` and `tools/eval_style.py` (needs a key); raw data in [`docs/`](docs/).

**Vision (photo → JSON), 21 photos each**

| Model | median s / photo | p90 s | category | type | colour | warmth ±1 | formality ±1 |
|---|---|---|---|---|---|---|---|
| Qwen/Qwen3-VL-8B-Instruct | 3.1 | 4.0 | 81% | 76% | 90% | 67% | 86% |
| **Qwen/Qwen3-VL-30B-A3B-Instruct** (default) | 4.4 | 5.0 | 90% | 81% | 100% | 100% | 90% |
| Qwen/Qwen3-VL-32B-Instruct | 6.0 | 8.5 | 95% | 71% | 95% | 90% | 86% |
| zai-org/GLM-4.5V | 9.2 | 14.2 | 90% | 81% | 95% | 90% | 86% |

I picked 30B-A3B: best warmth/colour numbers and only ~1.3 s slower than the 8B. The 8B was fastest but, for example, called a black ballet flat a hoodie. No model had a failed or unparsable call in this run. I did not look up per-token prices, so I make no cost claim. Describing all 21 photos took 94 s with 4 parallel workers, no faster than one at a time (the service seemed to serialise my requests; not investigated).

**Text (pick + explain), 5 scenarios each**

| Model | valid answers | median s | note |
|---|---|---|---|
| **Qwen/Qwen3.6-35B-A3B**, thinking off (default) | 5/5 | 2.5 | |
| Qwen/Qwen3.5-27B, thinking off | 5/5 | 11.9 | |
| Qwen/Qwen3.6-35B-A3B, thinking on | 4/5 | 22.4 | one unusable answer, cause not diagnosed |
| Qwen/Qwen3.5-27B, thinking on | 0/2 | n/a | both calls hit my 180 s timeout; stopped |

A whole `suggest` call (rules + one model request) took about 3 s wall-clock (four runs in 11-12 s).

## Honest limitations

- **Synthetic test data.** All numbers come from 21 simple illustrations I generated, not real photos. Real flat-lays and phone photos are harder; expect lower accuracy.
- **The vision model misreads things.** On the example set it called the denim jacket and the trench coat "blazers", the black flats "a belt" (so they are never used) and the tan suede loafers "a brown sandal". Mis-categorised pieces silently drop out or land in odd combinations. That is why every field can be overridden in `wardrobe.json`; review the `describe` output once.
- **Language-model reasons are fluent, not guaranteed true.** Material words ("silk", "wool") are the vision model's guesses. The grounding check only catches garments named in a reason that are not in the outfit; it does not check taste or claims like "slightly warmer".
- **Rules-only mode is mediocre on style.** It respects weather and dress code but has little taste (it once paired a shirt with shorts and heels for a date). That is the point of the model step.
- **Manual weather only.** Temperature and rain are typed in. No forecast lookup, no outfit history, no "I wore this yesterday".
- **Local models: untested here** (see table above).
- The yichu importer's default table and column names are guesses and have **not** been run against a real yichu database (see below).

## Bring your own wardrobe

`wardrobe.json` is just `{"items": [{"id": "...", "image": "photo.jpg"}, ...]}`, with optional per-item overrides (`"warmth": 4`, `"category": "outer"`, `"name": "Mum's camel coat"`). To import from a "yichu"-style self-hosted wardrobe app (FastAPI + SQLite + uploads folder, which is my own), see [`src/todays_outfit/sources/yichu.py`](src/todays_outfit/sources/yichu.py):

```bash
python -m todays_outfit import-yichu --db db.sqlite --uploads ./uploads --table items --image-col image_path --out my/wardrobe.json
python -m todays_outfit --wardrobe my/wardrobe.json describe
```

The database is opened read-only; photos are referenced in place. For this contest I did not use any private photos and the adapter is tested only with a synthetic SQLite file.

## Tests

`pytest` runs 48 offline tests (rule filter, JSON parsing, grounding check, fallback paths, privacy guard, config switch, importer, web API) plus 2 real SiliconFlow end-to-end tests that are skipped without a key. Last run: 50 passed (log: [`docs/test_run.txt`](docs/test_run.txt)). The end-to-end run on the sample wardrobe that produced `docs/examples.txt`, `docs/describe_run.txt` and the screenshots used the real service.

## Credits and license

- Written during the **Hacktoberfest Weekend Challenge: Build for a Friend**; built Oct 3-5 2026 (first commit 2026-10-03 18:23 Beijing time, within the challenge window).
- Models: Qwen3-VL and Qwen3.5/3.6 (Alibaba Qwen team) and GLM-4.5V (Z.ai), open-weight, served by SiliconFlow for my measurements.
- Libraries: [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [httpx](https://www.python-httpx.org/), [Pillow](https://python-pillow.org/), [pytest](https://pytest.org/). No code was copied from other projects; the rule table and prompts are mine.
- Example clothes are my own Pillow drawings (`tools/make_sample_wardrobe.py`), labelled "EXAMPLE DATA".
- The code was written with the help of an AI coding agent under my direction.
- License: MIT (see `LICENSE`).

### Commits after the deadline

The submission deadline is 2026-10-05 06:59 UTC (14:59 Beijing). **No commits after the deadline so far.** If any are made, they are listed here:

- _(none)_
