# Notes for you (bian wu)

Do these before submitting. Deadline: **Mon 2026-10-05 14:59 Beijing time (06:59 UTC)**.

## Only you can supply (everything else is done)
Article and README are written so they read fine **without** the optional items; optional items are invisible `<!-- OPTIONAL ... -->` comments, so leaving them in does not break the page.

**Mandatory (1 thing):**
- **Repo URL**: replace every `REPO_URL` (2 places in `ARTICLE.md`, 1 in `README.md`) with your public GitHub URL.

**Optional but worth it (the "for a friend" proof; only true things):**
- Her real mornings / her real reaction, in her words, good and bad: one or two sentences at the OPTIONAL comment near the top of `ARTICLE.md` (and a "What she said" section in `README.md`). I invented nothing about her and the article never claims she tried it. If she has not, say nothing.
- If you run it on her real photos: update the first bullet in "Limits" (the OPTIONAL comment there).
- One sentence on your own part in the build (the article only says the code was written with an AI coding agent under your direction; edit or keep as true).
- Screenshot: upload `docs/screenshot_rainy_commute.png` in the DEV editor and paste it at the SCREENSHOT comment (optionally also as `cover_image`).
- Your DEV handle / team: DEV fills this in from your account; nothing to edit in the file.
- Confirm `yichu` is your own wardrobe app (the article mentions it only in Limits, as an importer that is untested against your real DB).

## Publish steps
1. On GitHub create a **public** repo named `wardrobe-stylist` under your account (do not add a README/licence; the repo has them).
2. `git remote add origin <url> && git push -u origin HEAD` from `/workspace/wardrobe-stylist` (or copy the folder to your machine first). Check `git log --format='%an <%ae>'`: the author is `bian wu <noreply@example.invalid>`; set your real identity first if you care. Don't push anything you commit after 14:59 Beijing on Mon 2026-10-05 without listing it in README "Commits after the deadline".
3. Replace `REPO_URL` in `ARTICLE.md` and `README.md`, commit and push (before the deadline).
4. In DEV: create a new post from the challenge page's submission template (https://dev.to/challenges/hacktoberfest-weekend-2026-10-01), paste the body of `ARTICLE.md` (everything after the front matter), set the title from the front matter, and keep tags `devchallenge, weekendchallenge, hf26challenge, opensource` (max 4; the template may add its own).
5. Upload `docs/screenshot_rainy_commute.png` in the editor and paste it at the SCREENSHOT comment; optional cover image.
6. Click **Preview**: check the code blocks and table render, and that no `REPO_URL` is left. Then publish. Deadline **Mon 2026-10-05 14:59 Beijing (06:59 UTC)**; aim for Sunday.

## Reader test (weak signal only)
`docs/reader_test/` holds raw outputs of 3 SiliconFlow models (Qwen3.6-35B-A3B, DeepSeek-V4-Flash, GLM-4.5-Air) playing a tired judge, on the old draft (`v1_*`) and the revised one (`v2_*`). Rerun with `.venv/bin/python tools/reader_test.py ARTICLE.md TAG`. These are AI opinions, not judges; they mostly confirmed that unfinished placeholders hurt and that the rules-first idea reads clearly.

## Decisions I made (change if you disagree)
- **Vision default = Qwen/Qwen3-VL-30B-A3B-Instruct**, text default = **Qwen/Qwen3.6-35B-A3B with thinking off** (SiliconFlow `enable_thinking: false`). Measurements in `docs/vision_eval.*`, `docs/style_eval.*`. Qwen3.5-27B responded but was slow (12 s off, timeouts on).
- **Privacy modes**: `off`, `images-local` (photos only to localhost), `local-only` (nothing leaves localhost). The brief asked for images-only; I added the stricter one.
- **Prize categories**: none claimed (no partner tech used, no Gemma).
- **Hallucination guard**: model reasons naming garments not in the outfit are dropped. Added after I saw it happen in a real run.
- Sample wardrobe is my own Pillow drawings; the vision model misreads a few (see Limits). I did **not** hand-correct them, to keep the numbers honest.
- Config: `config.example.toml` is what the demo uses; copy to `config.toml` for your own setup (`config.toml` has no secrets, only the *name* of the env var).

## Not done / unverified
- **Local models (Ollama/llama.cpp) never run end to end**; no runtime on the box. The README and article say so. If you can run one on your machine for 5 minutes (`preset = "local"`, pull a vision model), you can measure it and turn the claim into a number.
- **yichu importer** is untested against your real DB/schema (column defaults are guesses); only a synthetic SQLite test. I did not touch the NAS.
- All accuracy numbers come from synthetic drawings, not real clothes photos.
- Web page tested via headless Chrome screenshots only, not on a real phone.
- DevRelay session embed (optional in the rules): not done.

## Safety
- The SiliconFlow key was only read from the environment by the HTTP client. It is in no file, log, or doc (I grepped the repo). `cache/` is gitignored; the committed `sample_wardrobe/descriptions.cache.json` holds only model descriptions of the drawings.
- Nothing pushed, posted or sent. No files outside `/workspace/wardrobe-stylist` except scratch in `/tmp`.
- Any commit after the deadline must be listed in README "Commits after the deadline".
