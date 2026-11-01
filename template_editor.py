"""
Drag-and-drop card layout editor.

Left:    the block palette. Drag a block onto the Front or Back to add it
         (or double-click it to add it to the side being previewed).
Middle:  the Front and Back, as stacks of blocks. Drag to reorder, drag
         between sides, drag back onto the palette (or click ✕) to remove.
Right:   a live preview using one of your real cards, and the settings of
         the selected block (size, alignment, colour, ...).
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


class TemplateEditor(tk.Toplevel):
    def __init__(self, app, template: dict, cards, on_save):
        super().__init__(app)
        self.app = app
        self.cards = cards
        self.on_save = on_save
        self.title(f"Card layout  ·  {app.profile['name']}")
        theme.dark_title_bar(self)
        self.geometry("1300x820")
        self.minsize(1120, 700)

        self.tpl = T.clone(template)
        self.saved_json = self._json()
        self.history: list[dict] = []
        self.selected: str = ""             # id of the selected block
        self.preview_side = "front"
        samples = cards.cards_in(cards.selected_deck) or cards.cards
        self.samples = samples or [SAMPLE_CARD]
        self.sample_i = 0
        self._drag: dict | None = None
        self.chips: dict[str, list[tk.Frame]] = {"front": [], "back": []}

        self._style()
        self._build()
        self._refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        self.bind("<Delete>", self._delete_key)
        self.bind("<Control-Up>", lambda e: self.move_selected(-1))
        self.bind("<Control-Down>", lambda e: self.move_selected(1))

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
        pal = ttk.Frame(body, width=230)
        pal.grid(row=0, column=0, sticky="ns")
        ttk.Label(pal, text="Blocks", style="Head.TLabel").pack(anchor="w")
        ttk.Label(pal, text="Drag a block onto the Front or Back.\nDouble-click to add it to the\nside shown in the preview.",
                  style="Hint.TLabel", justify="left").pack(anchor="w", pady=(2, 10))
        self.palette = tk.Frame(pal, background=theme.BG)
        self.palette.pack(fill="y", expand=True, anchor="n")
        for kind, info in T.BLOCK_TYPES.items():
            chip = self._make_chip(self.palette, kind, removable=False)
            chip.pack(fill="x", pady=3)
            self._bind_drag(chip, ("palette", kind))
            for w in self._chip_widgets(chip):
                w.bind("<Double-1>", lambda e, k=kind: self.add_block(k, self.preview_side), add="+")
        self.trash_hint = ttk.Label(pal, text="Drop a block here to remove it", style="Hint.TLabel")
        self.trash_hint.pack(anchor="w", pady=(8, 0))

        # ---------------- front / back stacks
        sides = ttk.Frame(body, width=330)
        sides.grid(row=0, column=1, sticky="ns", padx=(18, 18))
        self.side_box: dict[str, tk.Frame] = {}
        self.autoplay_vars: dict[str, tk.BooleanVar] = {}
        self.empty_labels: dict[str, tk.Label] = {}
        for side in ("front", "back"):
            head = ttk.Frame(sides)
            head.pack(fill="x", pady=(0 if side == "front" else 14, 4))
            ttk.Label(head, text=SIDE_LABEL[side].upper(), style="Head.TLabel").pack(side="left")
            var = tk.BooleanVar(value=self.tpl[side]["autoplay"])
            self.autoplay_vars[side] = var
            ttk.Checkbutton(head, text="Play audio automatically", variable=var,
                            command=lambda s=side: self._set_autoplay(s)).pack(side="right")
            box = tk.Frame(sides, background=theme.SURFACE, highlightthickness=1,
                           highlightbackground=theme.BORDER, width=320, height=250)
            box.pack(fill="both", expand=True)
            box.pack_propagate(False)
            box.bind("<Button-1>", lambda e, s=side: self.show_preview_side(s))
            self.side_box[side] = box
            self.empty_labels[side] = tk.Label(
                box, text="Drag blocks here", background=theme.SURFACE, foreground=theme.SUBTLE,
                font=("Segoe UI", 11, "italic"))
        self.indicator = tk.Frame(self, background=theme.ACCENT, height=3)

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
        nav = ttk.Frame(bar)
        nav.pack(side="right")
        ttk.Button(nav, text="◀", width=3, command=lambda: self._step_sample(-1)).pack(side="left")
        self.sample_var = tk.StringVar()
        ttk.Label(nav, textvariable=self.sample_var, foreground=theme.MUTED, width=18,
                  anchor="center").pack(side="left", padx=4)
        ttk.Button(nav, text="▶", width=3, command=lambda: self._step_sample(1)).pack(side="left")

        frame = tk.Frame(right, background=theme.BG, highlightthickness=1,
                         highlightbackground=theme.BORDER)
        frame.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        self.preview = CardView(frame, scale=0.72, on_select=self.select)
        self.preview.pack(fill="both", expand=True, padx=12, pady=8)
        ttk.Label(right, text="Click a block in the preview or in the Front/Back lists to change how it looks.",
                  style="Hint.TLabel").grid(row=2, column=0, sticky="w")

        self.props = ttk.Frame(right, padding=(0, 8, 0, 0))
        self.props.grid(row=3, column=0, sticky="ew")

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
    def _make_chip(self, parent, kind: str, removable: bool, block_id: str = "") -> tk.Frame:
        info = T.BLOCK_TYPES[kind]
        chip = tk.Frame(parent, background=theme.RAISED, highlightthickness=1,
                        highlightbackground=theme.BORDER, cursor="fleur")
        tk.Label(chip, text="⠿", background=theme.RAISED, foreground=theme.SUBTLE,
                 font=("Segoe UI", 11)).pack(side="left", padx=(6, 2), pady=5)
        tk.Label(chip, text=info["icon"], background=theme.RAISED, foreground=theme.ACCENT,
                 font=("Segoe UI", 11, "bold"), width=2).pack(side="left")
        tk.Label(chip, text=info["label"], background=theme.RAISED, foreground=theme.FG,
                 font=("Segoe UI", 10), anchor="w").pack(side="left", fill="x", expand=True, padx=(4, 4))
        if removable:
            x = tk.Label(chip, text="✕", background=theme.RAISED, foreground=theme.MUTED,
                         font=("Segoe UI", 10), cursor="hand2", padx=8)
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

    def _refresh_sides(self):
        for side in ("front", "back"):
            for chip in self.chips[side]:
                chip.destroy()
            self.chips[side] = []
            box = self.side_box[side]
            blocks = self.tpl[side]["blocks"]
            if not blocks:
                self.empty_labels[side].pack(expand=True)
            else:
                self.empty_labels[side].pack_forget()
            for b in blocks:
                chip = self._make_chip(box, b["type"], removable=True, block_id=b["id"])
                chip.pack(fill="x", padx=6, pady=(6, 0))
                self._bind_drag(chip, ("side", side, b["id"]))
                if b["id"] == self.selected:
                    self._paint_chip(chip, theme.RAISED, theme.ACCENT)
                self.chips[side].append(chip)
            self.autoplay_vars[side].set(self.tpl[side]["autoplay"])

    # ============================================================ drag & drop
    def _bind_drag(self, chip, source):
        for w in self._chip_widgets(chip):
            if getattr(chip, "remove_label", None) is w:
                continue  # the ✕ is a button, not a drag handle
            w.bind("<ButtonPress-1>", lambda e, s=source: self._press(e, s))
            w.bind("<B1-Motion>", self._motion)
            w.bind("<ButtonRelease-1>", self._release)

    def _press(self, e, source):
        self._drag = {"src": source, "x": e.x_root, "y": e.y_root, "ghost": None}

    def _motion(self, e):
        d = self._drag
        if not d:
            return
        if d["ghost"] is None:
            if abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) < 6:
                return  # still a click, not a drag
            kind = d["src"][1] if d["src"][0] == "palette" else self._find(d["src"][2])[2]["type"]
            d["ghost"] = self._make_ghost(kind)
        d["ghost"].geometry(f"+{e.x_root + 14}+{e.y_root + 8}")
        target = self._drop_target(e.x_root, e.y_root)
        self._show_indicator(target)
        over_palette = target is None and d["src"][0] == "side" and self._over(self.palette, e)
        self.trash_hint.configure(foreground=theme.TARGET if over_palette else theme.SUBTLE)

    def _release(self, e):
        d, self._drag = self._drag, None
        self.indicator.place_forget()
        self.trash_hint.configure(foreground=theme.SUBTLE)
        if not d:
            return
        if d["ghost"] is None:  # a click
            if d["src"][0] == "side":
                self.select(d["src"][2])
            return
        d["ghost"].destroy()
        target = self._drop_target(e.x_root, e.y_root)
        src = d["src"]
        if target:
            side, index = target
            if src[0] == "palette":
                self.add_block(src[1], side, index)
            else:
                self.move_block(src[2], side, index)
        elif src[0] == "side" and self._over(self.palette, e):
            self.remove_block(src[2])

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
    def _over(widget, e) -> bool:
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        return x <= e.x_root <= x + widget.winfo_width() and y <= e.y_root <= y + widget.winfo_height()

    def _drop_target(self, xr: int, yr: int):
        """(side, index) under the pointer, or None."""
        for side, box in self.side_box.items():
            x, y = box.winfo_rootx(), box.winfo_rooty()
            if x - 20 <= xr <= x + box.winfo_width() + 20 and y - 10 <= yr <= y + box.winfo_height() + 10:
                index = 0
                for chip in self.chips[side]:
                    if yr > chip.winfo_rooty() + chip.winfo_height() / 2:
                        index += 1
                return side, index
        return None

    def _show_indicator(self, target):
        if not target:
            self.indicator.place_forget()
            return
        side, index = target
        box, chips = self.side_box[side], self.chips[side]
        if not chips:
            y = 8
        elif index < len(chips):
            y = chips[index].winfo_y() - 4
        else:
            y = chips[-1].winfo_y() + chips[-1].winfo_height() + 2
        self.indicator.place(in_=box, x=6, y=max(y, 1), relwidth=1.0, width=-12)
        self.indicator.lift()

    # ============================================================== editing
    def _json(self) -> str:
        return json.dumps(self.tpl, sort_keys=True)

    def _push(self):
        self.history.append(T.clone(self.tpl))
        del self.history[:-60]

    def _find(self, block_id: str):
        for side in ("front", "back"):
            for i, b in enumerate(self.tpl[side]["blocks"]):
                if b["id"] == block_id:
                    return side, i, b
        return None, -1, None

    def add_block(self, kind: str, side: str, index: int | None = None):
        self._push()
        block = T.new_block(kind)
        blocks = self.tpl[side]["blocks"]
        blocks.insert(len(blocks) if index is None else index, block)
        self.selected = block["id"]
        self.preview_side = side
        self._refresh_all()

    def move_block(self, block_id: str, side: str, index: int):
        old_side, old_i, block = self._find(block_id)
        if block is None:
            return
        if old_side == side and index in (old_i, old_i + 1):
            self.select(block_id)  # dropped where it already was
            return
        self._push()
        del self.tpl[old_side]["blocks"][old_i]
        if old_side == side and index > old_i:
            index -= 1
        self.tpl[side]["blocks"].insert(index, block)
        self.selected = block_id
        self.preview_side = side
        self._refresh_all()

    def remove_block(self, block_id: str):
        side, i, block = self._find(block_id)
        if block is None:
            return
        self._push()
        del self.tpl[side]["blocks"][i]
        if self.selected == block_id:
            self.selected = ""
        self.preview_side = side
        self._refresh_all()

    def move_selected(self, delta: int):
        side, i, block = self._find(self.selected)
        if block is None:
            return
        j = i + delta
        if 0 <= j < len(self.tpl[side]["blocks"]):
            self.move_block(block["id"], side, j if delta < 0 else j + 1)

    def move_selected_to_other_side(self):
        side, i, block = self._find(self.selected)
        if block is not None:
            other = "back" if side == "front" else "front"
            self.move_block(block["id"], other, len(self.tpl[other]["blocks"]))

    def duplicate_selected(self):
        side, i, block = self._find(self.selected)
        if block is None:
            return
        self._push()
        copy = dict(block, id=T.new_block(block["type"])["id"])
        self.tpl[side]["blocks"].insert(i + 1, copy)
        self.selected = copy["id"]
        self._refresh_all()

    def _delete_key(self, e):
        if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return None  # deleting text in the Custom text box
        if self.selected:
            self.remove_block(self.selected)
        return "break"

    def _set_autoplay(self, side: str):
        self._push()
        self.tpl[side]["autoplay"] = bool(self.autoplay_vars[side].get())
        self._update_status()

    def set_prop(self, key: str, value):
        side, i, block = self._find(self.selected)
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
        if not self._find(self.selected)[2]:
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
        side, i, block = self._find(block_id)
        if block is None:
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
        self._refresh_preview()

    # ============================================================ refreshing
    def _refresh_all(self):
        self.side_var.set(self.preview_side)
        self._refresh_sides()
        self._refresh_preview()
        self._refresh_props()
        self._update_status()

    def _refresh_preview(self):
        card = self.samples[self.sample_i]
        real = card is not SAMPLE_CARD
        self.sample_var.set(f"card {self.sample_i + 1} of {len(self.samples)}" if real else "example card")
        self.preview.show(card, self.tpl[self.preview_side],
                          self.cards.abs_path if real else (lambda rel: ""),
                          selected=self.selected,
                          empty_text=f"The {self.preview_side} is empty.\nDrag blocks onto it from the left.")

    def _update_status(self):
        dirty = self._json() != self.saved_json
        self.status_var.set("Unsaved changes" if dirty else "All changes saved  ✓")
        self.undo_btn.configure(state="normal" if self.history else "disabled")

    def _refresh_props(self):
        for w in self.props.winfo_children():
            w.destroy()
        side, i, block = self._find(self.selected)
        if block is None:
            ttk.Label(self.props, text="No block selected.", foreground=theme.MUTED).pack(anchor="w")
            return
        info = T.BLOCK_TYPES[block["type"]]
        head = ttk.Frame(self.props)
        head.pack(fill="x", pady=(0, 6))
        ttk.Label(head, text=f"{info['icon']}  {info['label']}", style="Head.TLabel").pack(side="left")
        ttk.Label(head, text=f"on the {SIDE_LABEL[side].lower()}", foreground=theme.MUTED).pack(side="left", padx=8)
        for text, cmd in (("✕  Remove", lambda: self.remove_block(block["id"])),
                          ("⧉  Duplicate", self.duplicate_selected),
                          (f"⇄  Move to {('back' if side == 'front' else 'front')}",
                           self.move_selected_to_other_side),
                          ("↓", lambda: self.move_selected(1)), ("↑", lambda: self.move_selected(-1))):
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
