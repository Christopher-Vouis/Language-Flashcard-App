"""
Draws one side of a flashcard from a template (see templates.py).

Used by study mode and by the template editor's live preview, so what you
design is exactly what you study.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import templates as T
import theme
from audio import play_wav

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

COLOR = {"text": theme.FG, "muted": theme.MUTED, "subtle": theme.SUBTLE,
         "accent": theme.ACCENT, "target": theme.TARGET}
ANCHOR = {"left": "w", "center": "center", "right": "e"}
JUSTIFY = {"left": "left", "center": "center", "right": "right"}


def fmt_time(seconds: float) -> str:
    seconds = max(float(seconds or 0), 0)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class CardView(tk.Frame):
    """A frame that shows one side of one card.

    scale        shrink fonts and images (the editor preview uses < 1)
    on_select    if given, clicking a block calls on_select(block_id) and the
                 selected block gets an outline (used by the editor)
    """

    def __init__(self, parent, scale: float = 1.0, on_select=None, **kw):
        super().__init__(parent, background=theme.BG, **kw)
        self.scale = scale
        self.on_select = on_select
        self._audio = ""
        self._images: list = []   # keep PhotoImages alive

    # ------------------------------------------------------------ public
    def show(self, card: dict | None, side: dict, abs_path, selected: str = "",
             empty_text: str = "") -> None:
        """Draw `side` (a template side) for `card`. abs_path(rel) turns a
        card's media path into a file path."""
        for w in self.winfo_children():
            w.destroy()
        self._images.clear()
        card = card or {}
        self._audio = abs_path(card.get("audio_clip", "")) if card else ""
        drawn = 0
        for block in side.get("blocks", []):
            if self._draw_block(block, card, abs_path, block.get("id") == selected):
                drawn += 1
        if not drawn:
            tk.Label(self, text=empty_text or "This side is empty.", bg=theme.BG, fg=theme.SUBTLE,
                     font=("Segoe UI", self._px(12))).pack(expand=True)

    def has_audio(self) -> bool:
        return bool(self._audio) and os.path.isfile(self._audio)

    def play(self) -> None:
        play_wav(self._audio)

    # ------------------------------------------------------------ blocks
    def _px(self, pt: int) -> int:
        return max(int(round(pt * self.scale)), 7)

    def _wrapper(self, block: dict, selected: bool, expand: bool = False) -> tk.Frame:
        """Each block sits in a frame that can show a selection outline and be clicked."""
        f = tk.Frame(self, background=theme.BG, highlightthickness=2 if self.on_select else 0,
                     highlightbackground=theme.ACCENT if selected else theme.BG,
                     highlightcolor=theme.ACCENT if selected else theme.BG)
        pad = self._px(6)
        if expand:
            f.pack(fill="both", expand=True, pady=pad)
        else:
            f.pack(fill="x", pady=pad)
        return f

    def _clickable(self, block: dict, *widgets) -> None:
        if not self.on_select:
            return
        for w in widgets:
            w.bind("<Button-1>", lambda e, bid=block["id"]: self.on_select(bid), add="+")
            try:
                w.configure(cursor="hand2")
            except tk.TclError:
                pass

    def _value(self, kind: str, block: dict, card: dict) -> str:
        if kind == "word":
            return card.get("target_word", "")
        if kind == "reading":
            return card.get("reading", "")
        if kind == "definition":
            return card.get("definition", "")
        if kind == "sentence":
            return card.get("sentence", "")
        if kind == "text":
            return block.get("text", "")
        if kind == "source":
            src = os.path.basename(card.get("source_file", ""))
            return f"{src}  ·  {fmt_time(card.get('start', 0))}" if src else ""
        return ""

    def _draw_block(self, block: dict, card: dict, abs_path, selected: bool) -> bool:
        kind = block["type"]
        if kind == "divider":
            f = self._wrapper(block, selected)
            line = tk.Frame(f, height=1, background=theme.BORDER)
            line.pack(fill="x", padx=self._px(10), pady=self._px(6))
            self._clickable(block, f, line)
            return True
        if kind == "audio":
            f = self._wrapper(block, selected)
            btn = ttk.Button(f, text="▶  Play audio", command=self.play, takefocus=False,
                             state="normal" if self.has_audio() else "disabled")
            btn.pack()
            self._clickable(block, f)
            return True
        if kind == "image":
            return self._draw_image(block, card, abs_path, selected)
        if kind == "sentence":
            return self._draw_sentence(block, card, selected)
        text = self._value(kind, block, card)
        if not text and not self.on_select:
            return False  # nothing to show (e.g. no reading) - skip in study mode
        f = self._wrapper(block, selected)
        font = ("Segoe UI", self._px(T.FONT_PX.get(block.get("size", "m"), 14)),
                "bold" if block.get("bold") else "normal")
        align = block.get("align", "center")
        lbl = tk.Label(f, text=text or f"({T.BLOCK_TYPES[kind]['label']} – empty on this card)",
                       font=font, bg=theme.BG,
                       fg=COLOR.get(block.get("color", "text"), theme.FG) if text else theme.SUBTLE,
                       anchor=ANCHOR[align], justify=JUSTIFY[align])
        lbl.pack(fill="x", padx=self._px(8))
        f.bind("<Configure>", lambda e: lbl.configure(wraplength=max(e.width - 24, 100)))
        self._clickable(block, f, lbl)
        return True

    def _draw_sentence(self, block: dict, card: dict, selected: bool) -> bool:
        text = card.get("sentence", "")
        if not text and not self.on_select:
            return False
        f = self._wrapper(block, selected)
        size = self._px(T.FONT_PX.get(block.get("size", "l"), 18))
        weight = "bold" if block.get("bold") else "normal"
        box = tk.Text(f, height=1, wrap="word", font=("Segoe UI", size, weight),
                      relief="flat", borderwidth=0, highlightthickness=0, background=theme.BG,
                      foreground=COLOR.get(block.get("color", "text"), theme.FG),
                      cursor="hand2" if self.on_select else "arrow", takefocus=False)
        align = block.get("align", "center")
        box.tag_configure("all", justify=JUSTIFY[align])
        box.tag_configure("target", foreground=theme.TARGET, font=("Segoe UI", size, "bold"))
        box.insert("1.0", text or "(Sentence – empty on this card)", "all")
        target = card.get("target_word", "")
        if text and target and block.get("highlight", True):
            start = "1.0"
            while True:
                pos = box.search(target, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(target)}c"
                box.tag_add("target", pos, end)
                start = end
        box.configure(state="disabled")
        box.pack(fill="x", padx=self._px(8))

        def fit_height(_e=None):
            # grow the box to the number of wrapped lines
            try:
                lines = box.count("1.0", "end", "displaylines")
                n = lines[0] if isinstance(lines, tuple) else lines
                box.configure(height=max(int(n or 1), 1))
            except tk.TclError:
                pass
        box.bind("<Configure>", lambda e: box.after_idle(fit_height))
        self._clickable(block, f, box)
        return True

    def _draw_image(self, block: dict, card: dict, abs_path, selected: bool) -> bool:
        path = abs_path(card.get("screenshot", "")) if card else ""
        has = bool(path) and os.path.isfile(path) and Image is not None
        if not has and not self.on_select:
            return False  # audio-only card: no empty grey box in study mode
        size = block.get("size", "fill")
        f = self._wrapper(block, selected, expand=(size == "fill"))
        holder = tk.Frame(f, background=theme.IMAGE_BG,
                          height=self._px(T.IMAGE_PX.get(size, 200)))
        if size == "fill":
            holder.configure(height=self._px(160))
            holder.pack(fill="both", expand=True)
        else:
            holder.pack(fill="x")
        holder.pack_propagate(False)
        lbl = tk.Label(holder, background=theme.IMAGE_BG, foreground=theme.MUTED,
                       font=("Segoe UI", self._px(10)),
                       text="" if has else "Screenshot (none on this card)")
        lbl.pack(fill="both", expand=True)
        self._clickable(block, f, holder, lbl)
        if has:
            with Image.open(path) as im:
                original = im.copy()
            state = {"size": None}

            def render(_e=None):
                w, h = max(lbl.winfo_width() - 4, 40), max(lbl.winfo_height() - 4, 40)
                if state["size"] == (w, h):
                    return
                state["size"] = (w, h)
                img = original.copy()
                img.thumbnail((w, h))
                photo = ImageTk.PhotoImage(img)
                self._images.append(photo)
                del self._images[:-8]
                lbl.configure(image=photo)
            lbl.bind("<Configure>", render)
        return True
