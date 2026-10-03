"""Configuration: ONE OpenAI-compatible endpoint abstraction, chosen by a preset.

Secrets never live in config. A preset only names the environment variable that holds the key.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PRESETS: dict[str, dict] = {
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_env": "SILICONFLOW_API_KEY",
        # Qwen3.5/3.6 "think" before answering by default; for a pick-from-a-list task that only costs seconds
        "text_extra_body": {"enable_thinking": False},
    },
    # Ollama's OpenAI-compatible endpoint; llama.cpp's `llama-server` uses http://localhost:8080/v1
    "local": {"base_url": "http://localhost:11434/v1", "api_key_env": ""},
}

DEFAULT_MODELS = {
    "siliconflow": {"vision": "Qwen/Qwen3-VL-30B-A3B-Instruct", "text": "Qwen/Qwen3.6-35B-A3B"},
    "local": {"vision": "qwen2.5vl:7b", "text": "qwen3:8b"},
}

PRIVACY_MODES = ("off", "images-local", "local-only")


@dataclass
class Endpoint:
    base_url: str
    model: str
    api_key_env: str = ""
    extra_body: dict = field(default_factory=dict)


@dataclass
class Config:
    vision: Endpoint
    text: Endpoint
    privacy: str = "off"
    language: str = "English"
    weather: dict = field(default_factory=dict)   # optional [weather]: city = "..." or lat/lon (+ name); default none = manual


def _endpoint(kind: str, section: dict, llm: dict) -> Endpoint:
    preset_name = section.get("preset") or llm.get("preset", "siliconflow")
    if preset_name not in PRESETS:
        raise ValueError(f"unknown preset {preset_name!r}; choose one of {sorted(PRESETS)}")
    preset = PRESETS[preset_name]
    model = section.get("model")
    if not model:
        # only fall back to the preset's default model if the section did not name its own preset
        model = DEFAULT_MODELS[preset_name][kind]
    return Endpoint(
        base_url=section.get("base_url", preset["base_url"]).rstrip("/"),
        model=model,
        api_key_env=section.get("api_key_env", preset["api_key_env"]),
        extra_body=dict(section.get("extra_body", preset.get("text_extra_body", {}) if kind == "text" else {})),
    )


def load_config(path: str | os.PathLike | None = None, privacy: str | None = None) -> Config:
    path = path or os.environ.get("TODAYS_OUTFIT_CONFIG") or "config.toml"
    data: dict = {}
    if Path(path).is_file():
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    llm = dict(data.get("llm", {}))
    if os.environ.get("TODAYS_OUTFIT_PRESET"):
        llm["preset"] = os.environ["TODAYS_OUTFIT_PRESET"]
    cfg = Config(
        vision=_endpoint("vision", data.get("vision", {}), llm),
        text=_endpoint("text", data.get("text", {}), llm),
        privacy=privacy or llm.get("privacy", "off"),
        language=llm.get("language", "English"),
        weather=dict(data.get("weather", {})),
    )
    if cfg.privacy not in PRIVACY_MODES:
        raise ValueError(f"privacy must be one of {PRIVACY_MODES}")
    return cfg
