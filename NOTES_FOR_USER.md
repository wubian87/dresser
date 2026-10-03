# Notes for you (bian wu)

Do these before submitting. Deadline: **Mon 2026-10-05 14:59 Beijing time (06:59 UTC)**.

## TODOs only you can do
1. **"What she said"**: have your wife try it, then fill the TODO block in `README.md` ("What she said") and in `ARTICLE.md` ("What I Built"). Her real words only; I left both empty on purpose. The bonus is for actually handing it over.
2. **Repo URL**: create the public GitHub repo yourself (I pushed nothing), push, then replace every `TODO repo url` in `README.md` (clone line) and `ARTICLE.md` (Demo, Code).
   - Check `git log --format='%an <%ae>'`: commits use author `bian wu <noreply@example.invalid>`. Rewrite or set your real git identity if you care before pushing (rewriting history is your call; I did not do it).
3. **Screenshots**: upload `docs/screenshot_rainy_commute.png` (and optionally `docs/screenshot_warm_date.png`) to DEV and paste the URL in `ARTICLE.md` (Demo + `cover_image`). I could not upload anything.
4. **DEV handle / team**, and the `published: false` flag in the front matter (set to true or paste into DEV's submission template; the template adds the three required tags itself; DEV allows 4 tags max and the file has the 3 required + `opensource`).
5. **Your own voice** in `ARTICLE.md`: the TODO about her mornings, whether yichu holds her photos (I assumed it from your brief and marked it TODO), and one honest sentence about your part in the build.
6. **AI-assistance disclosure**: the article and README say the code was written with an AI coding agent under your direction. Keep, edit, or remove as true; AI use is allowed by the rules.

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
