import json
import random
from datetime import timedelta

from conftest import ROOT, TODAY, make_stylist
from todays_outfit.config import load_config
from todays_outfit.demo import init_demo
from todays_outfit.history import History
from todays_outfit.rules import build_outfits
from todays_outfit.service import Stylist
from todays_outfit.simulate import make_weather, seed_habit_history, simulate


def test_demo_copy_is_writable_and_history_is_marked_synthetic(tmp_path):
    cfg = load_config(ROOT / "config.example.toml")
    p = init_demo(tmp_path / "d", cfg, tmp_path / "c.json", today=TODAY)
    raw = json.loads((tmp_path / "d" / "history.json").read_text())
    assert "SYNTHETIC" in raw["_note"] and len(raw["wears"]) == 14
    assert raw["wears"][0]["date"] == "2026-09-19" and raw["wears"][-1]["date"] == "2026-10-02"
    st = Stylist(cfg, p, tmp_path / "c.json", today=lambda: TODAY)
    assert not st.readonly
    assert "_readonly" not in json.loads(p.read_text())
    assert json.loads((ROOT / "sample_wardrobe" / "wardrobe.json").read_text())["_readonly"] is True   # original untouched
    assert init_demo(tmp_path / "d", cfg, tmp_path / "c.json", today=TODAY) == p      # idempotent: no overwrite
    st.history.wear(TODAY, ["white-tee"]); st.history.save()
    init_demo(tmp_path / "d", cfg, tmp_path / "c.json", today=TODAY)
    assert History(tmp_path / "d" / "history.json").wear_on(TODAY) is not None


def test_seeded_history_is_rule_valid_and_deterministic(items):
    h1, fav, wx = seed_habit_history(items, TODAY, 14, seed=7)
    h2, fav2, _ = seed_habit_history(items, TODAY, 14, seed=7)
    assert h1.wears == h2.wears and fav == fav2
    for w in wx:
        e = h1.wear_on(w["date"])
        allowed = [set(c.ids) for c in build_outfits(items, w["temp"], w["rain"], w["occasion"])]
        assert e is None or set(e["items"]) in allowed          # every synthetic day is a rule-approved outfit


def test_weather_generator_is_plausible():
    wx = make_weather(random.Random(1), TODAY, 14)
    assert len(wx) == 14 and all(5 <= w["temp"] <= 26 for w in wx)
    assert sum(w["occasion"] == "date" for w in wx) == 1 and wx[0]["date"] == TODAY


def test_rotation_simulation_beats_no_rotation_on_repeats(items):
    """Real computed comparison on the example wardrobe over 10 seeds (rules only)."""
    runs = [simulate(items, s) for s in range(10)]
    for key in ("piece_repeats_vs_previous_day", "max_repeats_one_piece"):
        rot = sum(r["arms"]["rotation"][key] for r in runs)
        base = sum(r["arms"]["no_rot"][key] for r in runs)
        assert rot < base, (key, rot, base)
    cov = lambda arm: sum(r["arms"][arm]["share_of_wardrobe_worn"] for r in runs)  # noqa: E731
    assert cov("rotation") > cov("no_rot") and cov("rotation") > cov("habit")
    # rotation only re-ranks rule-approved outfits, so the rule score may drop a little but not collapse
    sc = lambda arm: sum(r["arms"][arm]["mean_rule_score"] for r in runs) / len(runs)  # noqa: E731
    assert sc("rotation") > sc("no_rot") - 1.5
    assert all(r["arms"]["rotation"]["relaxed_days"] == 0 for r in runs)
