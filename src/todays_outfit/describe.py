"""Step 1 - 'describe': a vision model turns each clothing photo into structured JSON."""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .jsonparse import extract_json
from .llm import LLMClient, LLMError, PrivacyError, image_to_data_url

CATEGORIES = ("top", "bottom", "dress", "outer", "shoes", "accessory")
SEASONS = ("spring", "summer", "autumn", "winter")

PROMPT = """You are cataloguing a wardrobe. Look at this single clothing photo and answer with ONE JSON object only, no prose, with exactly these keys:
{
 "category": one of "top","bottom","dress","outer","shoes","accessory"  (outer = jacket/coat/blazer worn over a top),
 "type": short garment name, e.g. "t-shirt", "jeans", "trench coat", "ankle boots",
 "color": main color in 1-2 words,
 "material": best guess of the material in 1-3 words (e.g. "cotton", "wool knit", "leather", "suede", "rubber", "canvas", "denim", "nylon"),
 "warmth": integer 1-5 (1 = very light summer piece, 3 = mild weather, 5 = heavy winter piece),
 "formality": integer 1-5 (1 = gym/lounge, 2 = casual, 3 = smart casual, 4 = office/business, 5 = formal/evening),
 "season": list of any of "spring","summer","autumn","winter",
 "notes": one short sentence about notable details (pattern, waterproof, fit)
}"""


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def normalize(raw: dict) -> dict:
    """Validate/clean a model's answer. Raises ValueError if it is unusable."""
    if not isinstance(raw, dict):
        raise ValueError("not an object")
    cat = str(raw.get("category", "")).strip().lower()
    if cat not in CATEGORIES:
        raise ValueError(f"bad category {cat!r}")

    def clamp(v, default):
        try:
            return max(1, min(5, int(round(float(v)))))
        except (TypeError, ValueError):
            return default

    seasons = raw.get("season", [])
    if isinstance(seasons, str):
        seasons = [seasons]
    seasons = [s.strip().lower() for s in seasons if isinstance(s, str) and s.strip().lower() in SEASONS]
    return {
        "category": cat,
        "type": str(raw.get("type", "")).strip().lower()[:40] or cat,
        "color": str(raw.get("color", "")).strip().lower()[:30] or "unknown",
        "material": str(raw.get("material", "")).strip().lower()[:40],
        "warmth": clamp(raw.get("warmth"), 3),
        "formality": clamp(raw.get("formality"), 3),
        "season": seasons or list(SEASONS),
        "notes": str(raw.get("notes", "")).strip()[:160],
    }


class Cache:
    def __init__(self, path, seed=None):
        """`seed`: optional read-only cache shipped with the repo (real model output for the example wardrobe)."""
        self.path = Path(path)
        self.data: dict = {}
        for src in (seed, self.path):
            if src and Path(src).is_file():
                try:
                    self.data.update(json.loads(Path(src).read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    pass

    @staticmethod
    def key(img_hash: str, model: str) -> str:
        return f"{img_hash}:{model}"

    def get(self, img_hash, model):
        return self.data.get(self.key(img_hash, model))

    def put(self, img_hash, model, record):
        self.data[self.key(img_hash, model)] = record

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")


def describe_image(client: LLMClient, image_path: Path, hint: str | None = None) -> tuple[dict, float]:
    """Describe one photo. Returns (normalized description, seconds). Retries once on bad JSON.

    `hint`: optional text from a shop page (title/description); the model is told to trust the photo over it."""
    text = PROMPT
    if hint:
        text += ("\nThe shop page that this photo came from calls it: " + json.dumps(hint[:300], ensure_ascii=False) +
                 ". Use this as a hint for type and material, but trust the photo for colour and category.")
    msg = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
        {"type": "text", "text": text},
    ]}]
    last = None
    t0 = time.perf_counter()
    for _ in range(2):
        try:
            return normalize(extract_json(client.chat(msg, max_tokens=400, temperature=0.1))), time.perf_counter() - t0
        except ValueError as e:
            last = e
    raise ValueError(f"vision model gave unusable output: {last}")


def describe_all(client: LLMClient, items: list[dict], cache: Cache, workers: int = 4,
                 progress=None) -> dict[str, dict]:
    """Fill `item['desc']` for every item, using the cache when possible.

    items: [{"id", "image_path": Path, ...}]. Returns {id: error string} for items that failed.
    Manual fields in an item (e.g. "warmth": 4) override the model's answer.
    """
    errors: dict[str, str] = {}
    todo = []
    for it in items:
        h = file_hash(it["image_path"])
        it["hash"] = h
        rec = cache.get(h, client.ep.model)
        if rec:
            it["desc"] = rec["desc"]
        else:
            todo.append(it)

    def work(it):
        try:
            desc, secs = describe_image(client, it["image_path"])
            return it, desc, secs, None
        except (LLMError, ValueError) as e:
            return it, None, 0.0, str(e)
        except PrivacyError:
            raise

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for it, desc, secs, err in ex.map(work, todo):
            if err:
                errors[it["id"]] = err
                continue
            it["desc"] = desc
            cache.put(it["hash"], client.ep.model, {"desc": desc, "seconds": round(secs, 2)})
            if progress:
                progress(it["id"], desc, secs)
    cache.save()
    return errors
