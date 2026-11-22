"""
"Language Flashcards" shortcuts on the desktop and in the Start menu (Windows),
with the app's icon (assets/app.ico). They start the app with .venv's
pythonw.exe, so no console window opens.

Made the first time the app runs (once; see App._first_run_shortcuts) and from
Settings → Create shortcuts. Uses Windows' own shortcut maker (WScript.Shell
through PowerShell), so nothing extra needs installing.
"""

from __future__ import annotations

import os
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "Language Flashcards"
ICON = os.path.join(APP_DIR, "assets", "app.ico")

# paths come in through environment variables, so spaces and quotes in them can't break the script
_SCRIPT = r"""
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    if (-not $dir) { continue }
    $s = $ws.CreateShortcut((Join-Path $dir ($env:LF_NAME + '.lnk')))
    $s.TargetPath = $env:LF_TARGET
    $s.Arguments = '"' + $env:LF_SCRIPT + '"'
    $s.WorkingDirectory = $env:LF_DIR
    $s.IconLocation = $env:LF_ICON + ',0'
    $s.Description = 'Transcribe videos and study flashcards'
    $s.Save()
    Write-Output $s.FullName
}
"""


def supported() -> bool:
    return os.name == "nt"


def launcher() -> str:
    """The program the shortcut runs: pythonw.exe (no console) next to the
    Python running the app - normally .venv's."""
    venv = os.path.join(APP_DIR, ".venv", "Scripts", "pythonw.exe")
    if os.path.isfile(venv):
        return venv
    here = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return here if os.path.isfile(here) else sys.executable


def create() -> list[str]:
    """Make (or update) both shortcuts. Returns their paths; raises OSError
    with the reason if Windows refused."""
    if not supported():
        raise OSError("Shortcuts can only be made on Windows.")
    env = dict(os.environ, LF_NAME=NAME, LF_TARGET=launcher(), LF_SCRIPT=os.path.join(APP_DIR, "app.py"),
               LF_DIR=APP_DIR, LF_ICON=ICON)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-Command", _SCRIPT], capture_output=True, text=True, env=env, timeout=60,
                           creationflags=0x08000000)          # CREATE_NO_WINDOW
    except (OSError, subprocess.SubprocessError) as e:
        raise OSError(f"Couldn't run PowerShell: {e}") from e
    made = [line.strip() for line in r.stdout.splitlines() if line.strip().lower().endswith(".lnk")]
    if r.returncode != 0 or not made:
        raise OSError((r.stderr or r.stdout or "PowerShell gave no reason.").strip()[:500])
    return made
