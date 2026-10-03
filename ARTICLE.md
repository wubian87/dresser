---
title: "12 °C, rain, commute: an outfit picker I built for my wife, with a rule that keeps suede out of the rain"
published: false
tags: devchallenge, weekendchallenge, hf26challenge, opensource
# cover_image: (optional) URL of docs/screenshot_rainy_commute.png after uploading it to DEV
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

I built a small tool for my wife that answers one question: **given the weather and where I'm going, what do I wear from the clothes I already own?** I typed "12 °C, rain, commute" and, in about three seconds, got this:

```
Outfit 1: gray sweater + black trousers + yellow rain boots
  The warm gray wool knit sweater pairs perfectly with black trousers for a cozy, professional
  commute. Yellow rain boots keep feet dry in the rain while adding a cheerful pop of color.

Outfit 2: light blue button-down shirt + black trousers + beige blazer + brown ankle boots
  ...Brown ankle boots offer superior warmth and stability for wet, chilly commuting conditions.

Outfit 3: navy blue maxi dress + black blazer + yellow rain boots
  ...Yellow rain boots provide essential waterproof protection against the rain...
```

Two things to know about that output. The wardrobe here is 21 example drawings I generated, not her closet (her photos are not in the repo). And the wardrobe also holds a pair of tan suede loafers that never appear, because a plain rule I wrote removes suede shoes on rainy days *before* any AI is asked. On a 26 °C date night the same wardrobe gives a yellow dress with heels instead.

That split is the idea of the project: **rules decide what is allowed, the AI only chooses among the allowed outfits and explains the choice.** I did not want to trust a language model with "will these shoes survive the rain?", because a rule is something I can check.

<!-- OPTIONAL (owner): one or two sentences in your own voice about her real mornings or her reaction. Only add what is true. Delete this comment if you have nothing to add; the article reads fine without it. -->

## What I Built

**Today's Outfit** is a command-line tool and a phone-sized web page. You give it the temperature, whether it rains, and one tap for the occasion (commute, casual, date or formal). It suggests one to three complete outfits from clothes in your wardrobe, with a one-sentence reason each. It never suggests buying anything.

Anyone with a closet and an OpenAI-compatible model endpoint can use it. A wardrobe is photos of what someone owns, so I made it possible to keep those photos on a machine at home (see the privacy setting below).

## Demo

- **Try it with no account and no API key:** `git clone REPO_URL && cd wardrobe-stylist && ./demo.sh`. It installs, runs the tests, and prints two suggestions from the bundled example wardrobe. Without a key it runs on the rules alone and says so; with a SiliconFlow key it uses the models described below.
- **Screenshot** of the phone-sized page on the rainy-commute case:

<!-- SCREENSHOT (owner): upload docs/screenshot_rainy_commute.png in the DEV editor and paste the image here. A second one, for the warm date, is docs/screenshot_warm_date.png. -->

- **Code:** REPO_URL (MIT licence, English README; first commit 2026-10-03 18:23 Beijing time, inside the challenge window).

## How it works

1. **Describe.** A vision model turns each photo into JSON: category, type, colour, material, warmth 1-5, formality 1-5, season. Results are cached by image hash and model, so each photo is paid for once.
2. **Filter, with no AI.** Temperature becomes a warmth target. Rain removes suede, canvas, satin and similar shoes. The occasion bounds how formal the outfit may be. An outfit is top + bottom or a dress, plus shoes, plus an optional outer layer. If a small wardrobe leaves nothing, the rules relax step by step and the result is labelled "loosest match" instead of pretending.
3. **Style.** A text model picks the best one to three of the surviving candidates and writes the reason. If its answer is not valid JSON, points at nothing real, or names a garment the outfit does not contain, that pick is dropped. If nothing survives, the app shows the rule-based ranking: someone who just wants to leave the house never sees an error screen.

Python 3.11+, FastAPI, one static HTML page, `httpx` and Pillow. About 1,900 lines including tests and tools. There are 48 offline tests and 2 real end-to-end tests against SiliconFlow; 50 passed on my last run.

## Why open-weight models, and how I chose them

Everything goes through one OpenAI-compatible client, so comparing models was a loop over model names, not four integrations. The privacy setting is one line:

```toml
[llm]
preset = "siliconflow"   # cloud, open-weight Qwen models
# preset = "local"       # Ollama or llama.cpp on your own machine, no key, nothing leaves it
privacy = "off"          # or "images-local", or "local-only"
```

With `images-local` the program refuses to send a photo to anything that is not `localhost`; with `local-only` it refuses to call anything that is not `localhost`. The check runs before the request is made, so it does not depend on me remembering. A real refusal is captured in `docs/privacy_demo.txt`. In the default cloud mode each photo leaves the machine once (downscaled to 512 px, then cached); later questions send only text: the weather and a list of candidate outfits.

I compared four vision models on the 21 example drawings. "Right" means it matched what I drew; "warmth" counts as right if within one point on the 1-5 scale.

| Vision model | seconds per photo (median) | category right | warmth right | colour right |
|---|---|---|---|---|
| Qwen3-VL-8B | 3.1 | 81% | 67% | 90% |
| **Qwen3-VL-30B-A3B** (my default) | 4.4 | 90% | 100% | 100% |
| Qwen3-VL-32B | 6.0 | 95% | 90% | 95% |
| GLM-4.5V | 9.2 | 90% | 90% | 95% |

The smallest model (8B) was the fastest and the worst: it called a black ballet flat a hoodie. The 30B-A3B was 1.3 seconds slower per photo and better on warmth and colour, the two things the rules depend on, so it became the default. For the text step I used **Qwen3.6-35B-A3B** with its "thinking" mode off: 5 valid answers out of 5 scenarios, median 2.5 s. With thinking on, the same model took a median of 22 s and gave one unusable answer out of five, and Qwen3.5-27B with thinking on timed out twice at my 180 s limit, so I stopped. For choosing one outfit from a short list, thinking was pure cost.

I did not run a closed model, so I cannot say open models read clothes better or worse; I would not be surprised if the best closed vision models do better on blurry photos. What I can say from this build is that privacy became a setting rather than a promise, that weights can be pinned and self-hosted so the app does not depend on a vendor's deprecation schedule, and that swapping model or provider is one line.

## Limits

- **Everything is measured on 21 clean drawings, not real photos.** Even there the vision model called my denim jacket and trench coat "blazers", my black flats "a belt" (so they are never used), and my suede loafers "a brown sandal" (made of suede, so the rain rule still caught them). Every field can be overridden by hand in `wardrobe.json`. Her real closet is the real test, and I have not reported results on it. <!-- OPTIONAL (owner): if you have since run it on her real photos, replace the last sentence with what actually happened. -->
- **The model's reasons are fluent, not guaranteed true.** Materials like "silk" are the vision model's guess. My check only catches garments that are not in the outfit.
- **The local-model path is untested end to end.** I had no local runtime to hand; only the privacy guard and the config switch are unit-tested.
- **Rules-only mode is dull.** It respects weather and dress code but once paired a shirt with shorts and heels for a date. The model step earns its keep.
- **Weather is typed in by hand.** No forecast lookup, no outfit history. Reading a whole wardrobe is slow once (94 s for 21 photos with 4 parallel workers), then cached.
- **The importer for my own self-hosted wardrobe app (yichu) is untested** against its real database; only a synthetic test file.

The code was written with an AI coding agent under my direction.

## Prize Categories

None of the partner categories: I did not use Render, TabPFN, Tinker, Arduino, DigitalOcean or Gemma (the models are Qwen and GLM, served by SiliconFlow). Entering for the overall prize.
