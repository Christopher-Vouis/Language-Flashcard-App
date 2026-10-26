"""
Dark color scheme for the whole app.

All colors live here so the look can be tuned in one place. Uses ttk's
"clam" theme, because the native Windows ("vista") theme draws buttons,
tables and fields itself and ignores custom colors.
"""

from __future__ import annotations

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


def apply(root: tk.Tk) -> ttk.Style:
    """Style every widget type used by the app. Call once, before building
    any widgets (some settings only affect widgets created afterwards)."""
    style = ttk.Style(root)
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

    # check boxes
    style.configure("TCheckbutton", background=BG, foreground=FG,
                    indicatorbackground=SURFACE, indicatorforeground=FG, indicatorcolor=SURFACE)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", RAISED)],
              indicatorcolor=[("selected", ACCENT)],
              indicatorforeground=[("selected", "#ffffff")])

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
