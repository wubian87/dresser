---
title: "A wardrobe-first outfit planner for my wife: it remembers what you wore and rotates the rest"
published: false
tags: devchallenge, weekendchallenge, hf26challenge, opensource
# cover_image: (optional) URL of docs/screenshot_today.png after uploading it to DEV
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

I built **Today's Outfit** for my wife so that choosing what to wear in the morning takes one tap. The problem it targets is my hypothesis, not a measurement: you stand in front of a full closet, wear the same few favourites, half of the clothes never get worn, picking takes time, and you can't remember what you wore last time. So the wardrobe is the hero. Your clothes live in the app, it logs what you wear, and it picks today's outfit from pieces you own, steering away from what you just wore and toward what has been sitting there.

Here is one real run (2026-10-04, Beijing time). It is raining in Shanghai (100% chance, 19-22 °C), it is a casual day, and the app picks from an example wardrobe of 21 drawings (no real clothes) with an invented two-week log of what was "worn", so the rotation has something to react to:

```
$ todays-outfit --demo today --occasion casual
Today in Shanghai: 19-22 °C, rain 100%  ->  occasion: casual, room: autumn

  Top pick: white t-shirt + blue jeans + yellow rain boots
    Yellow rain boots keep your feet dry in the rain, while the white tee and blue jeans offer a relaxed, casual vibe perfect for the mild 20.5°C weather.
    Rotation: Nothing in it was worn in the last 3 days.

  Alternative 1: white t-shirt + blue jeans + brown ankle boots
    Right weight for 20.5 °C and within the casual dress code; no rain-sensitive shoes; tagged for this occasion (rule-based pick).
    Rotation: Nothing in it was worn in the last 3 days.
```

The reason in the top pick is the model's. The **Rotation** line and "rule-based pick" are not: plain code builds them, so they can only say what is true. That split is the idea of the project: **rules decide what is allowed, the history decides what is fresh, and the model only chooses among what is left and explains it.** (I ran this three times and the top pick was the same each time. The rain rule keeps canvas and suede shoes out, and on this wet day the model chose the example wardrobe's bright boots over the brown ones. The model's choice can differ between runs; all outputs are in `docs/today_run.txt`.)

<!-- OPTIONAL (owner): one or two sentences in your own voice about her real mornings or her reaction. Only add what is true. Delete this comment if you have nothing to add; the article reads fine without it. -->

## What I Built

A phone-sized web page and a command-line tool. The page is one calm column with three tabs, in the spirit of a social feed: one thing to do per screen, lots of white space, and every technical detail (model names, endpoints, privacy mode, "21/21 ready", cache, which rule picked what) folded behind a small *Details* link or into Settings.

