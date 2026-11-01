"""
Card templates: how a card looks in study mode.

A template has a front and a back. Each side is a list of ROWS shown top to
bottom; each row holds one or more BLOCKS shown side by side. A side also has
an "autoplay" switch (play the audio clip when that side appears). Each block
shows one thing (the target word, the sentence, the screenshot, ...) with a
few display settings.

Drop targets used when adding/moving blocks:
    ("row", side, r)       a new row inserted at row index r
    ("in",  side, r, c)    inside existing row r, at position c

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
    # image: "image" picks which one - "" or "#1" = a card's 1st image, "#2" its
    # 2nd, ... (used by the default layout); an image id = that exact image
    # (used by a single card's own layout). Offered in the palette's Images section.
    "image":      {"label": "Image", "icon": "▣", "text": False, "palette": False,
                   "defaults": {"size": "fill", "image": ""}},
    "slideshow":  {"label": "Slideshow", "icon": "⧉", "text": False, "palette": False,
                   "defaults": {"size": "fill", "autoplay": False, "interval": 4.0, "loop": True}},
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
MIN_INTERVAL, MAX_INTERVAL = 0.5, 120.0   # slideshow autoplay: seconds per image
ALIGNS = [("left", "Left"), ("center", "Centre"), ("right", "Right")]
COLORS = [("text", "Normal"), ("muted", "Soft"), ("subtle", "Faint"),
          ("accent", "Blue"), ("target", "Red")]


def palette_types() -> list[str]:
    """Block types in the main Blocks list (images have their own section)."""
    return [k for k, v in BLOCK_TYPES.items() if v.get("palette", True)]


def resolve_image(block: dict, images: list[dict]) -> tuple[int, dict | None]:
    """(index, image) an image block shows for a card's images, or (-1, None)."""
    ref = block.get("image", "") or "#1"
    if ref.startswith("#"):
        try:
            i = int(ref[1:]) - 1
        except ValueError:
            i = 0
        return (i, images[i]) if 0 <= i < len(images) else (i, None)
    for i, img in enumerate(images):
        if img["id"] == ref:
            return i, img
    return -1, None


def block_title(block: dict, images: list[dict] | None = None) -> str:
    """Name shown on a block chip, e.g. "Image 2 · photo"."""
    kind = block["type"]
    if kind == "image":
        ref = block.get("image", "") or "#1"
        if ref.startswith("#"):
            return f"Image {ref[1:]}"
        i, img = resolve_image(block, images or [])
        return f"Image {i + 1} · {img['name']}" if img else "Image (removed)"
    return BLOCK_TYPES[kind]["label"]


def new_block(kind: str, **overrides) -> dict:
    block = {"id": uuid.uuid4().hex[:8], "type": kind, **BLOCK_TYPES[kind]["defaults"]}
    block.update(overrides)
    return block


def default_template() -> dict:
    """Looks exactly like study mode did before templates existed."""
    return {
        "version": 2,
        "front": {"autoplay": False, "rows": [[new_block("word")], [new_block("sentence")]]},
        "back": {"autoplay": True, "rows": [
            [new_block("word")], [new_block("sentence")], [new_block("divider")],
            [new_block("reading")], [new_block("definition")], [new_block("image")],
            [new_block("audio")],
        ]},
    }


def _clean_block(b) -> dict | None:
    if not (isinstance(b, dict) and b.get("type") in BLOCK_TYPES):
        return None
    nb = new_block(b["type"])
    nb.update({k: v for k, v in b.items() if k in nb or k == "id"})
    if nb["type"] == "slideshow":
        # older files: "interval" 0 = off, 3/5/10 = autoplay every n seconds
        if "autoplay" not in b:
            nb["autoplay"] = bool(b.get("interval"))
            if not b.get("interval"):
                nb["interval"] = 4.0
        try:
            nb["interval"] = min(max(float(nb["interval"]), MIN_INTERVAL), MAX_INTERVAL)
        except (TypeError, ValueError):
            nb["interval"] = 4.0
        nb["autoplay"], nb["loop"] = bool(nb["autoplay"]), bool(nb["loop"])
    return nb


def normalize(tpl: dict) -> dict:
    """Fill in anything missing and drop unknown blocks, so a hand-edited or
    older file can't break study mode. Version-1 files (a flat "blocks" list)
    become one block per row."""
    out = {"version": 2}
    base = default_template()
    seen: set[str] = set()
    for side in ("front", "back"):
        src = tpl.get(side) if isinstance(tpl, dict) and isinstance(tpl.get(side), dict) else base[side]
        raw_rows = src.get("rows")
        if raw_rows is None:  # version 1
            raw_rows = [[b] for b in src.get("blocks", [])]
        rows = []
        for raw in raw_rows:
            row = []
            for b in (raw if isinstance(raw, list) else [raw]):
                nb = _clean_block(b)
                if nb:
                    if nb["id"] in seen:  # ids must be unique across the template
                        nb["id"] = new_block(nb["type"])["id"]
                    seen.add(nb["id"])
                    row.append(nb)
            if row:
                rows.append(row)
        out[side] = {"autoplay": bool(src.get("autoplay", base[side]["autoplay"])), "rows": rows}
    return out


# ------------------------------------------------------------ editing helpers
def blocks(side: dict):
    """All blocks of a side, top to bottom, left to right."""
    for row in side.get("rows", []):
        yield from row


def find(tpl: dict, block_id: str):
    """(side, row index, column index, block) or (None, -1, -1, None)."""
    for side in ("front", "back"):
        for r, row in enumerate(tpl[side]["rows"]):
            for c, b in enumerate(row):
                if b["id"] == block_id:
                    return side, r, c, b
    return None, -1, -1, None


def insert(tpl: dict, block: dict, target) -> None:
    rows = tpl[target[1]]["rows"]
    if target[0] == "row":
        rows.insert(max(0, min(target[2], len(rows))), [block])
    else:
        _, _, r, c = target
        if 0 <= r < len(rows):
            rows[r].insert(max(0, min(c, len(rows[r]))), block)
        else:
            rows.append([block])


def _drop_empty_rows(tpl: dict) -> None:
    for side in ("front", "back"):
        tpl[side]["rows"] = [row for row in tpl[side]["rows"] if row]


def remove(tpl: dict, block_id: str) -> dict | None:
    side, r, c, b = find(tpl, block_id)
    if b is None:
        return None
    del tpl[side]["rows"][r][c]
    _drop_empty_rows(tpl)
    return b


def move(tpl: dict, block_id: str, target) -> bool:
    """Move a block to a drop target. Works by inserting a copy at the target
    and then removing the original object, so no index juggling is needed."""
    side, r, c, original = find(tpl, block_id)
    if original is None:
        return False
    insert(tpl, dict(original), target)
    for s in ("front", "back"):
        for row in tpl[s]["rows"]:
            row[:] = [b for b in row if b is not original]
    _drop_empty_rows(tpl)
    return True


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
