"""A tiny OpenAI-compatible chat client (httpx only) with a privacy guard."""
from __future__ import annotations

import base64
import io
import os
import time
from urllib.parse import urlparse

import httpx
from PIL import Image

from .config import Endpoint

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"}


class PrivacyError(RuntimeError):
    """Raised when the privacy mode forbids sending data to this endpoint."""


class LLMError(RuntimeError):
    pass


def is_local(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host in LOCAL_HOSTS or host.endswith(".localhost")


def check_privacy(privacy: str, base_url: str, has_images: bool) -> None:
    if is_local(base_url):
        return
    if privacy == "local-only":
        raise PrivacyError(f"privacy=local-only: refusing to call non-local endpoint {base_url}")
    if privacy == "images-local" and has_images:
        raise PrivacyError(f"privacy=images-local: refusing to send photos to non-local endpoint {base_url}")


def image_to_data_url(path, max_side: int = 512) -> str:
    """Downscale and JPEG-encode a photo: cheaper, faster, and sends fewer pixels off-device."""
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class LLMClient:
    def __init__(self, endpoint: Endpoint, privacy: str = "off", timeout: float = 120.0):
        self.ep = endpoint
        self.privacy = privacy
        self.timeout = timeout
        self.last_latency: float | None = None

    def chat(self, messages: list[dict], *, max_tokens: int = 700, temperature: float = 0.2,
             json_mode: bool = False) -> str:
        has_images = any(
            isinstance(m.get("content"), list) and any(p.get("type") == "image_url" for p in m["content"])
            for m in messages
        )
        check_privacy(self.privacy, self.ep.base_url, has_images)
        headers = {"Content-Type": "application/json"}
        if self.ep.api_key_env:
            key = os.environ.get(self.ep.api_key_env)
            if not key:
                raise LLMError(f"environment variable {self.ep.api_key_env} is not set")
            headers["Authorization"] = f"Bearer {key}"
        body = {"model": self.ep.model, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature, **self.ep.extra_body}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        try:
            r = httpx.post(f"{self.ep.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise LLMError(f"request failed: {type(e).__name__}") from None
        self.last_latency = time.perf_counter() - t0
        if r.status_code != 200:
            # never echo request headers; the response body from the server is safe to show (truncated)
            raise LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
        try:
            return r.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError):
            raise LLMError("unexpected response shape") from None
