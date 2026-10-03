"""Season rooms and auto tags: deterministic rules, room filtering, the model stage with mocked models."""
import json
from datetime import date

import pytest

from conftest import FakeText, TODAY, make_stylist
from todays_outfit.llm import LLMError
from todays_outfit.rules import build_outfits
from todays_outfit.seasons import SEASONS, hemisphere, in_room, infer_seasons, suggest_season
from todays_outfit.tags import clean_tag, infer_tags, merge_tags, parse_model_tags, suggest_with_model


# ---------------- seasons ----------------
@pytest.mark.parametrize("d,lat,want", [
    (date(2026, 10, 3), None, "autumn"), (date(2026, 10, 3), 31.2, "autumn"), (date(2026, 10, 3), -33.9, "spring"),
    (date(2026, 12, 1), 40, "winter"), (date(2026, 12, 1), -34, "summer"), (date(2026, 3, 1), None, "spring"),
    (date(2026, 7, 15), 52, "summer"), (date(2026, 1, 31), 0, "winter"), (date(2026, 6, 1), -10, "winter")])
def test_suggest_season_by_date_and_hemisphere(d, lat, want):
    assert suggest_season(d, lat) == want
    assert hemisphere(lat) == ("south" if lat is not None and lat < 0 else "north")


def p(**k):
    return {"category": "top", "type": "t-shirt", "warmth": 3, **k}


@pytest.mark.parametrize("item,want", [
    (p(warmth=1), ["spring", "summer"]),
    (p(warmth=2), ["spring", "summer", "autumn"]),
    (p(warmth=3), ["spring", "autumn", "winter"]),
    (p(warmth=3, category="bottom", type="jeans"), ["spring", "summer", "autumn", "winter"]),
    (p(warmth=4, type="sweater"), ["autumn", "winter"]),
    (p(warmth=5, type="sweater"), ["winter"]),
    (p(warmth=3, category="bottom", type="khaki shorts"), ["spring", "summer"]),          # keyword override
    (p(warmth=3, category="shoes", type="sandals"), ["spring", "summer"]),
    (p(warmth=3, category="outer", type="wool coat"), ["autumn", "winter"]),
    (p(warmth="x"), ["spring", "autumn", "winter"]),                                       # junk warmth -> default 3
])
def test_infer_seasons_table(item, want):
    assert infer_seasons(item) == want


def test_own_season_list_wins_over_rules():
    assert in_room({**p(warmth=5), "season": ["summer"]}, "summer")
    assert not in_room({**p(warmth=5), "season": ["summer"]}, "winter")
    assert in_room(p(warmth=5), "winter")           # no own list -> rules


def test_each_piece_of_the_example_wardrobe_is_in_at_least_one_room(tmp_path):
    st = make_stylist(tmp_path)
    for m in st.described():
        assert m["season"], m["id"]
    sizes = {s: len(st.room(s)) for s in SEASONS}
    assert all(0 < n < len(st.described()) for n in (sizes["summer"], sizes["winter"])), sizes     # rooms really isolate


def test_season_defaults_from_date_then_override_persists(tmp_path):
    st = make_stylist(tmp_path)
    assert st.season_info()["current"] == "autumn" and st.season_info()["override"] is None
    st.set_season("summer")
    info = st.season_info()
    assert info["current"] == "summer" and info["auto"] == "autumn" and info["override"] == "summer"
    st2 = make_stylist(tmp_path)         # same data folder: setting survives a restart
    assert st2.season_info()["current"] == "summer"
    st2.set_season("auto")
    assert st2.season_info()["current"] == "autumn"
    with pytest.raises(ValueError):
        st2.set_season("monsoon")


def test_southern_hemisphere_city_flips_the_suggestion(tmp_path):
    from todays_outfit import weather as wx
    st = make_stylist(tmp_path)
    st.set_location(wx.Location("Sydney", -33.87, 151.2))
    info = st.season_info()
    assert info["auto"] == "spring" and info["hemisphere"] == "south"


def test_room_is_what_wardrobe_view_shows_and_what_styling_uses(tmp_path):
    st = make_stylist(tmp_path)
    st.set_season("winter")
    ids = {m["id"] for m in st.wardrobe_view()}
    assert ids == {m["id"] for m in st.room("winter")} and "khaki-shorts" not in ids and "yellow-sundress" not in ids
    res = st.suggest(2, False, "casual", use_model=False)
    used = {i["id"] for s in res["suggestions"] for i in s.items}
    assert used and used <= ids
    allv = {m["id"] for m in st.wardrobe_view("all")}
    assert allv == {m["id"] for m in st.described()} and len(allv) > len(ids)
    rooms = st.rooms_view()
    assert rooms["current"] == "winter" and rooms["in_room"] == len(ids) and rooms["total"] == len(allv)


