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

The picture isn't one big image: each part (the dots band in tiles, the line, the
A / あ, the stripes, the tabs, the panels' corners) is its own canvas item, made
once per window height and then only moved. So resizing sideways, and changing
screens, costs almost nothing; only a new height scales the parts again (quickly
while the window is being dragged, then properly once it stops).
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
_scaled: dict = {}           # (height, fast) -> scaled parts (resizing the 3840 px band is slow)
DRAG_STEP = 16               # while dragging, parts are scaled again only every this many px of height


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
    _pieces.clear()


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


def _scaled_parts(h: int, fast: bool = False):
    """The parts scaled for a window h px tall: (dots, dots flipped, line column,
    glyphs, stripes, line height). fast = a quick, slightly softer scaling (while
    the window is being dragged); the proper one replaces it when it stops."""
    key = (h, False)
    if key not in _scaled and fast:
        h = max(round(h / DRAG_STEP) * DRAG_STEP, DRAG_STEP)   # nearby heights share one quick scaling
        key = (h, True)
    if key not in _scaled:
        sy = h / DESIGN_H
        dots, line, glyphs, stripes = _layers()
        how = Image.BILINEAR if fast else Image.LANCZOS
        scale = lambda im: im.resize((max(round(im.width * sy), 1), max(round(im.height * sy), 1)), how)  # noqa: E731
        band_h = max(round(LINE_Y * sy), 1)
        if fast:                                  # the band is 3840 px wide: halve it quickly first
            dots = dots.reduce(2) if dots.height > band_h * 3 else dots
        dots = dots.resize((max(round(dots.width * band_h / dots.height), 1), band_h), how)
        if len(_scaled) > 12:
            _scaled.clear()
        _scaled[key] = (dots, dots.transpose(Image.FLIP_LEFT_RIGHT), line, scale(glyphs), scale(stripes),
                        max(round(line.height * sy), 1))
    return _scaled[key], key


def available() -> bool:
    return Image is not None and bool(_layers())


def glyph_x(w: int, h: int, glyph_w: int, screen_w: int) -> int:
    """Left edge of the A / あ: they drift right as the window widens."""
    sy = h / DESIGN_H
    home = (GLYPH_BOX[0] + GLYPH_BOX[2]) / 2 / DESIGN_W
    narrow = DESIGN_W * sy
    t = min(max((w - narrow) / (screen_w - narrow), 0), 1) if screen_w > narrow else 1
    centre = (home + (GLYPH_FULL_SCREEN - home) * t) * w
    return min(max(round(centre - glyph_w / 2), 0), max(w - glyph_w, 0))


# ------------------------------------------------------------------ panels
_pieces: dict = {}           # small pictures made once: panel corners, ...


