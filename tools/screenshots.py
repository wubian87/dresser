"""Phone-sized screenshots of the real web app (headless Chrome via Playwright).

Dev-only helper, not needed to run the app:   pip install playwright   (uses your installed Google Chrome)
    python tools/screenshots.py      # SERVER_PY=/path/to/app/python if the app lives in another venv

It starts two throw-away servers (nothing in your own data folder is touched):
  1. the demo wardrobe (example drawings + SYNTHETIC 14-day history) with a REAL Open-Meteo forecast for Shanghai
     -> docs/screenshot_today.png, docs/screenshot_wardrobe.png, docs/screenshot_settings.png
  2. an empty wardrobe where a REAL public product page ($SHOT_LINK) is imported through "Add clothes > Paste a link"
     -> docs/screenshot_add_link.png
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
    p = subprocess.Popen([PY, "-m", "dresser", "--config", str(ROOT / "config.example.toml"), "--data-dir", str(data),
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


LINK = os.environ.get("SHOT_LINK", "https://www.allbirds.com/products/mens-tree-runners")      # a real public product page
SHANGHAI = {"name": "Shanghai, Shanghai Municipality, China", "lat": 31.22222, "lon": 121.45806}


def put_json(url: str, body: dict) -> None:
    import json
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def shot_today_wardrobe_settings(ctx, tmp: Path, procs: list) -> None:
    procs.append(start(8765, tmp / "demo", tmp / "cache1" / "d.json", ["--demo"]))
    put_json("http://127.0.0.1:8765/api/settings/location", SHANGHAI)       # real Open-Meteo forecast follows
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1:8765/#today")
    pg.wait_for_selector("#wear", timeout=120000)                             # the model's pick has arrived
    pg.wait_for_timeout(1200)
    pg.screenshot(path=str(ROOT / "docs" / "screenshot_today.png"))
    pg.click(".tabs button[data-tab=wardrobe]")
    pg.wait_for_selector(".tile")
    pg.wait_for_timeout(1200)
    pg.screenshot(path=str(ROOT / "docs" / "screenshot_wardrobe.png"))
    pg.click(".tabs button[data-tab=settings]")
    pg.wait_for_selector(".opt")
    pg.click("#v-settings details.more summary")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(ROOT / "docs" / "screenshot_settings.png"), full_page=True)


def shot_add_link(ctx, tmp: Path, procs: list) -> None:
    procs.append(start(8766, tmp / "empty", tmp / "cache2" / "d.json"))
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1:8766/#wardrobe")
    pg.wait_for_selector("#fab:not([hidden])")
    pg.click("#fab")
    pg.click("#seg button[data-m=link]")
    pg.fill("#url", LINK)
    pg.click("#fetchlink")
    pg.wait_for_selector("#d1_save", timeout=240000)                          # page read, picture downloaded, vision done
    pg.wait_for_timeout(1000)
    pg.evaluate("document.querySelector('#addsheet').scrollTo(0,0)")
    pg.screenshot(path=str(ROOT / "docs" / "screenshot_add_link.png"))


def main() -> None:
    only = sys.argv[1:] or ["today", "add"]                 # e.g. `python tools/screenshots.py add`
    tmp = Path(tempfile.mkdtemp(prefix="shots_"))
    procs: list = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=shutil.which("google-chrome") or "/usr/bin/google-chrome", args=["--no-sandbox"])
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            if "today" in only:
                shot_today_wardrobe_settings(ctx, tmp, procs)
            if "add" in only:
                shot_add_link(ctx, tmp, procs)
            b.close()
    finally:
        for p in procs:
            p.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
