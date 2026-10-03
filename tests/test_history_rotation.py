from datetime import date, timedelta

from conftest import FakeText, TODAY, make_stylist
from dresser.history import History
from dresser.rotation import Rotation, RotationPolicy, history_claims
from dresser.rules import build_outfits
from dresser.style import suggest


def d(n):
    return TODAY - timedelta(days=n)


def test_history_wear_replace_merge_unwear_and_persist(tmp_path):
    h = History(tmp_path / "h.json")
    h.wear(d(1), ["a", "b"], "commute")
    h.wear(d(1), ["c"], "casual")                      # one entry per day: replaced
    assert h.wear_on(d(1))["items"] == ["c"]
    h.wear(d(1), ["a"], merge=True)                   # "I wore this too": merged
    assert h.wear_on(d(1))["items"] == ["c", "a"] and h.wear_on(d(1))["occasion"] == "casual"
    h.skip(d(0), ["a", "c"], "casual")
    h.save()
    h2 = History(tmp_path / "h.json")
    assert h2.wears == h.wears and len(h2.skips) == 1
    assert h2.unwear(d(1)) and not h2.unwear(d(1))


def test_history_stats_and_damaged_file(tmp_path):
    h = History()
    h.wear(d(10), ["a", "b"])
    h.wear(d(3), ["a"])
    st = h.stats()
    assert st["a"].wear_count == 2 and st["a"].last_worn == d(3) and st["a"].days_since(TODAY) == 3
    assert st["b"].days_since(TODAY) == 10
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert History(bad).wears == []                   # never crashes the app


def test_history_forget_deleted_items():
    h = History()
    h.wear(d(2), ["a", "b"])
    h.wear(d(1), ["b"])
    h.skip(d(1), ["a", "b"])
    h.forget_items({"b"})
    assert h.wear_on(d(2))["items"] == ["a"] and h.wear_on(d(1)) is None and h.skips == []


def test_rotation_penalises_yesterday_and_rewards_neglect(items):
    h = History()
    h.wear(d(1), ["black-trousers"])
    h.wear(d(3), ["white-tee"])
    h.wear(d(20), ["blue-jeans"])
    rot = Rotation(h, TODAY, policy=RotationPolicy())
    by = {i["id"]: i for i in items}
    p = RotationPolicy()
    assert rot.adjust([by["black-trousers"]]) < rot.adjust([by["white-tee"]]) < 0.6
    assert rot.adjust([by["black-trousers"]]) <= -p.yesterday_penalty + 0.6
    # a piece last worn 20 days ago gets almost the full bonus (capped at 0.5 from 21 days)
    assert 0.4 < rot.adjust([by["blue-jeans"]]) <= p.neglect_bonus
    # a never-worn piece counts from when logging began (20 days ago), not from forever
    assert rot.unworn_days("grey-knit-sweater") == 20


def test_no_history_means_no_adjustment(items):
    rot = Rotation(History(), TODAY)
    assert all(rot.adjust([i]) == 0 for i in items)
    assert rot.facts(items[:2])["note"] == ""


def test_rotation_avoids_yesterdays_pieces_when_alternatives_exist(items):
    base = build_outfits(items, 16, False, "commute")
    top = base[0]
    h = History()
    h.wear(d(1), top.ids)
    rot = Rotation(h, TODAY)
    res = suggest(items, 16, False, "commute", None, rotation=rot)
    first = res["suggestions"][0]
    assert not set(i["id"] for i in first.items) & set(top.ids), "top pick should not repeat any of yesterday's pieces"
    assert "Repeats" not in first.note


def test_rotation_never_admits_rule_forbidden_outfits(items):
    h = History()
    h.wear(d(14), ["white-tee"])                       # history exists, suede loafers never worn -> big neglect bonus
    rot = Rotation(h, TODAY)
    for o in build_outfits(items, 12, True, "commute", adjust=rot.adjust):
        assert "tan-suede-loafers" not in o.ids and "white-sneakers" not in o.ids   # rain rule still wins
    for o in build_outfits(items, 30, False, "casual", adjust=rot.adjust):
        assert "olive-puffer" not in o.ids                                          # heat rule still wins


