"""
Multilingual Transcriber - desktop app.

Run:  python app.py            (or double-click run.bat)
      python app.py myvideo.mp4   (opens with a file pre-selected)
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import media
import subtitles
import transcriber as tr
from cards import CardStore
from saved import SavedStore

try:
    from PIL import Image, ImageTk
except ImportError:  # screenshots won't display until setup.bat is re-run
    Image = ImageTk = None

try:
    import winsound
except ImportError:  # not Windows
    winsound = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_DIR, "output")
SAVED_DIR = os.path.join(APP_DIR, "saved")
CARDS_DIR = os.path.join(APP_DIR, "cards")
UNCHECKED, CHECKED = "☐", "☑"

MEDIA_TYPES = [
    ("Audio / video", "*.mp3 *.wav *.m4a *.flac *.ogg *.opus *.aac *.wma "
                      "*.mp4 *.mkv *.mov *.avi *.webm *.wmv *.m4v *.flv"),
    ("All files", "*.*"),
]


# ---------------------------------------------------------------- audio
def play_wav(path: str) -> bool:
    if not path or winsound is None or not os.path.isfile(path):
        return False
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    return True


def stop_wav() -> None:
    if winsound is not None:
        winsound.PlaySound(None, 0)


def open_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606
    else:
        messagebox.showinfo("Folder", path)


# ------------------------------------------------------- preview panel
class PreviewPanel(ttk.Frame):
    """Screenshot + (card fields) + line text + Play/Stop. Used by every window."""

    def __init__(self, parent, autoplay_var: tk.BooleanVar | None = None, image_height: int = 260):
        super().__init__(parent, padding=(8, 0, 0, 0))
        self._audio = ""
        self._photo = None        # keep a reference so Tk doesn't drop the image
        self._image = None        # (path, PIL image) currently shown

        # fixed-size holder so the image never pushes the layout around
        holder = tk.Frame(self, bg="#1e1e1e", width=420, height=image_height)
        holder.pack(fill="both", expand=True)
        holder.pack_propagate(False)
        self.image_label = tk.Label(holder, bg="#1e1e1e", fg="#bbbbbb",
                                    text="Select a line to preview it", font=("Segoe UI", 10))
        self.image_label.pack(fill="both", expand=True)
        self.image_label.bind("<Configure>", lambda e: self._render())

        # card fields (only shown for cards)
        self.details = ttk.Frame(self)
        self.word_var, self.reading_var, self.def_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(self.details, textvariable=self.word_var,
                  font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(self.details, textvariable=self.reading_var, font=("Segoe UI", 12),
                  foreground="#555").pack(anchor="w")
        self.def_label = ttk.Label(self.details, textvariable=self.def_var, font=("Segoe UI", 11),
                                   wraplength=420, justify="left")
        self.def_label.pack(anchor="w", fill="x", pady=(2, 0))

        self.meta_var = tk.StringVar()
        self.text_var = tk.StringVar()
        self.meta_label = ttk.Label(self, textvariable=self.meta_var, foreground="#666")
        self.meta_label.pack(anchor="w", pady=(8, 0))
        self.text_label = ttk.Label(self, textvariable=self.text_var, font=("Segoe UI", 14),
                                    wraplength=420, justify="left")
        self.text_label.pack(anchor="w", fill="x", pady=(2, 8))
        self.bind("<Configure>", self._rewrap)

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 4))
        self.play_btn = ttk.Button(controls, text="▶  Play", command=self.play, state="disabled")
        self.play_btn.pack(side="left")
        ttk.Button(controls, text="■  Stop", command=stop_wav).pack(side="left", padx=6)
        if autoplay_var is not None:
            ttk.Checkbutton(controls, text="Auto-play on select",
                            variable=autoplay_var).pack(side="left", padx=6)
            ttk.Label(self, text="Tip: ↑/↓ to move, Space or double-click to play.",
                      foreground="#888").pack(anchor="w")

    def _rewrap(self, e):
        w = max(e.width - 20, 200)
        self.text_label.configure(wraplength=w)
        self.def_label.configure(wraplength=w)

    def show(self, text: str, meta: str, audio: str = "", shot: str = "", placeholder: str = "",
             card: dict | None = None):
        self.text_var.set(text)
        self.meta_var.set(meta)
        self._audio = audio if audio and os.path.isfile(audio) else ""
        self.play_btn.config(state="normal" if self._audio else "disabled")
        if card:
            self.word_var.set(card.get("target_word", ""))
            self.reading_var.set(card.get("reading", ""))
            self.def_var.set(card.get("definition", ""))
            self.details.pack(anchor="w", fill="x", pady=(8, 0), before=self.meta_label)
        else:
            self.details.pack_forget()

        if shot and os.path.isfile(shot) and Image is not None:
            try:
                if not self._image or self._image[0] != shot:
                    with Image.open(shot) as im:
                        self._image = (shot, im.copy())
                self._render()
                return
            except OSError:
                pass
        if shot and Image is None:
            placeholder = "Run setup.bat once more to enable screenshot display (installs Pillow)."
        self._image = None
        self._photo = None
        self.image_label.config(image="", text=placeholder or ("♪  Audio only" if self._audio
                                                               else "No screenshot"))

    def clear(self, msg: str = "Select a line to preview it"):
        self._image = self._photo = None
        self._audio = ""
        self.image_label.config(image="", text=msg)
        self.text_var.set("")
        self.meta_var.set("")
        self.details.pack_forget()
        self.play_btn.config(state="disabled")

    def play(self):
        play_wav(self._audio)

    def _render(self):
        if not self._image:
            return
        w = max(self.image_label.winfo_width() - 4, 50)
        h = max(self.image_label.winfo_height() - 4, 50)
        img = self._image[1].copy()
        img.thumbnail((w, h))
        self._photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=self._photo, text="")


# ------------------------------------------------------- card editor
class CardEditor(tk.Toplevel):
    """Modal dialog: fill in target word / reading / definition for a line.
    After wait_window(), .result is a dict of the three fields, or None."""

    def __init__(self, parent, title: str, sentence: str, meta: str,
                 audio: str = "", shot: str = "", fields: dict | None = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("640x780")
        self.minsize(520, 600)
        self.transient(parent)
        self.result = None
        fields = fields or {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        self.preview = PreviewPanel(body, image_height=240)
        self.preview.pack(fill="both", expand=True)
        self.preview.show("", meta, audio=audio, shot=shot)
        self.preview.text_label.pack_forget()  # the sentence is shown below, selectable

        ttk.Label(body, text="Sentence  (highlight a word, then click “Use selection”)",
                  foreground="#666").pack(anchor="w", pady=(6, 2))
        self.sentence = tk.Text(body, height=3, wrap="word", font=("Segoe UI", 14),
                                relief="flat", background="#f6f6f6")
        self.sentence.insert("1.0", sentence)
        self.sentence.config(state="disabled")  # read-only but still selectable
        self.sentence.pack(fill="x")
        ttk.Button(body, text="↓  Use selection as target word",
                   command=self._use_selection).pack(anchor="w", pady=(4, 8))

        form = ttk.Frame(body)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        self.word_var = tk.StringVar(value=fields.get("target_word", ""))
        self.reading_var = tk.StringVar(value=fields.get("reading", ""))
        ttk.Label(form, text="Target word:").grid(row=0, column=0, sticky="w", pady=3)
        self.word_entry = ttk.Entry(form, textvariable=self.word_var, font=("Segoe UI", 13))
        self.word_entry.grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Reading:").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self.reading_var, font=("Segoe UI", 13)).grid(
            row=1, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Definition:").grid(row=2, column=0, sticky="nw", pady=3)
        self.def_text = tk.Text(form, height=4, wrap="word", font=("Segoe UI", 11))
        self.def_text.insert("1.0", fields.get("definition", ""))
        self.def_text.grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="  ", width=12).grid(row=3, column=0)  # keeps label column width

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(buttons, text="Save card", command=self.save).pack(side="right", padx=6)
        ttk.Label(buttons, text="Ctrl+Enter to save, Esc to cancel", foreground="#888").pack(side="left")

        self.bind("<Control-Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.word_entry.focus_set()
        self.grab_set()

    def _use_selection(self):
        try:
            text = self.sentence.get("sel.first", "sel.last").strip()
        except tk.TclError:  # nothing highlighted
            text = ""
        if text:
            self.word_var.set(text)
            self.word_entry.focus_set()
            self.word_entry.icursor("end")

    def save(self):
        word = self.word_var.get().strip()
        if not word:
            messagebox.showwarning("Target word needed", "Please enter the target word.", parent=self)
            self.word_entry.focus_set()
            return
        self.result = {
            "target_word": word,
            "reading": self.reading_var.get().strip(),
            "definition": self.def_text.get("1.0", "end").strip(),
        }
        stop_wav()
        self.destroy()

    def cancel(self):
        stop_wav()
        self.destroy()


# ------------------------------------------------ list window (base class)
class RecordWindow(tk.Toplevel):
    """Searchable table + preview panel. Subclasses describe their records."""

    TITLE = ""
    NOUN = ("item", "items")
    COLUMNS: tuple = ()        # (id, heading, width, stretch, anchor)
    FOLDER = ""
    WINDOW_ATTR = ""           # attribute on App holding the open window

    def __init__(self, app: "App"):
        super().__init__(app)
        self.app = app
        self.title(self.TITLE)
        self.geometry("1200x660")
        self.minsize(820, 440)
        self.autoplay_var = tk.BooleanVar(value=False)
        self.search_var = tk.StringVar()
        self.count_var = tk.StringVar()

        top = ttk.Frame(self, padding=(10, 10, 10, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        ttk.Entry(top, textvariable=self.search_var, width=32).pack(side="left", padx=6)
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Label(top, textvariable=self.count_var, foreground="#666").pack(side="left", padx=10)

        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=4)

        table = ttk.Frame(main)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in self.COLUMNS],
                                 show="headings", selectmode="extended")
        for col, label, w, stretch, anchor in self.COLUMNS:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, stretch=stretch, anchor=anchor)
        ysb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.preview.play())
        self.tree.bind("<space>", lambda e: (self.preview.play(), "break")[1])
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Control-a>", lambda e: (self.tree.selection_set(self.tree.get_children()), "break")[1])
        self.tree.bind("<Button-3>", self._context_menu)
        main.add(table, weight=3)

        self.preview = PreviewPanel(main, self.autoplay_var)
        main.add(self.preview, weight=2)

        bottom = ttk.Frame(self, padding=(10, 4, 10, 10))
        bottom.pack(fill="x")
        self.menu = tk.Menu(self, tearoff=False)
        self.add_actions(bottom, self.menu)
        self.menu.add_command(label="▶  Play", command=self.preview.play)
        self.menu.add_separator()
        self.menu.add_command(label="Delete selected", command=self.delete_selected)
        ttk.Button(bottom, text="Delete selected", command=self.delete_selected).pack(side="left", padx=6)
        ttk.Button(bottom, text="Open folder",
                   command=lambda: open_folder(self.FOLDER)).pack(side="left")
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self.tree.focus_set()

    # --- subclass hooks
    def records(self) -> list[dict]:
        raise NotImplementedError

    def row(self, r: dict) -> tuple:
        raise NotImplementedError

    def search_text(self, r: dict) -> str:
        raise NotImplementedError

    def preview_record(self, r: dict) -> None:
        raise NotImplementedError

    def remove(self, ids: list[str]) -> None:
        raise NotImplementedError

    def add_actions(self, bar: ttk.Frame, menu: tk.Menu) -> None:
        """Add window-specific buttons (left side) and context-menu items."""

    # --- shared behaviour
    @staticmethod
    def media_icons(r: dict) -> str:
        return (("♪" if r.get("audio_clip") else "") + (" ▣" if r.get("screenshot") else "")).strip()

    def refresh(self):
        q = self.search_var.get().strip().lower()
        prev = set(self.tree.selection())
        focus = self.tree.focus()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        records = self.records()
        for r in records:
            if q and q not in self.search_text(r).lower():
                continue
            self.tree.insert("", "end", iid=r["id"], values=self.row(r))
            shown += 1
        total = len(records)
        one, many = self.NOUN
        self.count_var.set(f"{total} {one if total == 1 else many}" + (f" ({shown} shown)" if q else ""))
        keep = [i for i in prev if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
            if focus and self.tree.exists(focus):
                self.tree.focus(focus)
                self._on_select()
        else:
            self.preview.clear(f"No {many} yet." if not total else "Select a line to preview it")

    def focused(self) -> dict | None:
        iid = self.tree.focus() or (self.tree.selection() or [None])[0]
        return next((r for r in self.records() if r["id"] == iid), None) if iid else None

    def _on_select(self, event=None):
        r = self.focused()
        if not r:
            return
        self.preview_record(r)
        if self.autoplay_var.get() and event is not None:
            self.preview.play()

    def _context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set([iid])
        self.tree.focus(iid)
        self._on_select()
        self.menu.tk_popup(event.x_root, event.y_root)

    def delete_selected(self):
        ids = list(self.tree.selection())
        if not ids:
            return
        one, many = self.NOUN
        if not messagebox.askyesno(f"Delete {many}",
                                   f"Delete {len(ids)} {one if len(ids) == 1 else many} "
                                   "and their clips/screenshots?", parent=self):
            return
        stop_wav()
        self.remove(ids)
        self.preview.clear()
        self.refresh()

    def close(self):
        stop_wav()
        setattr(self.app, self.WINDOW_ATTR, None)
        self.destroy()


# ---------------------------------------------------- saved lines window
class SavedLinesWindow(RecordWindow):
    TITLE = "Saved lines"
    NOUN = ("saved line", "saved lines")
    COLUMNS = (
        ("text", "Text", 380, True, "w"),
        ("source", "From", 150, False, "w"),
        ("lang", "Lang", 45, False, "center"),
        ("time", "Time", 75, False, "center"),
        ("media", "Media", 55, False, "center"),
        ("cards", "Cards", 50, False, "center"),
    )
    FOLDER = SAVED_DIR
    WINDOW_ATTR = "saved_window"

    def records(self):
        return self.app.store.entries

    def row(self, e):
        n = self.app.cards.count_for_line(e["id"])
        return (e["text"], os.path.basename(e["source_file"]), e.get("language", ""),
                tr.fmt_time(e["start"])[:8], self.media_icons(e), n or "")

    def search_text(self, e):
        return e["text"]

    def preview_record(self, e):
        meta = (f"{os.path.basename(e['source_file'])}  ·  line {e.get('line_number', '?')}  ·  "
                f"{tr.fmt_time(e['start'])} – {tr.fmt_time(e['end'])}")
        self.preview.show(e["text"], meta,
                          audio=self.app.store.abs_path(e.get("audio_clip", "")),
                          shot=self.app.store.abs_path(e.get("screenshot", "")))

    def remove(self, ids):
        self.app.store.remove(ids)
        self.app.on_saved_changed()

    def add_actions(self, bar, menu):
        ttk.Button(bar, text="＋  New card...", command=self.new_card).pack(side="left")
        menu.add_command(label="＋  New card...", command=self.new_card)
        self.tree.bind("<Return>", lambda e: self.new_card())
        self.bind("<Control-n>", lambda e: self.new_card())
        ttk.Label(bar, text="Select a line, then New card (Enter / Ctrl+N)",
                  foreground="#888").pack(side="right", padx=10)

    def new_card(self):
        e = self.focused()
        if not e:
            messagebox.showinfo("No line selected", "Select a saved line first.", parent=self)
            return
        stop_wav()
        meta = f"{os.path.basename(e['source_file'])}  ·  {tr.fmt_time(e['start'])}"
        dlg = CardEditor(self, "New card", e["text"], meta,
                         audio=self.app.store.abs_path(e.get("audio_clip", "")),
                         shot=self.app.store.abs_path(e.get("screenshot", "")))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self.app.cards.add(e, self.app.store.root, dlg.result)
        except OSError as err:
            messagebox.showerror("Could not create card", str(err), parent=self)
            return
        self.app.on_cards_changed()  # refreshes this window's Cards column too
        self.app.status_var.set(f"Card created: {dlg.result['target_word']}.  View it in Cards → View cards (Ctrl+K)")


# ---------------------------------------------------------- cards window
class CardsWindow(RecordWindow):
    TITLE = "Cards"
    NOUN = ("card", "cards")
    COLUMNS = (
        ("word", "Target word", 140, False, "w"),
        ("reading", "Reading", 120, False, "w"),
        ("definition", "Definition", 220, True, "w"),
        ("sentence", "Sentence", 300, True, "w"),
        ("media", "Media", 55, False, "center"),
    )
    FOLDER = CARDS_DIR
    WINDOW_ATTR = "cards_window"

    def records(self):
        return self.app.cards.cards

    def row(self, c):
        one_line = lambda s: " ".join(s.split())  # noqa: E731 - definitions may be multi-line
        return (c["target_word"], c["reading"], one_line(c["definition"]),
                c["sentence"], self.media_icons(c))

    def search_text(self, c):
        return " ".join((c["target_word"], c["reading"], c["definition"], c["sentence"]))

    def preview_record(self, c):
        meta = (f"{os.path.basename(c.get('source_file', ''))}  ·  {tr.fmt_time(c.get('start', 0))}"
                f"  ·  created {c.get('created_at', '')[:10]}")
        self.preview.show(c["sentence"], meta,
                          audio=self.app.cards.abs_path(c.get("audio_clip", "")),
                          shot=self.app.cards.abs_path(c.get("screenshot", "")),
                          card=c)

    def remove(self, ids):
        self.app.cards.remove(ids)
        self.app.on_cards_changed()

    def add_actions(self, bar, menu):
        ttk.Button(bar, text="Study cards", command=self.app.show_study).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="✎  Edit card...", command=self.edit_card).pack(side="left")
        menu.add_command(label="✎  Edit card...", command=self.edit_card)
        self.tree.bind("<Return>", lambda e: self.edit_card())
        self.bind("<Control-e>", lambda e: self.edit_card())

    def edit_card(self):
        c = self.focused()
        if not c:
            messagebox.showinfo("No card selected", "Select a card first.", parent=self)
            return
        stop_wav()
        meta = f"{os.path.basename(c.get('source_file', ''))}  ·  {tr.fmt_time(c.get('start', 0))}"
        dlg = CardEditor(self, "Edit card", c["sentence"], meta,
                         audio=self.app.cards.abs_path(c.get("audio_clip", "")),
                         shot=self.app.cards.abs_path(c.get("screenshot", "")),
                         fields=c)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        self.app.cards.update(c["id"], dlg.result)
        self.app.on_cards_changed()  # refreshes this list and an open study window


# ------------------------------------------------------------ study mode
class StudyWindow(tk.Toplevel):
    """Go through the cards one at a time: front (word + sentence) → flip →
    back (reading, definition, screenshot, audio) → next card. A finished
    card goes to the bottom of the stack."""

    def __init__(self, app: "App"):
        super().__init__(app)
        self.app = app
        self.title("Study")
        self.geometry("820x860")
        self.minsize(600, 620)
        self.deck: list[str] = [c["id"] for c in app.cards.cards]  # top of stack = deck[0]
        self.reviewed = 0
        self.flipped = False
        self._photo = None
        self._image = None
        self._audio = ""

        self.progress_var = tk.StringVar()
        ttk.Label(self, textvariable=self.progress_var, foreground="#666",
                  padding=(12, 10, 12, 0)).pack(anchor="w")

        card = ttk.Frame(self, padding=(24, 8, 24, 8))
        card.pack(fill="both", expand=True)
        self.card_frame = card

        # ---- front
        self.word_var = tk.StringVar()
        ttk.Label(card, textvariable=self.word_var, font=("Segoe UI", 34, "bold"),
                  anchor="center").pack(fill="x", pady=(16, 8))
        self.sentence = tk.Text(card, height=3, wrap="word", font=("Segoe UI", 17),
                                relief="flat", borderwidth=0, highlightthickness=0,
                                background=self.cget("background"), cursor="arrow",
                                takefocus=False)
        self.sentence.tag_configure("center", justify="center")
        self.sentence.tag_configure("target", foreground="#c0392b", font=("Segoe UI", 17, "bold"))
        self.sentence.pack(fill="x")

        # ---- back (hidden until flipped)
        self.back = ttk.Frame(card)
        ttk.Separator(self.back).pack(fill="x", pady=12)
        self.reading_var = tk.StringVar()
        self.def_var = tk.StringVar()
        ttk.Label(self.back, textvariable=self.reading_var, font=("Segoe UI", 15),
                  foreground="#555", anchor="center").pack(fill="x")
        self.def_label = ttk.Label(self.back, textvariable=self.def_var, font=("Segoe UI", 14),
                                   justify="center", anchor="center", wraplength=700)
        self.def_label.pack(fill="x", pady=(6, 10))
        holder = tk.Frame(self.back, bg="#1e1e1e", width=640, height=330)
        holder.pack(fill="both", expand=True)
        holder.pack_propagate(False)
        self.image_label = tk.Label(holder, bg="#1e1e1e", fg="#bbbbbb", font=("Segoe UI", 10))
        self.image_label.pack(fill="both", expand=True)
        self.image_label.bind("<Configure>", lambda e: self._render())
        self.replay_btn = ttk.Button(self.back, text="▶  Replay audio", command=self.replay,
                                     takefocus=False)
        self.replay_btn.pack(pady=(8, 0))
        card.bind("<Configure>", lambda e: self.def_label.configure(wraplength=max(e.width - 60, 300)))

        # ---- action button
        bottom = ttk.Frame(self, padding=(12, 4, 12, 14))
        bottom.pack(fill="x")
        # takefocus=False: Space/Enter are handled by the window, so a focused
        # button must not fire a second time (which would skip a card)
        self.action_btn = ttk.Button(bottom, text="Flip", command=self.advance, width=20,
                                     takefocus=False)
        self.action_btn.pack()
        ttk.Label(bottom, text="Space / Enter: flip or next  ·  R: replay audio  ·  Esc: close",
                  foreground="#888").pack(pady=(6, 0))

        self.bind("<space>", lambda e: self.advance())
        self.bind("<Return>", lambda e: self.advance())
        self.bind("<KeyPress-r>", lambda e: self.replay())
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_front()
        self.focus_force()

    # --- deck handling
    def sync(self):
        """Called when cards are added/edited/deleted elsewhere."""
        ids = {c["id"] for c in self.app.cards.cards}
        self.deck = [i for i in self.deck if i in ids]
        self.deck += [c["id"] for c in self.app.cards.cards if c["id"] not in self.deck]
        current = self.current()
        if current is None or not self.flipped:
            self.show_front()
        else:
            self.show_back(autoplay=False)

    def current(self) -> dict | None:
        while self.deck:
            c = self.app.cards.get(self.deck[0])
            if c:
                return c
            self.deck.pop(0)  # deleted while studying
        return None

    def advance(self):
        self.focus_set()  # keep keyboard shortcuts on the window
        if self.current() is None:
            return
        if not self.flipped:
            self.show_back()
        else:
            self.deck.append(self.deck.pop(0))  # move to the bottom of the stack
            self.reviewed += 1
            self.show_front()

    # --- display
    def _update_progress(self):
        n = len(self.deck)
        self.progress_var.set(f"{n} card{'s' if n != 1 else ''} in deck  ·  "
                              f"{self.reviewed} reviewed this session")

    def show_front(self):
        stop_wav()
        self.flipped = False
        self.back.pack_forget()
        c = self.current()
        self._update_progress()
        if c is None:
            self.word_var.set("No cards yet")
            self._set_sentence("Create cards from Saved lines → New card, then come back here.", "")
            self.action_btn.config(text="Flip", state="disabled")
            return
        self.word_var.set(c["target_word"])
        self._set_sentence(c["sentence"], c["target_word"])
        self.action_btn.config(text="Flip", state="normal")

    def show_back(self, autoplay: bool = True):
        c = self.current()
        if c is None:
            return
        self.flipped = True
        self.reading_var.set(c.get("reading", ""))
        self.def_var.set(c.get("definition", ""))
        self._audio = self.app.cards.abs_path(c.get("audio_clip", ""))
        self.replay_btn.config(state="normal" if os.path.isfile(self._audio) else "disabled")
        self._load_image(self.app.cards.abs_path(c.get("screenshot", "")))
        self.back.pack(fill="both", expand=True)
        self.action_btn.config(text="Next card  →", state="normal")
        if autoplay:
            self.replay()

    def _set_sentence(self, text: str, target: str):
        s = self.sentence
        s.config(state="normal")
        s.delete("1.0", "end")
        s.insert("1.0", text, "center")
        if target:  # highlight every occurrence of the target word
            start = "1.0"
            while True:
                pos = s.search(target, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(target)}c"
                s.tag_add("target", pos, end)
                start = end
        s.config(state="disabled")

    def _load_image(self, path: str):
        self._image = self._photo = None
        if path and os.path.isfile(path) and Image is not None:
            try:
                with Image.open(path) as im:
                    self._image = im.copy()
                self._render()
                return
            except OSError:
                pass
        msg = ("Run setup.bat once more to enable screenshots (installs Pillow)."
               if path and Image is None else ("♪  Audio only" if os.path.isfile(self._audio)
                                                else "No screenshot"))
        self.image_label.config(image="", text=msg)

    def _render(self):
        if self._image is None:
            return
        w = max(self.image_label.winfo_width() - 4, 50)
        h = max(self.image_label.winfo_height() - 4, 50)
        img = self._image.copy()
        img.thumbnail((w, h))
        self._photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=self._photo, text="")

    def replay(self):
        if self.flipped:
            play_wav(self._audio)

    def refresh(self):  # used by App._open_window when re-focusing
        self.sync()

    def close(self):
        stop_wav()
        self.app.study_window = None
        self.destroy()


# ------------------------------------------------------------ main window
class App(tk.Tk):
    def __init__(self, initial_file: str | None = None):
        super().__init__()
        self.title("Multilingual Transcriber")
        self.geometry("1280x760")
        self.minsize(900, 520)

        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_flag = threading.Event()
        self.transcript: tr.Transcript | None = None
        self.started_at = 0.0
        self.music_used = False
        self._partial: list[tr.Segment] = []
        self.audio_paths: dict[int, str] = {}   # segment index -> wav path
        self.shot_paths: dict[int, str] = {}    # segment index -> jpg path
        self.media_total = 0
        self.store = SavedStore(SAVED_DIR)
        self.saved_window: SavedLinesWindow | None = None
        self.cards = CardStore(CARDS_DIR)
        self.cards_window: CardsWindow | None = None
        self.study_window: StudyWindow | None = None

        self.file_var = tk.StringVar(value=initial_file or "")
        self.model_var = tk.StringVar(value="small")
        self.lang_var = tk.StringVar(value="Auto-detect")
        self.device_var = tk.StringVar(value="auto")
        self.status_var = tk.StringVar(value="Choose an audio or video file to begin.")
        self.ts_var = tk.BooleanVar(value=True)
        self.media_var = tk.BooleanVar(value=True)
        self.music_var = tk.BooleanVar(value=False)
        self.subs_var = tk.StringVar()
        self.subs_offset_var = tk.StringVar(value="0.0")
        self.used_subs = False
        self.autoplay_var = tk.BooleanVar(value=False)
        self.sel_var = tk.StringVar()
        self.checked: set[int] = set()        # ticked line indices
        self._last_toggled: int | None = None  # anchor for Shift-click ranges

        self._build_menu()
        self._build_ui()
        self.subs_var.trace_add("write", self._on_subs_changed)
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_menu(self):
        bar = tk.Menu(self)
        filem = tk.Menu(bar, tearoff=False)
        filem.add_command(label="Open file...", command=self.browse, accelerator="Ctrl+O")
        filem.add_command(label="Save transcript as...", command=self.save_as)
        filem.add_command(label="Open output folder", command=lambda: open_folder(OUTPUT_DIR))
        filem.add_separator()
        filem.add_command(label="Exit", command=self._on_close)
        bar.add_cascade(label="File", menu=filem)

        savedm = tk.Menu(bar, tearoff=False)
        savedm.add_command(label="View saved lines...", command=self.show_saved, accelerator="Ctrl+L")
        savedm.add_command(label="Save selected lines", command=self.save_selected, accelerator="Ctrl+S")
        savedm.add_command(label="Select all lines", command=self.select_all, accelerator="Ctrl+A")
        savedm.add_separator()
        savedm.add_command(label="Open saved folder", command=lambda: open_folder(SAVED_DIR))
        bar.add_cascade(label="Saved lines", menu=savedm)

        cardsm = tk.Menu(bar, tearoff=False)
        cardsm.add_command(label="View cards...", command=self.show_cards, accelerator="Ctrl+K")
        cardsm.add_command(label="Study cards...", command=self.show_study, accelerator="Ctrl+T")
        cardsm.add_command(label="New card from a saved line...", command=self.show_saved)
        cardsm.add_separator()
        cardsm.add_command(label="Open cards folder", command=lambda: open_folder(CARDS_DIR))
        bar.add_cascade(label="Cards", menu=cardsm)
        self.config(menu=bar)

        self.bind_all("<Control-o>", lambda e: self.browse())
        self.bind_all("<Control-l>", lambda e: self.show_saved())
        self.bind_all("<Control-k>", lambda e: self.show_cards())
        self.bind_all("<Control-t>", lambda e: self.show_study())
        self.bind("<Control-s>", lambda e: self.save_selected())

    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        pad = {"padx": 6, "pady": 4}

        # --- file row
        top = ttk.Frame(self, padding=(10, 10, 10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="File:").pack(side="left")
        ttk.Entry(top, textvariable=self.file_var).pack(side="left", fill="x", expand=True, **pad)
        ttk.Button(top, text="Browse...", command=self.browse).pack(side="left")

        # --- subtitles row (optional): use a subtitle file's lines instead of AI transcription
        subs = ttk.Frame(self, padding=(10, 2, 10, 0))
        subs.pack(fill="x")
        ttk.Label(subs, text="Subtitles (optional):").pack(side="left")
        ttk.Entry(subs, textvariable=self.subs_var).pack(side="left", fill="x", expand=True, **pad)
        ttk.Button(subs, text="Browse...", command=self.browse_subs).pack(side="left")
        ttk.Button(subs, text="Clear", width=6,
                   command=lambda: self.subs_var.set("")).pack(side="left", padx=(6, 0))
        ttk.Label(subs, text="Offset (s):").pack(side="left", padx=(12, 0))
        ttk.Spinbox(subs, textvariable=self.subs_offset_var, from_=-600, to=600,
                    increment=0.1, width=6).pack(side="left", padx=(4, 0))

        # --- options row
        opts = ttk.Frame(self, padding=(10, 4, 10, 4))
        opts.pack(fill="x")
        ttk.Label(opts, text="Model:").pack(side="left")
        ttk.Combobox(opts, textvariable=self.model_var, values=tr.MODEL_SIZES,
                     width=14, state="readonly").pack(side="left", **pad)
        ttk.Label(opts, text="Language:").pack(side="left")
        ttk.Combobox(opts, textvariable=self.lang_var, values=list(tr.LANGUAGES),
                     width=14).pack(side="left", **pad)
        ttk.Label(opts, text="Device:").pack(side="left")
        ttk.Combobox(opts, textvariable=self.device_var, values=["auto", "cpu", "cuda"],
                     width=6, state="readonly").pack(side="left", **pad)
        ttk.Checkbutton(opts, text="Music mode",
                        variable=self.music_var).pack(side="left", padx=(10, 0))
        ttk.Checkbutton(opts, text="Audio clips + screenshots",
                        variable=self.media_var).pack(side="left", padx=(10, 0))

        self.go_btn = ttk.Button(opts, text="Transcribe", command=self.start, width=14)
        self.go_btn.pack(side="left", padx=(16, 4))
        self.stop_btn = ttk.Button(opts, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left")

        # --- progress
        prog = ttk.Frame(self, padding=(10, 0, 10, 4))
        prog.pack(fill="x")
        self.progress = ttk.Progressbar(prog, maximum=1000)
        self.progress.pack(fill="x")
        ttk.Label(prog, textvariable=self.status_var, foreground="#444").pack(anchor="w", pady=(4, 0))

        # --- main area: [table / full text]  |  [preview]
        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=4)

        left = ttk.PanedWindow(main, orient="vertical")
        main.add(left, weight=3)

        table_frame = ttk.Frame(left)
        selbar = ttk.Frame(table_frame, padding=(0, 4, 0, 4))
        selbar.pack(side="bottom", fill="x")
        # The ☐/☑ column chooses lines (for saving); clicking elsewhere on a row
        # just picks which line is shown in the preview.
        self.tree = ttk.Treeview(table_frame, columns=("check", "saved", "text", "start", "end", "media"),
                                 show="headings", selectmode="browse")
        for col, label, w, stretch, anchor in (
            ("check", UNCHECKED, 34, False, "center"),
            ("saved", "★", 30, False, "center"),
            ("text", "Text", 500, True, "w"),
            ("start", "Start", 105, False, "center"),
            ("end", "End", 105, False, "center"),
            ("media", "Media", 60, False, "center"),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, stretch=stretch, anchor=anchor)
        self.tree.heading("check", command=self._toggle_all)
        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.preview.play())
        self.tree.bind("<space>", lambda e: (self.preview.play(), "break")[1])
        self.tree.bind("<Control-a>", lambda e: (self.select_all(), "break")[1])
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Shift-Button-1>", lambda e: self._on_tree_click(e, shift=True))
        self.tree.bind("<Return>", lambda e: self._toggle_focused())
        left.add(table_frame, weight=3)

        # selection bar under the table
        ttk.Button(selbar, text="Select all", command=self.select_all).pack(side="left")
        ttk.Button(selbar, text="Select none", command=self.select_none).pack(side="left", padx=6)
        self.save_sel_btn = ttk.Button(selbar, text="★  Save selected lines",
                                       command=self.save_selected, state="disabled")
        self.save_sel_btn.pack(side="left", padx=(6, 0))
        ttk.Button(selbar, text="View saved lines...", command=self.show_saved).pack(side="left", padx=6)
        ttk.Label(selbar, textvariable=self.sel_var, foreground="#666").pack(side="left", padx=6)
        ttk.Label(selbar, text="Tick boxes to choose lines · Shift-click a box for a range · Enter ticks",
                  foreground="#888").pack(side="right")

        text_frame = ttk.Frame(left)
        hdr = ttk.Frame(text_frame)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Full transcript").pack(side="left")
        ttk.Checkbutton(hdr, text="Show timestamps", variable=self.ts_var,
                        command=self._refresh_text).pack(side="left", padx=12)
        self.text = tk.Text(text_frame, wrap="word", font=("Segoe UI", 11), height=6)
        tsb = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=tsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        self.text.tag_configure("chk", background="#dcebff")
        self.text.tag_configure("hl", background="#fff2a8")
        left.add(text_frame, weight=1)

        # --- preview panel
        self.preview = PreviewPanel(main, self.autoplay_var)
        main.add(self.preview, weight=2)

        # --- bottom buttons
        bottom = ttk.Frame(self, padding=(10, 4, 10, 10))
        bottom.pack(fill="x")
        self.save_btn = ttk.Button(bottom, text="Save transcript as...", command=self.save_as,
                                   state="disabled")
        self.save_btn.pack(side="left")
        self.copy_btn = ttk.Button(bottom, text="Copy text", command=self.copy_text, state="disabled")
        self.copy_btn.pack(side="left", padx=6)
        ttk.Button(bottom, text="Open output folder",
                   command=lambda: open_folder(OUTPUT_DIR)).pack(side="left")
        self.info_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.info_var, foreground="#666").pack(side="right")

    # -------------------------------------------------------------- actions
    def browse(self):
        path = filedialog.askopenfilename(title="Choose audio or video", filetypes=MEDIA_TYPES)
        if path:
            self.file_var.set(path)

    def browse_subs(self):
        start_dir = os.path.dirname(self.file_var.get().strip().strip('"')) or None
        path = filedialog.askopenfilename(title="Choose a subtitle file",
                                          filetypes=subtitles.SUB_TYPES, initialdir=start_dir)
        if path:
            self.subs_var.set(path)

    def _on_subs_changed(self, *_):
        """The main button says what will happen: AI transcription or subtitles."""
        if not (self.worker and self.worker.is_alive()):
            self.go_btn.config(text="Use subtitles" if self.subs_var.get().strip() else "Transcribe")

    def _language_code(self) -> str | None:
        val = self.lang_var.get().strip()
        if val in tr.LANGUAGES:
            return tr.LANGUAGES[val]
        return val.lower() or None  # allow typing a code like "ka" or "sw"

    def start(self):
        path = self.file_var.get().strip().strip('"')
        if not path or not os.path.isfile(path):
            messagebox.showwarning("No file", "Please choose an existing audio or video file.")
            return
        subs_path = self.subs_var.get().strip().strip('"')
        if subs_path and not os.path.isfile(subs_path):
            messagebox.showwarning("Subtitle file not found",
                                   "The subtitle file doesn't exist. Choose another, or click Clear "
                                   "to transcribe with AI instead.")
            return
        try:
            subs_offset = float(self.subs_offset_var.get().strip() or 0) if subs_path else 0.0
        except ValueError:
            messagebox.showwarning("Offset", "The subtitle offset must be a number of seconds, e.g. 1.5 or -0.8.")
            return
        stop_wav()
        self._clear_results()
        self.stop_flag.clear()
        self.go_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.save_btn.config(state="disabled")
        self.copy_btn.config(state="disabled")
        self.started_at = time.time()

        self.used_subs = bool(subs_path)
        self.music_used = self.music_var.get() and not subs_path
        args = (path, self.model_var.get(), self._language_code(),
                self.device_var.get(), self.media_var.get(), self.music_used,
                subs_path, subs_offset)
        self.worker = threading.Thread(target=self._run, args=args, daemon=True)
        self.worker.start()

    def stop(self):
        self.stop_flag.set()
        self.status_var.set("Stopping...")

    def _run(self, path, model, lang, device, want_media, music, subs_path="", subs_offset=0.0):
        """Runs in a background thread; talks to the UI via self.events."""
        put = self.events.put
        try:
            if subs_path:  # lines come from the subtitle file, no AI transcription
                result = subtitles.load(
                    path, subs_path, language=lang, offset=subs_offset,
                    on_segment=lambda seg, p: put(("segment", seg, p)),
                    on_status=lambda m: put(("status", m)),
                )
            else:
                result = tr.transcribe(
                    path, model_size=model, language=lang, device=device,
                    on_segment=lambda seg, p: put(("segment", seg, p)),
                    on_status=lambda m: put(("status", m)),
                    should_stop=self.stop_flag.is_set,
                    music=music,
                )
            base = media.safe_name(os.path.splitext(os.path.basename(path))[0])
            out_dir = os.path.join(OUTPUT_DIR, base)
            os.makedirs(out_dir, exist_ok=True)

            media_error = None
            if want_media and result.segments and not self.stop_flag.is_set():
                put(("media_start", len(result.segments)))
                try:
                    media.build_media(
                        result, os.path.join(out_dir, "media"),
                        on_item=lambda kind, i, p: put(("media", kind, i, p)),
                        on_status=lambda m: put(("status", m)),
                        should_stop=self.stop_flag.is_set,
                    )
                except Exception as e:  # noqa: BLE001 - keep the transcript anyway
                    media_error = e

            for ext in (".json", ".srt", ".txt"):
                result.save(os.path.join(out_dir, base + ext))
            put(("done", result, out_dir, media_error))
        except Exception as e:  # noqa: BLE001
            put(("error", e))

    def _poll_events(self):
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "status":
                    self.status_var.set(ev[1])
                elif kind == "segment":
                    seg, p = ev[1], ev[2]
                    self.tree.insert("", "end", iid=str(seg.index),
                                     values=(UNCHECKED, "", seg.text, tr.fmt_time(seg.start),
                                             tr.fmt_time(seg.end), ""))
                    if not self.tree.selection():
                        self.tree.yview_moveto(1.0)
                    self.progress["value"] = p * 1000
                    self._append_text(seg)
                elif kind == "media_start":
                    self.media_total = ev[1]
                    self.progress["value"] = 0
                elif kind == "media":
                    self._on_media(ev[1], ev[2], ev[3])
                elif kind == "done":
                    self._finish(ev[1], ev[2], ev[3])
                elif kind == "error":
                    self._fail(ev[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _on_media(self, kind: str, index: int, path: str):
        (self.audio_paths if kind == "audio" else self.shot_paths)[index] = path
        iid = str(index)
        if self.tree.exists(iid):
            icons = ("♪" if index in self.audio_paths else "") + \
                    (" ▣" if index in self.shot_paths else "")
            self.tree.set(iid, "media", icons.strip())
        # audio pass, then (for video) screenshot pass: each runs 0..100%
        done = len(self.audio_paths if kind == "audio" else self.shot_paths)
        self.progress["value"] = done / max(self.media_total, 1) * 1000
        if self._focused_index() == index:
            self._show_preview(index)

    def _finish(self, result: tr.Transcript, out_dir: str, media_error):
        self.transcript = result
        if not self.stop_flag.is_set():
            self.progress["value"] = 1000
        elapsed = time.time() - self.started_at
        rel = os.path.relpath(out_dir, APP_DIR)
        n_clips, n_shots = len(self.audio_paths), len(self.shot_paths)
        extra = f", {n_clips} clips" + (f", {n_shots} screenshots" if n_shots else "") if n_clips else ""
        self.status_var.set(
            f"Done: {len(result.segments)} lines{extra} in {elapsed:.0f}s. Saved to {rel}\\  "
            f"Select lines and click ★ Save selected lines to keep them."
        )
        if self.used_subs:
            self.info_var.set(
                f"Lines from {result.model.split(': ', 1)[-1]}  |  Length: {tr.fmt_time(result.duration)}"
                + (f"  |  Language: {result.language}" if result.language else "")
            )
        else:
            self.info_var.set(
                f"Language: {result.language} ({result.language_probability:.0%})  |  "
                f"Length: {tr.fmt_time(result.duration)}  |  Model: {result.model}"
                + ("  |  Music mode" if self.music_used else "")
            )
        self._reset_buttons(done=True)
        self._mark_saved()
        self._update_selection_ui()
        if media_error:
            messagebox.showwarning(
                "Media extraction problem",
                f"The transcript was saved, but creating clips/screenshots failed:\n\n{media_error}",
            )

    def _fail(self, err: Exception):
        self._reset_buttons(done=False)
        msg = str(err) or err.__class__.__name__
        if isinstance(err, ModuleNotFoundError):
            msg = f"{msg}\n\nRun setup.bat first to install the required packages."
        self.status_var.set(f"Error: {msg.splitlines()[0]}")
        messagebox.showerror("Transcription failed", msg)

    def _reset_buttons(self, done: bool):
        self.go_btn.config(state="normal",
                           text="Use subtitles" if self.subs_var.get().strip() else "Transcribe")
        self.stop_btn.config(state="disabled")
        state = "normal" if done and self.transcript and self.transcript.segments else "disabled"
        self.save_btn.config(state=state)
        self.copy_btn.config(state=state)

    # ------------------------------------------------------------- results
    def _clear_results(self):
        self.transcript = None
        self.tree.delete(*self.tree.get_children())
        self.text.delete("1.0", "end")
        self.progress["value"] = 0
        self.info_var.set("")
        self._partial = []
        self.audio_paths.clear()
        self.checked.clear()
        self._last_toggled = None
        self.tree.heading("check", text=UNCHECKED)
        self.shot_paths.clear()
        self.media_total = 0
        self.preview.clear()
        self._update_selection_ui()

    def _append_text(self, seg: tr.Segment):
        self._partial.append(seg)
        line = (f"[{tr.fmt_time(seg.start)}]  {seg.text}\n" if self.ts_var.get()
                else f"{seg.text}\n")
        self.text.insert("end", line)
        if not self.tree.selection():
            self.text.see("end")

    def _refresh_text(self):
        segs = self.transcript.segments if self.transcript else self._partial
        self.text.delete("1.0", "end")
        for s in segs:
            self.text.insert("end", f"[{tr.fmt_time(s.start)}]  {s.text}\n"
                             if self.ts_var.get() else f"{s.text}\n")
        self._highlight_selection()

    def _segments(self) -> list[tr.Segment]:
        return self.transcript.segments if self.transcript else self._partial

    def _segment(self, index: int) -> tr.Segment | None:
        segs = self._segments()
        return segs[index] if 0 <= index < len(segs) else None

    def _focused_index(self) -> int | None:
        iid = self.tree.focus() or (self.tree.selection() or [""])[0]
        return int(iid) if iid else None

    def _on_select(self, event=None):
        self._highlight_selection()
        self._update_selection_ui()
        index = self._focused_index()
        if index is None:
            return
        self.text.see(f"{index + 1}.0")
        self._show_preview(index)
        if self.autoplay_var.get() and event is not None:
            self.preview.play()

    def _highlight_selection(self):
        """Full transcript: ticked lines in light blue, the previewed line in yellow."""
        self.text.tag_remove("hl", "1.0", "end")
        self.text.tag_remove("chk", "1.0", "end")
        for index in self.checked:
            self.text.tag_add("chk", f"{index + 1}.0", f"{index + 1}.end")
        index = self._focused_index()
        if index is not None:
            self.text.tag_add("hl", f"{index + 1}.0", f"{index + 1}.end")

    def _show_preview(self, index: int):
        seg = self._segment(index)
        if seg is None:
            return
        if self.media_total and index not in self.shot_paths and self.worker and self.worker.is_alive():
            placeholder = "Screenshot not ready yet..."
        else:
            placeholder = ""
        self.preview.show(
            seg.text, f"Line {index + 1}   {tr.fmt_time(seg.start)} – {tr.fmt_time(seg.end)}",
            audio=self.audio_paths.get(index, ""), shot=self.shot_paths.get(index, ""),
            placeholder=placeholder,
        )

    # --------------------------------------------------------- checkboxes
    def _set_checked(self, indices, value: bool):
        for index in indices:
            iid = str(index)
            if not self.tree.exists(iid):
                continue
            (self.checked.add if value else self.checked.discard)(index)
            self.tree.set(iid, "check", CHECKED if value else UNCHECKED)
        all_rows = self.tree.get_children()
        self.tree.heading("check", text=CHECKED if all_rows and len(self.checked) == len(all_rows)
                          else UNCHECKED)
        self._highlight_selection()
        self._update_selection_ui()

    def _on_tree_click(self, event, shift: bool = False):
        """Clicks in the ☐ column tick/untick; elsewhere, normal row selection."""
        if self.tree.identify_region(event.x, event.y) != "cell" or \
                self.tree.identify_column(event.x) != "#1":
            return None
        iid = self.tree.identify_row(event.y)
        if not iid:
            return None
        index = int(iid)
        new_value = index not in self.checked
        if shift and self._last_toggled is not None:
            lo, hi = sorted((self._last_toggled, index))
            self._set_checked(range(lo, hi + 1), new_value)
        else:
            self._set_checked([index], new_value)
        self._last_toggled = index
        return "break"  # don't move the preview when only ticking a box

    def _toggle_focused(self):
        index = self._focused_index()
        if index is not None:
            self._set_checked([index], index not in self.checked)
            self._last_toggled = index
        return "break"

    def _toggle_all(self):
        rows = [int(i) for i in self.tree.get_children()]
        self._set_checked(rows, len(self.checked) < len(rows))

    # --------------------------------------------------------- saving lines
    def select_all(self):
        self._set_checked([int(i) for i in self.tree.get_children()], True)

    def select_none(self):
        self._set_checked(list(self.checked), False)

    def _update_selection_ui(self):
        n = len(self.checked)
        ready = self.transcript is not None and not (self.worker and self.worker.is_alive())
        self.save_sel_btn.config(state="normal" if ready and n else "disabled")
        self.sel_var.set(f"{n} selected" if n else "")

    def save_selected(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Please wait", "Lines can be saved once transcription and "
                                "clip/screenshot creation have finished.")
            return
        if not self.transcript:
            return
        ids = sorted(self.checked)
        if not ids:
            messagebox.showinfo("No lines selected", "Tick the boxes of one or more lines first "
                                "(or click Select all).")
            return
        segs = [self.transcript.segments[i] for i in ids]
        try:
            added, skipped = self.store.add(self.transcript, segs, self.audio_paths, self.shot_paths)
        except OSError as e:
            messagebox.showerror("Could not save lines", str(e))
            return
        msg = f"Saved {added} line{'s' if added != 1 else ''}"
        if skipped:
            msg += f" ({skipped} already saved)"
        self.status_var.set(msg + ".  Saved lines → View saved lines... (Ctrl+L)")
        self._mark_saved()
        if self.saved_window:
            self.saved_window.refresh()

    def _mark_saved(self):
        """Show ★ next to lines of this transcript that are in the saved library."""
        if not self.transcript:
            return
        keys = {SavedStore._key(e["source_file"], e["start"], e["end"], e["text"])
                for e in self.store.entries}
        src = self.transcript.source_file
        for s in self.transcript.segments:
            iid = str(s.index)
            if self.tree.exists(iid):
                self.tree.set(iid, "saved",
                              "★" if SavedStore._key(src, s.start, s.end, s.text) in keys else "")

    def _open_window(self, attr: str, cls):
        stop_wav()
        win = getattr(self, attr)
        if win and win.winfo_exists():
            win.refresh()
            win.deiconify()
            win.lift()
            win.focus_force()
        else:
            setattr(self, attr, cls(self))

    def show_saved(self):
        self._open_window("saved_window", SavedLinesWindow)

    def show_cards(self):
        self._open_window("cards_window", CardsWindow)

    def show_study(self):
        self._open_window("study_window", StudyWindow)

    def on_saved_changed(self):
        self._mark_saved()

    def on_cards_changed(self):
        """Keep both list windows in step (card counts / card list)."""
        for win in (self.saved_window, self.cards_window, self.study_window):
            if win and win.winfo_exists():
                win.refresh()

    # ------------------------------------------------------------- misc
    def _on_close(self):
        stop_wav()
        self.destroy()

    def save_as(self):
        if not self.transcript:
            return
        base = os.path.splitext(os.path.basename(self.transcript.source_file))[0]
        path = filedialog.asksaveasfilename(
            initialdir=OUTPUT_DIR, initialfile=base + ".srt", defaultextension=".srt",
            filetypes=[("SubRip subtitles", "*.srt"), ("WebVTT subtitles", "*.vtt"),
                       ("JSON (with word timings)", "*.json"), ("Plain text", "*.txt")],
        )
        if path:
            self.transcript.save(path)
            self.status_var.set(f"Saved {path}")

    def copy_text(self):
        if self.transcript:
            self.clipboard_clear()
            self.clipboard_append(self.transcript.to_text(timestamps=self.ts_var.get()))
            self.status_var.set("Transcript copied to clipboard.")


if __name__ == "__main__":
    App(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
