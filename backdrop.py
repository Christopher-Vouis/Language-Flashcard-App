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
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk
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


def page_colour() -> tuple:
    """The page colour, in the current theme."""
    return theme.tint_rgb(BASE)


def load_themed(name: str):
    """An asset picture, turned to the current colour theme."""
    img = load(name)
    return theme.shift_image(img) if img is not None else None


def reset() -> None:
    """The colour theme changed: the background pictures are made again."""
    global _parts
    _parts = None
    _scaled.clear()


def all_backdrops(widget) -> list:
    """Every Backdrop in a window (to redraw them)."""
    found = [widget] if isinstance(widget, Backdrop) else []
    for child in widget.winfo_children():
        found += all_backdrops(child)
    return found


def _layers():
    """Cut the background picture into its parts (once), in the current theme."""
    global _parts
    if _parts is None:
        src = load("menu_bg.png")
        if src is None:
            _parts = ()
            return _parts
        themed = theme.shift_image(src)
        stripes = themed.crop(STRIPES_BOX)
        gx0, gy0, gx1, gy1 = GLYPH_BOX            # blank the letters out of the stripes part
        stripes.paste(page_colour(), (gx0 - STRIPES_BOX[0], gy0 - STRIPES_BOX[1],
                               gx1 - STRIPES_BOX[0], gy1 - STRIPES_BOX[1]))
        # the white line and its shadow are the same all the way across: one column is enough
        dots = load_themed("menu_dots.png") or themed.crop((0, 0, DESIGN_W, LINE_Y))
        line = themed.crop((0, LINE_Y, 1, HEADER_H))
        glyphs = themed.crop(GLYPH_BOX)          # the A / あ take the theme's hue too
        _parts = (dots, line, glyphs, stripes)
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


def compose(w: int, h: int, screen_w: int, band: float = 1.0, line: bool = True):
    """The background picture at the window's size. `band` = how much of the
    dots band to show (from its bottom edge, where the dots are; Study and
    Create show less of it to leave room for their controls). line=False leaves
    out the white line and its shadow (Create draws them itself, with its tabs).
    Returns (image, dots_height, header_height) - the line and shadow sit
    between dots_height and header_height."""
    sy = h / DESIGN_H
    dots, line_img, glyphs, stripes, line_h = _scaled_parts(h, sy)
    img = Image.new("RGB", (w, h), page_colour())
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
    if line:
        img.paste(line_img.resize((w, line_h), Image.LANCZOS), (0, shown))
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


# the white line and the shadow under it, measured from menu_bg.png (design px)
LINE_STROKE = 3            # white, (234, 234, 234)
SHADOW_LEN = 25            # the shadow fades from SHADOW_DARK to nothing over this many px
SHADOW_DARK = 0.67         # right under the line the page is this much darker
LINE_WHITE = (234, 234, 234)


