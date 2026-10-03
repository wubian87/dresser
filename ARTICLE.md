---
title: "A wardrobe-first outfit planner for my wife: it remembers what you wore and rotates the rest"
published: false
tags: devchallenge, weekendchallenge, hf26challenge, opensource
# cover_image: (optional) URL of docs/screenshot_today.png after uploading it to DEV
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

The problem this tool targets, as a design hypothesis rather than a measurement: every morning you stand in front of a full closet, wear the same few favourites, half of the clothes never get worn, picking takes time, and you can't remember what you wore last time. I built **Today's Outfit** for my wife around that idea. The wardrobe is the hero: your clothes live in the app, it logs what you wear with one tap, and it picks today's outfit from pieces you own, steering away from what you just wore and toward what has been sitting there.

Here is a real run (the Autumn room of an example wardrobe of drawings with a *synthetic* 14-day wear history; real Open-Meteo forecast and a real open-weight model):

```
$ todays-outfit --demo today --occasion commute
Today in Shanghai: 18-23 °C, rain 98%  ->  occasion: commute, room: autumn

  Top pick: yellow maxi dress + beige blazer + yellow rain boots
    The wool blazer adds warmth to the light silk dress, while yellow rain boots keep you dry and stylish during the commute.
    Rotation: Nothing in it was worn in the last 3 days.
```

The reason is the model's. The **Rotation** line is not: plain code builds it from the wear log, so it can only say what is true. That split is the idea of the project: **rules decide what is allowed, the history decides what is fresh, and the model only chooses among what is left and explains it.**

<!-- OPTIONAL (owner): one or two sentences in your own voice about her real mornings or her reaction. Only add what is true. Delete this comment if you have nothing to add; the article reads fine without it. -->

## What I Built

A phone-sized web page and a command-line tool. The page is one calm column with three tabs, in the spirit of a social feed: one thing to do per screen, lots of white space, and every technical detail (model names, endpoints, privacy mode, "21/21 ready", cache, which rule picked what) folded behind a small *Details* link or into Settings.

