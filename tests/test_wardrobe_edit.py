import json

import pytest

from conftest import FakeVision, ROOT, TODAY, make_stylist, photo_bytes
from todays_outfit.cli import main
from todays_outfit.config import load_config
from todays_outfit.service import NotFound, ReadOnlyError, Stylist
from todays_outfit.wardrobe import is_example, photo_to_jpeg


def test_photo_is_reencoded_upright_without_metadata():
    from io import BytesIO
    from PIL import Image
    raw = photo_bytes(size=(60, 80), exif_orientation=6)          # phone says: rotate 90 degrees
    assert Image.open(BytesIO(raw)).size == (60, 80)
    out = photo_to_jpeg(raw)
    im = Image.open(BytesIO(out))
    assert im.format == "JPEG" and im.size == (80, 60) and not im.getexif()
    big = photo_to_jpeg(photo_bytes(size=(4000, 3000)))
    assert max(Image.open(BytesIO(big)).size) == 1600
    with pytest.raises(ValueError):
        photo_to_jpeg(b"definitely not an image")


def test_add_flow_describe_edit_before_save(tmp_path):
    st = make_stylist(tmp_path, demo=False)
    staged = st.stage_photo(photo_bytes("red"))
    assert staged["describe_error"] is None and staged["fields"]["type"] == "t-shirt"
    assert (st.staging / f"{staged['staging_id']}.jpg").is_file() and st.items == []   # not in the wardrobe yet
    f = {**staged["fields"], "type": "linen shirt", "color": "red", "warmth": 1, "name": "Red linen shirt"}   # user edits
    it = st.add_item(staged["staging_id"], f)
    assert it["id"] == "red-linen-shirt" and it["type"] == "linen shirt" and it["added"] == "2026-10-03"
    assert not list(st.staging.glob("*.jpg"))
    # persisted in wardrobe.json with the edited fields, photo copied into images/
    data = json.loads(st.path.read_text())
    assert data["items"][0]["warmth"] == 1 and (st.dir / data["items"][0]["image"]).is_file()
    # a new process sees it, described, without any model call
    st2 = Stylist(st.cfg, st.path, tmp_path / "cache" / "descriptions.json", today=lambda: TODAY)
    assert st2.undescribed() == [] and st2.described()[0]["name"] == "Red linen shirt"


def test_multi_upload_gets_unique_ids_and_duplicate_warning(tmp_path):
    st = make_stylist(tmp_path, demo=False)
    ids = []
    for c in ("red", "blue", "green"):
        s = st.stage_photo(photo_bytes(c))
        ids.append(st.add_item(s["staging_id"], {**s["fields"], "name": "Tee"})["id"])
    assert ids == ["tee", "tee-2", "tee-3"]
    again = st.stage_photo(photo_bytes("red"))
    assert again["duplicate_of"] == "tee"


def test_vision_failure_still_lets_user_fill_in_by_hand(tmp_path):
    class Boom(FakeVision):
        def chat(self, *a, **k):
            from todays_outfit.llm import LLMError
            raise LLMError("HTTP 500")
    st = make_stylist(tmp_path, demo=False, vision=Boom())
    s = st.stage_photo(photo_bytes())
    assert "Fill the fields in by hand" in s["describe_error"] and s["fields"]["type"] == ""
    it = st.add_item(s["staging_id"], {**s["fields"], "type": "jeans", "category": "bottom", "color": "blue"})
    assert it["category"] == "bottom"


def test_privacy_mode_blocks_cloud_vision_before_any_request(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("network call attempted"))
    cfg = load_config(ROOT / "config.example.toml", "images-local")
    st = make_stylist(tmp_path, demo=False, cfg=cfg)
    st.vision = Stylist(cfg, st.path, tmp_path / "c.json").vision          # the REAL client with the privacy guard
    s = st.stage_photo(photo_bytes())
    assert "images-local" in s["describe_error"] and "by hand" in s["describe_error"]
    assert st.add_item(s["staging_id"], {**s["fields"], "type": "shirt", "category": "top"})["type"] == "shirt"


def test_add_validates_fields(tmp_path):
    st = make_stylist(tmp_path, demo=False)
    s = st.stage_photo(photo_bytes())
    with pytest.raises(ValueError):
        st.add_item(s["staging_id"], {**s["fields"], "category": "spaceship"})
    with pytest.raises(NotFound):
        st.add_item("nope", s["fields"])
    with pytest.raises(NotFound):
        st.add_item("../../etc/passwd", s["fields"])


