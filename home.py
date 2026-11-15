"""
The main menu screen.

    ┌────────────────────────────────────────────────────────────────┐
    │ Welcome, <profile>                         Deck: [ deck ▾ ]    │  header
    │ Change | Sign Out                                              │
    ├─── gradient band, black bar, soft shadow ──────────────────────┤
    │                      New:      0                               │
    │                      Due:      0                               │  centred
    │                      Total:    0                               │  column
    │                    ┌──────────────┐                            │
    │                    │    Study     │                            │
    │                    └──────────────┘                            │
    │                    ┌──────────────┐                            │
    │                    │    Create    │                            │
    │                    └──────────────┘                            │
    └────────────────────────────────────────────────────────────────┘

The header band and the bevelled buttons are drawn on canvases (Tk has no
gradients). Everything in the lower part sits in one column that is centred
horizontally and scales with the window.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import theme

# colours sampled from the mockup
HEADER_BG = theme.BG
BAND_TOP, BAND_BOTTOM = theme.BG, "#3b4249"      # lighter steel strip under the header
BAR = "#060708"                                  # black bar
FACE, FACE_HOVER, FACE_PRESS = "#2d3035", "#363a40", "#25282c"
EDGE_OUTER, EDGE_INNER = "#0b0c0e", "#16181b"    # bevel: darkest at the rim


def _mix(c1: str, c2: str, t: float) -> str:
    """Colour between c1 and c2 (t = 0..1)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


class HeaderBand(tk.Canvas):
    """The strip under the header: gradient, black bar, then a shadow fading into the page."""

    def __init__(self, parent, scale_h: int = 64):
        super().__init__(parent, height=scale_h, highlightthickness=0, background=theme.BG, bd=0)
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        grad, bar = int(h * 0.55), max(int(h * 0.1), 4)
        for y in range(grad):                                     # header → steel
            self.create_line(0, y, w, y, fill=_mix(BAND_TOP, BAND_BOTTOM, (y / grad) ** 1.6))
        self.create_rectangle(0, grad, w, grad + bar, fill=BAR, outline=BAR)
        shadow = h - grad - bar
        for i in range(shadow):                                   # black → page
            y = grad + bar + i
            self.create_line(0, y, w, y, fill=_mix(BAR, theme.BG, (i / max(shadow, 1)) ** 0.6))


class BevelButton(tk.Canvas):
    """A large button with a dark inset bevel, like the mockup's Study / Create.
    Hover / pressed states, keyboard focus (Tab), Enter or Space to press."""

    def __init__(self, parent, text: str, command, width: int = 327, height: int = 149,
                 font_size: int = 30):
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0,
                         background=theme.BG, takefocus=True, cursor="hand2")
        self.text, self.command = text, command
        self.font_size = font_size
        # hover and "mouse button held down" are tracked separately, so the
        # Leave/Enter events some systems send when a click starts can't cancel it
        self._hover = False
        self._down = False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", lambda e: self._draw())
        self.bind("<FocusOut>", lambda e: self._draw())
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<space>", lambda e: (self.invoke(), "break")[1])

    def resize(self, width: int, height: int, font_size: int):
        width -= width % 2            # even width: centres exactly on the window's middle
        self.font_size = font_size
        self.configure(width=width, height=height)
        self._draw()

    def invoke(self):
        if self.command:
            self.command()

    @property
    def state(self) -> str:
        if self._down and self._hover:
            return "pressed"
        return "hover" if self._hover else "normal"

    def _inside(self, e) -> bool:
        return 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()

    def _set_hover(self, on: bool):
        self._hover = on
        self._draw()

    def _press(self, e):
        self.focus_set()
        self._down, self._hover = True, True
        self._draw()

    def _motion(self, e):
        # while held: look pressed only when the pointer is over the button
        inside = self._inside(e)
        if inside != self._hover:
            self._set_hover(inside)

    def _release(self, e):
        inside = self._inside(e)
        was_down, self._down = self._down, False
        self._hover = inside
        self._draw()
        if was_down and inside:     # released over the button = a click
            self.invoke()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        face = {"normal": FACE, "hover": FACE_HOVER, "pressed": FACE_PRESS}[self.state]
        self.create_rectangle(0, 0, w - 1, h - 1, fill=EDGE_OUTER, outline=EDGE_OUTER)
        bevel = max(int(min(w, h) * 0.055), 5)
        for i in range(bevel):                    # dark rim easing into the face
            c = _mix(EDGE_INNER, face, (i / bevel) ** 0.8)
            self.create_rectangle(2 + i, 2 + i, w - 3 - i, h - 3 - i, outline=c, fill=c)
        self.create_rectangle(2 + bevel, 2 + bevel, w - 3 - bevel, h - 3 - bevel, fill=face, outline=face)
        if self.focus_get() is self:              # keyboard focus ring
            self.create_rectangle(1, 1, w - 2, h - 2, outline=theme.ACCENT, width=2)
        shift = 1 if self.state == "pressed" else 0
        self.create_text(w / 2 + shift, h / 2 + shift, text=self.text, fill="#ffffff",
                         font=("Segoe UI", self.font_size, "bold"))


