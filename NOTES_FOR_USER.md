# Notes for you (bian wu)

Do these before submitting. Deadline: **Mon 2026-10-05 14:59 Beijing time (06:59 UTC)**.

## What changed in round 2 (your feedback on the "running ledger" home page)
1. **Home redesigned** as a calm single column with a bottom tab bar (**Today / Wardrobe / Settings**). Today = one quiet weather line (*Shanghai 19-23 °C, rain 98% · Autumn*, tap to override), four occasion words, and one card with **Wear this / Show another**. Model names, endpoints, privacy mode, "N/N ready", cache and the rule/source badges are gone from the main screens: a small **Details** link on the card, full list in Settings. Dark mode is there via `prefers-color-scheme` (cheap; I only looked at the Today screen in dark).
2. **Four season rooms** with a selector in Settings (Automatic = suggested from today's date, flipped for a southern-hemisphere city; or pick one). Only the current room is shown in Wardrobe and used for styling; weather still drives the pick inside the room. Rooms per piece come from a rule table on warmth (+ keyword overrides) and are editable.
3. **Paste a product link** in Add clothes. Honest result: it worked on 4 of the ~15 real shop pages I tried (Allbirds, Everlane, Uniqlo JP, Nike) and failed with clear messages on the rest (Zara 403, Patagonia and L.L.Bean with no picture in the HTML, Taobao/Tmall, a fake Xiaohongshu id; a few failures were my network/DNS or wrongly guessed URLs rather than the shop) (see README table and `docs/link_import_run.txt`). SSRF guard + privacy modes + size/time caps are tested with mocked pages.
4. **Auto tags**: stage 1 deterministic (tested), stage 2 model suggestions on request as accept/remove chips (mocked tests + one real call), filter in Wardrobe, light nudge (+0.25, max +1.0) in the style step and tags in the model prompt.
5. Rerun: **204 tests passed** (201 offline + 3 real SiliconFlow), new phone screenshots (`docs/screenshot_today|wardrobe|settings|add_link.png`; the old UI's `screenshot_add_clothes.png` is deleted), simulation rerun on the autumn room (`docs/rotation_simulation.md`), README / ARTICLE rewritten for the new UI (pain point first, the real Today run on the first screen, link-import failures in the limits).

### Where I deviated from your brief, and why
- **Season for each piece comes from my rule table, not from the vision model's guess**: the model's season guess is ignored so rooms are predictable and testable. The table is untuned.
- **User agent is honest** (`TodaysOutfit/0.3 ... single page fetch`), not a browser disguise; the cost is that several shops answer 403. No cookies, no login, no JavaScript, so Taobao/Xiaohongshu/JD basically do not work. I did not try to get around that on purpose.
- **Stage-2 tags only on request** ("More ideas from the model" button), not automatically for every photo: avoids an extra model call per piece and keeps privacy modes simple. Stage 1 is always on.
- **DNS rebinding is not fully mitigated** (address checked, then the HTTP client resolves again). Fine for a single-user localhost app; do not expose the link feature to strangers.
- **Link import fallback**: if the vision model is slow/denied (`images-local`), fields are filled from the page title by keyword rules and the form says so, instead of failing.
- **Wardrobe default sort is "longest unworn first"**, so never-worn pieces lead the grid (the screenshot shows several "never worn"). Change it under "Filter by tag · sort".
- **The Add form waits 75 s for the vision model** (was 45 s) because the endpoint was slow today.
- **Demo/simulation use the autumn room** (today is 3 Oct); I deleted and rebuilt `demo_data/`, so any piece you added in the demo copy earlier is gone.
- Dark mode was optional; included because it is ~20 lines of CSS.

## Only you can supply (everything else is done)
Article and README read fine **without** the optional items; optional items are invisible `<!-- OPTIONAL ... -->` comments.

**Mandatory (1 thing):**
- **Repo URL**: done, `REPO_URL` was replaced with https://github.com/wubian87/wardrobe-stylist in `ARTICLE.md` and `README.md`.

**Optional but worth it (only true things):**
- Her real mornings / her real reaction, in her words, good and bad: one or two sentences at the OPTIONAL comment near the top of `ARTICLE.md` (and a "What she said" section in `README.md`). The article never claims she tried it. The pain-point paragraph is explicitly "design hypothesis"; if she has told you things that confirm or contradict it, that is the single most valuable edit.
- **Try it on her real photos on a real phone** (see "Not verified" below) and, if you do, update the first bullet in "Limits" (OPTIONAL comment there).
- One sentence on your own part in the build (the article only says the code was written with an AI coding agent under your direction).
- Screenshots: upload `docs/screenshot_today.png`, `docs/screenshot_wardrobe.png`, `docs/screenshot_settings.png`, `docs/screenshot_add_link.png` in the DEV editor and paste them at the SCREENSHOT comment (optionally one as `cover_image`).
- Confirm `yichu` is your own wardrobe app (mentioned only in Limits / "Bring your own wardrobe").

## Look at it now
The server on port 8000 was restarted from the new code in demo mode: `.venv/bin/python -m todays_outfit --config config.example.toml --demo serve` (log `/tmp/serve.log`). That is the **example** wardrobe copy in `demo_data/` with a **synthetic** 14-day history, so you can tap Wear this / Show another / Add clothes safely. I pre-set the demo's city to **Shanghai** (in `demo_data/settings.json`, only a guess from your time zone): change it under Settings > City. For your own wardrobe run `python -m todays_outfit serve` (data goes to `./data/`, git-ignored; starts empty). `demo_data/` and `data/` are git-ignored.

## Publish steps
1. On GitHub create a **public** repo named `wardrobe-stylist` under your account (do not add a README/licence; the repo has them).
2. `git remote add origin <url> && git push -u origin HEAD` from `/workspace/wardrobe-stylist` (or copy the folder to your machine first). Check `git log --format='%an <%ae>'`: the author is `bian wu <noreply@example.invalid>`; set your real identity first if you care. Don't push anything you commit after 14:59 Beijing on Mon 2026-10-05 without listing it in README "Commits after the deadline".
3. Replace `REPO_URL` in `ARTICLE.md` and `README.md`, commit and push (before the deadline).
4. In DEV: create a new post from the challenge page's submission template (https://dev.to/challenges/hacktoberfest-weekend-2026-10-01), paste the body of `ARTICLE.md` (everything after the front matter), set the title from the front matter, and keep tags `devchallenge, weekendchallenge, hf26challenge, opensource` (max 4; the template may add its own).
5. Upload the four screenshots in the editor and paste them at the SCREENSHOT comment; optional cover image.
6. Click **Preview**: check the code blocks and tables render, and that no `REPO_URL` is left. Then publish. Aim for Sunday.

## Reader test (weak signal only, OLD draft)
`docs/reader_test/` holds raw outputs of 3 SiliconFlow models playing a tired judge on the **previous** article draft (`v1_*`, `v2_*`). The article has since been rewritten, so those outputs no longer describe it. Rerun with `.venv/bin/python tools/reader_test.py ARTICLE.md TAG` if you want a fresh weak signal; AI opinions, not judges.

## Decisions I made (change if you disagree)
- **Rotation weights** (-2.5 worn today/yesterday, -1.0 two to three days ago, up to +0.5 for unworn pieces, -4 for a skipped combo fading over 14 days), **rain = forecast probability >= 50%**, **dress for the midpoint of the day's low and high**, **badge from 7 days unworn**. All are my judgement, untuned; constants live in `rotation.py` / `weather.py` / `service.py`.
- **"Show another" = "not this one", stored as a skip** that ranks that exact combination lower for ~2 weeks. It is not a dislike signal.
- **`serve` defaults to `./data`** (created empty) instead of the example wardrobe; the example `sample_wardrobe/` is read-only (`"_readonly": true`) and the app refuses to write into it. `--demo` makes a writable copy.
- **Weather and privacy:** `local-only` mode disables the forecast too (nothing leaves localhost); `images-local` keeps the forecast but the Add form then asks you to type the fields.
- **Models unchanged:** vision Qwen3-VL-30B-A3B, text Qwen3.6-35B-A3B with thinking off. The model never sees the wear history, and any reason of its that talks about history is rejected.
- Config: `config.example.toml` is what the demo uses; copy to `config.toml` for your own setup (no secrets, only the *name* of the env var). Optional `[weather]` section for a default city/lat-lon.

## Not done / unverified
- **Real phone untested.** Everything UI-wise was driven in headless Chrome (390 px wide) and over HTTP. The "Take photo" button is `<input type=file capture>`; I have not seen it on a real device, nor large camera photos (they are resized to 1600 px and EXIF-stripped on the server).
- **Link import on real shops is a small sample** (~15 pages, my network, one afternoon; `docs/link_import_run.txt` holds the 8 from the final probe). A real Xiaohongshu post link was never tried (I had none); a real Taobao item page not either (only a fake id). Shop pages change; expect breakage.
- **Season rooms / tags are untuned rules.** I have not checked them against a real closet; the vision model's warmth guess (mostly 2-4) feeds the rooms, so many pieces land in 3 rooms.
- **Dark mode** only looked at on the Today screen.
- **Real photos untested.** Accuracy numbers (vision table) are from my 21 drawings; the rotation numbers are a **simulation** with a made-up habit user and rules only (no model). They say the mechanism works; they say nothing about her closet.
- **The pain point is a hypothesis**, written as such. No data about her.
- **Vision endpoint flakiness:** while I built this, SiliconFlow's vision calls were sometimes slow (one photo ~14 s; one real e2e test hit its 120 s timeout once and passed on rerun). The Add form waits 75 s and then lets you type the fields (or, for a pasted link, falls back to the page title). Today it got slower still: one photo took ~30 s, two attempts at the link screenshot timed out before one worked, and the real describe test timed out once at 120 s (it now waits 170 s and retries once). Open-Meteo returned HTTP 429 once during repeated screenshot runs; the app retries once and falls back to manual.
- **Local models (Ollama/llama.cpp) never run end to end**; no runtime on the box.
- **yichu importer** untested against your real DB (synthetic SQLite test only). I did not touch the NAS.
- No login on the web app (localhost by default; `--host 0.0.0.0` exposes it to your LAN).
- DevRelay session embed (optional in the rules): not done.

## Safety
- The SiliconFlow key is only read from the environment by the HTTP client. It is in no file, log, or doc (grepped the repo). `cache/`, `data/`, `demo_data/` are git-ignored; the committed `sample_wardrobe/descriptions.cache.json` holds only model descriptions of the drawings.
- Real calls made today: SiliconFlow (vision + text), Open-Meteo (geocoding "Shanghai" + forecast; coordinates of the city only), and GET requests to public shop pages for the link-import checks (allbirds, everlane, uniqlo, nike, zara, patagonia, taobao, tmall, xiaohongshu, muji, gap, asos, bonobos, h&m, l.l.bean; one page each, no login, honest user agent). Nothing pushed, posted or sent. Files outside `/workspace/wardrobe-stylist`: scratch in `/tmp` only.
- Any commit after the deadline must be listed in README "Commits after the deadline".
