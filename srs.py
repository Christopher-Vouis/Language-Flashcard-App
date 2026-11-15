"""
Spaced repetition: when each card is due, and what Again / Hard / Correct do.

Every card has a schedule (card["srs"]):
    state     "new"         never studied
              "learning"    new card being learned (needs LEARN_STEPS Corrects in a row)
              "review"      learned; comes back after `interval` days
              "relearning"  a learned card that got Again on a later day
    step      Corrects so far while learning
    due       "YYYY-MM-DD": the card is due (shows in Study) on or after this day
    interval  days between the last two reviews
    last      "YYYY-MM-DD" the card was last studied on a scheduled day
    lapses    how many times a learned card got Again

Answers
    Again    due today: the card comes back later in this session. A new or
             learning card starts its Corrects again; a learned card studied on
             an earlier day goes to relearning, so its next Correct = tomorrow.
    Hard     learning / relearning: repeat this step later today (no reset).
             review: next interval = 1.2 x days since last studied (at least 1).
    Correct  learning: one step further; after LEARN_STEPS Corrects -> due tomorrow.
             relearning: due tomorrow.
             review: next interval = EASE x days since last studied (at least 1),
             so a card remembered after a long gap is pushed further out.
"""

from __future__ import annotations

import datetime as dt

LEARN_STEPS = 3      # Corrects in a row a new card needs before it's due another day
EASE = 2.5           # Correct: interval = EASE x days since the card was last studied
HARD = 1.2           # Hard on a learned card: interval = HARD x days since last studied
AGAIN, HARD_GRADE, CORRECT = "again", "hard", "correct"
REQUEUE_AFTER = 3    # a card that stays due today comes back after this many other cards


def today() -> dt.date:
    return dt.date.today()


def _d(s: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(s) if s else None
    except ValueError:
        return None


def schedule(card: dict, day: dt.date | None = None) -> dict:
    """The card's schedule, created on first use. Cards from before scheduling
    existed: studied ones count as learned ("review"), the rest as new; all are
    due today, so nothing disappears."""
    day = day or today()
    s = card.get("srs")
    if isinstance(s, dict) and s.get("state") in ("new", "learning", "review", "relearning"):
        return s
    last = _d((card.get("last_reviewed") or "")[:10])
    if card.get("reviews"):
        s = {"state": "review", "step": 0, "due": day.isoformat(), "interval": 0,
             "last": (last or day).isoformat(), "lapses": 0}
    else:
        s = {"state": "new", "step": 0, "due": day.isoformat(), "interval": 0, "last": None, "lapses": 0}
    card["srs"] = s
    return s


def due_date(card: dict) -> dt.date:
    return _d(schedule(card)["due"]) or today()


def is_due(card: dict, day: dt.date | None = None) -> bool:
    return due_date(card) <= (day or today())


def is_new(card: dict) -> bool:
    return schedule(card)["state"] == "new"


def _elapsed(s: dict, day: dt.date) -> int:
    last = _d(s.get("last"))
    return max((day - last).days, 0) if last else 0


def _plan(card: dict, grade: str, day: dt.date) -> dict:
    """What answering `grade` would change: the new schedule (a copy)."""
    s = dict(schedule(card, day))
    state = s["state"]
    if grade == AGAIN:
        if state == "review":
            # studied on an earlier day and forgotten: relearn; next Correct = tomorrow
            s.update(state="relearning", step=0, lapses=int(s.get("lapses", 0)) + 1)
        elif state in ("new", "learning"):
            s.update(state="learning", step=0)        # start the Corrects again
        s["due"] = day.isoformat()
        return s
    if state in ("new", "learning"):
        if grade == HARD_GRADE:
            s.update(state="learning")                 # repeat this step, no progress lost
            s["due"] = day.isoformat()
            return s
        step = int(s.get("step", 0)) + 1
        if step >= LEARN_STEPS:                        # learned: first real interval
            s.update(state="review", step=0, interval=1, last=day.isoformat(),
                     due=(day + dt.timedelta(days=1)).isoformat())
        else:
            s.update(state="learning", step=step, due=day.isoformat())
        return s
    if state == "relearning":
        if grade == HARD_GRADE:
            s["due"] = day.isoformat()                 # once more later today
            return s
        s.update(state="review", step=0, interval=1, last=day.isoformat(),
                 due=(day + dt.timedelta(days=1)).isoformat())
        return s
    # review: proportional to the time since the card was last studied
    factor = EASE if grade == CORRECT else HARD
    days = max(round(_elapsed(s, day) * factor), 1)
    s.update(interval=days, last=day.isoformat(), due=(day + dt.timedelta(days=days)).isoformat())
    return s


def answer(card: dict, grade: str, day: dt.date | None = None) -> dict:
    """Apply an answer to the card (in place). Returns the new schedule."""
    day = day or today()
    s = _plan(card, grade, day)
    card["srs"] = s
    card["reviews"] = int(card.get("reviews", 0)) + 1
    card["last_reviewed"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return s


def preview(card: dict, grade: str, day: dt.date | None = None) -> str:
    """Short label for a button: when the card would come back."""
    day = day or today()
    s = _plan(card, grade, day)
    due = _d(s["due"])
    if due <= day:
        if s["state"] == "learning" and grade == CORRECT:
            return f"later today ({s['step']}/{LEARN_STEPS})"
        return "later today"
    return describe_days((due - day).days)


def describe_days(days: int) -> str:
    if days <= 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days < 31:
        return f"in {days} days"
    if days < 365:
        return f"in {days / 30.4:.1f} months".replace(".0 ", " ")
    return f"in {days / 365:.1f} years".replace(".0 ", " ")


def stays_today(card: dict, day: dt.date | None = None) -> bool:
    """After answering: is the card still due today (so it comes back this session)?"""
    return is_due(card, day)
