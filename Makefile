PY ?= .venv/bin/python

.PHONY: install test demo serve
install:
	python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"

test: install
	$(PY) -m pytest -q

# One command, bundled EXAMPLE data. Works offline (rules-only). If SILICONFLOW_API_KEY is set, a
# language model picks and explains the outfits; with no key it falls back to rules only, by design.
demo: install
	$(PY) -m todays_outfit suggest --temp 12 --rain --occasion commute
	$(PY) -m todays_outfit suggest --temp 26 --occasion date

serve: install
	$(PY) -m todays_outfit serve
