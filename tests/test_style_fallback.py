from dresser.llm import LLMError
from dresser.style import suggest


class FakeClient:
    last_latency = 0.1

    def __init__(self, answer=None, error=None):
        self.answer, self.error = answer, error

    def chat(self, *a, **k):
        if self.error:
            raise self.error
        return self.answer


def test_model_choice_is_used(items):
    res = suggest(items, 16, False, "commute", FakeClient('{"outfits":[{"candidate":1,"reason":"Nice and light."}]}'))
    assert res["mode"] == "model" and res["suggestions"][0].reason == "Nice and light."
    assert res["suggestions"][0].source == "model"


def test_invalid_json_falls_back_to_rules(items):
    res = suggest(items, 16, False, "commute", FakeClient("I think you should wear the blue one!"))
    assert res["mode"] == "rules" and 1 <= len(res["suggestions"]) <= 3 and res["warning"]
    assert all("rule-based" in s.reason for s in res["suggestions"])


def test_out_of_range_candidate_falls_back(items):
    res = suggest(items, 16, False, "commute", FakeClient('{"outfits":[{"candidate":999,"reason":"x"}]}'))
    assert res["mode"] == "rules"


def test_network_error_falls_back(items):
    res = suggest(items, 16, False, "commute", FakeClient(error=LLMError("boom")))
    assert res["mode"] == "rules"


def test_no_client_is_rules_only(items):
    assert suggest(items, 16, False, "commute", None)["mode"] == "rules"


def test_nothing_fits(items):
    res = suggest([i for i in items if i["category"] == "shoes"], 16, False, "commute", None)
    assert res["mode"] == "none" and res["suggestions"] == []


def test_ungrounded_reason_is_dropped(items):
    from dresser.rules import build_outfits
    from dresser.style import ungrounded_terms
    o = build_outfits(items, 16, False, "commute")[0]
    assert ungrounded_terms("Looks smart with the " + o.items[0]["type"], o.items) == []
    assert ungrounded_terms("Much better than a puffer jacket and sandals", [i for i in o.items if i["category"] == "top"]) == ["jacket", "sandal"]


def test_all_ungrounded_falls_back(items):
    res = suggest(items, 20, False, "formal", FakeClient('{"outfits":[{"candidate":0,"reason":"Perfect with cozy jeans and sneakers."}]}'))
    assert res["mode"] == "rules"


def test_mixed_picks_keep_grounded_only(items):
    from dresser.rules import build_outfits
    cands = build_outfits(items, 20, False, "formal")
    ok = "Elegant: " + cands[1].items[0]["type"]
    res = suggest(items, 20, False, "formal", FakeClient('{"outfits":[{"candidate":0,"reason":"Great with jeans."},{"candidate":1,"reason":"%s"}]}' % ok))
    assert res["mode"] == "model" and len(res["suggestions"]) == 1 and res["dropped_ungrounded"] == 1


def test_ungrounded_has_no_false_positives(items):
    from dresser.style import ungrounded_terms
    shoes = [i for i in items if i["id"] == "black-flats"]
    assert ungrounded_terms("It flatters the dress code and is dressy enough.", shoes) == []
