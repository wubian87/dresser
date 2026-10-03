import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def items():
    """Sample wardrobe with the hand-written ground truth as descriptions (no network needed)."""
    gt = json.loads((ROOT / "sample_wardrobe/ground_truth.json").read_text())
    return [dict(id=k, category=v["cat"], type=v["type"], color=v["color"], material=v["material"],
                 warmth=v["warmth"], formality=v["formality"], notes="", name=f"{v['color']} {v['type']}")
            for k, v in gt.items()]