class HomeScreen(ttk.Frame):
    """Main menu. `app` provides: show_study, show_create, show_profiles, sign_out,
    and the deck dropdown handlers (_on_home_deck)."""

    # full-size measurements (scaled down in small windows). Buttons are 75% of the
    # original mockup size (436 x 198, 40 pt); "gap" is the space between the stats and Study.
    BASE = {"btn_w": 327, "btn_h": 149, "btn_font": 30, "stat_font": 26, "gap": 120, "btn_gap": 22}

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # ---------------- header
        header = tk.Frame(self, background=HEADER_BG, height=118)
        header.pack(fill="x")
        header.pack_propagate(False)
        left = tk.Frame(header, background=HEADER_BG)
        left.place(x=46, y=40)
        self.welcome_var = tk.StringVar()
        tk.Label(left, textvariable=self.welcome_var, background=HEADER_BG, foreground="#ffffff",
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        links = tk.Frame(left, background=HEADER_BG)
        links.pack(anchor="w", pady=(4, 0))
        self._link(links, "Change", app.show_profiles).pack(side="left")
        tk.Label(links, text="|", background=HEADER_BG, foreground=theme.FG,
                 font=("Segoe UI", 12)).pack(side="left", padx=5)
        self._link(links, "Sign Out", app.sign_out).pack(side="left")

        right = tk.Frame(header, background=HEADER_BG)
        right.place(relx=1.0, x=-36, y=54, anchor="ne")
        tk.Label(right, text="Deck:", background=HEADER_BG, foreground=theme.FG,
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))
        self.deck_var = tk.StringVar()
        self.deck_combo = ttk.Combobox(right, textvariable=self.deck_var, state="readonly",
                                       width=28, font=("Segoe UI", 11))
        self.deck_combo.pack(side="left")
        self.deck_combo.bind("<<ComboboxSelected>>", app._on_home_deck)
        HeaderBand(self, 70).pack(fill="x")

        # ---------------- centred column: stats, then the two buttons
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)
        self.column = ttk.Frame(self.body)
        self.column.place(relx=0.5, rely=0.46, anchor="center")   # centred horizontally

        stats = ttk.Frame(self.column)
        stats.pack()                                              # centred in the column
        self.stat_vars = {}
        self.stat_labels = []
        for r, name in enumerate(("New", "Due", "Total")):
            var = tk.StringVar(value="0")
            self.stat_vars[name] = var
            a = ttk.Label(stats, text=f"{name}:", foreground="#ffffff")
            b = ttk.Label(stats, textvariable=var, foreground="#ffffff", anchor="e", width=4)
            a.grid(row=r, column=0, sticky="w")
            b.grid(row=r, column=1, sticky="e", padx=(70, 0))
            self.stat_labels += [a, b]

        self.spacer = ttk.Frame(self.column, height=self.BASE["gap"])
        self.spacer.pack()
        self.study_btn = BevelButton(self.column, "Study", app.show_study)
        self.study_btn.pack()
        self.btn_gap = ttk.Frame(self.column, height=self.BASE["btn_gap"])
        self.btn_gap.pack()
        self.create_btn = BevelButton(self.column, "Create", app.show_create)
        self.create_btn.pack()

        self.body.bind("<Configure>", self._fit)
        self._fit()

    def _link(self, parent, text, command) -> tk.Label:
        """A text link (white, underlined while the mouse is over it)."""
        lbl = tk.Label(parent, text=text, background=HEADER_BG, foreground="#ffffff",
                       font=("Segoe UI", 12), cursor="hand2")
        lbl.bind("<Button-1>", lambda e: command())
        lbl.bind("<Enter>", lambda e: lbl.configure(font=("Segoe UI", 12, "underline")))
        lbl.bind("<Leave>", lambda e: lbl.configure(font=("Segoe UI", 12)))
        return lbl

    def _fit(self, _e=None):
        """Scale the column to the space available (full size from ~760 px tall)."""
        b = self.BASE
        h = max(self.body.winfo_height(), 1)
        w = max(self.body.winfo_width(), 1)
        if h < 10:          # not laid out yet
            s = 1.0
        else:
            s = max(min(h / 820, w / 640, 1.0), 0.45)
        self.study_btn.resize(int(b["btn_w"] * s), int(b["btn_h"] * s), max(int(b["btn_font"] * s), 14))
        self.create_btn.resize(int(b["btn_w"] * s), int(b["btn_h"] * s), max(int(b["btn_font"] * s), 14))
        font = ("Segoe UI", max(int(b["stat_font"] * s), 12))
        for lbl in self.stat_labels:
            lbl.configure(font=font)
        self.spacer.configure(height=int(b["gap"] * s))
        self.btn_gap.configure(height=int(b["btn_gap"] * s))

    def update_view(self, profile_name: str, deck_labels: list[str], current: int,
                    new: int, due: int, total: int):
        self.welcome_var.set(f"Welcome, {profile_name}")
        self.deck_combo.configure(values=deck_labels)
        if 0 <= current < len(deck_labels):
            self.deck_combo.current(current)
        self.stat_vars["New"].set(str(new))
        self.stat_vars["Due"].set(str(due))
        self.stat_vars["Total"].set(str(total))
