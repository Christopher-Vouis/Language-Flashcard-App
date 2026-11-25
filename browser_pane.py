"""
A web browser inside the app (Create Cards tab, on the right), for looking words up
while making cards.

It uses tkwry, which puts Microsoft Edge WebView2 inside a Tk frame. tkwry isn't in
requirements.txt (it's new, and the rest of the app must never fail to install because
of it): the first time the pane is shown and tkwry is missing, the pane offers to
install it. WebView2 itself comes with Windows 10/11; if it's missing, the pane says
where to get it. Whatever goes wrong, "Open in browser" still opens the page in the
normal web browser.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk
from urllib.parse import quote

import theme

# (name, address with {q} for the search words)
SITES = (
    ("Jisho", "https://jisho.org/search/{q}"),
    ("Wiktionary", "https://en.wiktionary.org/wiki/Special:Search?search={q}&go=Go"),
    ("Google Translate", "https://translate.google.com/?sl=auto&tl=en&text={q}&op=translate"),
    ("Google Images", "https://www.google.com/search?tbm=isch&q={q}"),
    ("Forvo", "https://forvo.com/search/{q}/"),
)
SEARCH = "https://www.google.com/search?q={q}"     # typed words that aren't an address
WEBVIEW2_URL = "https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def site_url(site: str, words: str) -> str:
    template = dict(SITES).get(site, SITES[0][1])
    return template.format(q=quote(words.strip()))


def to_url(text: str) -> str:
    """What was typed in the address box -> an address (a search if it isn't one)."""
    text = text.strip()
    if not text:
        return ""
    if "://" in text or text.startswith("about:"):
        return text
    if " " not in text and "." in text:
        return "https://" + text
    return SEARCH.format(q=quote(text))


def have_tkwry() -> bool:
    importlib.invalidate_caches()
    return importlib.util.find_spec("tkwry") is not None


def pip_python() -> str:
    """The Python to run pip with (python.exe next to pythonw.exe, which has no console)."""
    exe = sys.executable
    folder, name = os.path.split(exe)
    if name.lower() == "pythonw.exe" and os.path.isfile(os.path.join(folder, "python.exe")):
        return os.path.join(folder, "python.exe")
    return exe


class BrowserPane(ttk.Frame):
    """Toolbar (back / forward / reload / address / look up) + the web page."""

    def __init__(self, parent, data_dir: str, settings=None, start_url: str = ""):
        super().__init__(parent, padding=(8, 0, 0, 0))
        self.data_dir = data_dir
        self.settings = settings
        self.web = None
        self._url = start_url or "https://jisho.org/"   # where the page is (or would be)
        self._poll_job = None
        self._started = False
        self._q: queue.Queue = queue.Queue()

        nav = ttk.Frame(self)
        nav.pack(fill="x", pady=(0, 4))
        self.back_btn = ttk.Button(nav, text="◀", width=3, command=self.back)
        self.back_btn.pack(side="left")
        self.fwd_btn = ttk.Button(nav, text="▶", width=3, command=self.forward)
        self.fwd_btn.pack(side="left", padx=(2, 0))
        ttk.Button(nav, text="⟳", width=3, command=self.reload).pack(side="left", padx=(2, 6))
        ttk.Button(nav, text="↗", width=3, command=self.open_outside).pack(side="right")
        self.address = tk.StringVar(value=self._url)
        self.address_entry = ttk.Entry(nav, textvariable=self.address)
        self.address_entry.pack(side="left", fill="x", expand=True)
        self.address_entry.bind("<Return>", lambda e: self.go(to_url(self.address.get())))

        find = ttk.Frame(self)
        find.pack(fill="x", pady=(0, 6))
        ttk.Label(find, text="Look up in").pack(side="left")
        names = [n for n, _ in SITES]
        site = settings.get("browser_site") if settings else ""
        self.site = tk.StringVar(value=site if site in names else names[0])
        box = ttk.Combobox(find, textvariable=self.site, values=names, state="readonly", width=15)
        box.pack(side="left", padx=6)
        box.bind("<<ComboboxSelected>>", lambda e: self._site_chosen())
        self.words = tk.StringVar()
        words = ttk.Entry(find, textvariable=self.words)
        words.pack(side="left", fill="x", expand=True)
        words.bind("<Return>", lambda e: self.lookup(self.words.get()))
        ttk.Button(find, text="🔍", width=3,
                   command=lambda: self.lookup(self.words.get())).pack(side="left", padx=(4, 0))

        self.title_var = tk.StringVar()
        ttk.Label(self, textvariable=self.title_var, foreground=theme.SUBTLE).pack(
            side="bottom", anchor="w", pady=(2, 0))
        # the page goes in here (a plain Tk frame: WebView2 draws into its window)
        self.host = tk.Frame(self, background=theme.IMAGE_BG, highlightthickness=0)
        self.host.pack(fill="both", expand=True)
        self.note = None
        self.host.bind("<Map>", lambda e: self.start())     # nothing is loaded until it's shown
        self._update_buttons(False, False)

    # ------------------------------------------------------------------ starting up
    def start(self):
        if self._started:
            return
        self._started = True
        if have_tkwry():
            self._create()
        else:
            self._show_note(
                "The built-in browser needs one more package (tkwry, about 2 MB). It uses Microsoft "
                "Edge WebView2, which comes with Windows 10 and 11.",
                [("Install browser support", self._install)])

    def _create(self):
        self._clear_note()
        try:
            from tkwry import WebView
        except Exception as err:  # noqa: BLE001 - a broken install mustn't stop the app
            self._show_note(f"The browser package didn't load: {err}",
                            [("Install again", self._install)])
            return
        os.makedirs(self.data_dir, exist_ok=True)
        try:
            self.web = WebView(self.host, url=self._url, data_directory=self.data_dir, focused=False,
                               on_title_changed=self._title_changed, on_new_window=self._new_window,
                               on_creation_failed=self._failed)
        except Exception as err:  # noqa: BLE001
            self.web = None
            self._failed(err)
            return
        self._poll()

    def _failed(self, err):
        self.web = None
        text = str(err)
        buttons = [("Try again", self._retry)]
        if "WebView2" in text:
            text = ("Microsoft Edge WebView2 isn't installed, and the built-in browser needs it. "
                    "Get the “Evergreen Bootstrapper” from Microsoft's WebView2 page, "
                    "install it, then click Try again.")
            buttons.insert(0, ("Open the WebView2 page", lambda: webbrowser.open(WEBVIEW2_URL)))
        self._show_note(f"The browser couldn't start.\n\n{text}", buttons)

    def _retry(self):
        if self.web is not None:
            try:
                self.web.destroy()
            except Exception:  # noqa: BLE001
                pass
            self.web = None
        self._create()

    # ------------------------------------------------------------------ install tkwry
    def _install(self):
        if sys.version_info < (3, 10):
            self._show_note("The built-in browser needs Python 3.10 or newer; this is Python "
                            f"{sys.version_info[0]}.{sys.version_info[1]}.", [])
            return
        self._show_note("Installing browser support...", [])

        def work():
            try:
                p = subprocess.run([pip_python(), "-m", "pip", "install", "tkwry"], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=600,
                                   creationflags=NO_WINDOW,
                                   env=dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK="1"))
                self._q.put((p.returncode == 0, (p.stdout + p.stderr)[-600:]))
            except (OSError, subprocess.SubprocessError) as err:
                self._q.put((False, str(err)))

        threading.Thread(target=work, daemon=True).start()
        self._wait_install()

    def _wait_install(self):
        try:
            ok, log = self._q.get_nowait()
        except queue.Empty:
            self.after(300, self._wait_install)
            return
        if ok and have_tkwry():
            self._create()
        else:
            self._show_note("Installing browser support didn't work. Check the internet connection "
                            "and try again.\n\n" + log.strip(), [("Try again", self._install)])

    # ------------------------------------------------------------------ the message shown instead of a page
    def _show_note(self, text: str, buttons):
        self._clear_note()
        self.note = tk.Frame(self.host, background=theme.IMAGE_BG)
        self.note.place(relx=0.5, rely=0.4, anchor="center", relwidth=0.9)
        tk.Label(self.note, text=text, background=theme.IMAGE_BG, foreground=theme.MUTED,
                 font=("Segoe UI", 10), wraplength=320, justify="left").pack(anchor="w")
        row = tk.Frame(self.note, background=theme.IMAGE_BG)
        row.pack(anchor="w", pady=(10, 0))
        for label, command in buttons:
            ttk.Button(row, text=label, command=command).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Open in browser", command=self.open_outside).pack(side="left")
        self.note.bind("<Configure>", lambda e: [w.configure(wraplength=max(e.width - 10, 150))
                                                 for w in self.note.winfo_children()
                                                 if isinstance(w, tk.Label)])

    def _clear_note(self):
        if self.note is not None:
            self.note.destroy()
            self.note = None

    # ------------------------------------------------------------------ browsing
    def go(self, url: str):
        if not url:
            return
        self._url = url
        self.address.set(url)
        if self.web is not None:
            try:
                self.web.load_url(url)
            except Exception:  # noqa: BLE001 - not ready yet / failed: the note says why
                pass

    def lookup(self, words: str, site: str = ""):
        """Search for the words on the chosen site (e.g. a dictionary)."""
        words = words.strip()
        if not words:
            return
        if site:
            self.site.set(site)
        self.words.set(words)
        self.go(site_url(self.site.get(), words))

    def _site_chosen(self):
        if self.settings:
            self.settings.set("browser_site", self.site.get())
        if self.words.get().strip():
            self.lookup(self.words.get())

    def back(self):
        if self.web is not None:
            try:
                self.web.go_back()
            except Exception:  # noqa: BLE001
                pass

    def forward(self):
        if self.web is not None:
            try:
                self.web.go_forward()
            except Exception:  # noqa: BLE001
                pass

    def reload(self):
        if self.web is not None:
            try:
                self.web.reload()
            except Exception:  # noqa: BLE001
                pass
        elif self._started and self.note is not None and have_tkwry():
            self._retry()

    def open_outside(self):
        """Open the current page in the normal web browser."""
        webbrowser.open(self._url)

    def _new_window(self, event):
        """Links that would open a new window open here instead."""
        from tkwry import NewWindowResponse
        url = getattr(event, "url", "")
        if url:
            self.after(0, lambda: self.go(url))
        return NewWindowResponse.Deny

    def _title_changed(self, title: str):
        self.title_var.set(title or "")

    def _update_buttons(self, back: bool, fwd: bool):
        self.back_btn.state(["!disabled"] if back else ["disabled"])
        self.fwd_btn.state(["!disabled"] if fwd else ["disabled"])

    def _poll(self):
        """Keep back/forward and the address box in step with the page."""
        self._poll_job = None
        web = self.web
        if web is None or not self.winfo_exists():
            return
        try:
            if getattr(web, "creation_failed", False):
                return
            s = web.get_state()
            self._update_buttons(bool(s.can_go_back), bool(s.can_go_forward))
            if s.url and s.url != self._url:
                self._url = s.url
                if self.focus_get() is not self.address_entry:
                    self.address.set(s.url)
        except Exception:  # noqa: BLE001 - not ready yet
            pass
        self._poll_job = self.after(400, self._poll)

    def destroy(self):
        if self._poll_job:
            self.after_cancel(self._poll_job)
        super().destroy()
