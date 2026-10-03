"""Tolerant JSON extraction from model output (code fences, <think> blocks, chatter)."""
from __future__ import annotations

import json
import re


def extract_json(text: str):
    """Return the first JSON object/array found in `text`, or raise ValueError."""
    if not text:
        raise ValueError("empty response")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # scan for the first balanced {...} or [...]
    for start, ch in enumerate(text):
        if ch not in "{[":
            continue
        close = "}" if ch == "{" else "]"
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == ch:
                depth += 1
            elif c == close:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("no valid JSON found in model output")
