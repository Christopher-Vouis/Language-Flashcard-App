"""
User profiles.

Each profile has its own saved lines and its own cards/decks. Transcripts in
output/ are shared (they're only working files).

profiles.json (next to the app) lists the profiles and which one, if any,
is signed in automatically at startup. A profile's data lives in
profiles/<id>/saved and profiles/<id>/cards. The very first profile,
created from data that existed before profiles were added, keeps using the
original saved/ and cards/ folders (its "dir" is "") so nothing is moved.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid


class ProfileStore:
    def __init__(self, app_dir: str):
        self.app_dir = app_dir
        self.path = os.path.join(app_dir, "profiles.json")
        self.profiles: list[dict] = []   # [{"id", "name", "dir"}]
        self.default: str = ""           # profile id signed in at startup ("" = ask)
        self.load()

    # ------------------------------------------------------------ storage
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        self.profiles = data.get("profiles", [])
        self.default = data.get("default", "")
        if not self.profiles:
            # First run with profiles: existing saved/ and cards/ become "Main",
            # signed in automatically so nothing changes for the existing user.
            self.profiles = [{"id": "main", "name": "Main", "dir": ""}]
            self.default = "main"
            self._write()
        if self.default and not self.get(self.default):
            self.default = ""

    def _write(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "default": self.default, "profiles": self.profiles},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------ lookup
    def get(self, profile_id: str) -> dict | None:
        return next((p for p in self.profiles if p["id"] == profile_id), None)

    def _root(self, profile: dict) -> str:
        return os.path.join(self.app_dir, profile["dir"]) if profile.get("dir") else self.app_dir

    def saved_dir(self, profile: dict) -> str:
        return os.path.join(self._root(profile), "saved")

    def cards_dir(self, profile: dict) -> str:
        return os.path.join(self._root(profile), "cards")

    # ------------------------------------------------------------ editing
    def _check_name(self, name: str, ignore_id: str = "") -> str:
        name = " ".join((name or "").split())
        if not name:
            raise ValueError("Please enter a profile name.")
        if any(p["name"].lower() == name.lower() and p["id"] != ignore_id for p in self.profiles):
            raise ValueError(f'There is already a profile called "{name}".')
        return name

    def add(self, name: str) -> dict:
        pid = uuid.uuid4().hex[:8]
        profile = {"id": pid, "name": self._check_name(name), "dir": os.path.join("profiles", pid)}
        self.profiles.append(profile)
        self._write()
        return profile

    def rename(self, profile_id: str, name: str) -> None:
        p = self.get(profile_id)
        if p:
            p["name"] = self._check_name(name, ignore_id=profile_id)
            self._write()

    def delete(self, profile_id: str) -> None:
        """Remove a profile AND its saved lines, cards and decks from disk."""
        p = self.get(profile_id)
        if not p:
            return
        if len(self.profiles) == 1:
            raise ValueError("You can't delete the only profile.")
        root = os.path.realpath(self._root(p))
        profiles_dir = os.path.realpath(os.path.join(self.app_dir, "profiles"))
        if not p.get("dir"):
            # the original profile: its data is saved/ and cards/ next to the app
            for folder in (self.saved_dir(p), self.cards_dir(p)):
                if os.path.isdir(folder):
                    shutil.rmtree(folder, ignore_errors=True)
        elif root.startswith(profiles_dir + os.sep):  # never delete anything outside profiles/
            shutil.rmtree(root, ignore_errors=True)
        self.profiles = [x for x in self.profiles if x["id"] != profile_id]
        if self.default == profile_id:
            self.default = ""
        self._write()

    def set_default(self, profile_id: str) -> None:
        """profile_id = "" means no default: choose a profile at startup."""
        self.default = profile_id if (profile_id == "" or self.get(profile_id)) else self.default
        self._write()