- **Today.** A quiet weather line (*Shanghai 19-22 °C, rain 100% · Autumn*; tap to override), four occasion words, and one card: the pick, a one-sentence reason, **Wear this** and **Show another**. The forecast comes from Open-Meteo, no key, for a city you set once. **Show another** remembers that you passed on that exact combination. There is no "do you like it?" question.
- **Wardrobe, in four season rooms.** Spring, Summer, Autumn and Winter, like the winter/summer separation in my old self-hosted wardrobe app. Only the current room is shown and used for styling; the season is suggested from the date (and the city's hemisphere) and can be overridden in Settings. Each piece's rooms come from its warmth by a fixed rule table, and you can edit them.
- **Add clothes.** Photos from the gallery or camera, pre-filled by a vision model and **reviewed by you before saving**. Or **paste a product link**: it works on simple shop pages and fails, with a clear message, on most big ones (see Limits).
- **Auto tags.** Each piece gets tags (`work`, `casual`, `rain-ready`, `layering`, `neutral`...) from plain rules on category, colour, material, warmth and formality. An optional "More ideas" button asks the model for extra tags; you accept or remove chips. Tags filter the wardrobe and nudge the style step lightly.
- **Rotation.** The ranking avoids pieces from the last three days and gives long-unworn pieces a small boost, only among outfits the rules already approved.

It never suggests buying anything.

## Demo

- **Try it with no account and no API key:** `git clone https://github.com/wubian87/wardrobe-stylist && cd wardrobe-stylist && ./demo.sh`. It installs, runs the tests, and prints suggestions from the bundled example wardrobe, including one with an invented wear log so you can see the rotation line. Without a key it runs on the rules alone and says so. For the web page: `python -m todays_outfit --demo serve`.
- **Screenshots** of the phone-sized page (example wardrobe, invented wear log, real forecast and model, taken on 2026-10-04; a separate run, so the model's pick and the rotation line differ from the run above):

<!-- SCREENSHOT (owner): upload docs/screenshot_today.png (Today), docs/screenshot_wardrobe.png (Autumn room), docs/screenshot_settings.png (season room + folded details) and docs/screenshot_add_link.png (Paste a link on a real public shop page) in the DEV editor and paste them here. -->

- **Code:** https://github.com/wubian87/wardrobe-stylist (MIT licence, English README; first commit 2026-10-03 18:23 Beijing time, inside the challenge window).

## How it works

1. **Describe.** A vision model turns each photo into JSON: category, type, colour, material, warmth 1-5, formality 1-5. Cached per photo and model. What you save after editing overrides it.
2. **Filter, with no AI.** Only pieces in the current season room count. Temperature becomes a warmth target, rain removes suede, canvas and similar shoes, the occasion bounds formality, and an outfit is top + bottom or a dress, plus shoes, plus an optional outer layer. If a small wardrobe leaves nothing, the rules relax step by step and the result says "loosest match".
3. **Rotate, with no AI.** Re-scores the candidates from the history: -2.5 per piece worn today or yesterday, -1.0 for 2-3 days ago, up to +0.5 per piece for being unworn, up to -4 for a combination you skipped. These weights are my judgement, not tuned on anyone. A tag that fits the chosen occasion adds +0.25, never enough to beat a weather or dress-code rule.
4. **Style.** A text model picks the best one to three and writes the reason. It never sees the history, and a reason that talks about history ("yesterday", "haven't worn") or names a garment that isn't in the outfit is dropped. If nothing survives, the app shows the rule ranking: nobody sees an error screen on a weekday morning.

Season rooms come from each piece's warmth by a fixed table plus keyword overrides ("shorts" are spring and summer, "coat" autumn and winter); I ignore the vision model's own season guess so the rooms are predictable, and you can edit any piece's rooms.

Weather uses the day's high, low and rain probability; the rules dress for the midpoint, and "rain" means 50% or more. On 2026-10-04 I compared the app's numbers with a plain request and a `curl` to the same Open-Meteo URL: identical (`docs/weather_check.md`). Pasting a link only reads what a shop puts in its HTML, from public addresses only, with an honest user agent; most big shops fail (see Limits).

Python 3.11+, FastAPI, one static HTML page, `httpx` and Pillow. About 6,200 lines including tests and tools. 202 offline tests (weather and shop pages use mocked HTTP) and 3 real end-to-end tests against SiliconFlow; 205 passed on my last run.

## Does the rotation do anything? A simulation

I have no real wear data, so I simulated, using a **made-up habit user**. That is a small script I wrote, not a person: it picks a few favourite pieces (one per kind of garment, two tops), and among the best six outfits the rules allow it chooses ones containing favourites about 4 times as often (mild) or 12 times as often (strong). I use it only to produce a plausible fortnight of history for the rotation to push against. It can show that the mechanism does what I designed (fewer repeats, more pieces worn); it cannot show that a real person has such habits, would follow the picks, or has a closet with unworn pieces. In fact this user wore 70-75% of the pieces.

On the Autumn room of the example wardrobe (19 pieces), rules only, 50 random runs: 14 days of that history, then 14 more days of random autumn weather dressed three ways from the same history. Means over the 50 runs (mild habit):

| 14 days, 19 pieces | made-up habit user | app top pick, no rotation | app top pick, **with rotation** |
|---|---|---|---|
| Pieces worn at least once | 14.3 | 13.0 | **16.7** |
| Most times one piece was worn | 7.7 | 7.8 | **4.3** |
| Piece-days repeated from the previous day | 14.0 | 17.0 | **0.2** |
| Mean rule score of the outfit worn | 10.3 | 10.7 | 10.0 |

The "no rotation" arm repeats its best outfit whenever the weather repeats, and rotation costs about 0.7 rule-score points. The strong-habit setting and min-max ranges are in `docs/rotation_simulation.md`.

## Why open-weight models, and how I chose them

Everything goes through one OpenAI-compatible client, so comparing models was a loop over names, not four integrations. Privacy is one line:

```toml
[llm]
preset = "siliconflow"   # cloud, open-weight Qwen models
# preset = "local"       # Ollama or llama.cpp on your own machine, no key, nothing leaves it
privacy = "off"          # or "images-local", or "local-only"
```

With `images-local` the program refuses to send a photo to anything but `localhost`; with `local-only` it refuses to call anything but `localhost`, including the forecast and link fetching. The check runs before the request is made (a real refusal is in `docs/privacy_demo.txt`). In the default cloud mode each photo leaves the machine once, downscaled to 512 px, then cached; later questions send only text. The wear history stays on disk.

I compared four vision models on the 21 example drawings. "Right" means it matched what I drew; warmth counts as right if within one point on the 1-5 scale. Twenty-one drawings is a tiny, easy set, so read 100% as "fine on this set", not as general accuracy.

| Vision model | seconds per photo (median) | category right | warmth right | colour right |
|---|---|---|---|---|
| Qwen3-VL-8B | 3.1 | 81% | 67% | 90% |
| **Qwen3-VL-30B-A3B** (my default) | 4.4 | 90% | 100% | 100% |
| Qwen3-VL-32B | 6.0 | 95% | 90% | 95% |
| GLM-4.5V | 9.2 | 90% | 90% | 95% |

The smallest model was fastest and worst: it called a black ballet flat a hoodie. The 30B-A3B was 1.3 seconds slower and better on warmth and colour, which the rules depend on, so it became the default. For the text step I used Qwen3.6-35B-A3B with its "thinking" mode off (5 valid answers in 5 test scenarios, median 2.5 s); turning thinking on was slower and less reliable in that small test, so it stays off.

I did not run a closed model, so I cannot say open models read clothes better or worse. What I can say is that privacy became a setting rather than a promise, and that swapping model or provider is one line.

## Limits

- **Everything measured is synthetic.** The wardrobe is 21 drawings, the wear logs are invented, and the rotation table is a simulation. Even on the drawings the vision model called my denim jacket and trench coat "blazers", my black flats "a belt" (so they are never used) and my suede loafers "a brown sandal". Every field can be edited in the app. Her real closet is the real test, and I have not reported results on it. <!-- OPTIONAL (owner): if you have since run it on her real photos, replace the last sentence with what actually happened. -->
- **The pain point is my hypothesis.** I have no data that it holds for any particular person, and I don't claim the app fixes it.
- **Pasting a product link mostly fails on big shops.** I tried 16 real public pages on 2026-10-03: 4 worked (Allbirds, Everlane, Uniqlo Japan, Nike; 14-21 s each). The other 12 failed with a clear message and an "upload a picture instead" button: Zara and Muji answered 403, Patagonia, L.L.Bean and Gap had no picture in the HTML, two timed out from my network, a Taobao and a Tmall item page (made-up ids) gave a JavaScript-or-login page, and a made-up Xiaohongshu id returned only a tiny logo. Two of the 12 are on me (a wrong URL, and my own DNS refusing H&M). A real Taobao item or Xiaohongshu post was never tried. No login, no JavaScript, no pretending to be a browser, and DNS rebinding is not fully mitigated, so don't expose this feature to untrusted users. Per page: `docs/link_import_probe.md`.
- **Rotation only knows what you tap.** An unlogged day makes every "not worn in N days" wrong.
- **The model's reasons are fluent, not guaranteed true,** and its tag suggestions are guesses. My checks catch wrong garments and invented wear history, not taste; for the beige blazer the model suggested `professional, business-casual, smart, versatile, tailored`, and for the navy dress it added `v-neck`, which the app cannot know (`docs/tag_suggestions_run.md`). You accept or remove each chip.
- **The rules and weights are my judgement, untuned.** Rotation penalties, season-room table, tag rules, the 50% rain cut-off. The rules still have little taste (they once accepted khaki shorts under a jacket at 14 °C).
- **Tested in headless Chrome and over HTTP, not on a real phone;** local models (Ollama) and my importer for my own wardrobe app (yichu) are untested end to end. The vision endpoint was slow at times while I built this (one photo took 14 s, later 30 s), so the Add form gives up after 75 s and lets you type. There is no login: only run it on a network you trust.

The code was written with an AI coding agent under my direction. I am not entering any partner prize category; this is an entry for the overall prize.
