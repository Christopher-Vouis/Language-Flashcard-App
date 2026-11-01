"""Play the WAV audio clips (Windows' built-in player; silent elsewhere)."""

from __future__ import annotations

import os

try:
    import winsound
except ImportError:  # not Windows
    winsound = None


def play_wav(path: str) -> bool:
    if not path or winsound is None or not os.path.isfile(path):
        return False
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    return True


def stop_wav() -> None:
    if winsound is not None:
        winsound.PlaySound(None, 0)
