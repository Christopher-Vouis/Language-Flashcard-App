"""
Flashcard deck.

A card is made from a saved line: the sentence, its audio clip and
screenshot, plus three fields the user fills in - the target word, its
reading, and a definition.

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


class CardStore:
    def __init__(self, root: str):
        self.root = root
        self.media_dir = os.path.join(root, "media")
        self.path = os.path.join(root, "cards.json")
        self.cards: list[dict] = []
        self.load()

    # ------------------------------------------------------------ storage
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                self.cards = json.load(f).get("cards", [])
        except FileNotFoundError:
            self.cards = []

    def _write(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "cards": self.cards}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # atomic: never leaves a half-written file

    def abs_path(self, rel: str) -> str:
        return os.path.join(self.root, rel) if rel else ""

    def get(self, card_id: str) -> dict | None:
        return next((c for c in self.cards if c["id"] == card_id), None)

    def count_for_line(self, line_id: str) -> int:
        return sum(1 for c in self.cards if c.get("saved_line_id") == line_id)

    # ------------------------------------------------------------ editing
    def add(self, line: dict, line_media_root: str, fields: dict) -> dict:
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

    def update(self, card_id: str, fields: dict) -> bool:
        card = self.get(card_id)
        if not card:
            return False
        for k in FIELDS:
            if k in fields:
                card[k] = fields[k].strip()
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
