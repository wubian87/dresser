---
title: "12 °C, raining, office at 9: an outfit picker built from my wife's own closet and open-weight models"
published: false
tags: devchallenge, weekendchallenge, hf26challenge, opensource
# cover_image: TODO (optional) URL of docs/screenshot_rainy_commute.png after uploading it to DEV
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

I typed "12 °C, rain, commute" and got this, in about three seconds:

```
Outfit 1: gray sweater + black trousers + yellow rain boots
  The warm gray wool knit sweater pairs perfectly with black trousers for a cozy, professional
  commute. Yellow rain boots keep feet dry in the rain while adding a cheerful pop of color.

Outfit 2: light blue button-down shirt + black trousers + beige blazer + brown ankle boots
  ...Brown ankle boots offer superior warmth and stability for wet, chilly commuting conditions.

Outfit 3: navy blue maxi dress + black blazer + yellow rain boots
  ...Yellow rain boots provide essential waterproof protection against the rain...
```

Every piece in those outfits is in the wardrobe. The tan suede loafers are not, because it is raining and a rule I wrote throws suede out before any AI is asked. On a 26 °C date night the same wardrobe gives a yellow dress with heels instead. The demo section below has the one command that reproduces this on your own machine.

## What I Built

**Today's Outfit** is a small web page and command-line tool that answers the question my wife asks every morning in some form: *what do I wear today?* [TODO: replace with one or two sentences in your own voice, e.g. the real morning scene. I only know the project, not her mornings.]

I already keep a digital version of her wardrobe in a self-hosted app I wrote, called yichu. [TODO: confirm and adjust.] It knows what she owns. It has never been able to tell her what to put on *today*. So this project reads that wardrobe, takes two inputs (the temperature and whether it rains) plus one tap for the occasion (commute, casual, date or formal), and suggests one to three complete outfits from clothes she already has, with a one-sentence reason each. It never suggests buying anything.

What she said when she tried it:

> **TODO: her real reaction, in her words, good and bad. I have deliberately left this empty; I will not make it up.**

## Demo

- Try it yourself, no account and no API key: `git clone TODO-repo-url && cd wardrobe-stylist && ./demo.sh` installs, runs the tests and prints two suggestions from the bundled example wardrobe (21 drawings of clothes I generated with Pillow, labelled "EXAMPLE DATA"; her real photos are not in the repo). Without a key it runs on the rules alone and tells you so; with a key it uses the models described below.
- Screenshot of the phone-sized page on the rainy-commute case: TODO (upload `docs/screenshot_rainy_commute.png` to DEV and paste the image here). A second one for the warm date is in `docs/screenshot_warm_date.png`.
- Live demo link: TODO (none; it runs on your own machine).

A second real run, 4 °C and casual, to show the layering:

```
Outfit 1: gray sweater + blue jeans + olive green jacket + brown ankle boots
  The olive green jacket and brown ankle boots provide excellent warmth for the 4°C chill. ...
Outfit 2: gray sweater + blue jeans + beige cardigan + white sneaker
  Layering the beige cardigan over the gray sweater adds necessary warmth for the cool temperature. ...
```

## Code

TODO: repo URL (MIT licensed, English README, built in the challenge window; first commit 2026-10-03 18:23 Beijing time). No commits after the deadline [TODO: update this line if that changes].

## Open models, and why they matter here

This is the part I care about most, because a wardrobe is a personal thing. It is photos of what someone owns and, indirectly, of where she lives and what she does.

**One line decides where the models run.** Everything goes through a single OpenAI-compatible client. The config looks like this:

```toml
[llm]
preset = "siliconflow"   # cloud, open-weight Qwen models
# preset = "local"       # Ollama or llama.cpp on your own machine, no key, nothing leaves it
privacy = "off"          # or "images-local", or "local-only"
```

With `--privacy images-local` the program refuses to send a photo to anything that is not `localhost`, and with `local-only` it refuses to call anything that is not `localhost`. The check runs before the request is made, so it does not depend on me remembering. There is a real refusal captured in `docs/privacy_demo.txt`. In the default cloud mode, the photos leave the machine once (downscaled to 512 px, then cached), and later questions only send text: the weather and a list of candidate outfits.

**I could swap models in an afternoon.** Because the models are open-weight and the client is generic, comparing four vision models and two text models was a loop over model names, not four integrations. That mattered, because the cheapest model was not the best one. Below, "accuracy" is measured against what I drew in my 21 example images, so treat it as a relative comparison between models, not as how well it will read real photos.

