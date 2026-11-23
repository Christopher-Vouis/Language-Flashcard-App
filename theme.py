"""
Dark color scheme for the whole app.

All colors live here so the look can be tuned in one place. Uses ttk's
"clam" theme, because the native Windows ("vista") theme draws buttons,
tables and fields itself and ignores custom colors.
"""

from __future__ import annotations

import colorsys
import sys
import tkinter as tk
from tkinter import ttk

# ---- palette
BG = "#1e1f22"          # window background
SURFACE = "#2b2d31"     # tables, text boxes, input fields
RAISED = "#383a40"      # buttons
RAISED_HOVER = "#45474e"
RAISED_PRESS = "#50535b"
BORDER = "#45474e"
FG = "#e3e5e8"          # main text
MUTED = "#a3a7ad"       # secondary text (≈7:1 on BG)
SUBTLE = "#80858c"      # hints (≈4.6:1 on BG)
DISABLED = "#6b6f76"
ACCENT = "#5b8def"      # focus, progress, primary actions
ACCENT_HOVER = "#6f9cf2"
SELECT = "#2f4a7a"      # selected row / selected text
IMAGE_BG = "#141517"    # behind screenshots
HIGHLIGHT = "#5a4a12"   # previewed line in the full transcript (dark amber)
CHECKED = "#1f3552"     # ticked lines in the full transcript (dark blue)
TARGET = "#ff7a6e"      # target word in study mode
SCROLL = "#4a4d55"

FONT = ("Segoe UI", 10)

# ---- colour themes: the whole design turned to another hue (measured from the design
# mock-ups). Anything white stays white.
THEMES = {"Blue": 0, "Orange": -168, "Red": 161, "Green": -92, "Purple": 80}   # degrees, for the pictures
# the app's own colours (buttons, selections, progress...) use hues a little closer to
# each theme's name: blue 220° -> orange 32°, red 8°, green 135°, purple 280°
UI_HUES = {"Blue": 0, "Orange": -188, "Red": -212, "Green": -85, "Purple": 60}
NAME = "Blue"           # the current theme
HUE = 0                 # its turn, in degrees (pictures)
UI_HUE = 0              # its turn for the app's own colours
_THEMED = ("BG", "SURFACE", "RAISED", "RAISED_HOVER", "RAISED_PRESS", "BORDER", "FG", "MUTED", "SUBTLE",
           "DISABLED", "ACCENT", "ACCENT_HOVER", "SELECT", "IMAGE_BG", "CHECKED", "SCROLL")
# (TARGET and HIGHLIGHT keep their meaning - red word, amber line - in every theme)


def _luminance(rgb) -> float:
    """How bright a colour looks (WCAG relative luminance, 0 - 1)."""
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def shift_hex(colour: str, degrees: float) -> str:
    """A "#rrggbb" colour turned around the colour wheel. Its colourfulness and how
    bright it LOOKS are kept (yellow and green look much brighter than blue at the
    same lightness), so white text on it stays as readable as on the blue one."""
    if not degrees:
        return colour
    rgb = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    target = _luminance(rgb)
    h, l, s = colorsys.rgb_to_hls(*rgb)
    h = (h + degrees / 360) % 1.0
    lo, hi = 0.0, 1.0
    for _ in range(30):                     # find the lightness that looks as bright as before
        mid = (lo + hi) / 2
        if _luminance(colorsys.hls_to_rgb(h, mid, s)) < target:
            lo = mid
        else:
            hi = mid
    return "#" + "".join(f"{round(v * 255):02x}" for v in colorsys.hls_to_rgb(h, (lo + hi) / 2, s))


def tint(colour: str) -> str:
    """A colour from the blue design, in the current theme."""
    return shift_hex(colour, UI_HUE)


def tint_rgb(rgb: tuple) -> tuple:
    """A page colour of the background picture, in the current theme (as the picture is turned)."""
    if not HUE:
        return tuple(rgb)
    h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in rgb])
    return tuple(round(v * 255) for v in colorsys.hls_to_rgb((h + HUE / 360) % 1.0, l, s))


def shift_image(img, degrees: float | None = None):
    """A picture from the blue design, turned to the current theme (white, black
    and grey stay as they are)."""
    degrees = HUE if degrees is None else degrees
    if not degrees:
        return img
    alpha = img.getchannel("A") if img.mode in ("RGBA", "LA") else None
    h, s, v = img.convert("RGB").convert("HSV").split()
    turn = round(degrees / 360 * 256)
    h = h.point(lambda x: (x + turn) % 256)
    from PIL import Image
    out = Image.merge("HSV", (h, s, v)).convert("RGB")
    if alpha is not None:
        out.putalpha(alpha)
    return out


