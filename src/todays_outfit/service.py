"""Shared glue used by both the CLI and the web app."""
from __future__ import annotations

from pathlib import Path

from .config import Config
from .describe import Cache, describe_all
from .llm import LLMClient
from .style import suggest
from .wardrobe import load_wardrobe, merged


class Stylist:
    def __init__(self, cfg: Config, wardrobe_path, cache_path="cache/descriptions.json"):
        self.cfg = cfg
        self.items = load_wardrobe(wardrobe_path)
        self.cache = Cache(cache_path, seed=Path(wardrobe_path).parent / "descriptions.cache.json")
        self.vision = LLMClient(cfg.vision, cfg.privacy)
        self.text = LLMClient(cfg.text, cfg.privacy)
        self.load_cached()

    def load_cached(self):
        """Attach cached descriptions without calling any model."""
        from .describe import file_hash
        for it in self.items:
            it["hash"] = file_hash(it["image_path"])
            rec = self.cache.get(it["hash"], self.cfg.vision.model)
            if rec:
                it["desc"] = rec["desc"]

    def undescribed(self):
        return [i for i in self.items if "desc" not in i]

    def describe(self, progress=None) -> dict:
        todo = self.undescribed()
        return describe_all(self.vision, todo, self.cache, progress=progress)

    def described(self) -> list[dict]:
        return [m for m in (merged(i) for i in self.items) if m]

    def suggest(self, temp_c: float, rain: bool, occasion: str, use_model: bool = True) -> dict:
        res = suggest(self.described(), temp_c, rain, occasion, self.text if use_model else None, self.cfg.language)
        res["undescribed"] = len(self.undescribed())
        return res
