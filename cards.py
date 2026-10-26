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

from media import safe_name

FIELDS = ("target_word", "reading", "definition")
ALL = ""  # "deck id" meaning every card, whatever its decks


class CardStore:
    def __init__(self, root: str):
        self.root = root
        self.media_dir = os.path.join(root, "media")
        self.path = os.path.join(root, "cards.json")
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
                       "cards": self.cards}, f, ensure_ascii=False, indent=2)
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

    def remove(self, ids) -> int:
        ids = set(ids)
        keep, gone = [], []
        for c in self.cards:
            (gone if c["id"] in ids else keep).append(c)
        for c in gone:
            for key in ("audio_clip", "screenshot"):
                p = self.abs_path(c.get(key, ""))
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        self.cards = keep
        if gone:
            self._write()
        return len(gone)