| Vision model | seconds per photo (median) | category right | warmth within ±1 | colour right |
|---|---|---|---|---|
| Qwen3-VL-8B | 3.1 | 81% | 67% | 90% |
| **Qwen3-VL-30B-A3B** (my default) | 4.4 | 90% | 100% | 100% |
| Qwen3-VL-32B | 6.0 | 95% | 90% | 95% |
| GLM-4.5V | 9.2 | 90% | 90% | 95% |

The 8B is the fastest and the worst: it called a black ballet flat a hoodie. The 30B-A3B was 1.3 seconds slower per photo and noticeably better on the numbers the rules depend on (warmth, colour), so it became the default. For the text step, **Qwen3.6-35B-A3B** with its "thinking" mode off answered 5 out of 5 scenarios in a median of 2.5 s. The same model with thinking on took a median of 22 s and gave one unusable answer out of five, and Qwen3.5-27B with thinking on timed out twice at my 180 s limit (so I stopped). Timing the switch was how I learned that "thinking" is pure cost for choosing one outfit from a list.

**Where I think open beats closed here, and where I can't say.** I did not run a closed model, so I can't tell you it reads clothes worse; I would not be surprised if the best closed vision models do better on blurry photos. What I can say from this build:

- *Privacy is a setting, not a promise.* Her photos can stay on a machine I control. (The local path is untested end to end in this build, since I had no local runtime to hand; only the guard and the switch are tested.)
- *Pinning and switching.* Weights can be pinned and self-hosted, so the app does not depend on a vendor's deprecation schedule, and changing model or provider is one line.
- *The rules do the safety-critical work.* A small model can be fluent and wrong. Mine is only allowed to choose among outfits that already passed deterministic checks, and its explanation is rejected if it mentions a garment that is not in the outfit. That design is cheaper and easier to trust because the model is swappable; it is not something open models give you for free.

## How I Built It

The code was written with an AI coding agent under my direction. [TODO: one honest sentence about your part: what you specified, reviewed and changed.] Python 3.11+, FastAPI, one static HTML page, `httpx` and Pillow; nothing else. About 1,800 lines including tests and tools.

1. **Describe.** A vision model turns each photo into JSON: category, type, colour, material, warmth 1-5, formality 1-5, season. Results are cached by image hash and model, so each photo is paid for once.
2. **Filter, with no AI.** Temperature becomes a warmth target. Rain removes suede, canvas, satin and similar shoes. The occasion bounds formality. An outfit is top + bottom or a dress, plus shoes, plus an optional outer layer. If a small wardrobe leaves nothing, the rules relax in steps and the result is labelled "loosest match" rather than pretending.
3. **Style.** A text model chooses the best one to three of the surviving candidates and writes the reason. If its answer is not valid JSON, points at nothing real, or names a garment the outfit does not contain, that pick is dropped; if nothing survives, the app serves the rule-based ranking. It never shows an error screen to someone who just wants to leave the house.

There are 48 offline tests (rules, parsing, fallbacks, privacy guard, config switch, importer, web API) and 2 real end-to-end tests against SiliconFlow; 50 passed on my last run. Describing all 21 example photos took 94 s once, and a full suggestion about 3 s.

## Limits

- All numbers are from 21 clean drawings, not real photos. On this set the vision model still called my denim jacket and trench coat "blazers", my black flats "a belt" (so they never get used) and my suede loafers "a brown sandal". Every field can be overridden by hand in `wardrobe.json`, and I plan to review the descriptions once with her. [TODO: update after you do this with her real photos, if you do.]
- The model's reasons are fluent, not guaranteed true: materials like "silk" are the vision model's guess, and my check only catches garments that do not exist in the outfit.
- Rules-only mode is dull: it respects weather and dress code but once paired a shirt with shorts and heels for a date. The model step earns its keep.
- Weather is typed in by hand; there is no forecast lookup or outfit history.
- Reading a whole wardrobe is slow once, then cached: 94 s for 21 photos with 4 parallel workers versus 118 s one at a time. Parallel requests helped by only ~20% on SiliconFlow and I did not investigate why.

## Prize Categories

None of the partner categories. I did not use Render, TabPFN, Tinker, Arduino, DigitalOcean, Gemma (the models I used are Qwen and GLM, served by SiliconFlow, which does not list Gemma) or any of the other partner technologies. Entering for the overall prize.

*Team: TODO (solo?). DEV handle: TODO.*