- **Today.** A quiet weather line (*Shanghai 19-23 °C, rain 98% · Autumn*; tap to override), four occasion words, and one card: the pick, a one-sentence reason, **Wear this** and **Show another**. The forecast comes from Open-Meteo, no key, for a city you set once. **Show another** remembers that you passed on that exact combination. There is no "do you like it?" question.
- **Wardrobe, in four season rooms.** Spring, Summer, Autumn and Winter rooms, like the winter/summer separation in my old self-hosted wardrobe app. Only the current room is shown and used for styling; the current season is suggested from the date (and the city's hemisphere) and can be overridden in Settings. Each piece's rooms come from its warmth by a fixed rule table, and you can edit them. The grid shows quietly how long each piece has been unworn.
- **Add clothes.** Photos from the gallery or camera, pre-filled by a vision model, **reviewed and edited by you before saving**. Or **paste a product link**: the server reads the public page's picture and title and fills the same form. It works on simple shop pages and fails, with a clear message, on many big ones (see Limits).
- **Auto tags.** Each piece gets tags (`work`, `casual`, `rain-ready`, `layering`, `neutral`...) from plain rules on category, colour, material, warmth and formality. An optional "More ideas" button asks the model for extra tags; you accept or remove chips. Tags filter the wardrobe and nudge the style step lightly.
- **Rotation.** The ranking avoids pieces from the last three days and gives long-unworn pieces a small boost, only among outfits the rules already approved.

It never suggests buying anything.

## Demo

- **Try it with no account and no API key:** `git clone REPO_URL && cd wardrobe-stylist && ./demo.sh`. It installs, runs the tests, and prints suggestions from the bundled example wardrobe, including one on a demo copy with a synthetic wear history so you can see the rotation line. Without a key it runs on the rules alone and says so. For the web page: `python -m todays_outfit --demo serve`.
- **Screenshots** of the phone-sized page (example wardrobe, synthetic history, real forecast and model):

<!-- SCREENSHOT (owner): upload docs/screenshot_today.png (Today), docs/screenshot_wardrobe.png (Autumn room), docs/screenshot_settings.png (season room + folded details) and docs/screenshot_add_link.png (Paste a link on a real public shop page) in the DEV editor and paste them here. -->

- **Code:** REPO_URL (MIT licence, English README; first commit 2026-10-03 18:23 Beijing time, inside the challenge window).

## How it works

1. **Describe.** A vision model turns each photo into JSON: category, type, colour, material, warmth 1-5, formality 1-5, season. Cached by image hash and model, so each photo is paid for once. What you save after editing overrides it.
2. **Filter, with no AI.** Temperature becomes a warmth target. Rain removes suede, canvas, satin and similar shoes. The occasion bounds how formal the outfit may be. An outfit is top + bottom or a dress, plus shoes, plus an optional outer layer. If a small wardrobe leaves nothing, the rules relax step by step and the result is labelled "loosest match".
3. **Rotate, with no AI.** Re-scores those candidates from the history: -2.5 per piece worn today or yesterday, -1.0 for 2-3 days ago, up to +0.5 per piece for being unworn (full at 21 days), up to -4 for a combination you skipped, fading over 14 days. These weights are my judgement, not tuned on anyone.
4. **Style.** A text model picks the best one to three and writes the reason. It never sees the history, is told not to talk about it, and a reason that does ("yesterday", "haven't worn", "rotation") is dropped, as is one naming a garment the outfit doesn't contain. If nothing survives, the app shows the rule-based ranking: nobody sees an error screen on a weekday morning.

**Rooms and tags, no AI.** Before any of that, only pieces in the current season room are considered. Warmth 1 means spring and summer, 2 adds autumn, 3 is spring, autumn and winter (summer too for bottoms, dresses and shoes), 4 is autumn and winter, 5 is winter only; "shorts/sandal/sundress..." are spring+summer only and "coat/parka/puffer..." autumn+winter only. I ignore the vision model's own season guess so the rooms are predictable. Tags work the same way (for example formality 4-5 gives `work`, a rain-proof shoe or coat gives `rain-ready`), and a piece tagged for the chosen occasion gets +0.25 on its rule score, never enough to beat a weather or dress-code rule.

**Paste a link, in short.** The server fetches the page with an honest user agent (no browser pretending, no cookies, no JavaScript), reads `og:image`/`og:title`/`og:description` and any JSON-LD `Product` block, downloads the picture, and gives the picture and the page title to the vision model. Only http/https to public addresses is allowed (loopback, private and link-local ranges are refused, redirects are re-checked, 10 s timeout, size caps). Under `local-only` it does nothing at all.

**Weather** uses the day's high, low and maximum rain probability. The rules dress for the midpoint of high and low; "rain" means probability of 50% or more; the card shows the raw numbers. The response is cached on disk, retried once on a rate-limit, and if the network is down the last saved forecast for today is used, or the page asks for a temperature. Only the city's coordinates leave the machine for this call.

Python 3.11+, FastAPI, one static HTML page, `httpx` and Pillow. About 6,200 lines including tests and tools. There are 201 offline tests (weather and shop pages use mocked HTTP) and 3 real end-to-end tests against SiliconFlow (describe a photo, style an outfit, suggest tags); 204 passed on my last run. I also made one real call each to Open-Meteo geocoding and forecast and compared the forecast with a plain `curl` of the same URL: same numbers.

## Does the rotation do anything? A simulation

I have no real wear data, so I simulated. On the Autumn room of the example wardrobe (19 pieces), rules only, 50 random runs: a **made-up** habit user (leans on one favourite per category) produces 14 days of history; then 14 more days of random autumn weather are dressed three ways from that same history. Means over the 50 runs:

| 14 days, 19 pieces | made-up habit user | app top pick, no rotation | app top pick, **with rotation** |
|---|---|---|---|
| Pieces worn at least once | 14.3 | 13.0 | **16.7** |
| Most times one piece was worn | 7.7 | 7.8 | **4.3** |
| Piece-days repeated from the previous day | 14.0 | 17.0 | **0.2** |
| Mean rule score of the outfit worn | 10.3 | 10.7 | 10.0 |

(That is the "mild habit" setting; a stronger habit and min-max ranges are in `docs/rotation_simulation.md`.) Two caveats up front: the "no rotation" arm repeats its best outfit whenever the weather repeats, and rotation costs about 0.7 rule-score points; and my habit user wore 70-75% of the pieces in a fortnight, so it did **not** reproduce "half the closet unworn". The simulation shows the mechanism works as designed. It says nothing about whether a real closet looks like the hypothesis or whether a real person would follow the picks.

## Why open-weight models, and how I chose them

Everything goes through one OpenAI-compatible client, so comparing models was a loop over model names, not four integrations. The privacy setting is one line:

```toml
[llm]
preset = "siliconflow"   # cloud, open-weight Qwen models
# preset = "local"       # Ollama or llama.cpp on your own machine, no key, nothing leaves it
privacy = "off"          # or "images-local", or "local-only"
```

With `images-local` the program refuses to send a photo to anything that is not `localhost`; with `local-only` it refuses to call anything that is not `localhost`, including the forecast. The check runs before the request is made, so it does not depend on me remembering. A real refusal is captured in `docs/privacy_demo.txt`. In the default cloud mode each photo leaves the machine once (downscaled to 512 px, then cached); later questions send only text: the weather and a list of candidate outfits. The wear history stays on disk.

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

- **Everything measured is synthetic.** The wardrobe is 21 drawings, the 14-day histories are generated, and the rotation table is a simulation with a made-up user who always takes the top pick. Even on the drawings the vision model called my denim jacket and trench coat "blazers", my black flats "a belt" (so they are never used) and my suede loafers "a brown sandal". Every field can be edited in the app. Her real closet is the real test, and I have not reported results on it. <!-- OPTIONAL (owner): if you have since run it on her real photos, replace the last sentence with what actually happened. -->
- **The pain point is my hypothesis.** I have no data that it holds for any particular person, and I don't claim the app fixes it.
- **Rotation only knows what you tap.** An unlogged day makes every "not worn in N days" badge wrong.
- **The model's reasons are fluent, not guaranteed true.** The sentence "boots provide waterproofing" in the run above is the model's claim; my checks catch wrong garments and invented wear history, not taste.
- **The rules still have little taste.** They accepted khaki shorts under a jacket at 14 °C.
- **Pasting a product link often fails, and it should.** I tried about 15 real public pages on 2026-10-03: it worked on Allbirds, Everlane, Uniqlo Japan and Nike (title, picture and fields in 14-21 s with the vision model), and did not on Zara (HTTP 403), Patagonia (no picture in the HTML), Taobao/Tmall (JavaScript or login) or a Xiaohongshu note link (a made-up id returned a "page gone" page with only a logo, which is rejected; I had no real post to try). Others I tried (Muji, Gap, ASOS, H&M) were refused, empty or unreachable from my network. The app says why and offers to upload a picture instead. It does not log in, run JavaScript or imitate a browser. DNS rebinding is not fully mitigated, so do not expose this feature to untrusted users.
- **Season rooms and tags are rules, not learning.** The room table and tag rules are my judgement, untuned on any real closet; a misread type puts a piece in the wrong rooms until you edit it. Model tag suggestions are fluent guesses (for a beige trench coat a real call returned `classic`, `smart`, `transitional`, `professional`, `versatile`).
- **Weights and thresholds are untuned.** Rotation penalties, the tag nudge, the 50% rain cut-off, the 7-day badge.
- **The vision endpoint was sometimes slow while I built this** (one photo took about 14 s, later 30 s; one end-to-end test timed out once and passed on a rerun; two attempts at the link-import screenshot hit the form's timeout before one worked), so the Add form gives up after 75 s and lets you type or falls back to the page title.
- **Tested in headless Chrome and over HTTP, not on a real phone** (dark mode only looked at on the Today screen). The camera button is a plain file input with `capture`; I haven't seen it on a device. There is no login, so only run it on a network you trust.
- **The local-model path is untested end to end.** I had no local runtime to hand; only the privacy guard and the config switch are unit-tested.
- **The importer for my own self-hosted wardrobe app (yichu) is untested** against its real database; only a synthetic test file.

The code was written with an AI coding agent under my direction.

## Prize Categories

None of the partner categories: I did not use Render, TabPFN, Tinker, Arduino, DigitalOcean or Gemma (the models are Qwen and GLM, served by SiliconFlow). Entering for the overall prize.
