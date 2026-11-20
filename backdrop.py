"""
The app's background picture, shared by the main menu, Study and Create.

It is built from parts of assets/menu_bg.png (design size 1200 x 1500) plus
the wide dots band (assets/menu_dots.png). Nothing is ever stretched: each
part is scaled with the window's HEIGHT only, and

  - the dots band starts at the left; a wider window shows more of it
  - the white line and its shadow run the full width under the dots
  - the A / あ keep their shape, always inside the window, drifting to the
    right as the window widens (GLYPH_FULL_SCREEN across at full screen width)
  - the stripes stay in the bottom-left corner

Tk widgets can't be see-through, so on screens with many controls the picture
shows around and between them; the controls sit on panels drawn here.
"""

from __future__ import annotations

import os
import tkinter as tk

import theme

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:  # no Pillow: plain background colour
    Image = None

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
DESIGN_W, DESIGN_H = 1200, 1500

# parts of the background picture (design px): the page colour, the dotted band
# with its line and shadow, the box holding the A / あ, and the corner stripes
BASE = (30, 31, 34)
LINE_Y, HEADER_H = 300, 345                     # dots end / white line starts; shadow ends
GLYPH_BOX = (520, 430, 1020, 960)
GLYPH_FULL_SCREEN = 0.80                        # where the A / あ centre sits in a full-screen-wide window
STRIPES_BOX = (0, 400, 1040, 1500)


def load(name: str):
    if Image is None:
        return None
    try:
        return Image.open(os.path.join(ASSETS, name)).convert("RGB")
    except OSError:
        return None


_parts = None
_scaled: dict = {}           # height -> scaled parts (resizing the 3840 px band is slow)


def _layers():
    """Cut the background picture into its parts (once)."""
    global _parts
    if _parts is None:
        src = load("menu_bg.png")
        if src is None:
            _parts = ()
            return _parts
        stripes = src.crop(STRIPES_BOX)
        gx0, gy0, gx1, gy1 = GLYPH_BOX            # blank the letters out of the stripes part
        stripes.paste(BASE, (gx0 - STRIPES_BOX[0], gy0 - STRIPES_BOX[1],
                             gx1 - STRIPES_BOX[0], gy1 - STRIPES_BOX[1]))
        # the white line and its shadow are the same all the way across: one column is enough
        dots = load("menu_dots.png") or src.crop((0, 0, DESIGN_W, LINE_Y))
        line = src.crop((0, LINE_Y, 1, HEADER_H))
        _parts = (dots, line, src.crop(GLYPH_BOX), stripes)
    return _parts


def _scaled_parts(h: int, sy: float):
    if h not in _scaled:
        dots, line, glyphs, stripes = _layers()
        scale = lambda im: im.resize((max(round(im.width * sy), 1), max(round(im.height * sy), 1)),  # noqa: E731
                                     Image.LANCZOS)
        band_h = max(round(LINE_Y * sy), 1)
        dots = dots.resize((max(round(dots.width * band_h / dots.height), 1), band_h), Image.LANCZOS)
        if len(_scaled) > 6:
            _scaled.clear()
        _scaled[h] = (dots, line, scale(glyphs), scale(stripes), max(round(line.height * sy), 1))
    return _scaled[h]


def available() -> bool:
    return Image is not None and bool(_layers())


