"""
Saved-lines library.

Lines the user saves are kept in  saved/saved_lines.json  with their own
copies of the audio clip and screenshot in  saved/media/ , so they survive
re-transcribing or deleting the original output folder. This is the pool
the flashcard step will draw from.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid

from collections import Counter

from media import is_shared, safe_name, shared_copy


class SavedStore:
    def __init__(self, root: str):
        self.root = root
        self.media_dir = os.path.join(root, "media")
        self.path = os.path.join(root, "saved_lines.json")
        self.entries: list[dict] = []
        self.load()

    # ------------------------------------------------------------ storage
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                self.entries = json.load(f).get("lines", [])
        except FileNotFoundError:
            self.entries = []

    def _write(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "lines": self.entries}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # atomic: never leaves a half-written file

    def abs_path(self, rel: str) -> str:
        return os.path.join(self.root, rel) if rel else ""

    # ------------------------------------------------------------ editing
    @staticmethod
    def _key(source: str, start: float, end: float, text: str) -> tuple:
        return (os.path.normcase(source), round(start, 2), round(end, 2), text)

    def add(self, transcript, segments, audio_paths: dict, shot_paths: dict) -> tuple[int, int]:
        """Save segments (with copies of their media). Returns (added, already_saved)."""
        existing = {self._key(e["source_file"], e["start"], e["end"], e["text"]) for e in self.entries}
        os.makedirs(self.media_dir, exist_ok=True)
        base = safe_name(os.path.splitext(os.path.basename(transcript.source_file))[0])
        # a picture used by several lines (Use one image for all) is copied once and shared
        uses = Counter(os.path.normcase(p) for p in shot_paths.values() if p)
        added = skipped = 0
        for seg in segments:
            if self._key(transcript.source_file, seg.start, seg.end, seg.text) in existing:
                skipped += 1
                continue
            uid = uuid.uuid4().hex[:10]
            entry = {
                "id": uid,
                "text": seg.text,
                "start": seg.start,
                "end": seg.end,
                "language": transcript.language,
                "source_file": transcript.source_file,
                "line_number": seg.index + 1,
                "words": [w.__dict__ for w in seg.words],
                "audio_clip": "",
                "screenshot": "",
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for key, paths, ext in (("audio_clip", audio_paths, ".wav"),
                                    ("screenshot", shot_paths, ".jpg")):
                src = paths.get(seg.index)
                if src and os.path.isfile(src):
                    if key == "screenshot" and uses[os.path.normcase(src)] > 1:
                        entry[key] = f"media/{shared_copy(src, self.media_dir)}"
                        continue
                    name = f"{base}_{uid}{ext}"
                    shutil.copy2(src, os.path.join(self.media_dir, name))
                    entry[key] = f"media/{name}"
            self.entries.append(entry)
            added += 1
        if added:
            self._write()
        return added, skipped

    def get(self, entry_id: str) -> dict | None:
        return next((e for e in self.entries if e["id"] == entry_id), None)

    def set_text(self, entry_id: str, text: str) -> bool:
        """Change a saved line's text (typed corrections). The text it was
        saved with is kept as "original_text". Returns True if it changed."""
        e = self.get(entry_id)
        text = " ".join(text.split())
        if e is None or not text or text == e["text"]:
            return False
        e.setdefault("original_text", e["text"])
        e["text"] = text
        e["edited_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._write()
        return True

    def set_times(self, entry_id: str, start: float, end: float, audio_src: str = "", shot_src: str = "") -> bool:
        """New start/end for a saved line (its line was re-clipped on the Create
        screen), with copies of the re-cut audio clip and screenshot."""
        e = self.get(entry_id)
        if e is None:
            return False
        e["start"], e["end"] = start, end
        e["edited_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(self.media_dir, exist_ok=True)
        for key, src, ext in (("audio_clip", audio_src, ".wav"), ("screenshot", shot_src, ".jpg")):
            if not src or not os.path.isfile(src):
                continue
            if key == "screenshot" and is_shared(src):
                continue                       # one picture for every line: unchanged
            dst = self.abs_path(e.get(key, ""))
            if not dst or is_shared(dst):
                name = f"{safe_name(os.path.splitext(os.path.basename(e['source_file']))[0])}_{e['id']}{ext}"
                dst = os.path.join(self.media_dir, name)
                e[key] = f"media/{name}"
            shutil.copy2(src, dst)
        self._write()
        return True

    def remove(self, ids) -> int:
        ids = set(ids)
        keep, gone = [], []
        for e in self.entries:
            (gone if e["id"] in ids else keep).append(e)
        in_use = {e.get(k) for e in keep for k in ("audio_clip", "screenshot")}
        for e in gone:
            for key in ("audio_clip", "screenshot"):
                if e.get(key) in in_use:       # shared with a line that's kept
                    continue
                p = self.abs_path(e.get(key, ""))
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        self.entries = keep
        if gone:
            self._write()
        return len(gone)