def draw_tabs(img, tabs: list[tuple[float, float]], active: int, top: float, line_y: float,
              radius: float, flare: float, sy: float, fill=None):
    """The white line across the window with tabs standing on it, like folder tabs.

    tabs    (left, right) of each tab's outer edge, in px
    active  which tab is open: it has no line under it, so it opens into the page
    top     the tabs' outer top edge; line_y = the top of the white line
    radius  the tabs' top corners; flare = the small curves where a tab meets the line

    The outline, the fills and the shadow are all made from the same shapes: a
    shadow falls under every edge (under the line, and inside each tab under its
    top), just like the plain line's shadow. Drawn 3x bigger and shrunk, so the
    curves are smooth."""
    w = img.width
    stroke = max(LINE_STROKE * sy, 1.2)
    shadow_len = max(round(SHADOW_LEN * sy), 3)
    flare = max(flare, stroke + 1.5)
    height = min(int(line_y + stroke + shadow_len + 3), img.height)
    k = 3
    S = lambda v: round(v * k)                    # noqa: E731

    base = line_y + stroke                        # the bottom of the white line = top of the page

    def region(x0: float, x1: float, grow: float):
        """Mask of one tab's inside (grow=0), or of it grown by the line's
        thickness (grow=stroke), down to the bottom of the line."""
        m = Image.new("L", (w * k, height * k), 0)
        d = ImageDraw.Draw(m)
        for cx, left in ((x0 - flare, True), (x1 + flare, False)):    # the flares
            cy = base - flare
            d.rectangle([S(cx), S(cy), S(cx + flare), S(base)] if left else
                        [S(cx - flare), S(cy), S(cx), S(base)], fill=255)
            r = flare - grow
            d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], fill=0)
        d.rounded_rectangle([S(x0 - grow), S(top + stroke - grow), S(x1 + grow),
                             S(base + radius + 2)], radius=S(radius + grow), fill=255)
        d.rectangle([0, S(base), w * k, height * k], fill=0)
        return m

    full = (w * k, height * k)
    rings = Image.new("L", full, 0)               # every tab's outline (open at the bottom)
    tabs_in = Image.new("L", full, 0)             # every tab's inside
    opening = Image.new("L", full, 0)             # the open tab's inside: no line under it
    for i, (x0, x1) in enumerate(tabs):
        x0, x1 = x0 + stroke, x1 - stroke         # inside edges
        a, b = region(x0, x1, 0), region(x0, x1, stroke)
        rings = ImageChops.lighter(rings, ImageChops.subtract(b, a))
        tabs_in = ImageChops.lighter(tabs_in, a)
        if i == active:
            opening = a
    line = Image.new("L", full, 0)
    ImageDraw.Draw(line).rectangle([0, S(line_y), w * k, S(base) - 1], fill=255)
    page = Image.new("L", full, 0)
    ImageDraw.Draw(page).rectangle([0, S(base), w * k, height * k], fill=255)
    white = ImageChops.lighter(rings, ImageChops.subtract(line, opening))
    inside = ImageChops.lighter(tabs_in, page)
    white = white.resize((w, height), Image.LANCZOS)
    inside = inside.resize((w, height), Image.LANCZOS)
    tabs_in = tabs_in.resize((w, height), Image.LANCZOS)

    strip = img.crop((0, 0, w, height))
    strip.paste(fill or page_colour(), (0, 0), tabs_in)  # the tabs' insides cover the dots
    # shadow: under every bit of white, fading over shadow_len px down the page / tab
    shadow = Image.new("L", (w, height), 0)
    for dist in range(1, shadow_len + 1):
        strength = SHADOW_DARK * (1 - (dist - 1) / shadow_len)
        moved = Image.new("L", (w, height), 0)
        moved.paste(white.crop((0, 0, w, height - dist)), (0, dist))
        shadow = ImageChops.lighter(shadow, moved.point(lambda v, s=strength: int(v * s)))
    shadow = ImageChops.multiply(shadow, inside).filter(ImageFilter.GaussianBlur(0.7))
    strip = Image.composite(Image.new("RGB", strip.size, (0, 0, 0)), strip, shadow)
    strip.paste(LINE_WHITE, (0, 0), white)
    img.paste(strip, (0, 0))


def hex_rgb(colour: str) -> tuple:
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


class Backdrop(tk.Canvas):
    """A canvas showing the background picture. `layout(w, h, dots_h, header_h)`
    is called whenever the size changes: it places the screen's widgets and
    canvas items, and returns the panels to draw behind them as a list of
    dicts for draw_panel (box, radius, fill / shade, outline). `decorate(img)`,
    if given, draws the white line itself (Create: with its tabs)."""

    def __init__(self, parent, band: float = 1.0, layout=None, decorate=None):
        super().__init__(parent, highlightthickness=0, bd=0, background=theme.BG)
        self.band = band
        self.layout = layout
        self.decorate = decorate     # decorate(img): draws the line itself (e.g. with tabs)
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
        img, _dots_h, _header_h = compose(w, h, self.winfo_screenwidth(), self.band,
                                          line=self.decorate is None)
        if self.decorate:
            self.decorate(img)
        for p in self._panels or []:
            draw_panel(img, **p)
        self._img = ImageTk.PhotoImage(img)
        self.itemconfigure("bg", image=self._img)
        self.tag_lower("bg")
        self._drawn = (w, h)