def test_note_is_computed_and_true(items):
    h = History()
    h.wear(d(1), ["black-trousers"])
    h.wear(d(20), ["grey-knit-sweater"])
    rot = Rotation(h, TODAY)
    by = {i["id"]: i for i in items}
    f = rot.facts([by["grey-knit-sweater"], by["black-trousers"], by["white-tee"]])
    assert "grey-knit-sweater" not in f["note"]        # uses names, not ids
    assert "not worn for 19 days" in f["note"] or "not worn for 20 days" in f["note"]
    assert "worn yesterday" in f["note"]
    assert f["recent"] == [by["black-trousers"]["name"]]
    f2 = rot.facts([by["grey-knit-sweater"], by["white-tee"]])
    assert "Repeats" not in f2["note"] and "Nothing in it was worn in the last 3 days." in f2["note"]


def test_note_says_nothing_recent_only_when_true(items):
    h = History()
    h.wear(d(8), ["black-trousers"])
    rot = Rotation(h, TODAY)
    by = {i["id"]: i for i in items}
    assert "Nothing in it was worn in the last 3 days." in rot.facts([by["black-trousers"]])["note"]
    h.wear(d(2), ["white-tee"])
    assert "Nothing in it" not in Rotation(h, TODAY).facts([by["white-tee"]])["note"]


def test_skip_penalty_hits_exact_combo_and_fades(items):
    top = build_outfits(items, 16, False, "commute")[0]
    h = History()
    h.skip(d(0), top.ids)
    h.wear(d(30), ["white-tee"])
    rot = Rotation(h, TODAY)
    assert rot.adjust(top.items) < rot.adjust(top.items[:-1]) - 2     # exact combo is penalised, a subset is not
    assert build_outfits(items, 16, False, "commute", adjust=rot.adjust)[0].ids != top.ids
    later = Rotation(h, TODAY + timedelta(days=14))
    assert later.adjust(top.items) > rot.adjust(top.items)            # penalty has faded
    assert abs(later.adjust(top.items)) < 3


def test_history_words_in_model_reason_are_dropped(items):
    top = build_outfits(items, 16, False, "commute")
    ok = "Light layers for a mild day."
    assert history_claims("You haven't worn this recently.") and history_claims("a nice rotation of pieces")
    assert not history_claims(ok)
    answers = '{"outfits":[{"candidate":0,"reason":"You wore the other one yesterday so this is fresh."}]}'
    res = suggest(items, 16, False, "commute", _Fake(answers), rotation=Rotation(History(), TODAY))
    assert res["mode"] == "rules"                       # the invented history claim was rejected, fell back


class _Fake(FakeText):
    pass


def test_model_is_not_told_the_history_and_gets_fresh_candidates(items):
    top = build_outfits(items, 16, False, "commute")[0]
    h = History()
    h.wear(d(1), top.ids)
    fake = FakeText('{"outfits":[{"candidate":0,"reason":"A calm, light combination."}]}')
    res = suggest(items, 16, False, "commute", fake, rotation=Rotation(h, TODAY))
    assert res["mode"] == "model"
    prompt = fake.prompts[0]
    assert "yesterday" not in prompt.lower().replace("do not mention what she wore before", "")
    picked = {i["id"] for i in res["suggestions"][0].items}
    assert not picked & set(top.ids)


def test_pad_with_rules_fills_up_to_three(items):
    fake = FakeText('{"outfits":[{"candidate":0,"reason":"A calm, light combination."}]}')
    res = suggest(items, 16, False, "commute", fake, pad_with_rules=True)
    assert [s.source for s in res["suggestions"]] == ["model", "rules", "rules"]
    assert len({frozenset(i["id"] for i in s.items) for s in res["suggestions"]}) == 3