def test_switching_season_switches_the_pick_and_today_card(tmp_path):
    st = make_stylist(tmp_path)
    st.set_season("summer")
    v = st.today_view(temp=28, rain=False, use_model=False)
    assert v["season"] == "summer" and v["suggestions"]
    summer = {m["id"] for m in st.room("summer")}
    assert {i["id"] for s in v["suggestions"] for i in s["items"]} <= summer
    st.set_season("winter")
    v2 = st.today_view(temp=3, rain=False, use_model=False)
    assert v2["season"] == "winter" and v2["outside_room"] > 0
    assert {i["id"] for s in v2["suggestions"] for i in s["items"]} <= {m["id"] for m in st.room("winter")}


def test_empty_room_says_so(tmp_path):
    st = make_stylist(tmp_path)
    for it in st.items:
        it["season"] = ["summer"]
    st.set_season("winter")
    v = st.today_view(temp=3, rain=False, use_model=False)
    assert v["suggestions"] == [] and "winter room" in v["warning"]


# ---------------- tags, stage 1 ----------------
def tg(**k):
    return {"category": "top", "type": "t-shirt", "color": "white", "material": "cotton", "warmth": 2, "formality": 2, **k}


@pytest.mark.parametrize("item,has,hasnt", [
    (tg(), {"casual", "neutral", "light", "cotton"}, {"work", "warm", "rain-ready"}),
    (tg(type="blazer", category="outer", formality=4, warmth=3, material="wool blend", color="black"), {"work", "layering", "neutral", "wool"}, {"casual", "light"}),
    (tg(type="rain boots", category="shoes", material="rubber", color="yellow", warmth=3), {"rain-ready", "colourful", "casual"}, {"neutral"}),
    (tg(type="suede loafers", category="shoes", material="suede", color="tan", formality=3), {"smart-casual", "not-for-rain"}, {"rain-ready"}),
    (tg(type="trench coat", category="outer", formality=4, warmth=3, color="beige", material="cotton"), {"rain-ready", "layering", "work"}, set()),
    (tg(type="sweater", material="wool knit", warmth=4, formality=3, color="grey"), {"warm", "knit", "wool", "smart-casual", "neutral"}, {"light"}),
    (tg(type="dress", category="dress", formality=5, warmth=2, color="navy"), {"formal", "dressy", "work"}, set()),
    (tg(type="hoodie", category="outer", warmth=3, color="mustard yellow", material="cotton blend"), {"sporty", "layering", "colourful"}, {"neutral"}),
    (tg(type="jeans", category="bottom", material="denim", warmth=3, color="blue"), {"denim", "casual"}, {"light"}),
])
def test_stage1_tags(item, has, hasnt):
    t = infer_tags(item)
    assert has <= set(t), t
    assert not (hasnt & set(t)), t
    assert len(t) == len(set(t)) <= 12


def test_stage1_is_deterministic_and_handles_junk():
    a = infer_tags(tg())
    assert a == infer_tags(tg())
    assert isinstance(infer_tags({}), list)
    assert infer_tags({"category": "top", "warmth": "abc", "formality": None})


def test_clean_and_merge_tags():
    assert clean_tag("  Smart Casual! ") == "smart-casual" and clean_tag("Rain_Ready") == "rain-ready"
    assert merge_tags(["a", "B"], ["b", "c", ""], "notalist") == ["a", "b", "c"]
    assert len(merge_tags([f"t{i}" for i in range(40)])) == 12


def test_tags_follow_the_item_unless_edited(tmp_path):
    st = make_stylist(tmp_path)
    v = {m["id"]: m for m in st.wardrobe_view()}
    assert "neutral" in v["black-trousers"]["tags"] and v["black-trousers"]["tags"] == v["black-trousers"]["tags_auto"]
    st.update_item("black-trousers", {**v["black-trousers"], "tags": ["my-fave", "Work"]})
    v = {m["id"]: m for m in st.wardrobe_view()}
    assert v["black-trousers"]["tags"] == ["my-fave", "work"] and v["black-trousers"]["tags_edited"]
    assert "neutral" in v["black-trousers"]["tags_auto"]