def test_edit_and_delete(tmp_path):
    st = make_stylist(tmp_path)          # demo copy with synthetic history
    n = len(st.items)
    st.update_item("blue-jeans", {"category": "bottom", "type": "jeans", "color": "dark blue", "warmth": 4, "name": "Good jeans"})
    v = {m["id"]: m for m in st.wardrobe_view()}
    assert v["blue-jeans"]["name"] == "Good jeans" and v["blue-jeans"]["warmth"] == 4
    assert json.loads(st.path.read_text())["items"][[i["id"] for i in st.items].index("blue-jeans")]["name"] == "Good jeans"
    used = [i for i, s in st.history.stats().items()][0]
    st.delete_item(used)
    assert len(st.items) == n - 1 and used not in {i for w in st.history.wears for i in w["items"]}
    with pytest.raises(NotFound):
        st.find(used)


def test_delete_removes_own_photo_but_never_a_referenced_one(tmp_path):
    st = make_stylist(tmp_path)
    s = st.stage_photo(photo_bytes())
    it = st.add_item(s["staging_id"], s["fields"])
    own = it["image_path"]
    assert own.is_file()
    st.delete_item(it["id"])
    assert not own.exists()
    keep = st.find("white-tee")["image_path"]                  # copied in place by the demo (not under images/)
    st.delete_item("white-tee")
    assert keep.exists()


def test_example_wardrobe_is_read_only():
    cfg = load_config(ROOT / "config.example.toml")
    st = Stylist(cfg, ROOT / "sample_wardrobe" / "wardrobe.json", ROOT / "cache" / "descriptions.json")
    assert is_example(st.path) and st.readonly
    with pytest.raises(ReadOnlyError):
        st.wear(["white-tee"])
    with pytest.raises(ReadOnlyError):
        st.stage_photo(photo_bytes())
    assert not (ROOT / "sample_wardrobe" / "history.json").exists()


def test_wear_stats_in_wardrobe_view(tmp_path):
    st = make_stylist(tmp_path)
    st.history.wears.clear()
    st.history.wear(TODAY.replace(day=1), ["white-tee"])
    st.history.wear(TODAY.replace(day=2), ["white-tee", "blue-jeans"])
    v = {m["id"]: m for m in st.wardrobe_view()}
    assert v["white-tee"]["wear_count"] == 2 and v["white-tee"]["last_worn"] == "2026-10-02" and v["white-tee"]["days_since"] == 1
    assert v["white-tee"]["badge"] is None
    assert v["black-trousers"]["badge"] is None and v["black-trousers"]["unworn_days"] == 2   # < 7 days: no badge yet
    st.history.wear(TODAY.replace(day=1) - __import__("datetime").timedelta(days=10), ["grey-knit-sweater"])
    v = {m["id"]: m for m in st.wardrobe_view()}
    assert v["grey-knit-sweater"]["badge"] == "not worn in 12 days" and v["grey-knit-sweater"]["badge_level"] == "mid"
    assert v["black-trousers"]["badge"] == "not worn in 12 days" and v["black-trousers"]["never_logged"]


def test_cli_add_wear_and_wardrobe(tmp_path, monkeypatch, capsys):
    from todays_outfit import service
    monkeypatch.setattr(service, "describe_image", lambda client, path: (FakeVision().desc, 0.1))
    p = tmp_path / "a.png"
    p.write_bytes(photo_bytes("red"))
    q = tmp_path / "b.png"
    q.write_bytes(photo_bytes("blue"))
    base = ["--config", str(ROOT / "config.example.toml"), "--data-dir", str(tmp_path / "d"), "--cache", str(tmp_path / "c.json")]
    assert main(base + ["add", str(p), str(q), "--color", "crimson"]) == 0
    out = capsys.readouterr().out
    assert "2 added" in out and "crimson t-shirt" in out
    assert main(base + ["wear", "crimson-t-shirt"]) == 0
    assert main(base + ["wardrobe"]) == 0
    out = capsys.readouterr().out
    assert "crimson-t-shirt" in out and "worn 1x" in out
    assert main(base + ["wear", "nope"]) == 1
    assert main(base + ["add", str(tmp_path / "missing.png"), "--category", "top", "--no-describe"]) == 1
    assert main(base + ["add", str(p), "--no-describe"]) == 1            # needs --category


def test_add_form_uses_a_shorter_vision_timeout_than_batch_describe(tmp_path, monkeypatch):
    from todays_outfit import service
    seen = []
    monkeypatch.setattr(service, "describe_image", lambda client, path: (seen.append(client.timeout), (FakeVision().desc, 0.1))[1])
    st = make_stylist(tmp_path, demo=False)
    st.vision = Stylist(st.cfg, st.path, tmp_path / "c.json").vision        # real client class (120 s default)
    assert st.vision.timeout == 120.0
    st.stage_photo(photo_bytes())
    assert seen == [Stylist.interactive_timeout] and Stylist.interactive_timeout < 120
