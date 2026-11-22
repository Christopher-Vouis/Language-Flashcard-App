"""
First-run setup, done by the app itself (no setup.bat needed).

app.py calls ensure_ready() before anything else. It only uses Python's own
modules, so it works on any Python:

  - the packages are already importable (e.g. started from .venv, or from a
    Python where they're installed)        -> nothing to do, the app starts
  - .venv exists and has them               -> restart the app with .venv's Python
  - otherwise                               -> a small window: find a compatible
    Python, create .venv, install requirements.txt into it, then restart the
    app with .venv's Python

faster-whisper needs 64-bit (x86-64) Python 3.9 - 3.14.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import queue
import shutil
import struct
import subprocess
import sys
import threading

APP_DIR = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(APP_DIR, ".venv")
REQUIREMENTS = os.path.join(APP_DIR, "requirements.txt")
REQUIRED = (("faster_whisper", "faster-whisper"), ("av", "PyAV"), ("PIL", "Pillow"))
DONE_FLAG = "LANGUAGE_FLASHCARDS_SET_UP"      # set on the restart, so a failed setup can't loop
WINDOWS = os.name == "nt"
NO_WINDOW = 0x08000000 if WINDOWS else 0      # CREATE_NO_WINDOW: no console windows popping up
CHECK = ("import platform, struct, sys; ok = (3, 9) <= sys.version_info[:2] <= (3, 14) and "
         "struct.calcsize('P') == 8 and platform.machine().upper() in ('AMD64', 'X86_64'); "
         "sys.exit(0 if ok else 1)")


def compatible() -> bool:
    """Can this Python run faster-whisper?"""
    return ((3, 9) <= sys.version_info[:2] <= (3, 14) and struct.calcsize("P") == 8
            and platform.machine().upper() in ("AMD64", "X86_64"))


def missing(required=None) -> list[str]:
    return [name for module, name in (required or REQUIRED) if importlib.util.find_spec(module) is None]


def venv_python(gui: bool = False) -> str:
    if WINDOWS:
        return os.path.join(VENV, "Scripts", "pythonw.exe" if gui else "python.exe")
    return os.path.join(VENV, "bin", "python")


def in_venv() -> bool:
    return os.path.normcase(os.path.abspath(sys.prefix)) == os.path.normcase(VENV)


def _run_quiet(cmd: list[str], timeout: float = 60) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def venv_ready(required=None) -> bool:
    required = required or REQUIRED
    py = venv_python()
    if not os.path.isfile(py):
        return False
    return _run_quiet([py, "-c", CHECK]) and _run_quiet(
        [py, "-c", "; ".join(f"import {m}" for m, _ in required)], timeout=120)


def restart_in_venv() -> None:
    """Start the app again with .venv's Python, and end this process."""
    env = dict(os.environ, **{DONE_FLAG: "1"})
    py = venv_python(gui=True)
    if not os.path.isfile(py):
        py = venv_python()
    subprocess.Popen([py, os.path.join(APP_DIR, "app.py"), *sys.argv[1:]], cwd=APP_DIR, env=env,
                     creationflags=NO_WINDOW)
    sys.exit(0)


def find_base_python() -> list[str] | None:
    """A compatible Python to build .venv with: this one if it can, else one
    found with the py launcher (Windows) or on PATH."""
    if compatible() and not in_venv():
        return [getattr(sys, "_base_executable", "") or sys.executable]
    if compatible():                               # a venv's Python: build from the Python it came from
        base = getattr(sys, "_base_executable", "")
        if base and os.path.isfile(base):
            return [base]
    candidates = []
    if WINDOWS:
        candidates += [["py", f"-3.{v}"] for v in (13, 12, 14, 11, 10)]
        candidates += [["python"]]
    else:
        candidates += [[f"python3.{v}"] for v in (13, 12, 14, 11, 10)] + [["python3"]]
    for cmd in candidates:
        if _run_quiet(cmd + ["-c", CHECK], timeout=20):
            return cmd
    return None


def ensure_ready() -> None:
    """Make sure the app can start; set it up first if needed (see the top of this file)."""
    if not missing():
        return
    if not in_venv() and venv_ready():
        restart_in_venv()
    SetupWindow().run()


