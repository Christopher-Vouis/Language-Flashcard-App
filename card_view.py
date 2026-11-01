"""
Draws one side of a flashcard from a template (see templates.py).

Used by study mode and by the template editor's preview, so what you design
is exactly what you study.

Modes
    "study"  study mode: buttons work, blocks with nothing to show are skipped
    "test"   the editor's Test preview: same as study
    "edit"   the editor's Edit preview: every block (buttons included) is a
             drag handle - pressing it starts a drag or selects it, and never
             presses the button; empty blocks show a placeholder so they can
             still be grabbed
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import templates as T
import theme
from audio import play_wav
from cards import card_images

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

    scale   shrink fonts and images (the editor preview uses < 1)
    mode    "study", "test" or "edit" (see module docstring)
    drag    in edit mode: an object with press(event, block_id),
            motion(event) and release(event) - the editor's drag handler
    """

    def __init__(self, parent, scale: float = 1.0, mode: str = "study", drag=None, **kw):
        super().__init__(parent, background=theme.BG, **kw)
        self.scale = scale
        self.mode = mode
        self.drag = drag
        self._audio = ""
        self._images: list = []   # keep PhotoImages alive
        # geometry for drag & drop: [(row_frame, [(block_id, block_frame), ...]), ...]
        # one entry per template row, in order (only complete in edit mode)
        self.rows: list[tuple[tk.Frame, list]] = []

    @property
    def editing(self) -> bool:
        return self.mode == "edit"

    # ------------------------------------------------------------ public
    def show(self, card: dict | None, side: dict, abs_path, selected: str = "",
             empty_text: str = "") -> None:
        """Draw `side` (a template side) for `card`. abs_path(rel) turns a
        card's media path into a file path."""
        for w in self.winfo_children():
            w.destroy()
        self._images.clear()
        self.rows = []
        card = card or {}
        self._audio = abs_path(card.get("audio_clip", "")) if card else ""
        self._card_images = card_images(card) if card else []
        for row in side.get("rows", []):
            grows = any(b["type"] in ("image", "slideshow") and b.get("size") == "fill" for b in row)
            rf = tk.Frame(self, background=theme.BG)
            rf.pack(fill="both" if grows else "x", expand=grows, pady=self._px(3))
            items = []
            for block in row:
                frame = self._draw_block(rf, block, card, abs_path, block.get("id") == selected)
                if frame is not None:
                    items.append((block["id"], frame))
            if items:
                self.rows.append((rf, items))
            else:
                rf.destroy()  # nothing on this row for this card (study/test mode)
        if not self.rows:
            tk.Label(self, text=empty_text or "This side is empty.", bg=theme.BG, fg=theme.SUBTLE,
                     font=("Segoe UI", self._px(12)), justify="center").pack(expand=True)

    def has_audio(self) -> bool:
        return bool(self._audio) and os.path.isfile(self._audio)

    def play(self) -> None:
        play_wav(self._audio)

    # ------------------------------------------------------------ helpers
    def _px(self, pt: int) -> int:
        return max(int(round(pt * self.scale)), 7)

    def _block_frame(self, row: tk.Frame, selected: bool, grow: bool = False) -> tk.Frame:
        """Each block sits in its own frame (side by side when a row has several)."""
        f = tk.Frame(row, background=theme.BG, highlightthickness=2 if self.editing else 0,
                     highlightbackground=theme.ACCENT if selected else theme.BORDER,
                     highlightcolor=theme.ACCENT if selected else theme.BORDER)
        f.pack(side="left", fill="both", expand=True, padx=self._px(3), pady=0)
        return f

    def _make_draggable(self, block: dict, frame: tk.Frame) -> None:
        """Edit mode: the whole block - every widget inside it - becomes a drag
        handle. Returning "break" stops buttons from being pressed and text
        from being selected."""
        if not (self.editing and self.drag):
            return
        bid = block["id"]

        def bind(w):
            w.bind("<ButtonPress-1>", lambda e: (self.drag.press(e, bid), "break")[1])
            w.bind("<B1-Motion>", lambda e: (self.drag.motion(e), "break")[1])
            w.bind("<ButtonRelease-1>", lambda e: (self.drag.release(e), "break")[1])
            w.bind("<Double-1>", lambda e: "break")
            try:
                w.configure(cursor="fleur")
            except tk.TclError:
                pass
            for child in w.winfo_children():
                bind(child)
        bind(frame)

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

    # ------------------------------------------------------------ blocks
    def _draw_block(self, row, block: dict, card: dict, abs_path, selected: bool):
        kind = block["type"]
        if kind == "image":
            f = self._draw_image(row, block, card, abs_path, selected)
        elif kind == "slideshow":
            f = self._draw_slideshow(row, block, abs_path, selected)
        elif kind == "sentence":
            f = self._draw_sentence(row, block, card, selected)
        elif kind == "divider":
            f = self._block_frame(row, selected)
            tk.Frame(f, height=1, background=theme.BORDER).pack(fill="x", padx=self._px(10),
                                                               pady=self._px(8))
        elif kind == "audio":
            f = self._block_frame(row, selected)
            ttk.Button(f, text="▶  Play audio", command=self.play, takefocus=False,
                       state="normal" if (self.has_audio() or self.editing) else "disabled"
                       ).pack(pady=self._px(2))
        else:
            f = self._draw_text(row, block, card, selected)
        if f is not None:
            self._make_draggable(block, f)
        return f

    def _draw_text(self, row, block: dict, card: dict, selected: bool):
        kind = block["type"]
        text = self._value(kind, block, card)
        if not text and not self.editing:
            return None  # nothing to show (e.g. no reading)
        f = self._block_frame(row, selected)
        font = ("Segoe UI", self._px(T.FONT_PX.get(block.get("size", "m"), 14)),
                "bold" if block.get("bold") else "normal")
        align = block.get("align", "center")
        lbl = tk.Label(f, text=text or f"({T.BLOCK_TYPES[kind]['label']} – empty on this card)",
                       font=font, bg=theme.BG,
                       fg=COLOR.get(block.get("color", "text"), theme.FG) if text else theme.SUBTLE,
                       anchor=ANCHOR[align], justify=JUSTIFY[align])
        lbl.pack(fill="both", expand=True, padx=self._px(6), pady=self._px(2))
        f.bind("<Configure>", lambda e: lbl.configure(wraplength=max(e.width - 20, 60)), add="+")
        return f

    def _draw_sentence(self, row, block: dict, card: dict, selected: bool):
        text = card.get("sentence", "")
        if not text and not self.editing:
            return None
        f = self._block_frame(row, selected)
        size = self._px(T.FONT_PX.get(block.get("size", "l"), 18))
        weight = "bold" if block.get("bold") else "normal"
        box = tk.Text(f, height=1, wrap="word", font=("Segoe UI", size, weight),
                      relief="flat", borderwidth=0, highlightthickness=0, background=theme.BG,
                      foreground=COLOR.get(block.get("color", "text"), theme.FG),
                      cursor="arrow", takefocus=False)
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
        box.pack(fill="x", padx=self._px(6), pady=self._px(2))

        def fit_height(_e=None):
            # grow the box to the number of wrapped lines
            try:
                lines = box.count("1.0", "end", "displaylines")
                n = lines[0] if isinstance(lines, tuple) else lines
                box.configure(height=max(int(n or 1), 1))
            except tk.TclError:
                pass
        box.bind("<Configure>", lambda e: box.after_idle(fit_height), add="+")
        return f

    def _image_area(self, parent, size: str, placeholder: str = ""):
        """A dark box that shows a picture scaled to fit. Returns set_path(path)."""
        holder = tk.Frame(parent, background=theme.IMAGE_BG, height=self._px(T.IMAGE_PX.get(size, 160)))
        holder.pack(fill="both", expand=(size == "fill"))
        holder.pack_propagate(False)
        lbl = tk.Label(holder, background=theme.IMAGE_BG, foreground=theme.MUTED,
                       font=("Segoe UI", self._px(10)), text=placeholder)
        lbl.pack(fill="both", expand=True)
        state = {"img": None, "size": None}

        def render(_e=None):
            if state["img"] is None:
                return
            w, h = max(lbl.winfo_width() - 4, 40), max(lbl.winfo_height() - 4, 40)
            if state["size"] == (w, h):
                return
            state["size"] = (w, h)
            img = state["img"].copy()
            img.thumbnail((w, h))
            photo = ImageTk.PhotoImage(img)
            self._images.append(photo)
            del self._images[:-24]
            lbl.configure(image=photo, text="")

        def set_path(path: str):
            state["img"], state["size"] = None, None
            if path and os.path.isfile(path) and Image is not None:
                try:
                    with Image.open(path) as im:
                        im.seek(0)                      # first frame of a GIF
                        state["img"] = im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im.copy()
                except OSError:
                    state["img"] = None
            if state["img"] is None:
                lbl.configure(image="", text=placeholder or "(picture can't be shown)")
            render()
        lbl.bind("<Configure>", render, add="+")
        return set_path

    def _draw_image(self, row, block: dict, card: dict, abs_path, selected: bool):
        i, img = T.resolve_image(block, self._card_images)
        path = abs_path(img["path"]) if img else ""
        has = bool(path) and os.path.isfile(path) and Image is not None
        if not has and not self.editing:
            return None  # this card has no such image: no empty grey box
        f = self._block_frame(row, selected)
        title = T.block_title(block, self._card_images)
        set_path = self._image_area(f, block.get("size", "fill"),
                                    "" if has else f"{title} (not on this card)")
        set_path(path if has else "")
        return f

    def _draw_slideshow(self, row, block: dict, abs_path, selected: bool):
        images = [img for img in self._card_images if os.path.isfile(abs_path(img["path"]))]
        if not images and not self.editing:
            return None
        f = self._block_frame(row, selected)
        set_path = self._image_area(f, block.get("size", "fill"),
                                    "Slideshow (this card has no images)" if not images else "")
        if not images:
            return f
        # autoplay: move to the next image every `interval` seconds (study / test only)
        interval = float(block.get("interval", 4) or 4)
        loop = bool(block.get("loop", True))
        can_autoplay = bool(block.get("autoplay")) and len(images) > 1
        state = {"i": 0, "job": None, "playing": can_autoplay and not self.editing}
        counter = tk.StringVar()
        pause_btn = None

        def show(i):
            state["i"] = i % len(images)
            set_path(abs_path(images[state["i"]]["path"]))
            counter.set(f"{state['i'] + 1} / {len(images)}")

        def cancel():
            if state["job"]:
                try:
                    f.after_cancel(state["job"])
                except tk.TclError:
                    pass
                state["job"] = None

        def schedule():
            cancel()
            if state["playing"]:
                state["job"] = f.after(max(int(interval * 1000), 500), tick)

        def tick():
            state["job"] = None
            if not loop and state["i"] == len(images) - 1:
                set_playing(False)          # reached the last image: stop there
                return
            show(state["i"] + 1)
            schedule()

        def set_playing(on: bool):
            state["playing"] = on
            if pause_btn is not None:
                pause_btn.configure(text="⏸" if on else "⏵")
            schedule()

        def toggle():
            if not state["playing"] and not loop and state["i"] == len(images) - 1:
                show(0)                     # finished: play again from the start
            set_playing(not state["playing"])

        def step(delta):
            show(state["i"] + delta)
            schedule()                      # a manual step restarts the timer

        if len(images) > 1:
            bar = tk.Frame(f, background=theme.BG)
            bar.pack(pady=(self._px(4), 0))
            ttk.Button(bar, text="◀", width=3, takefocus=False, command=lambda: step(-1)).pack(side="left")
            tk.Label(bar, textvariable=counter, background=theme.BG, foreground=theme.MUTED,
                     font=("Segoe UI", self._px(10)), width=7).pack(side="left")
            ttk.Button(bar, text="▶", width=3, takefocus=False, command=lambda: step(1)).pack(side="left")
            if can_autoplay:
                pause_btn = ttk.Button(bar, text="⏸" if state["playing"] else "⏵", width=3,
                                       takefocus=False, command=toggle)
                pause_btn.pack(side="left", padx=(self._px(8), 0))
                if self.editing:
                    tk.Label(bar, text=f"autoplay every {interval:g} s" + ("" if loop else ", once"),
                             background=theme.BG, foreground=theme.SUBTLE,
                             font=("Segoe UI", self._px(9))).pack(side="left", padx=(self._px(6), 0))

        f.bind("<Destroy>", lambda e: cancel(), add="+")
        show(0)
        schedule()
        return f
