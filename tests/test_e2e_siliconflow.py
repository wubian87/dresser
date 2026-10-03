"""REAL end-to-end test against SiliconFlow (open-weight models). Skipped automatically without SILICONFLOW_API_KEY.

Run: SILICONFLOW_API_KEY=... pytest tests/test_e2e_siliconflow.py -v
"""
import os
from pathlib import Path

import pytest

from todays_outfit.config import load_config
from todays_outfit.describe import describe_image
from todays_outfit.llm import LLMClient
from todays_outfit.service import Stylist

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not os.environ.get("SILICONFLOW_API_KEY"), reason="no SILICONFLOW_API_KEY")


def test_describe_one_photo_for_real():
    cfg = load_config(ROOT / "config.example.toml")
    d, secs = describe_image(LLMClient(cfg.vision), ROOT / "sample_wardrobe/yellow-rain-boots.png")
    assert d["category"] == "shoes" and "boot" in d["type"] and "yellow" in d["color"]
    assert 1 <= d["warmth"] <= 5 and 1 <= d["formality"] <= 5


def test_style_for_real_picks_via_model_not_fallback(tmp_path):
    cfg = load_config(ROOT / "config.example.toml")
    st = Stylist(cfg, ROOT / "sample_wardrobe/wardrobe.json", tmp_path / "c.json")  # uses the bundled real descriptions
    assert not st.undescribed()
    res = st.suggest(12, True, "commute")
    assert res["mode"] == "model", res.get("warning")
    assert 1 <= len(res["suggestions"]) <= 3
    for s in res["suggestions"]:
        assert not any(i["id"] == "tan-suede-loafers" for i in s.items)  # rain rule held
        assert s.reason
