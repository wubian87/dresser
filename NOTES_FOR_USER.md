# Notes for you (bian wu)

Do these before submitting. Deadline: **Mon 2026-10-05 14:59 Beijing time (06:59 UTC)**.

## What changed since your feedback ("just answers one question, not smart enough")
The wardrobe is now the hero. The main page opens on a **Today card** (automatic forecast + remembered occasion, *Wear this* / *Show another*) above a **wardrobe grid** (category filters, wear counts, "not worn in N days" badges). New: add clothes from phone photos (multi-upload, vision model pre-fills editable fields), edit/delete, one-tap wear log, rotation in the ranking, Open-Meteo weather, CLI `add / wear / today / wardrobe`. README and ARTICLE now lead with the pain point (worded as a **design hypothesis**, no claims or quotes about your wife) and the wardrobe-as-hero; stale claims ("manual weather only", "no history", old test counts, old screenshots) are gone. Numbers are from the latest runs: **104 tests passed** (102 offline + 2 real SiliconFlow), simulation tables in `docs/rotation_simulation.md`.

## Only you can supply (everything else is done)
Article and README read fine **without** the optional items; optional items are invisible `<!-- OPTIONAL ... -->` comments.

**Mandatory (1 thing):**
- **Repo URL**: replace every `REPO_URL` (2 places in `ARTICLE.md`, 1 in `README.md`) with your public GitHub URL.

**Optional but worth it (only true things):**
- Her real mornings / her real reaction, in her words, good and bad: one or two sentences at the OPTIONAL comment near the top of `ARTICLE.md` (and a "What she said" section in `README.md`). The article never claims she tried it. The pain-point paragraph is explicitly "design hypothesis"; if she has told you things that confirm or contradict it, that is the single most valuable edit.
- **Try it on her real photos on a real phone** (see "Not verified" below) and, if you do, update the first bullet in "Limits" (OPTIONAL comment there).
- One sentence on your own part in the build (the article only says the code was written with an AI coding agent under your direction).
- Screenshots: upload `docs/screenshot_today.png`, `docs/screenshot_wardrobe.png`, `docs/screenshot_add_clothes.png` in the DEV editor and paste them at the SCREENSHOT comment (optionally one as `cover_image`).
- Confirm `yichu` is your own wardrobe app (mentioned only in Limits / "Bring your own wardrobe").

## Look at it now
The server on port 8000 was restarted from the new code in demo mode: `.venv/bin/python -m todays_outfit --config config.example.toml --demo serve` (log `/tmp/serve.log`). That is the **example** wardrobe copy in `demo_data/` with a **synthetic** 14-day history, so you can tap Wear this / Show another / Add clothes safely. I pre-set the demo's city to **Shanghai** (in `demo_data/settings.json`, only a guess from your time zone): use *Change* on the Today card to set yours. For your own wardrobe run `python -m todays_outfit serve` (data goes to `./data/`, git-ignored; starts empty). `demo_data/` and `data/` are git-ignored.

## Publish steps
1. On GitHub create a **public** repo named `wardrobe-stylist` under your account (do not add a README/licence; the repo has them).
2. `git remote add origin <url> && git push -u origin HEAD` from `/workspace/wardrobe-stylist` (or copy the folder to your machine first). Check `git log --format='%an <%ae>'`: the author is `bian wu <noreply@example.invalid>`; set your real identity first if you care. Don't push anything you commit after 14:59 Beijing on Mon 2026-10-05 without listing it in README "Commits after the deadline".
3. Replace `REPO_URL` in `ARTICLE.md` and `README.md`, commit and push (before the deadline).
4. In DEV: create a new post from the challenge page's submission template (https://dev.to/challenges/hacktoberfest-weekend-2026-10-01), paste the body of `ARTICLE.md` (everything after the front matter), set the title from the front matter, and keep tags `devchallenge, weekendchallenge, hf26challenge, opensource` (max 4; the template may add its own).
5. Upload the three screenshots in the editor and paste them at the SCREENSHOT comment; optional cover image.
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
- **Real photos untested.** Accuracy numbers (vision table) are from my 21 drawings; the rotation numbers are a **simulation** with a made-up habit user and rules only (no model). They say the mechanism works; they say nothing about her closet.
- **The pain point is a hypothesis**, written as such. No data about her.
- **Vision endpoint flakiness:** while I built this, SiliconFlow's vision calls were sometimes slow (one photo ~14 s; one real e2e test hit its 120 s timeout once and passed on rerun). The Add form waits 45 s and then lets you type the fields. Open-Meteo returned HTTP 429 once during repeated screenshot runs; the app retries once and falls back to manual.
- **Local models (Ollama/llama.cpp) never run end to end**; no runtime on the box.
- **yichu importer** untested against your real DB (synthetic SQLite test only). I did not touch the NAS.
- No login on the web app (localhost by default; `--host 0.0.0.0` exposes it to your LAN).
- DevRelay session embed (optional in the rules): not done.

## Safety
- The SiliconFlow key is only read from the environment by the HTTP client. It is in no file, log, or doc (grepped the repo). `cache/`, `data/`, `demo_data/` are git-ignored; the committed `sample_wardrobe/descriptions.cache.json` holds only model descriptions of the drawings.
- Real calls made today: SiliconFlow (vision + text), Open-Meteo (geocoding "Shanghai" + forecast; coordinates of the city only). Nothing pushed, posted or sent. Files outside `/workspace/wardrobe-stylist`: scratch in `/tmp` only.
- Any commit after the deadline must be listed in README "Commits after the deadline".