_COLOUR_OPTIONS = ("background", "foreground", "highlightbackground", "highlightcolor", "insertbackground",
                   "selectbackground", "selectforeground", "activebackground", "activeforeground",
                   "disabledforeground", "troughcolor", "selectcolor", "fieldbackground")
_ITEM_OPTIONS = ("fill", "outline", "activefill", "activeoutline", "disabledfill")


def change(root: tk.Tk, name: str, also: tuple = ()) -> None:
    """Switch the colour theme while the app is running: restyle the ttk
    widgets and swap every old theme colour for the new one in all open
    windows (widgets, canvas items, text tags). `also` = more colours of the
    blue design used directly (they're swapped too). Pictures are redrawn by
    their owners (see App.apply_theme)."""
    g = globals()
    old_vals = {k: g[k] for k in _THEMED}
    old_ui = UI_HUE
    set_theme(name)
    swap = {}
    for k in _THEMED:
        if old_vals[k].lower() != g[k].lower():
            swap[old_vals[k].lower()] = g[k]
    for c in also:
        a, b = shift_hex(c, old_ui).lower(), tint(c)
        if a != b.lower():
            swap.setdefault(a, b)
    apply(root, first=False)
    if swap:
        _recolour(root, swap)


def _recolour(widget, swap: dict) -> None:
    keys = set()
    try:
        keys = set(widget.keys())
    except tk.TclError:
        pass
    for opt in _COLOUR_OPTIONS:
        if opt in keys:
            try:
                v = str(widget.cget(opt)).lower()
            except tk.TclError:
                continue
            if v in swap:
                try:
                    widget.configure(**{opt: swap[v]})
                except tk.TclError:
                    pass
    if isinstance(widget, tk.Canvas):
        for item in widget.find_all():
            for opt in _ITEM_OPTIONS:
                try:
                    v = str(widget.itemcget(item, opt)).lower()
                except tk.TclError:
                    continue
                if v in swap:
                    widget.itemconfigure(item, **{opt: swap[v]})
    elif isinstance(widget, tk.Text):
        for tag in widget.tag_names():
            for opt in ("background", "foreground"):
                v = str(widget.tag_cget(tag, opt)).lower()
                if v in swap:
                    widget.tag_configure(tag, **{opt: swap[v]})
    remembered = getattr(widget, "bg", None)     # a colour kept for later drawing (CardView)
    if isinstance(remembered, str) and remembered.lower() in swap:
        widget.bg = swap[remembered.lower()]
    for child in widget.winfo_children():
        _recolour(child, swap)


def set_theme(name: str) -> None:
    """Choose the colour theme. Call before building any widgets (at start-up)."""
    global NAME, HUE, UI_HUE
    if name not in THEMES:
        name = "Blue"
    g = globals()
    base = g.setdefault("_BLUE", {k: g[k] for k in _THEMED})
    NAME, HUE, UI_HUE = name, THEMES[name], UI_HUES[name]
    for k in _THEMED:
        g[k] = shift_hex(base[k], UI_HUE)
    # the page colours must match the background picture's page exactly
    for k in ("BG",):
        g[k] = "#" + "".join(f"{v:02x}" for v in tint_rgb(tuple(int(base[k][i:i + 2], 16) for i in (1, 3, 5))))


