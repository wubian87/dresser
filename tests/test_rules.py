import pytest

from dresser.rules import OCCASION_RULES, build_outfits, rain_unfriendly, target_warmth


def by_id(items, i):
    return next(x for x in items if x["id"] == i)


def valid_structure(o):
    cats = [i["category"] for i in o.items]
    core_ok = (cats.count("dress") == 1 and "top" not in cats and "bottom" not in cats) or \
              (cats.count("top") == 1 and cats.count("bottom") == 1 and "dress" not in cats)
    return core_ok and cats.count("shoes") == 1 and cats.count("outer") <= 1


@pytest.mark.parametrize("temp,rain,occ", [(30, False, "casual"), (18, False, "commute"), (12, True, "commute"),
                                           (8, False, "casual"), (22, False, "formal"), (25, False, "date")])
def test_every_outfit_is_structurally_complete(items, temp, rain, occ):
    outs = build_outfits(items, temp, rain, occ)
    assert outs, "sample wardrobe should cover these scenarios"
    assert all(valid_structure(o) for o in outs)


def test_rain_excludes_suede_and_canvas_shoes(items):
    outs = build_outfits(items, 14, True, "commute")
    shoes = {i["id"] for o in outs for i in o.items if i["category"] == "shoes"}
    assert "tan-suede-loafers" not in shoes and "white-sneakers" not in shoes
    assert shoes  # something remains


def test_dry_day_allows_suede(items):
    outs = build_outfits(items, 22, False, "commute", limit=100)
    assert any("tan-suede-loafers" in o.ids for o in outs)


def test_hot_day_has_no_heavy_layers(items):
    for o in build_outfits(items, 31, False, "casual", limit=50):
        assert "olive-puffer" not in o.ids and "grey-knit-sweater" not in o.ids and not any(i["category"] == "outer" for i in o.items)


def test_cold_day_requires_warm_outer(items):
    for o in build_outfits(items, 3, False, "casual", limit=50):
        outer = [i for i in o.items if i["category"] == "outer"]
        assert outer and outer[0]["warmth"] >= 3
        assert "khaki-shorts" not in o.ids


def test_formal_respects_dress_code(items):
    for o in build_outfits(items, 20, False, "formal", limit=50):
        assert all(i["formality"] >= 3 for i in o.items)
        assert "white-sneakers" not in o.ids and "mustard-hoodie" not in o.ids


def test_casual_excludes_formal_pieces(items):
    for o in build_outfits(items, 18, False, "casual", limit=50):
        assert all(i["formality"] <= 3 for i in o.items)


def test_results_sorted_and_diverse(items):
    outs = build_outfits(items, 16, False, "commute")
    assert [o.score for o in outs] == sorted((o.score for o in outs), reverse=True)
    for a in range(len(outs)):
        for b in range(a):
            assert len(set(outs[a].ids) & set(outs[b].ids)) < 3


def test_relaxes_instead_of_returning_nothing(items):
    outs = build_outfits(items, 5, True, "formal")
    assert outs and all(o.relaxed for o in outs)


def test_empty_wardrobe_gives_no_outfits():
    assert build_outfits([], 15, False, "casual") == []


def test_bad_occasion():
    with pytest.raises(ValueError):
        build_outfits([], 15, False, "beach")


def test_target_warmth_monotonic():
    assert target_warmth(30) < target_warmth(15) < target_warmth(0)


def test_rain_unfriendly_helper(items):
    assert rain_unfriendly(by_id(items, "tan-suede-loafers"))
    assert not rain_unfriendly(by_id(items, "yellow-rain-boots"))
    assert not rain_unfriendly(by_id(items, "brown-ankle-boots"))


def test_all_occasions_known():
    assert set(OCCASION_RULES) == {"commute", "casual", "date", "formal"}