def compose(w: int, h: int, screen_w: int, band: float = 1.0):
    """The background picture at the window's size. `band` = how much of the
    dots band to show (from its bottom edge, where the dots are; Study and
    Create show less of it to leave room for their controls).
    Returns (image, dots_height, header_height) - the line and shadow sit
    between dots_height and header_height."""
    sy = h / DESIGN_H
    dots, line, glyphs, stripes, line_h = _scaled_parts(h, sy)
    img = Image.new("RGB", (w, h), BASE)
    img.paste(stripes, (0, h - stripes.height))
    home = (GLYPH_BOX[0] + GLYPH_BOX[2]) / 2 / DESIGN_W
    narrow = DESIGN_W * sy
    t = min(max((w - narrow) / (screen_w - narrow), 0), 1) if screen_w > narrow else 1
    centre = (home + (GLYPH_FULL_SCREEN - home) * t) * w
    gx = min(max(round(centre - glyphs.width / 2), 0), max(w - glyphs.width, 0))
    img.paste(glyphs, (gx, round(GLYPH_BOX[1] * sy)))
    shown = max(round(dots.height * band), 1)
    if shown < dots.height:
        dots = dots.crop((0, dots.height - shown, dots.width, dots.height))
    x, flipped = 0, False
    while x < w:
        img.paste(dots.transpose(Image.FLIP_LEFT_RIGHT) if flipped else dots, (x, 0))
        x += dots.width
        flipped = not flipped
    img.paste(line.resize((w, line_h), Image.LANCZOS), (0, shown))
    return img, shown, shown + line_h


def draw_panel(img, box, radius: float, fill=None, shade: float | None = None, outline=None):
    """A rounded box on the picture: solid `fill`, or see-through - the picture
    darkened to `shade` - with an optional 1 px `outline`."""
    x0, y0, x1, y1 = (round(v) for v in box)
    bw, bh = x1 - x0, y1 - y0
    if bw < 2 or bh < 2:
        return
    k = 3                                         # draw 3x and shrink = smooth corners
    mask = Image.new("L", (bw * k, bh * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw * k - 1, bh * k - 1), radius=radius * k, fill=255)
    mask = mask.resize((bw, bh), Image.LANCZOS)
    if outline:
        img.paste(outline, (x0, y0), mask)
        inner = Image.new("L", ((bw - 2) * k, (bh - 2) * k), 0)
        ImageDraw.Draw(inner).rounded_rectangle((0, 0, (bw - 2) * k - 1, (bh - 2) * k - 1),
                                                radius=max(radius - 1, 0) * k, fill=255)
        mask = Image.new("L", (bw, bh), 0)
        mask.paste(inner.resize((bw - 2, bh - 2), Image.LANCZOS), (1, 1))
    if shade is not None:
        part = img.crop((x0, y0, x1, y1)).point(lambda v: max(int(v * shade - 4), 0))
        img.paste(part, (x0, y0), mask)
    else:
        img.paste(fill, (x0, y0), mask)


def hex_rgb(colour: str) -> tuple:
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


class Backdrop(tk.Canvas):
    """A canvas showing the background picture. `layout(w, h, dots_h, header_h)`
    is called whenever the size changes: it places the screen's widgets and
    canvas items, and returns the panels to draw behind them as a list of
    dicts for draw_panel (box, radius, fill / shade, outline)."""

    def __init__(self, parent, band: float = 1.0, layout=None):
        super().__init__(parent, highlightthickness=0, bd=0, background=theme.BG)
        self.band = band
        self.layout = layout
        self._img = None
        self._job = None
        self._drawn = (0, 0)
        self.create_image(0, 0, anchor="nw", tags="bg")
        self.bind("<Configure>", self._on_configure)

    def header(self, h: int) -> tuple[int, int]:
        """(dots height, header height) for a canvas `h` pixels tall."""
        sy = h / DESIGN_H
        shown = max(round(max(round(LINE_Y * sy), 1) * self.band), 1)
        return shown, shown + max(round((HEADER_H - LINE_Y) * sy), 1)

    def _on_configure(self, _e=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        self._panels = self.layout(w, h, *self.header(h)) if self.layout else []
        if self._job:
            self.after_cancel(self._job)
        # first draw at once; while the window is being dragged, wait for it to settle
        self._job = self.after(1 if self._drawn == (0, 0) else 40, self._render)

    def refresh(self):
        self._drawn = (-1, -1)
        self._on_configure()

    def _render(self):
        self._job = None
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20 or not available():
            return
        img, _dots_h, _header_h = compose(w, h, self.winfo_screenwidth(), self.band)
        for p in self._panels or []:
            draw_panel(img, **p)
        self._img = ImageTk.PhotoImage(img)
        self.itemconfigure("bg", image=self._img)
        self.tag_lower("bg")
        self._drawn = (w, h)
