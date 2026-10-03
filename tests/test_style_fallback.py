from todays_outfit.llm import LLMError
from todays_outfit.style import suggest


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