def _rounded_mask(w: int, h: int, radius: float, inset: int = 0):
    """A w x h mask of a rounded box (inset px in from the edges), smooth edges."""
    k = 3                                         # draw 3x and shrink = smooth corners
    m = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(m).rounded_rectangle((inset * k, inset * k, (w - inset) * k - 1, (h - inset) * k - 1),
                                        radius=max(radius - inset, 0) * k, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def panel_corners(radius: float, fill=None, outline=None, shade: float | None = None) -> tuple[int, list]:
    """The four corners of a panel as RGBA pictures (tl, tr, bl, br), each r x r.
    Between them a panel is straight, so the rest is plain rectangles."""
    key = ("corners", round(radius, 2), fill, outline, shade)
    if key not in _pieces:
        r = int(radius) + 2
        size = 2 * r + 1
        outer = _rounded_mask(size, size, radius)
        if shade is not None:
            pic = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            pic.putalpha(outer.point(lambda v: round(v * (1 - shade))))
        else:
            inner = _rounded_mask(size, size, radius, 1) if outline else outer
            rgb = Image.composite(Image.new("RGB", (size, size), tuple(fill)),
                                  Image.new("RGB", (size, size), tuple(outline or fill)), inner)
            pic = rgb.convert("RGBA")
            pic.putalpha(outer)
        crops = [pic.crop(b) for b in ((0, 0, r, r), (size - r, 0, size, r),
                                        (0, size - r, r, size), (size - r, size - r, size, size))]
        _pieces[key] = (r, crops)
    return _pieces[key]


# the white line and the shadow under it, measured from menu_bg.png (design px)
LINE_STROKE = 3            # white, (234, 234, 234)
SHADOW_LEN = 25            # the shadow fades from SHADOW_DARK to nothing over this many px
SHADOW_DARK = 0.67         # right under the line the page is this much darker
LINE_WHITE = (234, 234, 234)


def tabs_layer(w: int, tabs: list[tuple[float, float]], active: int, top: float, line_y: float,
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
    stroke = max(LINE_STROKE * sy, 1.2)
    shadow_len = max(round(SHADOW_LEN * sy), 3)
    flare = max(flare, stroke + 1.5)
    height = int(line_y + stroke + shadow_len + 3)
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

    # shadow: under every bit of white, fading over shadow_len px down the page / tab
    shadow = Image.new("L", (w, height), 0)
    for dist in range(1, shadow_len + 1):
        strength = SHADOW_DARK * (1 - (dist - 1) / shadow_len)
        moved = Image.new("L", (w, height), 0)
        moved.paste(white.crop((0, 0, w, height - dist)), (0, dist))
        shadow = ImageChops.lighter(shadow, moved.point(lambda v, s=strength: int(v * s)))
    shadow = ImageChops.multiply(shadow, inside).filter(ImageFilter.GaussianBlur(0.7))
    size = (w, height)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    for colour, mask in ((fill or page_colour(), tabs_in),      # the tabs' insides cover the dots
                         ((0, 0, 0), shadow), (LINE_WHITE, white)):
        part = Image.new("RGBA", size, tuple(colour) + (0,))
        part.putalpha(mask)
        layer = Image.alpha_composite(layer, part)
    return layer


def hex_rgb(colour: str) -> tuple:
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def rgb_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb[:3])


class Scene:
    """The background picture on a canvas, as separate items (see the top of the
    file). Its items have the tags "scene" (all), "scene_bg" (the picture) and
    "scene_panel" (panels); they're kept under everything else on the canvas.

        place(w, h, fast)   lay the picture out for a w x h canvas
        set_tabs(...)       the white line with tabs on it (Create), or None
        panels([...])       the panels: dicts of box, radius, fill / shade, outline
    """

    def __init__(self, canvas: tk.Canvas, band: float = 1.0, line: bool = True):
        self.c = canvas
        self.band = band
        self.line = line
        self._photos: dict = {}       # what the items show (Tk drops images nobody keeps)
        self._tiles: list[int] = []
        self._panel_items: list[int] = []
        self._solid: dict = {}          # panel number -> (its items, corner size, outlined)
        self._panel_key = None
        self._tabs_key = None
        self.fast = False             # True: parts were scaled quickly; place() again when settled
        self.size = (0, 0)
        canvas.configure(background=rgb_hex(page_colour()))
        for tag in ("stripes", "glyphs", "line", "tabs", "tabs_left", "tabs_right"):
            canvas.create_image(0, 0, anchor="nw", tags=("scene", "scene_bg", f"scene_{tag}"))

    def header(self, h: int) -> tuple[int, int]:
        """(dots height, header height) for a canvas h px tall: the white line and
        its shadow sit between them."""
        sy = h / DESIGN_H
        shown = max(round(max(round(LINE_Y * sy), 1) * self.band), 1)
        return shown, shown + max(round((HEADER_H - LINE_Y) * sy), 1)

    def retheme(self):
        """The colour theme changed (after reset()): make the pictures again."""
        self._photos.clear()
        self._panel_key = self._tabs_key = None
        self.size = (0, 0)
        self.c.configure(background=rgb_hex(page_colour()))

    def _photo(self, key, make):
        if key not in self._photos:
            if len(self._photos) > 40:
                self._photos.clear()      # (the items get their new pictures right after)
                self._panel_key = self._tabs_key = None
            self._photos[key] = ImageTk.PhotoImage(make())
        return self._photos[key]

    def place(self, w: int, h: int, fast: bool = False):
        c = self.c
        if not available():
            self.size = (w, h)
            return
        parts, pk = _scaled_parts(h, fast)            # pk: (the height they're scaled for, quick?)
        self.fast = pk[1]
        dots, flipped, line_col, glyphs, stripes, line_h = parts
        dots_h, _header_h = self.header(h)
        # stripes: bottom-left corner
        c.itemconfigure("scene_stripes", image=self._photo(("stripes", pk), lambda: stripes))
        c.coords("scene_stripes", 0, h - stripes.height)
        # A / あ
        c.itemconfigure("scene_glyphs", image=self._photo(("glyphs", pk), lambda: glyphs))
        c.coords("scene_glyphs", glyph_x(w, h, glyphs.width, c.winfo_screenwidth()), round(GLYPH_BOX[1] * sy(h)))
        # the dots band: tiles, every other one mirrored, so it continues seamlessly
        shown = max(round(dots.height * self.band), 1)    # the part of the band this screen shows
        crop = (0, dots.height - shown, dots.width, dots.height)
        normal = self._photo(("dots", pk, 0), lambda: dots.crop(crop))
        mirror = self._photo(("dots", pk, 1), lambda: flipped.crop(crop))
        n = -(-w // dots.width)
        while len(self._tiles) < n:
            self._tiles.append(c.create_image(0, 0, anchor="sw", tags=("scene", "scene_bg", "scene_dots")))
        for i, item in enumerate(self._tiles):
            c.itemconfigure(item, image=mirror if i % 2 else normal, state="normal" if i < n else "hidden",
                            anchor="sw")
            c.coords(item, i * dots.width, dots_h)          # (their bottom edge is on the line)
        # the white line and its shadow, the full width (or tabs: set_tabs)
        if self.line:
            lw = max(c.winfo_screenwidth(), w)
            c.itemconfigure("scene_line", image=self._photo(("line", pk, lw),
                                                             lambda: line_col.resize((lw, line_h), Image.LANCZOS)))
            c.coords("scene_line", 0, dots_h)
        self.size = (w, h)
        self._order()

    def set_tabs(self, tabs: list[tuple[float, float]], active: int, top: float, line_y: float,
                 radius: float, flare: float, sy: float, fill=None, fast: bool = False) -> bool:
        """The white line with tabs standing on it (see tabs_layer). Only the tabs'
        part is drawn; the line either side of it is one column of it, stretched.
        fast (while the window is being dragged): if only the height changed a
        little, the tabs drawn last time are just moved. Returns True if so (then
        set_tabs should be called again once the window has settled)."""
        c = self.c
        if Image is None:
            return False
        last = getattr(self, "_tabs_at", None)
        if (fast and last and self._tabs_key and self._tabs_key[1] == active
                and abs(sy / last[2] - 1) < 0.06):
            x0, y_line, _sy, half = last
            mid = (tabs[0][0] + tabs[-1][1]) / 2          # keep them centred where the new ones are
            c.move("scene_tabs || scene_tabs_left || scene_tabs_right", round(mid - half) - x0,
                   round(line_y - y_line))
            self._tabs_at = (x0 + round(mid - half) - x0, y_line + round(line_y - y_line), last[2], half)
            return True
        stroke = max(LINE_STROKE * sy, 1.2)
        pad = int(max(flare, stroke + 1.5) + stroke + 6)
        x0 = int(tabs[0][0]) - pad
        rel = [(round(l - x0, 1), round(r - x0, 1)) for l, r in tabs]
        span = int(tabs[-1][1] - x0) + pad
        key = (tuple(rel), active, round(top, 1), round(line_y, 1), round(radius, 2), round(flare, 2),
               round(sy, 4), fill, span)
        if key != self._tabs_key:
            layer = tabs_layer(span, rel, active, top, line_y, radius, flare, sy, fill)
            edge = layer.crop((0, 0, 1, layer.height))
            side = max(c.winfo_screenwidth(), 2000)
            self._photos["tabs"] = ImageTk.PhotoImage(layer)
            self._photos["tabs_side"] = ImageTk.PhotoImage(edge.resize((side, layer.height)))
            c.itemconfigure("scene_tabs", image=self._photos["tabs"])
            c.itemconfigure("scene_tabs_left", image=self._photos["tabs_side"], anchor="ne")
            c.itemconfigure("scene_tabs_right", image=self._photos["tabs_side"], anchor="nw")
            self._tabs_key = key
        c.coords("scene_tabs", x0, 0)
        c.coords("scene_tabs_left", x0, 0)
        c.coords("scene_tabs_right", x0 + span, 0)
        self._tabs_at = (x0, line_y, sy, (tabs[0][0] + tabs[-1][1]) / 2 - x0)
        self._order()
        return False

    def panels(self, panels: list[dict]):
        """Draw the panels: the corners are small pictures, the rest rectangles
        (solid panels) or one see-through picture (shaded panels). Panels that
        only moved are moved, not drawn again."""
        c = self.c
        boxes = [tuple(round(v) for v in p["box"]) for p in panels]
        looks = tuple((b[2] - b[0], b[3] - b[1], p.get("radius"), p.get("fill"), p.get("shade"),
                       p.get("outline")) for b, p in zip(boxes, panels))
        if self._panel_key is not None and looks == self._panel_key[0]:
            for i, (old, new) in enumerate(zip(self._panel_key[1], boxes)):
                if old != new:
                    c.move(f"scene_panel{i}", new[0] - old[0], new[1] - old[1])
            self._panel_key = (looks, boxes)
            return
        if (Image is not None and self._panel_key is not None and len(looks) == len(self._panel_key[0])
                and all(a[2:] == b[2:] and a[4] is None and a[0] > 2 * a[2] + 8 and a[1] > 2 * a[2] + 8
                        for a, b in zip(looks, self._panel_key[0]))):
            # solid panels that changed size: move their pieces (no new items)
            for i, (p, box) in enumerate(zip(panels, boxes)):
                if box != self._panel_key[1][i]:
                    self._solid_coords(i, box)
            self._panel_key = (looks, boxes)
            return
        self._panel_key = (looks, boxes)
        for item in self._panel_items:
            c.delete(item)
        self._panel_items = []
        self._solid = {}
        for i, p in enumerate(panels):
            self._panel(i, p)
        self._order()

    def _panel(self, i: int, p: dict):
        c = self.c
        x0, y0, x1, y1 = (round(v) for v in p["box"])
        if x1 - x0 < 4 or y1 - y0 < 4:
            return
        fill, outline, shade = p.get("fill"), p.get("outline"), p.get("shade")
        tags = ("scene", "scene_panel", f"scene_panel{i}")

        def add(item: int) -> int:
            self._panel_items.append(item)
            return item

        if Image is None:                                 # no Pillow: square corners
            colour = rgb_hex(fill) if fill else "#101113"
            add(c.create_rectangle(x0, y0, x1 - 1, y1 - 1, fill=colour, tags=tags,
                                   outline=rgb_hex(outline) if outline else ""))
            return
        radius = min(p.get("radius", 0), (x1 - x0) / 2 - 2, (y1 - y0) / 2 - 2)
        r, corners = panel_corners(radius, fill, outline, shade)
        if shade is not None:
            # see-through: one picture, dark and partly transparent, with the corners in it
            def make():
                pic = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, round(255 * (1 - shade))))
                for crop, (cx, cy) in zip(corners, ((0, 0), (x1 - x0 - r, 0), (0, y1 - y0 - r),
                                                    (x1 - x0 - r, y1 - y0 - r))):
                    pic.paste(crop, (cx, cy))
                return pic
            photo = ImageTk.PhotoImage(make())
            self._photos[("panel", i)] = photo
            add(c.create_image(x0, y0, anchor="nw", image=photo, tags=tags))
            return
        f = rgb_hex(fill)
        o = rgb_hex(outline) if outline else f
        items = [add(c.create_rectangle(0, 0, 0, 0, fill=colour, outline="", width=0, tags=tags))
                 for colour in (f, f, f) + ((o, o, o, o) if outline else ())]
        for n in range(4):
            photo = self._photo(("corner", r, fill, outline, n), lambda n=n: corners[n])
            items.append(add(c.create_image(0, 0, anchor="nw", image=photo, tags=tags)))
        self._solid[i] = (items, r, bool(outline))
        self._solid_coords(i, (x0, y0, x1, y1))

    def _solid_coords(self, i: int, box):
        """Put a solid panel's pieces (made by _panel) around box."""
        c = self.c
        items, r, outlined = self._solid[i]
        x0, y0, x1, y1 = box
        rects = [(x0 + r, y0, x1 - r, y1),                # the middle, top to bottom
                 (x0, y0 + r, x0 + r, y1 - r),            # the sides between the corners
                 (x1 - r, y0 + r, x1, y1 - r)]
        if outlined:
            rects += [(x0 + r, y0, x1 - r, y0 + 1), (x0 + r, y1 - 1, x1 - r, y1),
                      (x0, y0 + r, x0 + 1, y1 - r), (x1 - 1, y0 + r, x1, y1 - r)]
        for item, xy in zip(items, rects):
            c.coords(item, *xy)
        for item, xy in zip(items[len(rects):], ((x0, y0), (x1 - r, y0), (x0, y1 - r), (x1 - r, y1 - r))):
            c.coords(item, *xy)

    def _order(self):
        """The picture at the bottom, the panels on it, everything else above."""
        self.c.tag_lower("scene_panel")
        self.c.tag_lower("scene_bg")
        self.c.tag_lower("scene_dots")


