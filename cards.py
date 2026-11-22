"""
Flashcard deck.

A card is made from a saved line: the sentence, its audio clip and
screenshot, plus three fields the user fills in - the target word, its
reading, and a definition. Cards are grouped into decks; one card can be
in several decks (its "decks" list holds deck ids).

Stored in  cards/cards.json  with the card's own copies of the clip and
screenshot in  cards/media/ , so deleting a saved line never breaks a card.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid

import srs
from media import is_shared, safe_name, shared_copy

FIELDS = ("target_word", "reading", "definition")
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


def card_images(card: dict) -> list[dict]:
    """A card's images in order: [{"id", "path", "name"}]. Cards made before
    multiple images existed just have their screenshot, which is image 1."""
    if "images" in card:
        return list(card["images"])
    if card.get("screenshot"):
        return [{"id": "shot", "path": card["screenshot"], "name": "Screenshot"}]
    return []
ALL = ""  # "deck id" meaning every card, whatever its decks
DEFAULT_LIMITS = {"new_per_day": 20, "max_reviews": 200}   # Study settings, per deck


class CardStore:
    def __init__(self, root: str):
        self.root = root
        self.media_dir = os.path.join(root, "media")
        self.path = os.path.join(root, "cards.json")
        self.log_path = os.path.join(root, "study_log.jsonl")   # one line per answer (Stats)
        self.cards: list[dict] = []
        self.decks: list[dict] = []      # [{"id", "name"}], in display order
        self.selected_deck: str = ALL    # deck chosen on the main menu
        self.load()

    # ------------------------------------------------------------ storage
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        self.cards = data.get("cards", [])
        self.decks = data.get("decks", [])
        self.selected_deck = data.get("selected_deck", ALL)
        self.all_limits = data.get("all_limits", {})   # Study settings for "All cards"
        # Older files had no decks: put every existing card in a "Default" deck.
        changed = False
        if not self.decks:
            self.decks = [{"id": "default", "name": "Default"}]
            changed = bool(self.cards)
        for c in self.cards:
            if "decks" not in c:
                c["decks"] = [self.decks[0]["id"]]
                changed = True
        if self.selected_deck and not self.deck(self.selected_deck):
            self.selected_deck = ALL
        if changed:
            backup = os.path.join(self.root, "cards.before-decks.json")
            if os.path.isfile(self.path) and not os.path.exists(backup):
                shutil.copy2(self.path, backup)  # keep the pre-decks file, just in case
            self._write()

    def _write(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "decks": self.decks, "selected_deck": self.selected_deck,
                       "all_limits": self.all_limits, "cards": self.cards}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # atomic: never leaves a half-written file

    # ------------------------------------------------------------ decks
    def deck(self, deck_id: str) -> dict | None:
        return next((d for d in self.decks if d["id"] == deck_id), None)

    def deck_name(self, deck_id: str) -> str:
        d = self.deck(deck_id)
        return d["name"] if d else ("All cards" if deck_id == ALL else "?")

    def cards_in(self, deck_id: str = ALL) -> list[dict]:
        if deck_id == ALL:
            return list(self.cards)
        return [c for c in self.cards if deck_id in c.get("decks", [])]

    def _check_name(self, name: str, ignore_id: str = "") -> str:
        name = " ".join(name.split())
        if not name:
            raise ValueError("Please enter a deck name.")
        if any(d["name"].lower() == name.lower() and d["id"] != ignore_id for d in self.decks):
            raise ValueError(f'There is already a deck called "{name}".')
        return name

    def add_deck(self, name: str) -> dict:
        deck = {"id": uuid.uuid4().hex[:8], "name": self._check_name(name)}
        self.decks.append(deck)
        self._write()
        return deck

    def rename_deck(self, deck_id: str, name: str) -> None:
        d = self.deck(deck_id)
        if d:
            d["name"] = self._check_name(name, ignore_id=deck_id)
            self._write()

    def delete_deck(self, deck_id: str) -> None:
        """Remove a deck. Its cards are kept (still in their other decks and in
        "All cards"); only their membership of this deck goes."""
        self.decks = [d for d in self.decks if d["id"] != deck_id]
        for c in self.cards:
            if deck_id in c.get("decks", []):
                c["decks"] = [i for i in c["decks"] if i != deck_id]
        if self.selected_deck == deck_id:
            self.selected_deck = ALL
        self._write()

    def add_to_deck(self, card_ids, deck_id: str) -> int:
        """Add cards to a deck (keeping their other decks). Returns how many
        weren't already in it."""
        if not self.deck(deck_id):
            return 0
        added = 0
        for c in self.cards:
            if c["id"] in card_ids and deck_id not in c.setdefault("decks", []):
                c["decks"].append(deck_id)
                added += 1
        if added:
            self._write()
        return added

    # ------------------------------------------------------------ spaced repetition
    def answer(self, card_id: str, grade: str) -> dict | None:
        """Study mode's Again / Hard / Correct (see srs.py). Returns the new schedule."""
        card = self.get(card_id)
        if card is None:
            return None
        self._seed_log()
        before = srs.schedule(card)["state"]           # new / learning / review / relearning
        sched = srs.answer(card, grade)
        self._write()
        self._log({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "card": card_id, "grade": grade,
                   "state": before, "decks": list(card.get("decks", []))})
        return sched

    # ------------------------------------------------------------ daily limits (Study settings)
    def study_limits(self, deck_id: str = ALL) -> dict:
        d = self.deck(deck_id)
        stored = (d.get("limits") if d else self.all_limits) or {}
        return {k: int(stored.get(k, v)) for k, v in DEFAULT_LIMITS.items()}

    def set_study_limits(self, deck_id: str, new_per_day: int, max_reviews: int) -> None:
        limits = {"new_per_day": int(new_per_day), "max_reviews": int(max_reviews)}
        d = self.deck(deck_id)
        if d:
            d["limits"] = limits
        else:
            self.all_limits = limits
        self._write()

    def done_today(self, deck_id: str = ALL) -> dict:
        """Studied today in this deck: new cards introduced, and review cards
        (learned cards that were due) answered. Each card counts once."""
        today = srs.today().isoformat()
        new, reviews = set(), set()
        for e in self.study_log(deck_id):
            if e.get("t", "")[:10] != today:
                continue
            if e.get("state") == "new":
                new.add(e.get("card"))
            elif e.get("state") == "review":
                reviews.add(e.get("card"))
        return {"new": len(new), "reviews": len(reviews)}

    def study_queue(self, deck_id: str = ALL) -> tuple[list[dict], dict]:
        """The cards to study now, in order, within today's limits: cards being
        learned (always), then reviews (most overdue first), then new cards (in
        the order they were made). Also returns how many due cards the limits
        are holding back today: {"new": n, "reviews": n}."""
        limits, done = self.study_limits(deck_id), self.done_today(deck_id)
        due = self.due_cards(deck_id)
        state = lambda c: srs.schedule(c)["state"]          # noqa: E731
        learning = [c for c in due if state(c) in ("learning", "relearning")]
        reviews = sorted((c for c in due if state(c) == "review"), key=srs.due_date)
        new = [c for c in due if state(c) == "new"]
        r_left = max(limits["max_reviews"] - done["reviews"], 0)
        n_left = max(limits["new_per_day"] - done["new"], 0)
        held = {"new": max(len(new) - n_left, 0), "reviews": max(len(reviews) - r_left, 0)}
        return learning + reviews[:r_left] + new[:n_left], held

    def study_counts(self, deck_id: str = ALL) -> dict:
        """For the main menu: what Study will show today, within the limits.
        New = new cards it will introduce; Due = cards being learned + reviews."""
        queue, _held = self.study_queue(deck_id)
        new = sum(1 for c in queue if srs.is_new(c))
        return {"new": new, "due": len(queue) - new, "total": len(self.cards_in(deck_id))}

    # ------------------------------------------------------------ study log (Stats)
    def _log(self, entry: dict) -> None:
        os.makedirs(self.root, exist_ok=True)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass   # stats are nice to have; never stop studying over them

    def _seed_log(self) -> None:
        """Before the log existed only each card's last study date was kept: the
        first time, those go in the log (one entry per card, on that day)."""
        if os.path.exists(self.log_path):
            return
        entries = [{"t": c["last_reviewed"].replace(" ", "T"), "card": c["id"], "grade": "",
                    "decks": list(c.get("decks", [])), "from": "last_reviewed"}
                   for c in self.cards if c.get("last_reviewed")]
        entries.sort(key=lambda e: e["t"])
        os.makedirs(self.root, exist_ok=True)
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def study_log(self, deck_id: str = ALL) -> list[dict]:
        """Every answer given in Study (oldest first), for one deck or all.
        A deck's log is the answers to cards that were in it when studied."""
        self._seed_log()
        out = []
        try:
            with open(self.log_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue          # a half-written line (e.g. power cut): skip it
                    if deck_id == ALL or deck_id in e.get("decks", []):
                        out.append(e)
        except OSError:
            pass
        return out

    def due_cards(self, deck_id: str = ALL) -> list[dict]:
        """Cards in the deck whose due date is today or earlier."""
        day = srs.today()
        return [c for c in self.cards_in(deck_id) if srs.is_due(c, day)]

    def remove_from_deck(self, card_ids, deck_id: str) -> int:
        """Take cards out of a deck without deleting them. Returns how many."""
        ids, n = set(card_ids), 0
        for c in self.cards:
            if c["id"] in ids and deck_id in c.get("decks", []):
                c["decks"] = [d for d in c["decks"] if d != deck_id]
                n += 1
        if n:
            self._write()
        return n

    def reset_progress(self, card_ids) -> int:
        """Forget the study history of these cards: they become new, due today."""
        ids, n = set(card_ids), 0
        for c in self.cards:
            if c["id"] in ids:
                for k in ("srs", "reviews", "last_reviewed"):
                    c.pop(k, None)
                srs.schedule(c)
                n += 1
        if n:
            self._write()
        return n

    def next_due(self, deck_id: str = ALL):
        """The earliest due date among the deck's cards (a date), or None."""
        dates = [srs.due_date(c) for c in self.cards_in(deck_id)]
        return min(dates) if dates else None

    def counts(self, deck_id: str = ALL) -> dict:
        """For the main menu. New = never studied; Due = studied cards due today
        or earlier (learning, relearning or review); Total = all."""
        cards = self.cards_in(deck_id)
        day = srs.today()
        new = sum(1 for c in cards if srs.is_new(c))
        due = sum(1 for c in cards if not srs.is_new(c) and srs.is_due(c, day))
        return {"new": new, "due": due, "total": len(cards)}

    def select_deck(self, deck_id: str) -> None:
        if deck_id != self.selected_deck:
            self.selected_deck = deck_id
            self._write()

    def abs_path(self, rel: str) -> str:
        return os.path.join(self.root, rel) if rel else ""

    def get(self, card_id: str) -> dict | None:
        return next((c for c in self.cards if c["id"] == card_id), None)

    def count_for_line(self, line_id: str) -> int:
        return sum(1 for c in self.cards if c.get("saved_line_id") == line_id)

    # ------------------------------------------------------------ editing
    def add(self, line: dict, line_media_root: str, fields: dict, decks: list[str] | None = None) -> dict:
        """Create a card from a saved-line entry. line_media_root is the
        folder its audio_clip/screenshot paths are relative to."""
        os.makedirs(self.media_dir, exist_ok=True)
        uid = uuid.uuid4().hex[:10]
        base = safe_name(os.path.splitext(os.path.basename(line.get("source_file", "")))[0])
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        card = {
            "id": uid,
            **{k: fields.get(k, "").strip() for k in FIELDS},
            "sentence": line.get("text", ""),
            "audio_clip": "",
            "screenshot": "",
            "language": line.get("language", ""),
            "source_file": line.get("source_file", ""),
            "start": line.get("start", 0.0),
            "end": line.get("end", 0.0),
            "saved_line_id": line.get("id", ""),
            "decks": [d for d in (decks or []) if self.deck(d)],
            "created_at": now,
            "updated_at": now,
        }
        for key, ext in (("audio_clip", ".wav"), ("screenshot", ".jpg")):
            rel = line.get(key, "")
            src = os.path.join(line_media_root, rel) if rel else ""
            if src and os.path.isfile(src) and key == "screenshot" and is_shared(rel):
                # one picture shared by many lines: the cards share one copy too
                card[key] = f"media/{shared_copy(src, self.media_dir)}"
                continue
            if src and os.path.isfile(src):
                name = f"card_{base}_{uid}{ext}"
                shutil.copy2(src, os.path.join(self.media_dir, name))
                card[key] = f"media/{name}"
        self.cards.append(card)
        self._write()
        return card

    def update(self, card_id: str, fields: dict, decks: list[str] | None = None) -> bool:
        card = self.get(card_id)
        if not card:
            return False
        for k in FIELDS:
            if k in fields:
                card[k] = fields[k].strip()
        if decks is not None:
            card["decks"] = [d for d in decks if self.deck(d)]
        card["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._write()
        return True

    @staticmethod
    def _media_in_use(cards) -> set:
        """Media files these cards use (shared pictures can be used by many)."""
        used = set()
        for c in cards:
            used |= {c.get("audio_clip", ""), c.get("screenshot", "")} | {i["path"] for i in card_images(c)}
        return used

    def remove(self, ids) -> int:
        ids = set(ids)
        keep, gone = [], []
        for c in self.cards:
            (gone if c["id"] in ids else keep).append(c)
        in_use = self._media_in_use(keep)
        for c in gone:
            paths = {c.get("audio_clip", ""), c.get("screenshot", "")} | {i["path"] for i in card_images(c)}
            for rel in paths - in_use:          # (a shared picture stays while a card uses it)
                p = self.abs_path(rel)
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        self.cards = keep
        if gone:
            self._write()
        return len(gone)

    # ------------------------------------------------------------ images
    def add_image(self, card_id: str, src: str) -> dict:
        """Copy a picture file into the cards folder and add it to the card."""
        card = self.get(card_id)
        if card is None:
            raise ValueError("Card not found.")
        ext = os.path.splitext(src)[1].lower()
        if ext not in IMAGE_TYPES:
            raise ValueError(f"{os.path.basename(src)} isn't a supported picture "
                             f"({', '.join(IMAGE_TYPES)}).")
        os.makedirs(self.media_dir, exist_ok=True)
        uid = uuid.uuid4().hex[:8]
        name = f"img_{card_id}_{uid}{ext}"
        shutil.copy2(src, os.path.join(self.media_dir, name))
        images = card_images(card)
        image = {"id": uid, "path": f"media/{name}",
                 "name": os.path.splitext(os.path.basename(src))[0][:40]}
        images.append(image)
        card["images"] = images
        card["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._write()
        return image

    def remove_image(self, card_id: str, image_id: str) -> None:
        card = self.get(card_id)
        if card is None:
            return
        images = card_images(card)
        gone = [i for i in images if i["id"] == image_id]
        card["images"] = [i for i in images if i["id"] != image_id]
        in_use = self._media_in_use(c for c in self.cards if c is not card)
        for img in gone:
            if img["path"] == card.get("screenshot"):
                card["screenshot"] = ""
            if img["path"] in in_use:           # another card uses the same picture
                continue
            p = self.abs_path(img["path"])
            if p and os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        self._write()

    # ------------------------------------------------------------ per-card layout
    def set_layout(self, card_id: str, layout: dict | None) -> None:
        """Give one card its own layout (a template), or None to go back to
        the profile's default layout."""
        card = self.get(card_id)
        if card is None:
            return
        if layout is None:
            card.pop("layout", None)
        else:
            card["layout"] = layout
        self._write()
