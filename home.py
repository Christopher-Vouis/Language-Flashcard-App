"""
The main menu screen, drawn on one canvas over assets/menu_bg.png.

The design is 1200 x 1500 (the size of the background picture); every position
and size below is in those design pixels and is scaled to the window:

    Welcome, <profile>                                  header (over the dotted band)
    change | sign out
    ─────────────────────────────────────────────────  (line is part of the picture)
                        Deck:
                   <current deck name>
                 ┌────────────────────┐
                 │  New:           #  │
                 │  Due:           #  │
                 │  Total:         #  │
                 └────────────────────┘
                 Change Deck | Edit Deck

              ┌──────────┐ ┌──────────┐
              │  Study   │ │  Create  │
              └──────────┘ └──────────┘

The picture, the stats panel and the buttons are composed with Pillow (Tk has
no anti-aliased shapes); the text is drawn by Tk so it stays sharp.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import theme
from cards import ALL

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageTk
except ImportError:  # no Pillow: plain background, drawn buttons
    Image = None

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
DESIGN_W, DESIGN_H = 1200, 1500

HEAD_FONT, BODY_FONT = "Tahoma", "Segoe UI"
HEAD_FILL, HEAD_EDGE = "#dadada", "#6b6b6b"     # headings: light grey with a grey outline
PANEL_SHADE = 0.67                              # the stats box: the picture behind it, this bright
BTN_FACE, BTN_EDGE = "#323335", "#eaeaea"

# parts of the background picture (design px): the page colour, the dotted band
# with its line and shadow, the box holding the A / あ, and the corner stripes
BASE = (30, 31, 34)
HEADER_H = 345
GLYPH_BOX = (520, 430, 1020, 960)
STRIPES_BOX = (0, 400, 1040, 1500)

# vertical centre (design px) of each group; a group keeps its shape when the
# window isn't 4:5 and only its centre moves
HEADER_Y, DECK_Y, BUTTONS_Y = 160, 600, 1150


def _load(name: str):
    if Image is None:
        return None
    try:
        return Image.open(os.path.join(ASSETS, name)).convert("RGB")
    except OSError:
        return None


class HomeScreen(ttk.Frame):
    """Main menu. `app` provides: show_study, show_create, show_profiles, sign_out,
    show_deck, choose_deck, new_deck, rename_deck, delete_deck and `cards`."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.bg_src = _load("menu_bg.png")
        self.btn_src = _load("menu_button.png")
        self._bg_img = None
        self._btn_imgs: dict[str, object] = {}
        self._size = (0, 0)
        self._job = None
        self._btn_state = {"study": "normal", "create": "normal"}
        self._down: str | None = None

        self.canvas = c = tk.Canvas(self, highlightthickness=0, bd=0, background=theme.BG)
        c.pack(fill="both", expand=True)
        c.create_image(0, 0, anchor="nw", tags="bg")

        # ---- header
        self._outlined("welcome", anchor="w")
        self._link("change", "change", app.show_profiles)
        c.create_text(0, 0, text="|", fill="#ffffff", anchor="w", tags="bar1")
        self._link("signout", "sign out", app.sign_out)

        # ---- deck block
        self._outlined("deck_title", text="Deck:")
        c.create_text(0, 0, fill="#ffffff", tags="deck_name")
        for name in ("New", "Due", "Total"):
            c.create_text(0, 0, text=f"{name}:", fill="#ffffff", anchor="w", tags=f"lbl_{name}")
            c.create_text(0, 0, text="0", fill="#ffffff", anchor="e", tags=f"val_{name}")
        self._link("change_deck", "Change Deck", self.change_deck)
        c.create_text(0, 0, text="|", fill="#ffffff", tags="bar2")
        self._link("edit_deck", "Edit Deck", app.show_deck)

        # ---- buttons
        for key, text, command in (("study", "Study", app.show_study), ("create", "Create", app.show_create)):
            c.create_image(0, 0, tags=(f"btn_{key}", f"hit_{key}"))
            c.create_rectangle(0, 0, 0, 0, fill=BTN_FACE, outline=BTN_EDGE, width=2,
                               state="hidden", tags=(f"box_{key}", f"hit_{key}"))  # without Pillow
            self._outlined(f"txt_{key}", text=text, extra=(f"hit_{key}",))
            c.tag_bind(f"hit_{key}", "<Enter>", lambda e, k=key: self._hover(k, True))
            c.tag_bind(f"hit_{key}", "<Leave>", lambda e, k=key: self._hover(k, False))
            c.tag_bind(f"hit_{key}", "<ButtonPress-1>", lambda e, k=key: self._press(k))
            c.tag_bind(f"hit_{key}", "<ButtonRelease-1>", lambda e, k=key, cmd=command: self._release(k, cmd))

        c.bind("<Configure>", self._on_configure)

    # ------------------------------------------------------------ items
    def _outlined(self, tag: str, text: str = "", anchor: str = "center", extra: tuple = ()):
        """Heading text: 8 grey copies around a light one = an outline."""
        for i in range(8):
            self.canvas.create_text(0, 0, text=text, fill=HEAD_EDGE, anchor=anchor,
                                    tags=(tag, f"{tag}_edge{i}") + extra)
        self.canvas.create_text(0, 0, text=text, fill=HEAD_FILL, anchor=anchor, tags=(tag, f"{tag}_top") + extra)

    def _place_outlined(self, tag: str, x: float, y: float, font, edge: float):
        c = self.canvas
        c.itemconfigure(tag, font=font)
        e = max(edge, 1)
        d = e * 0.7
        for i, (dx, dy) in enumerate(((-e, 0), (e, 0), (0, -e), (0, e), (-d, -d), (d, -d), (-d, d), (d, d))):
            c.coords(f"{tag}_edge{i}", x + dx, y + dy)
        c.coords(f"{tag}_top", x, y)

    def _link(self, tag: str, text: str, command):
        """White text that underlines under the mouse and runs `command` on a click."""
        c = self.canvas
        c.create_text(0, 0, text=text, fill="#ffffff", anchor="w", tags=(tag, "link"))
        c.tag_bind(tag, "<Enter>", lambda e: self._link_hover(tag, True))
        c.tag_bind(tag, "<Leave>", lambda e: self._link_hover(tag, False))
        c.tag_bind(tag, "<Button-1>", lambda e: command())

    def _link_hover(self, tag: str, on: bool):
        size = self._link_px.get(tag, 14)
        self.canvas.itemconfigure(tag, font=(BODY_FONT, -size, "underline" if on else "normal"))
        self.canvas.configure(cursor="hand2" if on else "")

    _link_px: dict = {}

    # ------------------------------------------------------------ buttons
    def _show_button(self, key: str):
        img = self._btn_imgs.get(self._btn_state[key])
        if img is not None:
            self.canvas.itemconfigure(f"btn_{key}", image=img)
        else:
            face = {"normal": BTN_FACE, "hover": "#3c3d40", "pressed": "#28292b"}[self._btn_state[key]]
            self.canvas.itemconfigure(f"box_{key}", fill=face)

    def _hover(self, key: str, on: bool):
        self._btn_state[key] = ("pressed" if self._down == key else "hover") if on else "normal"
        self.canvas.configure(cursor="hand2" if on else "")
        self._show_button(key)

    def _press(self, key: str):
        self._down = key
        self._btn_state[key] = "pressed"
        self._show_button(key)

    def _release(self, key: str, command):
        was_down, self._down = self._down == key, None
        inside = self._btn_state[key] == "pressed"       # still over the button
        self._btn_state[key] = "hover" if inside else "normal"
        self._show_button(key)
        if was_down and inside:
            command()

    # ------------------------------------------------------------ deck menu
    def change_deck(self):
        """Change Deck: a menu of the decks, then New / Rename / Delete."""
        app, cards = self.app, self.app.cards
        menu = tk.Menu(self, tearoff=False)
        current = tk.StringVar(value=cards.selected_deck if cards.deck(cards.selected_deck) else ALL)
        for deck_id in [ALL] + [d["id"] for d in cards.decks]:
            menu.add_radiobutton(label=f"{cards.deck_name(deck_id)}  ({len(cards.cards_in(deck_id))})",
                                 variable=current, value=deck_id,
                                 command=lambda i=deck_id: app.choose_deck(i))
        menu.add_separator()
        menu.add_command(label="＋  New deck...", command=app.new_deck)
        menu.add_command(label="✎  Rename this deck...", command=app.rename_deck)
        menu.add_command(label="✕  Delete this deck...", command=app.delete_deck)
        self._deck_menu, self._deck_menu_var = menu, current     # keep them alive while shown
        x0, _y0, _x1, y1 = self.canvas.bbox("change_deck")
        menu.tk_popup(self.canvas.winfo_rootx() + x0, self.canvas.winfo_rooty() + y1 + 4)

    # ------------------------------------------------------------ layout
    def _on_configure(self, _e=None):
        if self._job:
            self.after_cancel(self._job)
        # first draw at once; while the window is being dragged, wait for it to settle
        self._job = self.after(1 if self._size == (0, 0) else 40, self._render)

    def _render(self):
        self._job = None
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return
        self._size = (w, h)
        sy = h / DESIGN_H
        s = min(w / DESIGN_W, sy)                 # size of everything
        cx = w / 2

        def at(x, y, group):                      # design point -> canvas point (centred groups)
            return cx + (x - DESIGN_W / 2) * s, group * sy + (y - group) * s

        def px(n):                                # design pixels -> font size (negative = pixels)
            return -max(round(n * s), 8)

        # ---- picture: background + stats panel
        px0, py0 = at(301, 498, DECK_Y)
        px1, py1 = at(901, 797, DECK_Y)
        if self.bg_src is not None:
            img = self._compose(w, h, sy)
            k = 3                                 # draw the rounded box 3x and shrink = smooth corners
            bw, bh = max(round(px1 - px0), 2), max(round(py1 - py0), 2)
            mask = Image.new("L", (bw * k, bh * k), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw * k - 1, bh * k - 1), radius=26 * s * k, fill=255)
            # translucent: the picture shows through, darkened (measured from the design)
            box = (round(px0), round(py0), round(px0) + bw, round(py0) + bh)
            dark = img.crop(box).point(lambda v: max(int(v * PANEL_SHADE - 4), 0))
            img.paste(dark, box[:2], mask.resize((bw, bh), Image.LANCZOS))
            self._bg_img = ImageTk.PhotoImage(img)
            c.itemconfigure("bg", image=self._bg_img)
            c.delete("panel")
        else:
            c.delete("panel")
            c.create_rectangle(px0, py0, px1, py1, fill="#101113", outline="", tags="panel")
            c.tag_raise("panel", "bg")

        # ---- header (kept at the left edge)
        hy = lambda y: HEADER_Y * sy + (y - HEADER_Y) * s      # noqa: E731
        self._place_outlined("welcome", 33 * s, hy(139), (HEAD_FONT, px(55), "bold"), 2 * s)
        link = px(33)
        self._link_px.update(change=-link, signout=-link)
        x = 37 * s
        for tag in ("change", "bar1", "signout"):
            c.itemconfigure(tag, font=(BODY_FONT, link))
            c.coords(tag, x, hy(204))
            x = c.bbox(tag)[2] + 9 * s

        # ---- deck block
        self._place_outlined("deck_title", *at(593, 366, DECK_Y), (HEAD_FONT, px(55), "bold"), 2 * s)
        c.itemconfigure("deck_name", font=(BODY_FONT, px(35)), width=max(w - 40, 100))
        c.coords("deck_name", *at(600, 436, DECK_Y))
        for name, y in (("New", 555), ("Due", 638), ("Total", 721)):
            for tag, x in ((f"lbl_{name}", 388), (f"val_{name}", 811)):
                c.itemconfigure(tag, font=(BODY_FONT, px(67)))
                c.coords(tag, *at(x, y, DECK_Y))
        link = px(30)
        self._link_px.update(change_deck=-link, edit_deck=-link)
        for tag in ("change_deck", "bar2", "edit_deck"):
            c.itemconfigure(tag, font=(BODY_FONT, link), anchor="w")
        gap = 8 * s
        widths = [c.bbox(t)[2] - c.bbox(t)[0] for t in ("change_deck", "bar2", "edit_deck")]
        x, y = at(601, 826, DECK_Y)
        x -= (sum(widths) + 2 * gap) / 2
        for tag, width in zip(("change_deck", "bar2", "edit_deck"), widths):
            c.coords(tag, x, y)
            x += width + gap

        # ---- Study / Create
        bw, bh = max(round(400 * s), 8), max(round(200 * s), 8)
        if self.btn_src is not None:
            base = self.btn_src.resize((bw, bh), Image.LANCZOS)
            self._btn_imgs = {"normal": ImageTk.PhotoImage(base),
                              "hover": ImageTk.PhotoImage(ImageEnhance.Brightness(base).enhance(1.22)),
                              "pressed": ImageTk.PhotoImage(ImageEnhance.Brightness(base).enhance(0.8))}
        for key, centre in (("study", 400), ("create", 826)):
            x, y = at(centre, 1150, BUTTONS_Y)
            c.coords(f"btn_{key}", x, y)
            if self.btn_src is None:
                c.itemconfigure(f"box_{key}", state="normal")
                c.coords(f"box_{key}", x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2)
            self._place_outlined(f"txt_{key}", x, y - 10 * s, (HEAD_FONT, px(66), "bold"), 2 * s)
            self._show_button(key)

    def _layers(self):
        """Cut the background picture into its three parts (once)."""
        if getattr(self, "_parts", None) is None:
            src = self.bg_src
            stripes = src.crop(STRIPES_BOX)
            gx0, gy0, gx1, gy1 = GLYPH_BOX        # blank the letters out of the stripes part
            stripes.paste(BASE, (gx0 - STRIPES_BOX[0], gy0 - STRIPES_BOX[1],
                                 gx1 - STRIPES_BOX[0], gy1 - STRIPES_BOX[1]))
            self._parts = (src.crop((0, 0, DESIGN_W, HEADER_H)), src.crop(GLYPH_BOX), stripes)
        return self._parts

    def _compose(self, w: int, h: int, sy: float):
        """The background at the window's size. Nothing is stretched: every
        part keeps its shape and is scaled with the window's height only.
          - dots band: starts at the left; in a wider window it repeats
            (each repeat mirrored, so the dots join without a seam)
          - A / あ: stay where they are, behind the middle of the menu
          - stripes: stay in the bottom-left corner"""
        header, glyphs, stripes = self._layers()
        scale = lambda im: im.resize((max(round(im.width * sy), 1), max(round(im.height * sy), 1)),  # noqa: E731
                                     Image.LANCZOS)
        img = Image.new("RGB", (w, h), BASE)
        stripes = scale(stripes)
        img.paste(stripes, (0, h - stripes.height))
        glyphs = scale(glyphs)
        img.paste(glyphs, (round(w / 2 + (GLYPH_BOX[0] - DESIGN_W / 2) * sy), round(GLYPH_BOX[1] * sy)))
        header = scale(header)
        x, flipped = 0, False
        while x < w:
            img.paste(header.transpose(Image.FLIP_LEFT_RIGHT) if flipped else header, (x, 0))
            x += header.width
            flipped = not flipped
        return img

    # ------------------------------------------------------------ data
    def update_view(self, profile_name: str, deck_name: str, new: int, due: int, total: int):
        c = self.canvas
        c.itemconfigure("welcome", text=f"Welcome, {profile_name}")
        c.itemconfigure("deck_name", text=deck_name)
        for name, value in (("New", new), ("Due", due), ("Total", total)):
            c.itemconfigure(f"val_{name}", text=str(value))
