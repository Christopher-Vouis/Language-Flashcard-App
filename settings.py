"""
App settings that are remembered between runs (settings.json next to the app).

Shared by every profile. Missing or unreadable file = the defaults.
"""

from __future__ import annotations

import json
import os

DEFAULTS = {
    "shot_match_input": True,   # screenshots at the video's own resolution
    "shot_width": "",           # ... otherwise this size (as typed)
    "shot_height": "",
    "window_width": 1280,       # the window's size when the app opens
    "window_height": 1000,
    "theme": "Blue",            # colour theme: Blue, Orange, Red, Green, Purple
    "shortcuts_made": False,    # desktop + Start menu shortcuts made on the first run (once)
}


class Settings:
    def __init__(self, folder: str):
        self.path = os.path.join(folder, "settings.json")
        self.values = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.values.update({k: v for k, v in data.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def get(self, key: str):
        return self.values.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        if self.values.get(key) == value:
            return
        self.values[key] = value
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.values, f, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass   # not being able to remember a setting shouldn't stop anything
