"""Phone-sized screenshots of the real web app (headless Chrome via Playwright).

Dev-only helper, not needed to run the app:   pip install playwright   (uses your installed Google Chrome)
    python tools/screenshots.py      # SERVER_PY=/path/to/app/python if the app lives in another venv

It starts two throw-away servers (nothing in your own data folder is touched):
  1. the demo wardrobe (example drawings + SYNTHETIC 14-day history) with a REAL Open-Meteo forecast for a city
     -> docs/screenshot_today.png, docs/screenshot_wardrobe.png
  2. an empty wardrobe where two example drawings are uploaded through the real "Add clothes" form
     -> docs/screenshot_add_clothes.png
SILICONFLOW_API_KEY from the environment is used for the model calls if present (otherwise rules-only / manual fields).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PY = os.environ.get("SERVER_PY") or (str(ROOT / ".venv" / "bin" / "python") if (ROOT / ".venv").exists() else sys.executable)   # python that runs the app
CITY = os.environ.get("SHOT_CITY", "Shanghai")


def start(port: int, data: Path, cache: Path, extra=()) -> subprocess.Popen:
    p = subprocess.Popen([PY, "-m", "todays_outfit", "--config", str(ROOT / "config.example.toml"), "--data-dir", str(data),
                          "--cache", str(cache), *extra, "serve", "--port", str(port)], cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1)
            return p
        except Exception:
            time.sleep(0.5)
    p.kill()
    raise RuntimeError("server did not start")


def shot_today_and_wardrobe(ctx, tmp: Path, procs: list) -> None:
    procs.append(start(8765, tmp / "demo", tmp / "cache1" / "d.json", ["--demo"]))
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1:8765/")
    pg.wait_for_selector("#wxtoggle")
    pg.click("#wxtoggle")                                   # set the city once ...
    pg.fill("#city", CITY)
    pg.click("#findcity")
    pg.wait_for_selector("#cityres .chip")
    pg.click("#cityres .chip >> nth=0")                     # ... the real Open-Meteo forecast and the model pick follow
    pg.wait_for_selector("#wear", timeout=120000)
    pg.wait_for_timeout(1200)
    pg.evaluate("window.scrollTo(0,0)")
    pg.screenshot(path=str(ROOT / "docs" / "screenshot_today.png"))
    pg.evaluate("document.querySelector('.whead').scrollIntoView()")
    pg.wait_for_timeout(800)
    pg.screenshot(path=str(ROOT / "docs" / "screenshot_wardrobe.png"))


def shot_add_clothes(ctx, tmp: Path, procs: list) -> None:
    procs.append(start(8766, tmp / "empty", tmp / "cache2" / "d.json"))
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1:8766/")
    pg.wait_for_selector("#addbtn")
    pg.click("#addbtn")
    pg.set_input_files("#fpick", [str(ROOT / "sample_wardrobe" / "blue-jeans.png"), str(ROOT / "sample_wardrobe" / "white-sneakers.png")])
    pg.wait_for_selector("#d1_save", timeout=240000)        # photos are described one after the other
    pg.wait_for_selector("#d2_save", timeout=240000)
    pg.click("#d1_save")                                    # first piece saved, the second still waits for review
    pg.wait_for_timeout(1000)
    pg.evaluate("document.querySelector('#addsheet').scrollTo(0,0)")
    pg.screenshot(path=str(ROOT / "docs" / "screenshot_add_clothes.png"))


def main() -> None:
    only = sys.argv[1:] or ["today", "add"]                 # e.g. `python tools/screenshots.py add`
    tmp = Path(tempfile.mkdtemp(prefix="shots_"))
    procs: list = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=shutil.which("google-chrome") or "/usr/bin/google-chrome", args=["--no-sandbox"])
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            if "today" in only:
                shot_today_and_wardrobe(ctx, tmp, procs)
            if "add" in only:
                shot_add_clothes(ctx, tmp, procs)
            b.close()
    finally:
        for p in procs:
            p.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
