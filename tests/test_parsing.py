import pytest

from todays_outfit.describe import normalize
from todays_outfit.jsonparse import extract_json
from todays_outfit.style import parse_choice


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_json():
    assert extract_json('Sure!\n```json\n{"a": [1, 2]}\n```\nbye') == {"a": [1, 2]}


def test_think_block_and_chatter():
    assert extract_json('<think>hmm {not json}</think> Here: {"a": "x}y"} thanks') == {"a": "x}y"}


def test_garbage_raises():
    for bad in ("", "no json here", "{broken"):
        with pytest.raises(ValueError):
            extract_json(bad)


def test_normalize_clamps_and_cleans():
    d = normalize({"category": "TOP", "type": "T-Shirt", "color": "White", "warmth": 9, "formality": "0",
                   "season": "summer", "material": "Cotton"})
    assert d["category"] == "top" and d["warmth"] == 5 and d["formality"] == 1 and d["season"] == ["summer"]


def test_normalize_defaults_and_rejects():
    d = normalize({"category": "shoes", "warmth": "abc"})
    assert d["warmth"] == 3 and set(d["season"]) == {"spring", "summer", "autumn", "winter"}
    with pytest.raises(ValueError):
        normalize({"category": "hat?"})
    with pytest.raises(ValueError):
        normalize("not a dict")


def test_parse_choice_valid():
    out = parse_choice('{"outfits":[{"candidate":2,"reason":"warm"},{"candidate":0,"reason":"light"}]}', 5)
    assert out == [(2, "warm"), (0, "light")]


def test_parse_choice_filters_bad_entries_and_limits():
    txt = '{"outfits":[{"candidate":9,"reason":"x"},{"candidate":1,"reason":""},{"candidate":1,"reason":"ok"},{"candidate":1,"reason":"dup"},' \
          '{"candidate":2,"reason":"a"},{"candidate":3,"reason":"b"},{"candidate":4,"reason":"c"}]}'
    assert parse_choice(txt, 5) == [(1, "ok"), (2, "a"), (3, "b")]


def test_parse_choice_unusable():
    for bad in ('{"outfits": []}', '{"x": 1}', '{"outfits":[{"candidate":"nine","reason":"a"}]}', "nonsense"):
        with pytest.raises(ValueError):
            parse_choice(bad, 3)
