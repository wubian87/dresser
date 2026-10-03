#!/usr/bin/env bash
# One-command check using the bundled EXAMPLE wardrobe (synthetic illustrations).
# Works offline: without an API key the app runs rules-only. With SILICONFLOW_API_KEY set
# (and config.example.toml as the config) a language model picks and explains the outfits.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -e ".[dev]"
.venv/bin/python -m pytest -q
CFG=()
[ -f config.toml ] || CFG=(--config config.example.toml)
.venv/bin/python -m dresser "${CFG[@]}" suggest --temp 12 --rain --occasion commute --season autumn
.venv/bin/python -m dresser "${CFG[@]}" suggest --temp 26 --occasion date --season summer
# Same wardrobe, now with a SYNTHETIC 14-day wear history (writable copy in ./demo_data): the pick avoids what was just
# worn, and the "Rotation:" line under each outfit is computed from that log. Manual weather, rules only: works offline.
.venv/bin/python -m dresser "${CFG[@]}" --demo today --temp 14 --rain --occasion commute --rules-only
# With a network: the same demo copy, today's REAL forecast for the default demo city (Shanghai; only its coordinates are sent
# to Open-Meteo). Without a network this prints a short message instead and the script still succeeds.
.venv/bin/python -m dresser "${CFG[@]}" --demo today --occasion casual --rules-only || echo "(no forecast: offline? the two runs above used a typed temperature)"
echo "Web page: .venv/bin/python -m dresser --demo serve   (then open http://127.0.0.1:8000)"
