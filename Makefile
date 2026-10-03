PY ?= .venv/bin/python

.PHONY: install test demo serve serve-demo
install:
	python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"

test: install
	$(PY) -m pytest -q

# One command, bundled EXAMPLE data. Works offline (rules-only). If SILICONFLOW_API_KEY is set, a
# language model picks and explains the outfits; with no key it falls back to rules only, by design.
demo:
	./demo.sh

serve: install        # your own wardrobe in ./data (created empty on first run)
	$(PY) -m todays_outfit serve

serve-demo: install   # writable copy of the example wardrobe + SYNTHETIC 14-day history in ./demo_data
	$(PY) -m todays_outfit --demo serve
