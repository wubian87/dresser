---
title: "Dresser: my wife's private wardrobe, now picking today's outfit in one tap"
published: false
tags: devchallenge, weekendchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

**Dresser**, a private wardrobe that picks today's outfit so you don't have to think.

My wife is an everyday user of the wardrobe app I built earlier and run on our NAS (it is called yichu). We designed it together: she asks for what she needs, I build it. Choosing what to wear takes thinking every morning, and you don't want to wear the same thing several days in a row. **Dresser** is the version that takes that thinking away: open it, get one outfit from clothes you own, tap *Wear this*. It is a new repository, written from scratch for this challenge; the original is its inspiration and the source of the requirements.

![Screen recording from a real phone: the Today card, Show another, Wear this, the Wardrobe tab, Settings (example wardrobe, rule-based picks)](https://raw.githubusercontent.com/wubian87/dresser/main/docs/demo.gif)

![The Today tab on a phone: Shanghai 19-22 °C, rain 100%, Autumn, one outfit card with Wear this / Show another](https://raw.githubusercontent.com/wubian87/dresser/main/docs/screenshot_today.png)

The same morning on the command line. It is raining in Shanghai (2026-10-04), and the example wardrobe is 21 drawings with a scripted two-week wear log:

```
$ dresser --demo today --occasion casual
Today in Shanghai: 19-22 °C, rain 100%  ->  occasion: casual, room: autumn

  Top pick: white t-shirt + blue jeans + yellow rain boots
    Yellow rain boots keep your feet dry in the rain, while the white tee and blue jeans offer a relaxed, casual vibe perfect for the mild 20.5°C weather.
    Rotation: Nothing in it was worn in the last 3 days.

  Alternative 1: white t-shirt + blue jeans + brown ankle boots
    Right weight for 20.5 °C and within the casual dress code; no rain-sensitive shoes; tagged for this occasion (rule-based pick).
    Rotation: Nothing in it was worn in the last 3 days.
```

The weather is live, the reason is written by an open-weight model, and the *Rotation* line is built by plain code from the wear log.

## A day with it

**Morning.** You open the page. One quiet line says *Shanghai 19-22 °C, rain 100% · Autumn*. Under it, four words: commute, casual, date, formal. Under those, one card: three pieces from your wardrobe and a sentence on why.

**Not feeling it?** *Show another* gives the next outfit, and the app remembers that you passed on that exact combination, so it is ranked lower from then on. There is no "do you like it?" question.

**Wearing it.** *Wear this* writes the day into a history on your own disk. Undo is one tap.

**Tomorrow.** The history does the remembering. Pieces you wore yesterday are steered away from, and a piece that has been sitting there for a while gets brought back, with a line that says so: *Brings back white t-shirt (not worn for 14 days).*

**When it rains.** Suede, canvas and other rain-sensitive shoes are taken out of the running before the model sees anything. That is why a rainy day gives yellow rain boots instead of the brown pair.

**Between seasons.** The wardrobe is split into four rooms, Spring, Summer, Autumn and Winter, as in the original app. You only see, and only get outfits from, the current room. The room follows the date and your city's hemisphere, and you can switch it by hand.

![The Wardrobe tab, Autumn room, grid of the example drawings](https://raw.githubusercontent.com/wubian87/dresser/main/docs/screenshot_wardrobe.png)

## Putting clothes in

Take or choose photos, and a vision model fills in category, colour, material and warmth. You look it over and fix anything before it is saved.

Or paste a link to a product page. On a shop page that exposes its picture, the item turns into a pre-filled form, here from a real Allbirds page:

![Add clothes, Paste a link: a product page read into a form for review](https://raw.githubusercontent.com/wubian87/dresser/main/docs/screenshot_add_link.png)

Tags (`work`, `casual`, `rain-ready`, `layering`) are added automatically, and a button can ask the model for more ideas; you keep or remove each one. The app never suggests buying anything.

## How it works

Rules decide what is allowed, the history decides what is fresh, and the model only chooses among what is left and explains it. If the model is slow or down, you get the rule-based pick instead of an error.

```
photo -> describe (vision model) -> filter by weather, occasion, season (rules)
      -> rotate by wear history (rules) -> choose + explain (text model)
```

## Rotation, in one number

I simulated two weeks of dressing on the example wardrobe, 50 runs. Without rotation, the same piece was worn two days in a row 17 times over the fortnight; with rotation, 0.2 (averages over the 50 runs). Details are in [`docs/rotation_simulation.md`](https://github.com/wubian87/dresser/blob/main/docs/rotation_simulation.md).

## Why open-weight models

The photos are her wardrobe. With an open-weight model, where those photos go is a choice. Everything goes through one OpenAI-compatible client, so the same code can point at the cloud or at a server on your own machine, such as Ollama:

```toml
[llm]
preset = "siliconflow"   # cloud, open-weight Qwen models
# preset = "local"       # Ollama or llama.cpp on your own machine, no key, nothing leaves it
privacy = "off"          # or "images-local", or "local-only"
```

With `images-local`, photos only go to `localhost`. With `local-only`, nothing leaves the machine, including the forecast and link fetching, and the app refuses before sending. In the default cloud mode a 512 px copy of each photo is sent once and cached; after that only text goes out, and the wear history stays on disk.

For photos I use Qwen3-VL-30B-A3B, and for the pick Qwen3.6-35B-A3B, both open-weight and served by SiliconFlow. Swapping either is a one-line change.

## Try it

To try it with no account and no key (the rules choose; with a key, the model writes the reason too):

```bash
git clone https://github.com/wubian87/dresser && cd dresser
./demo.sh                              # prints suggestions from the example wardrobe
python -m dresser --demo serve   # the web page, on the example wardrobe
```

Code (MIT): https://github.com/wubian87/dresser

## Limits

- The demo uses an example wardrobe of 21 drawings and a scripted wear log; the rotation figure comes from a simulation, not from a person.
- Paste-a-link works on shop pages that expose their product picture, and says so plainly when it can't; then you upload a photo.
- The model's pick and wording differ from run to run. There is no login, so keep it on a network you trust.

I built this with an AI coding agent, directing the design.
