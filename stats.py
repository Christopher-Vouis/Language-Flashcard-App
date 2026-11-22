"""
Study statistics, worked out from the study log (cards.CardStore.study_log):
the days you studied, how many cards you studied each day, and today.

"Cards studied" counts each card once a day, however many times it was
answered (Again / Hard / Correct); "answers" counts every answer.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict


def _day(entry: dict) -> dt.date | None:
    try:
        return dt.date.fromisoformat(entry.get("t", "")[:10])
    except ValueError:
        return None


class Stats:
    def __init__(self, log: list[dict], today: dt.date):
        self.today = today
        cards = defaultdict(set)
        answers = defaultdict(int)
        for e in log:
            d = _day(e)
            if d is None:
                continue
            cards[d].add(e.get("card"))
            if not e.get("from"):                 # entries carried over from before the log: no answer count
                answers[d] += 1
        self.cards_per_day = {d: len(v) for d, v in cards.items()}
        self.answers_per_day = dict(answers)
        self.days = sorted(self.cards_per_day)    # days studied

    # ---- today
    @property
    def today_cards(self) -> int:
        return self.cards_per_day.get(self.today, 0)

    @property
    def today_answers(self) -> int:
        return self.answers_per_day.get(self.today, 0)

    # ---- days studied
    @property
    def days_studied(self) -> int:
        return len(self.days)

    @property
    def streak(self) -> int:
        """Days in a row up to today (or up to yesterday, if not studied yet today)."""
        studied = set(self.days)
        d = self.today if self.today in studied else self.today - dt.timedelta(days=1)
        n = 0
        while d in studied:
            n += 1
            d -= dt.timedelta(days=1)
        return n

    @property
    def longest_streak(self) -> int:
        best = run = 0
        prev = None
        for d in self.days:
            run = run + 1 if prev and (d - prev).days == 1 else 1
            best = max(best, run)
            prev = d
        return best

    @property
    def average(self) -> float:
        """Cards studied per day, over the days studied."""
        return sum(self.cards_per_day.values()) / len(self.days) if self.days else 0.0

    def last_days(self, n: int) -> list[tuple[dt.date, int]]:
        """(day, cards studied) for the last n days, oldest first (0 = not studied)."""
        return [(d, self.cards_per_day.get(d, 0))
                for d in (self.today - dt.timedelta(days=i) for i in range(n - 1, -1, -1))]
