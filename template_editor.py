"""
Drag-and-drop card layout editor.

Left:    the block palette. Drag a block onto the preview or the Front / Back
         lists to add it (or double-click it to add it to the side shown in
         the preview).
Middle:  the Front and Back as rows of blocks (blocks in the same row sit side
         by side). Drag to reorder, drag between sides, drag back onto the
         palette (or click ✕) to remove.
Right:   the preview, with an Edit / Test switch.
           Edit - blocks are drag handles: press and hold to move them (drop
                  at a row's top/bottom edge for a new row, or in its middle
                  to sit beside the other blocks); click to select. Buttons
                  don't press.
           Test - the card works like in study mode: buttons press, Flip and
                  Next card, audio plays automatically if switched on.
         Below it, the selected block's settings.

Drop targets (see templates.py):  ("row", side, r)  or  ("in", side, r, c)
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

import templates as T
import theme
from audio import stop_wav
from card_view import CardView

SAMPLE_CARD = {"target_word": "夜", "reading": "よる", "definition": "night; evening",
               "sentence": "夜に駆ける", "source_file": "example video.mp4", "start": 83.0,
               "audio_clip": "", "screenshot": ""}
SIDE_LABEL = {"front": "Front", "back": "Back"}
EDGE = 0.3   # top/bottom share of a row that means "new row" rather than "beside"


class TemplateEditor(tk.Toplevel):
    def __init__(self, app, template: dict, cards, on_save):
        super().__init__(app)
        self.app = app
        self.cards = cards
        self.on_save = on_save
        self.title(f"Card layout  ·  {app.profile['name']}")
        theme.dark_title_bar(self)
        self.geometry("1320x840")
        self.minsize(1140, 720)

        self.tpl = T.normalize(template)
        self.saved_json = self._json()
        self.history: list[dict] = []
        self.selected: str = ""             # id of the selected block
        self.preview_side = "front"
        samples = cards.cards_in(cards.selected_deck) or cards.cards
        self.samples = samples or [SAMPLE_CARD]
        self.sample_i = 0
        self._drag: dict | None = None
        self.list_rows: dict[str, list] = {"front": [], "back": []}   # geometry of the lists

        self._style()
        self._build()
        self._refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        self.bind("<Delete>", self._delete_key)
        for key, (dr, dc) in (("Up", (-1, 0)), ("Down", (1, 0)), ("Left", (0, -1)), ("Right", (0, 1))):
            self.bind(f"<Control-{key}>", lambda e, dr=dr, dc=dc: self.nudge(dr, dc))

    # ================================================================ layout
    def _style(self):
        s = ttk.Style(self)
        s.configure("Seg.Toolbutton", background=theme.RAISED, foreground=theme.FG,
                    bordercolor=theme.BORDER, lightcolor=theme.RAISED, darkcolor=theme.RAISED,
                    padding=(10, 4), anchor="center")
        s.map("Seg.Toolbutton",
              background=[("selected", theme.ACCENT), ("active", theme.RAISED_HOVER)],
              lightcolor=[("selected", theme.ACCENT)], darkcolor=[("selected", theme.ACCENT)],
              foreground=[("selected", "#ffffff")])
        s.configure("Save.TButton", background=theme.ACCENT, lightcolor=theme.ACCENT,
                    darkcolor=theme.ACCENT, foreground="#ffffff", padding=(18, 6))
        s.map("Save.TButton", background=[("active", theme.ACCENT_HOVER)],
              lightcolor=[("active", theme.ACCENT_HOVER)], darkcolor=[("active", theme.ACCENT_HOVER)])
        s.configure("Head.TLabel", font=("Segoe UI", 13, "bold"))
        s.configure("Hint.TLabel", foreground=theme.SUBTLE, font=("Segoe UI", 9))

    def _build(self):
        body = ttk.Frame(self, padding=(14, 12, 14, 6))
        body.pack(fill="both", expand=True)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        # ---------------- palette
        pal = ttk.Frame(body)
        pal.grid(row=0, column=0, sticky="ns")
        ttk.Label(pal, text="Blocks", style="Head.TLabel").pack(anchor="w")
        ttk.Label(pal, text="Drag a block onto the preview\nor the Front / Back lists.\n"
                            "Double-click to add it to the\nside shown in the preview.",
                  style="Hint.TLabel", justify="left").pack(anchor="w", pady=(2, 10))
        self.palette = tk.Frame(pal, background=theme.BG)
        self.palette.pack(fill="both", expand=True, anchor="n")
        for kind in T.BLOCK_TYPES:
            chip = self._make_chip(self.palette, kind)
            chip.pack(fill="x", pady=3)
            self._bind_drag(chip, ("palette", kind))
            for w in self._chip_widgets(chip):
                w.bind("<Double-1>", lambda e, k=kind: self.add_block(
                    k, ("row", self.preview_side, len(self.tpl[self.preview_side]["rows"]))), add="+")
        self.trash_hint = ttk.Label(pal, text="Drop a block here to remove it", style="Hint.TLabel")
        self.trash_hint.pack(anchor="w", pady=(8, 0))

        # ---------------- front / back lists
        sides = ttk.Frame(body)
        sides.grid(row=0, column=1, sticky="ns", padx=(18, 18))
        self.side_box: dict[str, tk.Frame] = {}
        self.autoplay_vars: dict[str, tk.BooleanVar] = {}
        for side in ("front", "back"):
            head = ttk.Frame(sides)
            head.pack(fill="x", pady=(0 if side == "front" else 14, 4))
            ttk.Label(head, text=SIDE_LABEL[side].upper(), style="Head.TLabel").pack(side="left")
            var = tk.BooleanVar(value=self.tpl[side]["autoplay"])
            self.autoplay_vars[side] = var
            ttk.Checkbutton(head, text="Play audio automatically", variable=var,
                            command=lambda s=side: self._set_autoplay(s)).pack(side="right")
            box = tk.Frame(sides, background=theme.SURFACE, highlightthickness=1,
                           highlightbackground=theme.BORDER, width=340, height=270)
            box.pack(fill="both", expand=True)
            box.pack_propagate(False)
            box.bind("<Button-1>", lambda e, s=side: self.show_preview_side(s))
            self.side_box[side] = box
        ttk.Label(sides, text="Blocks in one row sit side by side.", style="Hint.TLabel").pack(anchor="w", pady=(6, 0))
        self.indicator = tk.Frame(self, background=theme.ACCENT)

        # ---------------- preview + settings
        right = ttk.Frame(body)
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        bar = ttk.Frame(right)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="Preview", style="Head.TLabel").pack(side="left")
        self.side_var = tk.StringVar(value="front")
        for side in ("front", "back"):
            ttk.Radiobutton(bar, text=SIDE_LABEL[side], value=side, variable=self.side_var,
                            style="Seg.Toolbutton",
                            command=lambda: self.show_preview_side(self.side_var.get())
                            ).pack(side="left", padx=(10 if side == "front" else 0, 0))
        self.mode_var = tk.StringVar(value="edit")
        for value, text in (("edit", "✎  Edit"), ("test", "▶  Test")):
            ttk.Radiobutton(bar, text=text, value=value, variable=self.mode_var, style="Seg.Toolbutton",
                            command=self._mode_changed).pack(side="left", padx=(16 if value == "edit" else 0, 0))
        nav = ttk.Frame(bar)
        nav.pack(side="right")
        ttk.Button(nav, text="◀", width=3, command=lambda: self._step_sample(-1)).pack(side="left")
        self.sample_var = tk.StringVar()
        ttk.Label(nav, textvariable=self.sample_var, foreground=theme.MUTED, width=16,
                  anchor="center").pack(side="left", padx=4)
        ttk.Button(nav, text="▶", width=3, command=lambda: self._step_sample(1)).pack(side="left")

        self.preview_frame = tk.Frame(right, background=theme.BG, highlightthickness=1,
                                      highlightbackground=theme.BORDER)
        self.preview_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 4))
        self.preview = CardView(self.preview_frame, scale=0.72, mode="edit", drag=self)
        self.preview.pack(fill="both", expand=True, padx=12, pady=8)

        # test-mode controls (shown only in Test)
        self.test_bar = ttk.Frame(right)
        self.test_btn = ttk.Button(self.test_bar, text="Flip", width=16, command=self._test_advance)
        self.test_btn.pack(side="left")
        ttk.Label(self.test_bar, text="Testing: buttons work and audio plays as in study mode.",
                  style="Hint.TLabel").pack(side="left", padx=12)

        self.hint_var = tk.StringVar()
        ttk.Label(right, textvariable=self.hint_var, style="Hint.TLabel").grid(row=3, column=0, sticky="w")
        self.props = ttk.Frame(right, padding=(0, 8, 0, 0))
        self.props.grid(row=4, column=0, sticky="ew")

        # ---------------- bottom bar
        bottom = ttk.Frame(self, padding=(14, 6, 14, 12))
        bottom.pack(fill="x")
        self.undo_btn = ttk.Button(bottom, text="↶  Undo", command=self.undo)
        self.undo_btn.pack(side="left")
        ttk.Button(bottom, text="Reset to default layout", command=self.reset).pack(side="left", padx=6)
        self.status_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.status_var, foreground=theme.MUTED).pack(side="left", padx=12)
        ttk.Button(bottom, text="Save", style="Save.TButton", command=self.save).pack(side="right")
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right", padx=6)

    # ---------------------------------------------------------------- chips
    def _make_chip(self, parent, kind: str, block_id: str = "", compact: bool = False) -> tk.Frame:
        info = T.BLOCK_TYPES[kind]
        chip = tk.Frame(parent, background=theme.RAISED, highlightthickness=1,
                        highlightbackground=theme.BORDER, cursor="fleur")
        if not compact:
            tk.Label(chip, text="⠿", background=theme.RAISED, foreground=theme.SUBTLE,
                     font=("Segoe UI", 11)).pack(side="left", padx=(6, 2), pady=5)
        tk.Label(chip, text=info["icon"], background=theme.RAISED, foreground=theme.ACCENT,
                 font=("Segoe UI", 11, "bold"), width=2).pack(side="left", padx=(4 if compact else 0, 0), pady=5)
        tk.Label(chip, text=info["label"], background=theme.RAISED, foreground=theme.FG,
                 font=("Segoe UI", 10), anchor="w", width=1 if compact else 0
                 ).pack(side="left", fill="x", expand=True, padx=(4, 2))
        chip.remove_label = None
        if block_id:
            x = tk.Label(chip, text="✕", background=theme.RAISED, foreground=theme.MUTED,
                         font=("Segoe UI", 10), cursor="hand2", padx=6)
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, bid=block_id: (self.remove_block(bid), "break")[1])
            chip.remove_label = x
        chip.kind = kind
        chip.block_id = block_id
        for w in self._chip_widgets(chip):
            w.bind("<Enter>", lambda e, c=chip: self._hover(c, True), add="+")
            w.bind("<Leave>", lambda e, c=chip: self._hover(c, False), add="+")
        return chip

    @staticmethod
    def _chip_widgets(chip):
        return [chip, *chip.winfo_children()]

    def _paint_chip(self, chip, bg, border):
        chip.configure(background=bg, highlightbackground=border)
        for w in chip.winfo_children():
            w.configure(background=bg)

    def _hover(self, chip, inside: bool):
        if self._drag:
            return
        selected = chip.block_id and chip.block_id == self.selected
        self._paint_chip(chip, theme.RAISED_HOVER if inside else theme.RAISED,
                         theme.ACCENT if selected else theme.BORDER)

    def _refresh_lists(self):
        for side in ("front", "back"):
            box = self.side_box[side]
            for w in box.winfo_children():
                w.destroy()
            self.list_rows[side] = []
            rows = self.tpl[side]["rows"]
            if not rows:
                tk.Label(box, text="Drag blocks here", background=theme.SURFACE, foreground=theme.SUBTLE,
                         font=("Segoe UI", 11, "italic")).pack(expand=True)
            for row in rows:
                multi = len(row) > 1
                rf = tk.Frame(box, background=theme.SURFACE, highlightthickness=1 if multi else 0,
                              highlightbackground=theme.BORDER)
                rf.pack(fill="x", padx=6, pady=(6, 0))
                items = []
                for b in row:
                    chip = self._make_chip(rf, b["type"], block_id=b["id"], compact=multi)
                    chip.pack(side="left", fill="x", expand=True, padx=2 if multi else 0, pady=2 if multi else 0)
                    self._bind_drag(chip, ("block", b["id"]))
                    if b["id"] == self.selected:
                        self._paint_chip(chip, theme.RAISED, theme.ACCENT)
                    items.append((b["id"], chip))
                self.list_rows[side].append((rf, items))
            self.autoplay_vars[side].set(self.tpl[side]["autoplay"])

    # ============================================================ drag & drop
    # The preview's CardView calls press/motion/release directly (with a block id).
    def _bind_drag(self, chip, source):
        for w in self._chip_widgets(chip):
            if w is chip.remove_label:
                continue  # the ✕ is a button, not a drag handle
            w.bind("<ButtonPress-1>", lambda e, s=source: self.press(e, s))
            w.bind("<B1-Motion>", self.motion)
            w.bind("<ButtonRelease-1>", self.release)

    def press(self, e, source):
        if isinstance(source, str):          # from the preview: a block id
            source = ("block", source)
        self._drag = {"src": source, "x": e.x_root, "y": e.y_root, "ghost": None}

    def motion(self, e):
        d = self._drag
        if not d:
            return
        if d["ghost"] is None:
            if abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) < 6:
                return  # still a click, not a drag
            kind = d["src"][1] if d["src"][0] == "palette" else T.find(self.tpl, d["src"][1])[3]["type"]
            d["ghost"] = self._make_ghost(kind)
        d["ghost"].geometry(f"+{e.x_root + 14}+{e.y_root + 8}")
        target, ind = self._drop_target(e.x_root, e.y_root)
        self._show_indicator(ind)
        trash = target is None and d["src"][0] == "block" and self._over(self.palette, e.x_root, e.y_root)
        self.trash_hint.configure(foreground=theme.TARGET if trash else theme.SUBTLE)

    def release(self, e):
        d, self._drag = self._drag, None
        self.indicator.place_forget()
        self.trash_hint.configure(foreground=theme.SUBTLE)
        if not d:
            return
        src = d["src"]
        if d["ghost"] is None:  # a click, not a drag
            if src[0] == "block":
                self.select(src[1])
            return
        d["ghost"].destroy()
        target, _ = self._drop_target(e.x_root, e.y_root)
        if target:
            if src[0] == "palette":
                self.add_block(src[1], target)
            else:
                self.move_block(src[1], target)
        elif src[0] == "block" and self._over(self.palette, e.x_root, e.y_root):
            self.remove_block(src[1])

    def _make_ghost(self, kind: str) -> tk.Toplevel:
        g = tk.Toplevel(self)
        g.overrideredirect(True)
        try:
            g.attributes("-alpha", 0.85)
            g.attributes("-topmost", True)
        except tk.TclError:
            pass
        info = T.BLOCK_TYPES[kind]
        tk.Label(g, text=f"  {info['icon']}   {info['label']}  ", background=theme.ACCENT,
                 foreground="#ffffff", font=("Segoe UI", 10, "bold"), pady=5).pack()
        return g

    @staticmethod
    def _over(widget, xr, yr, margin: int = 0) -> bool:
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        return (x - margin <= xr <= x + widget.winfo_width() + margin
                and y - margin <= yr <= y + widget.winfo_height() + margin)

    def _drop_target(self, xr: int, yr: int):
        """(target, indicator) for the pointer position, or (None, None)."""
        if self.mode_var.get() == "edit" and self._over(self.preview_frame, xr, yr):
            return self._target_in(self.preview, self.preview_side, self.preview.rows, xr, yr)
        for side, box in self.side_box.items():
            if self._over(box, xr, yr, margin=12):
                return self._target_in(box, side, self.list_rows[side], xr, yr)
        return None, None

    @staticmethod
    def _target_in(surface, side: str, rows, xr: int, yr: int):
        """Work out where a drop lands on a surface whose rows are
        [(row_frame, [(block_id, widget), ...]), ...]."""
        stop = surface.winfo_rooty()
        if not rows:
            return ("row", side, 0), ("h", surface, 8)
        for r, (rf, items) in enumerate(rows):
            top = rf.winfo_rooty()
            h = max(rf.winfo_height(), 1)
            bottom = top + h
            if yr < top:                                   # in the gap above this row
                return ("row", side, r), ("h", surface, top - stop - 3)
            if yr <= bottom:
                edge = h * EDGE
                if yr < top + edge:                        # top edge: new row above
                    return ("row", side, r), ("h", surface, top - stop - 3)
                if yr > bottom - edge:                     # bottom edge: new row below
                    return ("row", side, r + 1), ("h", surface, bottom - stop + 1)
                c = sum(1 for _, w in items if xr > w.winfo_rootx() + w.winfo_width() / 2)
                if c < len(items):                         # middle: beside, in this row
                    x = items[c][1].winfo_rootx() - rf.winfo_rootx() - 3
                else:
                    last = items[-1][1]
                    x = last.winfo_rootx() - rf.winfo_rootx() + last.winfo_width()
                return ("in", side, r, c), ("v", rf, x)
        last_rf = rows[-1][0]
        return ("row", side, len(rows)), ("h", surface, last_rf.winfo_rooty() + last_rf.winfo_height() - stop + 2)

    def _show_indicator(self, ind):
        if not ind:
            self.indicator.place_forget()
            return
        kind, widget, pos = ind
        if kind == "h":   # a new row here
            self.indicator.place(in_=widget, x=4, y=max(int(pos), 0), relwidth=1.0, width=-8, height=3)
        else:             # beside, in this row
            self.indicator.place(in_=widget, x=max(int(pos), 0), y=0, width=3, relheight=1.0)
        self.indicator.lift()

    # ============================================================== editing
    def _json(self) -> str:
        return json.dumps(self.tpl, sort_keys=True)

    def _push(self):
        self.history.append(T.clone(self.tpl))
        del self.history[:-60]

    def add_block(self, kind: str, target):
        self._push()
        block = T.new_block(kind)
        T.insert(self.tpl, block, target)
        self.selected = block["id"]
        self.preview_side = target[1]
        self._refresh_all()

    def move_block(self, block_id: str, target):
        before = self._json()
        self._push()
        T.move(self.tpl, block_id, target)
        if self._json() == before:
            self.history.pop()  # dropped where it already was
        self.selected = block_id
        self.preview_side = target[1]
        self._refresh_all()

    def remove_block(self, block_id: str):
        side = T.find(self.tpl, block_id)[0]
        if side is None:
            return
        self._push()
        T.remove(self.tpl, block_id)
        if self.selected == block_id:
            self.selected = ""
        self.preview_side = side
        self._refresh_all()

    def nudge(self, dr: int, dc: int):
        """Keyboard / button moves for the selected block.
        ← →  move within its row.   ↑ ↓  move to the row above / below; a block
        that shares its row is first taken out onto a row of its own."""
        side, r, c, block = T.find(self.tpl, self.selected)
        if block is None:
            return "break"
        row = self.tpl[side]["rows"][r]
        n_rows = len(self.tpl[side]["rows"])
        target = None
        if dc < 0 and c > 0:
            target = ("in", side, r, c - 1)
        elif dc > 0 and c < len(row) - 1:
            target = ("in", side, r, c + 2)
        elif dr < 0:
            target = ("row", side, r) if len(row) > 1 else (("row", side, r - 1) if r > 0 else None)
        elif dr > 0:
            target = ("row", side, r + 1) if len(row) > 1 else (("row", side, r + 2) if r < n_rows - 1 else None)
        if target:
            self.move_block(block["id"], target)
        return "break"

    def move_selected_to_other_side(self):
        side, r, c, block = T.find(self.tpl, self.selected)
        if block is not None:
            other = "back" if side == "front" else "front"
            self.move_block(block["id"], ("row", other, len(self.tpl[other]["rows"])))

    def duplicate_selected(self):
        side, r, c, block = T.find(self.tpl, self.selected)
        if block is None:
            return
        self._push()
        copy = dict(block, id=T.new_block(block["type"])["id"])
        T.insert(self.tpl, copy, ("row", side, r + 1))
        self.selected = copy["id"]
        self._refresh_all()

    def _delete_key(self, e):
        if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) and e.widget.winfo_toplevel() is self \
                and str(e.widget.cget("state")) == "normal":
            return None  # deleting text in the Custom text box
        if self.selected:
            self.remove_block(self.selected)
        return "break"

    def _set_autoplay(self, side: str):
        self._push()
        self.tpl[side]["autoplay"] = bool(self.autoplay_vars[side].get())
        self._update_status()

    def set_prop(self, key: str, value):
        block = T.find(self.tpl, self.selected)[3]
        if block is None or block.get(key) == value:
            return
        self._push()
        block[key] = value
        self._refresh_preview()
        self._update_status()

    def undo(self):
        if not self.history:
            return
        self.tpl = self.history.pop()
        if T.find(self.tpl, self.selected)[3] is None:
            self.selected = ""
        self._refresh_all()

    def reset(self):
        if not messagebox.askyesno("Reset layout", "Go back to the default card layout?\n\n"
                                   "(You can Undo this.)", parent=self):
            return
        self._push()
        self.tpl = T.default_template()
        self.selected = ""
        self._refresh_all()

    # ============================================================ selection
    def select(self, block_id: str):
        side = T.find(self.tpl, block_id)[0]
        if side is None:
            return
        self.selected = block_id
        self.preview_side = side
        self._refresh_all()

    def show_preview_side(self, side: str):
        self.preview_side = side
        self.side_var.set(side)
        self._refresh_preview()

    def _step_sample(self, delta: int):
        self.sample_i = (self.sample_i + delta) % len(self.samples)
        if self.mode_var.get() == "test":
            self.preview_side = "front"
            self.side_var.set("front")
            self._refresh_preview(autoplay=True)
        else:
            self._refresh_preview()

    # ============================================================ test mode
    def _mode_changed(self):
        stop_wav()
        if self.mode_var.get() == "test":
            self.preview_side = "front"
            self.side_var.set("front")
            self.test_bar.grid(row=2, column=0, sticky="w", pady=(0, 6))
            self._refresh_preview(autoplay=True)
        else:
            self.test_bar.grid_forget()
            self._refresh_preview()
        self._refresh_props()

    def _test_advance(self):
        """Test mode's Flip / Next card button, like study mode."""
        stop_wav()
        if self.preview_side == "front":
            self.preview_side = "back"
        else:
            self.preview_side = "front"
            self.sample_i = (self.sample_i + 1) % len(self.samples)
        self.side_var.set(self.preview_side)
        self._refresh_preview(autoplay=True)

    # ============================================================ refreshing
    def _refresh_all(self):
        self.side_var.set(self.preview_side)
        self._refresh_lists()
        self._refresh_preview()
        self._refresh_props()
        self._update_status()

    def _refresh_preview(self, autoplay: bool = False):
        card = self.samples[self.sample_i]
        real = card is not SAMPLE_CARD
        testing = self.mode_var.get() == "test"
        self.sample_var.set(f"card {self.sample_i + 1} of {len(self.samples)}" if real else "example card")
        self.preview.mode = "test" if testing else "edit"
        side = self.tpl[self.preview_side]
        self.preview.show(card, side, self.cards.abs_path if real else (lambda rel: ""),
                          selected="" if testing else self.selected,
                          empty_text=f"The {self.preview_side} is empty.\nDrag blocks onto it from the left.")
        if testing:
            self.test_btn.configure(text="Flip" if self.preview_side == "front" else "Next card  →")
            self.hint_var.set("")
            if autoplay and side.get("autoplay"):
                self.preview.play()
        else:
            self.hint_var.set("Edit: press and hold a block to drag it — drop at a row's top or bottom edge "
                              "for a new row, or in its middle to place it side by side. Click to select.")

    def _update_status(self):
        dirty = self._json() != self.saved_json
        self.status_var.set("Unsaved changes" if dirty else "All changes saved  ✓")
        self.undo_btn.configure(state="normal" if self.history else "disabled")

    def _refresh_props(self):
        for w in self.props.winfo_children():
            w.destroy()
        if self.mode_var.get() == "test":
            ttk.Label(self.props, text="Switch the preview to ✎ Edit to change the layout.",
                      foreground=theme.MUTED).pack(anchor="w")
            return
        side, r, c, block = T.find(self.tpl, self.selected)
        if block is None:
            ttk.Label(self.props, text="No block selected — click one to change how it looks.",
                      foreground=theme.MUTED).pack(anchor="w")
            return
        info = T.BLOCK_TYPES[block["type"]]
        row_len = len(self.tpl[side]["rows"][r])
        head = ttk.Frame(self.props)
        head.pack(fill="x", pady=(0, 6))
        ttk.Label(head, text=f"{info['icon']}  {info['label']}", style="Head.TLabel").pack(side="left")
        where = f"on the {SIDE_LABEL[side].lower()}, row {r + 1}" + \
                (f", {c + 1} of {row_len} side by side" if row_len > 1 else "")
        ttk.Label(head, text=where, foreground=theme.MUTED).pack(side="left", padx=8)
        for text, cmd in (("✕  Remove", lambda: self.remove_block(block["id"])),
                          ("⧉  Duplicate", self.duplicate_selected),
                          (f"⇄  To {('back' if side == 'front' else 'front')}", self.move_selected_to_other_side),
                          ("→", lambda: self.nudge(0, 1)), ("←", lambda: self.nudge(0, -1)),
                          ("↓", lambda: self.nudge(1, 0)), ("↑", lambda: self.nudge(-1, 0))):
            ttk.Button(head, text=text, command=cmd, width=3 if len(text) == 1 else 0).pack(side="right", padx=(4, 0))

        grid = ttk.Frame(self.props)
        grid.pack(fill="x")
        row = 0

        def segmented(label: str, key: str, options):
            nonlocal row
            ttk.Label(grid, text=label, foreground=theme.MUTED).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 12))
            var = tk.StringVar(value=block.get(key))
            f = ttk.Frame(grid)
            f.grid(row=row, column=1, sticky="w", pady=3)
            for value, text in options:
                ttk.Radiobutton(f, text=text, value=value, variable=var, style="Seg.Toolbutton",
                                command=lambda: self.set_prop(key, var.get())).pack(side="left")
            row += 1

        if block["type"] == "image":
            segmented("Size", "size", T.IMAGE_SIZES)
        elif info["text"]:
            segmented("Size", "size", T.TEXT_SIZES)
            segmented("Alignment", "align", T.ALIGNS)
            segmented("Colour", "color", T.COLORS)
            opts = ttk.Frame(grid)
            opts.grid(row=row, column=1, sticky="w", pady=3)
            bold = tk.BooleanVar(value=block.get("bold", False))
            ttk.Checkbutton(opts, text="Bold", variable=bold,
                            command=lambda: self.set_prop("bold", bold.get())).pack(side="left")
            if block["type"] == "sentence":
                hl = tk.BooleanVar(value=block.get("highlight", True))
                ttk.Checkbutton(opts, text="Highlight the target word in red", variable=hl,
                                command=lambda: self.set_prop("highlight", hl.get())).pack(side="left", padx=14)
            row += 1
            if block["type"] == "text":
                ttk.Label(grid, text="Text", foreground=theme.MUTED).grid(row=row, column=0, sticky="w", pady=3)
                tv = tk.StringVar(value=block.get("text", ""))
                entry = ttk.Entry(grid, textvariable=tv, width=44)
                entry.grid(row=row, column=1, sticky="w", pady=3)
                entry.bind("<FocusOut>", lambda e: self.set_prop("text", tv.get()))
                entry.bind("<Return>", lambda e: self.set_prop("text", tv.get()))
        else:
            ttk.Label(grid, text="This block has no settings — drag it to where you want it.",
                      foreground=theme.MUTED).grid(row=0, column=0, sticky="w")

    # ============================================================ save / close
    def save(self):
        self.on_save(self.tpl)
        self.saved_json = self._json()
        self._update_status()

    def close(self):
        if self._json() != self.saved_json:
            answer = messagebox.askyesnocancel("Card layout", "Save your changes to the card layout?",
                                               parent=self)
            if answer is None:
                return
            if answer:
                self.save()
        stop_wav()
        self.destroy()
