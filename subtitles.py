"""
Subtitle files as a source of lines, instead of AI transcription.

Supports SubRip (.srt), WebVTT (.vtt) and Advanced/SubStation Alpha
(.ass / .ssa). Each subtitle cue becomes one line (multi-line cues are
joined with a space); formatting tags are removed.
"""

from __future__ import annotations

import os
import re
from typing import Callable, Optional

import transcriber as tr

SUB_TYPES = [("Subtitles", "*.srt *.vtt *.ass *.ssa"), ("All files", "*.*")]

# Legacy (non-UTF-8) encodings to try for a chosen language.
_LEGACY = {
    "ja": "cp932", "zh": "gb18030", "ko": "cp949", "ru": "cp1251", "uk": "cp1251",
    "el": "cp1253", "tr": "cp1254", "he": "cp1255", "ar": "cp1256", "vi": "cp1258",
    "th": "cp874", "pl": "cp1250", "cs": "cp1250", "hu": "cp1250", "ro": "cp1250",
}


# ------------------------------------------------------------------ reading
def read_text(path: str, language: Optional[str] = None) -> str:
    """Decode a subtitle file: UTF-8 / UTF-16 first, then the legacy
    encoding for the chosen language, then common East Asian encodings,
    then Windows-1252."""
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    candidates = []
    if language and language in _LEGACY:
        candidates.append(_LEGACY[language])
    candidates += ["cp932", "gb18030", "cp949"]
    for enc in candidates:
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc == _LEGACY.get(language or ""):
            return text
        # only accept an East Asian guess if it actually produced that script
        if enc == "cp932" and re.search(r"[぀-ヿ]", text):
            return text
        if enc == "gb18030" and re.search(r"[一-鿿]", text):
            return text
        if enc == "cp949" and re.search(r"[가-힯]", text):
            return text
    return data.decode("cp1252", errors="replace")


# ------------------------------------------------------------------ parsing
_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{1,2})[,.](\d{1,3})"
_CUE = re.compile(_TIME + r"\s*-->\s*" + _TIME)


def _secs(h, m, s, frac) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")[:3]) / 1000


# Scripts written without spaces between words (Japanese, Chinese).
_NO_SPACE = re.compile(r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]*>", "", text)          # <i>, <font ...>, <c.red>, <00:01.000>
    text = re.sub(r"\{[^}]*\}", "", text)        # {\an8} etc. (also in some SRTs)
    text = text.replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # Join a multi-line cue into one line: with a space, except between
    # Japanese/Chinese characters, which don't use spaces.
    out = ""
    for part in (" ".join(p.split()) for p in text.split("\n")):
        if not part:
            continue
        if out and not (_NO_SPACE.match(out[-1]) or _NO_SPACE.match(part[0])):
            out += " "
        out += part
    return out


def parse_srt_vtt(text: str) -> list[tuple[float, float, str]]:
    cues = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _CUE.search(lines[i])
        if not m:
            i += 1
            continue
        g = m.groups()
        start, end = _secs(*g[0:4]), _secs(*g[4:8])
        i += 1
        body = []
        while i < len(lines) and lines[i].strip() and not _CUE.search(lines[i]):
            body.append(lines[i])
            i += 1
        # SRT index numbers of the next cue end up as a stray last line only
        # when blank lines are missing; drop a trailing bare number.
        if body and body[-1].strip().isdigit() and i < len(lines) and _CUE.search(lines[i]):
            body.pop()
        cues.append((start, end, _clean("\n".join(body))))
    return cues


def parse_ass(text: str) -> list[tuple[float, float, str]]:
    cues = []
    fields = ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"]
    in_events = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_events = s.lower() == "[events]"
            continue
        if not in_events:
            continue
        if s.lower().startswith("format:"):
            fields = [f.strip().lower() for f in s[7:].split(",")]
            continue
        if not s.lower().startswith("dialogue:"):
            continue  # skips Comment: lines
        parts = s[9:].split(",", len(fields) - 1)
        if len(parts) < len(fields):
            continue
        row = dict(zip(fields, parts))
        raw = row.get("text", "")
        if re.search(r"\{[^}]*\\p[1-9]", raw):
            continue  # vector drawing (signs/typesetting), not dialogue
        try:
            start = _ass_time(row["start"])
            end = _ass_time(row["end"])
        except (KeyError, ValueError):
            continue
        cues.append((start, end, _clean(raw)))
    return cues


def _ass_time(t: str) -> float:
    h, m, s = t.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse(path: str, language: Optional[str] = None) -> list[tuple[float, float, str]]:
    """Return sorted (start, end, text) cues, empty and duplicate cues removed."""
    text = read_text(path, language)
    ext = os.path.splitext(path)[1].lower()
    is_ass = ext in (".ass", ".ssa") or "[events]" in text[:20000].lower()
    cues = parse_ass(text) if is_ass else parse_srt_vtt(text)
    seen, out = set(), []
    for start, end, body in sorted(cues, key=lambda c: (c[0], c[1])):
        key = (round(start, 2), round(end, 2), body)
        if not body or end <= start or key in seen:
            continue
        seen.add(key)
        out.append((start, end, body))
    return out


# ------------------------------------------------------- media timing
def _media_timing(path: str) -> tuple[float, float]:
    """(duration, audio start offset) of the media file, in seconds."""
    try:
        import av
        with av.open(path) as c:
            duration = (c.duration or 0) / 1_000_000  # av.time_base is microseconds
            offset = 0.0
            if c.streams.audio:
                st = c.streams.audio[0]
                if st.start_time is not None and st.time_base is not None:
                    offset = float(st.start_time * st.time_base)
                    if c.start_time:
                        offset -= c.start_time / 1_000_000
            return duration, max(offset, 0.0)
    except Exception:  # noqa: BLE001 - timing is best-effort
        return 0.0, 0.0


def load(
    media_path: str,
    subs_path: str,
    language: Optional[str] = None,
    offset: float = 0.0,
    on_segment: Optional[Callable[[tr.Segment, float], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> tr.Transcript:
    """Build a Transcript from a subtitle file for the given media file.

    offset (seconds) shifts every subtitle: positive = later, for subtitles
    that appear too early.
    """
    status = on_status or (lambda m: None)
    if not os.path.isfile(media_path):
        raise FileNotFoundError(media_path)
    if not os.path.isfile(subs_path):
        raise FileNotFoundError(subs_path)
    status(f"Reading subtitles: {os.path.basename(subs_path)}")
    cues = parse(subs_path, language)
    if not cues:
        raise ValueError("No subtitle lines were found in that file. "
                         "Supported formats: .srt, .vtt, .ass, .ssa")

    duration, audio_start = _media_timing(media_path)
    if not duration:
        duration = cues[-1][1] + offset
    result = tr.Transcript(
        source_file=os.path.abspath(media_path),
        language=language or "",
        language_probability=1.0,
        duration=round(duration, 3),
        model=f"subtitles: {os.path.basename(subs_path)}",
    )
    for start, end, body in cues:
        # Clips are cut on the audio track's own timeline (like Whisper's
        # timestamps), so shift by the audio track's start offset too.
        s = start + offset - audio_start
        e = end + offset - audio_start
        if e <= 0 or (duration and s >= duration):
            continue  # outside the media after shifting
        seg = tr.Segment(index=len(result.segments), start=round(max(s, 0.0), 3),
                         end=round(e, 3), text=body)
        result.segments.append(seg)
        if on_segment:
            on_segment(seg, min(seg.end / duration, 1.0) if duration else 0.0)
    status(f"Loaded {len(result.segments)} lines from subtitles.")
    return result
