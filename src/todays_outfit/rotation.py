"""Rotation: use the wear history to nudge the ranking of rule-approved outfits.

Honest summary of what it does (all numbers are the defaults in `RotationPolicy`):
  * a piece worn today or yesterday costs the outfit 2.5 points, one worn 2-3 days ago costs 1.0;
  * every piece gets a small bonus (up to 0.5, reached after 21 unworn days) for being unworn for a while;
  * an outfit you tapped "Show another" on gets up to -4 for the exact same combination, fading to 0 over 14 days.
For scale: rule scores of good candidates are typically within ~1-3 points of each other, so these nudges reorder
the shortlist but can never make a rule-forbidden outfit appear: they only act on candidates the rules already approved.

The sentence shown under a suggestion ("note") is computed here from the log. A language model never writes it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .history import History


@dataclass(frozen=True)
class RotationPolicy:
    yesterday_penalty: float = 2.5     # piece worn today or yesterday
    recent_penalty: float = 1.0        # piece worn 2-3 days ago
    neglect_bonus: float = 0.5         # max per-piece bonus for long-unworn pieces
    neglect_full_days: int = 21
    skip_penalty: float = 4.0
    skip_days: int = 14
    note_days: int = 14                # mention a piece as "long unworn" from this many days


class Rotation:
    def __init__(self, history: History, today: date, added: dict[str, date] | None = None,
                 policy: RotationPolicy = RotationPolicy()):
        self.h, self.today, self.p = history, today, policy
        self.added = added or {}
        self.stats = history.stats()
        self.start = history.first_day()

    # ---- per-piece facts ----
    def days_since_worn(self, item_id: str) -> int | None:
        s = self.stats.get(item_id)
        return s.days_since(self.today) if s else None

    def unworn_days(self, item_id: str) -> int:
        """Days without a logged wear. A piece never logged counts from when logging started (or when it was added,
        if later). Zero if there is no history at all, because then we know nothing."""
        d = self.days_since_worn(item_id)
        if d is not None:
            return d
        if self.start is None:
            return 0
        since = max(self.start, self.added.get(item_id, self.start))
        return max(0, (self.today - since).days)

    def min_days_since_worn(self, items: list[dict]) -> int:
        ds = [d for d in (self.days_since_worn(i["id"]) for i in items) if d is not None]
        return min(ds) if ds else 99

    # ---- ranking ----
    def adjust(self, pieces: list[dict]) -> float:
        p, total = self.p, 0.0
        for it in pieces:
            d = self.days_since_worn(it["id"])
            if d is not None:
                if d <= 1:
                    total -= p.yesterday_penalty
                elif d <= 3:
                    total -= p.recent_penalty
            total += p.neglect_bonus * min(self.unworn_days(it["id"]), p.neglect_full_days) / p.neglect_full_days
        key = {i["id"] for i in pieces}
        worst = 0.0
        for s in self.h.skips:
            if set(s["items"]) == key:
                age = (self.today - date.fromisoformat(s["date"])).days
                if 0 <= age < p.skip_days:
                    worst = max(worst, p.skip_penalty * (1 - age / p.skip_days))
        return total - worst

    # ---- the true sentence shown to the user ----
    def facts(self, items: list[dict]) -> dict:
        names = {i["id"]: i.get("name", i["id"]) for i in items}
        recent = []
        for it in items:
            d = self.days_since_worn(it["id"])
            if d is not None and d <= 3:
                recent.append((names[it["id"]], d))
        longun = []
        for it in items:
            n = self.unworn_days(it["id"])
            if n >= self.p.note_days:
                longun.append((names[it["id"]], n, self.days_since_worn(it["id"]) is None))
        longun.sort(key=lambda x: -x[1])
        parts = []
        if longun:
            bits = [f"{nm} ({'no wear logged in' if never else 'not worn for'} {n} days)" for nm, n, never in longun[:3]]
            parts.append("Brings back " + ", ".join(bits) + ".")
        if recent:
            when = lambda d: "today" if d == 0 else "yesterday" if d == 1 else f"{d} days ago"  # noqa: E731
            parts.append("Repeats: " + ", ".join(f"{nm} (worn {when(d)})" for nm, d in recent) + ".")
        elif self.start is not None:
            parts.append("Nothing in it was worn in the last 3 days.")
        return {"note": " ".join(parts), "recent": [n for n, _ in recent], "long_unworn": [n for n, _, _ in longun]}


# A model must not talk about the wear history: it never saw it, so any such claim would be invented.
_HISTORY_WORDS = re.compile(
    r"\b(yesterday|last (week|time|month)|recently|lately|haven'?t (worn|used)|hasn'?t been worn|not (been )?worn|"
    r"never worn|rotation|rotate|you wore|worn (it )?(before|already)|in a while|for a while|a while since|"
    r"gathering dust|forgotten)\b", re.I)


def history_claims(reason: str) -> list[str]:
    return [m.group(0) for m in _HISTORY_WORDS.finditer(reason)]