class SetupWindow:
    """The one-time setup, with its progress shown in a small window."""

    def __init__(self, required=None, requirements=None):
        import tkinter as tk
        from tkinter import ttk
        self.required, self.requirements = required or REQUIRED, requirements or REQUIREMENTS
        self.q: queue.Queue = queue.Queue()
        self.ok = False
        self.root = root = tk.Tk()
        root.title("Language Flashcards – first-time setup")
        try:
            root.iconbitmap(default=os.path.join(APP_DIR, "assets", "app.ico"))
        except tk.TclError:
            pass
        root.configure(background="#1e1f22")
        root.geometry("680x420")
        root.minsize(480, 300)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background="#1e1f22", foreground="#e6e6e6")
        style.configure("TButton", background="#3a3d43", padding=(10, 4))
        style.configure("Horizontal.TProgressbar", background="#4a7bd9", troughcolor="#2b2d31",
                        bordercolor="#2b2d31", lightcolor="#4a7bd9", darkcolor="#4a7bd9")
        body = ttk.Frame(root, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Getting the app ready", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(body, wraplength=640, justify="left", text=(
            "This happens once: the app is installing the speech engine and the other packages it "
            "needs into a .venv folder next to it. It downloads a few hundred MB, so it can take "
            "several minutes. The app opens by itself when it's done.")).pack(anchor="w", pady=(6, 10))
        self.status = tk.StringVar(value="Starting...")
        ttk.Label(body, textvariable=self.status).pack(anchor="w")
        self.bar = ttk.Progressbar(body, mode="indeterminate")
        self.bar.pack(fill="x", pady=(6, 10))
        self.bar.start(12)
        self.log = tk.Text(body, height=10, background="#141517", foreground="#a9adb3",
                           relief="flat", font=("Consolas", 9), wrap="word")
        self.log.pack(fill="both", expand=True)
        self.buttons = ttk.Frame(body)
        self.buttons.pack(fill="x", pady=(10, 0))
        root.protocol("WM_DELETE_WINDOW", self._close)

    # ---------------------------------------------------------------- the work (a thread)
    def _say(self, kind: str, text: str):
        self.q.put((kind, text))

    def _stream(self, cmd: list[str]) -> bool:
        self._say("log", "> " + " ".join(cmd) + "\n")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PIP_DISABLE_PIP_VERSION_CHECK="1")
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=APP_DIR, env=env,
                                 text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        except OSError as e:
            self._say("log", f"{e}\n")
            return False
        for line in p.stdout:
            self._say("log", line)
        return p.wait() == 0

    def _work(self):
        try:
            py = venv_python()
            if os.path.isfile(py) and not _run_quiet([py, "-c", CHECK]):
                if in_venv():   # can't delete the Python that's running: rebuild from a compatible one
                    self._say("fail", "The .venv folder was made with a Python the speech engine can't "
                                      "use. Close this, delete the .venv folder, and start the app again.")
                    return
                self._say("status", "Removing an old .venv made with an unsuitable Python...")
                shutil.rmtree(VENV, ignore_errors=True)
            if not os.path.isfile(py):
                self._say("status", "Looking for a suitable Python...")
                base = find_base_python()
                if base is None:
                    self._say("fail", "No suitable Python found. The speech engine needs 64-bit Python "
                                      "3.10 - 3.14. Install Python 3.13 \"Windows installer (64-bit)\" from "
                                      "python.org/downloads/windows (you can keep your other Python), "
                                      "then start the app again.")
                    return
                self._say("status", "Creating the .venv folder...")
                if not self._stream(base + ["-m", "venv", VENV]):
                    self._say("fail", "Couldn't create the .venv folder (see the messages above).")
                    return
            self._say("status", "Installing packages (this is the long part)...")
            self._stream([py, "-m", "pip", "install", "--upgrade", "pip"])     # nice to have; not required
            if not self._stream([py, "-m", "pip", "install", "-r", self.requirements]):
                self._say("fail", "Installing the packages failed (see the messages above). Check the "
                                  "internet connection and start the app again; it carries on from here.")
                return
            self._say("done", "")
        except Exception as e:  # noqa: BLE001 - show anything unexpected in the window
            self._say("fail", f"Setup stopped: {e}")

    # ---------------------------------------------------------------- the window
    def _poll(self):
        try:
            while True:
                kind, text = self.q.get_nowait()
                if kind == "log":
                    self.log.insert("end", text)
                    self.log.see("end")
                elif kind == "status":
                    self.status.set(text)
                elif kind == "fail":
                    self._failed(text)
                    return
                elif kind == "done":
                    self.ok = True
                    self.status.set("Done - starting the app...")
                    self.root.after(400, self.root.destroy)
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _failed(self, message: str):
        from tkinter import ttk
        self.bar.stop()
        self.status.set(message)
        ttk.Button(self.buttons, text="Copy messages", command=self._copy).pack(side="left")
        ttk.Button(self.buttons, text="Close", command=self.root.destroy).pack(side="right")

    def _copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.status.get() + "\n\n" + self.log.get("1.0", "end"))

    def _close(self):
        if self.ok or self.buttons.winfo_children():
            self.root.destroy()
        # while installing, closing is ignored: stopping pip half-way would leave .venv broken

    def run(self):
        if os.environ.get(DONE_FLAG) and missing(self.required):
            # we were restarted after a setup that reported success, but the packages still
            # don't load: don't set up again in a loop
            self.root.after(50, lambda: self._failed(
                "Setup finished, but the packages still won't load: " + ", ".join(missing(self.required))
                + ". Delete the .venv folder and start the app again."))
        else:
            threading.Thread(target=self._work, daemon=True).start()
            self.root.after(100, self._poll)
        self.root.mainloop()
        if self.ok:
            restart_in_venv()
        sys.exit(1)
