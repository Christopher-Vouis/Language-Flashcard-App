"""
Card templates: how a card looks in study mode.

A template has a front and a back. Each side is a list of blocks shown top
to bottom, plus an "autoplay" switch (play the audio clip when that side
appears). Each block shows one thing (the target word, the sentence, the
screenshot, ...) with a few display settings.

Saved per profile as  <profile cards folder>/template.json.
"""

from __future__ import annotations

import copy
import json
import os
import uuid

# Block types the editor offers, in palette order.
#   label    name shown in the editor
#   icon     small glyph on the block chip
#   text     True for text blocks (they get size / colour / bold / alignment)
#   defaults the settings a new block starts with
BLOCK_TYPES: dict[str, dict] = {
    "word":       {"label": "Target word", "icon": "Aa", "text": True,
                   "defaults": {"size": "xxl", "align": "center", "color": "text", "bold": True}},
    "reading":    {"label": "Reading", "icon": "あ", "text": True,
                   "defaults": {"size": "l", "align": "center", "color": "muted", "bold": False}},
    "definition": {"label": "Definition", "icon": "≡", "text": True,
                   "defaults": {"size": "m", "align": "center", "color": "text", "bold": False}},
    "sentence":   {"label": "Sentence", "icon": "❝", "text": True,
                   "defaults": {"size": "l", "align": "center", "color": "text", "bold": False,
                                "highlight": True}},
    "image":      {"label": "Screenshot", "icon": "▣", "text": False,
                   "defaults": {"size": "fill"}},
    "audio":      {"label": "Audio button", "icon": "▶", "text": False, "defaults": {}},
    "source":     {"label": "Source (file & time)", "icon": "⏱", "text": True,
                   "defaults": {"size": "s", "align": "center", "color": "subtle", "bold": False}},
    "divider":    {"label": "Divider line", "icon": "―", "text": False, "defaults": {}},
    "text":       {"label": "Custom text", "icon": "T", "text": True,
                   "defaults": {"size": "m", "align": "center", "color": "muted", "bold": False,
                                "text": "Your text"}},
}

# Display options offered in the editor: (value, label)
TEXT_SIZES = [("s", "S"), ("m", "M"), ("l", "L"), ("xl", "XL"), ("xxl", "XXL")]
FONT_PX = {"s": 11, "m": 14, "l": 18, "xl": 26, "xxl": 34}
IMAGE_SIZES = [("s", "Small"), ("m", "Medium"), ("l", "Large"), ("fill", "Fill space")]
IMAGE_PX = {"s": 180, "m": 260, "l": 360}
ALIGNS = [("left", "Left"), ("center", "Centre"), ("right", "Right")]
COLORS = [("text", "Normal"), ("muted", "Soft"), ("subtle", "Faint"),
          ("accent", "Blue"), ("target", "Red")]


def new_block(kind: str, **overrides) -> dict:
    block = {"id": uuid.uuid4().hex[:8], "type": kind, **BLOCK_TYPES[kind]["defaults"]}
    block.update(overrides)
    return block


def default_template() -> dict:
    """Looks exactly like study mode did before templates existed."""
    return {
        "version": 1,
        "front": {"autoplay": False, "blocks": [
            new_block("word"),
            new_block("sentence"),
        ]},
        "back": {"autoplay": True, "blocks": [
            new_block("word"),
            new_block("sentence"),
            new_block("divider"),
            new_block("reading"),
            new_block("definition"),
            new_block("image"),
            new_block("audio"),
        ]},
    }


def normalize(tpl: dict) -> dict:
    """Fill in anything missing and drop unknown blocks, so a hand-edited or
    older file can't break study mode."""
    out = {"version": 1}
    base = default_template()
    for side in ("front", "back"):
        src = tpl.get(side) if isinstance(tpl.get(side), dict) else base[side]
        blocks = []
        for b in src.get("blocks", []):
            if isinstance(b, dict) and b.get("type") in BLOCK_TYPES:
                nb = new_block(b["type"])
                nb.update({k: v for k, v in b.items() if k in nb or k == "id"})
                blocks.append(nb)
        out[side] = {"autoplay": bool(src.get("autoplay", base[side]["autoplay"])), "blocks": blocks}
    return out


def path_for(cards_dir: str) -> str:
    return os.path.join(cards_dir, "template.json")


def load(cards_dir: str) -> dict:
    try:
        with open(path_for(cards_dir), encoding="utf-8") as f:
            return normalize(json.load(f))
    except (OSError, ValueError):
        return default_template()


def save(cards_dir: str, tpl: dict) -> None:
    os.makedirs(cards_dir, exist_ok=True)
    path = path_for(cards_dir)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(normalize(tpl), f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def clone(tpl: dict) -> dict:
    return copy.deepcopy(tpl)