def test_tag_filter_counts_in_rooms_view(tmp_path):
    st = make_stylist(tmp_path)
    tags = {t["tag"]: t["n"] for t in st.rooms_view()["tags"]}
    assert tags["neutral"] == sum(1 for m in st.wardrobe_view() if "neutral" in m["tags"]) > 0


# ---------------- tags in styling (light nudge) ----------------
def test_occasion_tag_nudges_but_never_overrules_rules(items):
    base = build_outfits(items, 18, False, "commute")
    tagged = [{**i, "tags": ["work"] if i["id"] == "blue-oxford-shirt" else []} for i in items]
    nudged = build_outfits(tagged, 18, False, "commute")
    assert base and nudged
    s_base = {frozenset(c.ids): c.base_score for c in base}
    s_new = {frozenset(c.ids): c.base_score for c in nudged}
    diffs = [s_new[k] - s_base[k] for k in s_base if k in s_new and "blue-oxford-shirt" in k]
    assert diffs and all(0 < d <= 1.0 for d in diffs)
    other = [s_new[k] - s_base[k] for k in s_base if k in s_new and "blue-oxford-shirt" not in k]
    assert all(d == 0 for d in other)


def test_no_tags_no_nudge(items):
    a = build_outfits(items, 18, False, "commute")
    b = build_outfits([{**i, "tags": []} for i in items], 18, False, "commute")
    assert [(c.ids, c.base_score) for c in a] == [(c.ids, c.base_score) for c in b]


def test_tags_reach_the_model_prompt(tmp_path):
    ft = FakeText(json.dumps({"choices": [1]}))
    st = make_stylist(tmp_path, text=ft)
    st.suggest(14, False, "commute")
    assert ft.prompts and "tags:" in ft.prompts[0]


# ---------------- tags, stage 2 (mocked model) ----------------
class TagModel:
    def __init__(self, answer=None, exc=None):
        self.answer, self.exc, self.prompts = answer, exc, []

    def chat(self, messages, **k):
        self.prompts.append(messages[0]["content"])
        if self.exc:
            raise self.exc
        return self.answer


def test_parse_model_tags_dedupes_and_drops_existing():
    assert parse_model_tags('{"tags": ["Preppy", "preppy", "casual", "weekend", "Cosy!", ""]}', ["casual"]) == ["preppy", "weekend", "cosy"]
    assert parse_model_tags('```json\n{"tags": ["a","b","c","d","e","f","g"]}\n```') == list("abcde")        # at most 5
    assert parse_model_tags('["x", "y"]') == ["x", "y"]
    with pytest.raises(ValueError):
        parse_model_tags("sorry, no json")
    with pytest.raises(ValueError):
        parse_model_tags('{"tags": "preppy"}')


def test_suggest_with_model_returns_only_new_tags_and_prompt_lists_stage1():
    m = TagModel('{"tags": ["office", "casual", "cosy"]}')
    out = suggest_with_model(m, tg())
    assert out == ["office", "cosy"] and "Already tagged" in m.prompts[0] and "casual" in m.prompts[0]


def test_service_stage2_success_failure_and_privacy(tmp_path):
    st = make_stylist(tmp_path, text=TagModel('{"tags": ["preppy", "neutral"]}'))
    r = st.suggest_tags(tg(), use_model=True)
    assert r["model"] == ["preppy"] and "casual" in r["auto"] and r["seasons"] and r["error"] is None
    assert st.suggest_tags(tg(), use_model=False)["model"] == []             # stage 2 only on request
    st.text = TagModel(exc=LLMError("boom"))
    r = st.suggest_tags(tg(), use_model=True)
    assert r["model"] == [] and "boom" in r["error"] and r["auto"]            # stage 1 still returned
    st.text = TagModel("not json")
    assert "could not" in st.suggest_tags(tg(), use_model=True)["error"]


def test_stage2_refused_by_privacy_mode_but_stage1_works(tmp_path):
    from todays_outfit.config import load_config
    from todays_outfit.llm import LLMClient
    from conftest import ROOT
    cfg = load_config(ROOT / "config.example.toml", "local-only")
    st = make_stylist(tmp_path, cfg=cfg)
    st.text = LLMClient(cfg.text, cfg.privacy)          # real client: cloud endpoint + local-only -> must refuse before any request
    r = st.suggest_tags(tg(), use_model=True)
    assert r["model"] == [] and "local-only" in r["error"] and r["auto"]