def apply(root: tk.Tk, first: bool = True) -> ttk.Style:
    """Style every widget type used by the app. Called before building any
    widgets, and again (first=False) when the colour theme changes."""
    style = ttk.Style(root)
    if first:
        style.theme_use("clam")
    root.configure(background=BG)

    style.configure(".", background=BG, foreground=FG, fieldbackground=SURFACE,
                    bordercolor=BORDER, lightcolor=BG, darkcolor=BG, troughcolor=SURFACE,
                    focuscolor=ACCENT, selectbackground=SELECT, selectforeground=FG,
                    insertcolor=FG, font=FONT)
    style.map(".", foreground=[("disabled", DISABLED)])

    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("TSeparator", background=BORDER)
    style.configure("TPanedwindow", background=BG)
    style.configure("Sash", sashthickness=6, gripcount=0, background=BG)

    # buttons
    style.configure("TButton", background=RAISED, foreground=FG, bordercolor=BORDER,
                    lightcolor=RAISED, darkcolor=RAISED, focusthickness=1, padding=(10, 4))
    style.map("TButton",
              background=[("disabled", BG), ("pressed", RAISED_PRESS), ("active", RAISED_HOVER)],
              lightcolor=[("pressed", RAISED_PRESS), ("active", RAISED_HOVER)],
              darkcolor=[("pressed", RAISED_PRESS), ("active", RAISED_HOVER)],
              foreground=[("disabled", DISABLED)],
              bordercolor=[("focus", ACCENT)])
    style.configure("Big.TButton", font=("Segoe UI", 18, "bold"), padding=(36, 22),
                    background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT, foreground="#ffffff")
    style.map("Big.TButton",
              background=[("pressed", "#4a7bd9"), ("active", ACCENT_HOVER)],
              lightcolor=[("pressed", "#4a7bd9"), ("active", ACCENT_HOVER)],
              darkcolor=[("pressed", "#4a7bd9"), ("active", ACCENT_HOVER)])

    style.configure("Accent.TButton", background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    foreground="#ffffff", font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton",
              background=[("pressed", "#4a7bd9"), ("active", ACCENT_HOVER)],
              lightcolor=[("pressed", "#4a7bd9"), ("active", ACCENT_HOVER)],
              darkcolor=[("pressed", "#4a7bd9"), ("active", ACCENT_HOVER)])

    # check boxes
    style.configure("TCheckbutton", background=BG, foreground=FG,
                    indicatorbackground=SURFACE, indicatorforeground=FG, indicatorcolor=SURFACE)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", RAISED)],
              indicatorcolor=[("selected", ACCENT)],
              indicatorforeground=[("selected", "#ffffff")])

    # radio buttons (Settings → Theme): no highlight when the mouse is over them
    style.configure("TRadiobutton", background=BG, foreground=FG,
                    indicatorbackground=SURFACE, indicatorforeground=FG, indicatorcolor=SURFACE)
    style.map("TRadiobutton",
              background=[("active", BG)],
              foreground=[("disabled", DISABLED), ("active", FG)],
              indicatorbackground=[("selected", ACCENT), ("active", SURFACE)],
              indicatorcolor=[("selected", ACCENT), ("active", SURFACE)])

    # text inputs and drop-downs
    for w in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(w, fieldbackground=SURFACE, foreground=FG, background=RAISED,
                        bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE,
                        arrowcolor=FG, insertcolor=FG)
        style.map(w, bordercolor=[("focus", ACCENT)],
                  fieldbackground=[("readonly", SURFACE), ("disabled", BG)],
                  foreground=[("disabled", DISABLED)],
                  selectbackground=[("focus", SELECT), ("!focus", SURFACE)],
                  selectforeground=[("focus", FG), ("!focus", FG)])
    # the drop-down list of a Combobox is a plain Tk listbox
    root.option_add("*TCombobox*Listbox.background", SURFACE)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", SELECT)
    root.option_add("*TCombobox*Listbox.selectForeground", FG)

    # tables
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=FG,
                    bordercolor=BORDER, rowheight=26, font=("Segoe UI", 11))
    style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", FG)])
    style.configure("Treeview.Heading", background=RAISED, foreground=FG, bordercolor=BORDER,
                    lightcolor=RAISED, darkcolor=RAISED, font=("Segoe UI", 10, "bold"))
    style.map("Treeview.Heading", background=[("active", RAISED_HOVER)])

    # scrollbars, progress bar
    style.configure("TScrollbar", background=SCROLL, troughcolor=BG, bordercolor=BG,
                    lightcolor=SCROLL, darkcolor=SCROLL, arrowcolor=FG)
    style.map("TScrollbar", background=[("active", RAISED_HOVER)])
    style.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE, bordercolor=BORDER,
                    lightcolor=ACCENT, darkcolor=ACCENT)

    # plain Tk widgets (Text boxes, menus) take their colors from the option database
    for pattern, value in (
        ("*Text.background", SURFACE), ("*Text.foreground", FG),
        ("*Text.insertBackground", FG), ("*Text.selectBackground", SELECT),
        ("*Text.selectForeground", FG), ("*Text.highlightThickness", 1),
        ("*Text.highlightBackground", BORDER), ("*Text.highlightColor", ACCENT),
        ("*Text.relief", "flat"), ("*Text.borderWidth", 0),
        ("*Menu.background", SURFACE), ("*Menu.foreground", FG),
        ("*Menu.activeBackground", SELECT), ("*Menu.activeForeground", FG),
        ("*Menu.disabledForeground", DISABLED), ("*Menu.relief", "flat"),
        ("*Toplevel.background", BG),
    ):
        root.option_add(pattern, value)

    dark_title_bar(root)
    return style


def separator(parent, **pack) -> tk.Frame:
    """A thin horizontal rule in the border color (ttk.Separator ignores colors in clam)."""
    line = tk.Frame(parent, height=1, background=BORDER)
    line.pack(fill="x", **pack)
    return line


def dark_title_bar(window: tk.Misc) -> None:
    """Ask Windows 10/11 to draw this window's title bar dark. No effect elsewhere."""
    if not sys.platform.startswith("win"):
        return

    def _apply():
        try:
            import ctypes
            window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            value = ctypes.c_int(1)
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (newer, then older builds)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                    break
        except Exception:  # noqa: BLE001 - purely cosmetic
            pass

    window.after(0, _apply)