def sy(h: int) -> float:
    return h / DESIGN_H


class Backdrop(tk.Canvas):
    """A canvas showing the background picture. `layout(w, h, dots_h, header_h)`
    is called whenever the size changes: it places the screen's widgets and
    canvas items, and returns the panels to draw behind them (dicts of box,
    radius, fill / shade, outline). `tabs()`, if given, returns the arguments of
    Scene.set_tabs (Create: the white line with its tabs).

    While the screen isn't the one shown (set_active(False)), size changes are
    only noted, and laid out when it's shown again."""

    def __init__(self, parent, band: float = 1.0, layout=None, tabs=None):
        super().__init__(parent, highlightthickness=0, bd=0, background=theme.BG)
        self.layout = layout
        self.tabs = tabs
        self.scene = Scene(self, band, line=tabs is None)
        self.active = True
        self._dirty = False
        self._settle = None
        self.bind("<Configure>", self._on_configure)

    def header(self, h: int) -> tuple[int, int]:
        return self.scene.header(h)

    def set_active(self, active: bool):
        self.active = active
        if active and self._dirty:
            self._apply(fast=False)

    def _on_configure(self, _e=None):
        if not self.active:
            self._dirty = True
            return
        # at once (the parts are only scaled again for a new height, quickly while
        # the window is being dragged); properly once it has settled
        self._apply(fast=self.scene.size != (0, 0))

    def refresh(self):
        """Lay the screen out again (its contents changed)."""
        if not self.active:
            self._dirty = True
            return
        self._apply(fast=False)

    def retheme(self):
        """The colour theme changed (after reset())."""
        self.scene.retheme()
        self.refresh()

    def _apply(self, fast: bool):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        self._dirty = False
        panels = self.layout(w, h, *self.header(h)) if self.layout else []
        self.scene.place(w, h, fast)
        moved_tabs = False
        if self.tabs:
            spec = self.tabs()
            if spec:
                moved_tabs = self.scene.set_tabs(**spec, fast=fast)
        self.scene.panels(panels or [])
        if self._settle:
            self.after_cancel(self._settle)
            self._settle = None
        if self.scene.fast or moved_tabs:
            self._settle = self.after(150, self._settled)

    def _settled(self):
        self._settle = None
        if self.active:
            self._apply(fast=False)
        else:
            self._dirty = True
