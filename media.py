"""
Per-line media extraction: an audio clip (WAV) for every transcript line and,
for video files, a screenshot (JPEG) from the middle of each line.

Uses PyAV (already installed with faster-whisper) so no ffmpeg is needed.
Screenshots additionally need Pillow.

Timing note: Whisper's timestamps count decoded audio samples from the first
audio frame. Audio clips are cut the same way (by counting samples), so they
line up exactly. Screenshots are taken at that time plus the audio track's
start offset in the container.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import wave
from typing import Callable, Optional

CLIP_RATE = 44100      # Hz, mono 16-bit WAV
PAD_BEFORE = 0.20      # seconds added before each line
PAD_AFTER = 0.30       # seconds added after each line
ATTACHED_PIC = 0x0400  # FFmpeg disposition flag: cover art in an audio file


def safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "media"


def has_video(path: str) -> bool:
    """True if the file has a real video track (not just MP3 cover art)."""
    import av
    with av.open(path) as c:
        for s in c.streams.video:
            try:
                if int(s.disposition) & ATTACHED_PIC:
                    continue
            except Exception:  # older PyAV without .disposition
                if s.codec_context.name in ("mjpeg", "png", "bmp", "gif") and (s.frames or 0) <= 1:
                    continue
            return True
    return False


# ------------------------------------------------------------------ audio
def extract_audio_clips(
    path: str,
    clips: list[tuple[int, float, float, str]],
    on_clip: Optional[Callable[[int, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> float:
    """Write one WAV per (index, start, end, out_path), in a single pass.

    Returns the start time (seconds) of the first audio frame, which is
    needed to align screenshots with the transcript.
    """
    import av
    import numpy as np

    rate = CLIP_RATE
    pending = sorted(
        [(int(max(s, 0) * rate), int(e * rate), i, out) for i, s, e, out in clips],
        key=lambda c: c[0],
    )
    first_time = 0.0
    chunks: list = []        # int16 arrays not yet consolidated
    buf_start = 0            # sample index of the first sample held in chunks
    total = 0                # samples decoded so far

    def write(i, s0, s1, out, data):
        seg = data[max(s0 - buf_start, 0): max(s1 - buf_start, 0)]
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(seg.astype("<i2").tobytes())
        if on_clip:
            on_clip(i, out)

    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=rate)
    with av.open(path) as container:
        if not container.streams.audio:
            return 0.0
        frames = container.decode(audio=0)
        first = True
        while pending:
            if should_stop and should_stop():
                return first_time
            try:
                frame = next(frames)
            except StopIteration:
                frame = None
            except av.error.InvalidDataError:
                continue
            if frame is not None and first:
                first = False
                first_time = float(frame.time or 0.0)
            if frame is not None:
                frame.pts = None
            for out in resampler.resample(frame):  # frame None = flush
                arr = out.to_ndarray().reshape(-1)
                chunks.append(arr)
                total += arr.shape[0]

            # write every clip whose end we have reached (or all, at EOF)
            if pending and (frame is None or pending[0][1] <= total):
                data = np.concatenate(chunks) if chunks else np.zeros(0, np.int16)
                while pending and (frame is None or pending[0][1] <= total):
                    s0, s1, i, out = pending.pop(0)
                    write(i, s0, s1, out, data)
                chunks = [data]
            # forget audio that no remaining clip needs
            keep_from = pending[0][0] if pending else total
            if keep_from > buf_start and chunks:
                data = np.concatenate(chunks)
                drop = min(keep_from - buf_start, data.shape[0])
                chunks = [data[drop:]]
                buf_start += drop
            if frame is None:
                break
    return first_time


# ------------------------------------------------------------- screenshots
def extract_screenshots(
    path: str,
    shots: list[tuple[int, float, str]],
    time_offset: float = 0.0,
    on_shot: Optional[Callable[[int, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    size: Optional[tuple[int, int]] = None,
) -> None:
    """Save a JPEG for each (index, time_seconds, out_path). size = (width,
    height) to save them at; None = the video's own resolution."""
    import av
    from PIL import Image

    with av.open(path) as container:
        vs = next((s for s in container.streams.video), None)
        if vs is None:
            return
        vs.thread_type = "AUTO"
        tb = float(vs.time_base)
        for i, t, out in sorted(shots, key=lambda x: x[1]):
            if should_stop and should_stop():
                return
            target = t + time_offset
            try:
                container.seek(int(max(target - 0.05, 0) / tb), stream=vs, backward=True)
                img = None
                for frame in container.decode(vs):
                    img = frame
                    if frame.time is None or frame.time >= target:
                        break
                if img is None:
                    continue
                pil = img.to_image()
                if size and tuple(size) != pil.size:
                    pil = pil.resize(tuple(size), Image.LANCZOS)
                pil.save(out, "JPEG", quality=85)
                if on_shot:
                    on_shot(i, out)
            except Exception:  # noqa: BLE001 - one bad frame shouldn't stop the rest
                continue


# ------------------------------------------------------------ one image for every line
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


def shared_copy(src: str, dest_dir: str) -> str:
    """Put an image in dest_dir ONCE, so every line using it shares one file.
    A file that's already in dest_dir is used as it is; otherwise the copy is
    named after its contents (img_<hash>.ext), so copying the same picture
    again reuses the same file. Returns the file's name."""
    os.makedirs(dest_dir, exist_ok=True)
    if os.path.normcase(os.path.dirname(os.path.abspath(src))) == os.path.normcase(os.path.abspath(dest_dir)):
        return os.path.basename(src)
    h = hashlib.sha1()
    with open(src, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    name = f"img_{h.hexdigest()[:16]}{os.path.splitext(src)[1].lower() or '.jpg'}"
    dst = os.path.join(dest_dir, name)
    if not os.path.isfile(dst):
        shutil.copy2(src, dst)
    return name


def is_shared(name: str) -> bool:
    """A file made by shared_copy (used by several lines / cards)."""
    return os.path.basename(name).startswith("img_")


# ------------------------------------------------------------ orchestration
def build_media(
    transcript,
    media_dir: str,
    on_item: Optional[Callable[[str, int, str], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    shot_size: Optional[tuple[int, int]] = None,
    image: Optional[str] = None,
) -> None:
    """Create clips/screenshots for every segment and store their paths
    (relative to the transcript's folder) on each segment. shot_size =
    (width, height) for the screenshots; None = the video's own resolution.
    image = a picture to use as every line's screenshot instead (copied into
    media_dir once; all lines share that one file)."""
    status = on_status or (lambda m: None)
    os.makedirs(media_dir, exist_ok=True)
    src = transcript.source_file
    base = safe_name(os.path.splitext(os.path.basename(src))[0])
    rel = os.path.basename(media_dir)
    segs = {s.index: s for s in transcript.segments}
    dur = transcript.duration or 1e9

    def done_audio(i, out):
        segs[i].audio_clip = f"{rel}/{os.path.basename(out)}"
        if on_item:
            on_item("audio", i, out)

    def done_shot(i, out):
        segs[i].screenshot = f"{rel}/{os.path.basename(out)}"
        if on_item:
            on_item("shot", i, out)

    status("Cutting audio clips...")
    clips = [
        (s.index, max(s.start - PAD_BEFORE, 0), min(s.end + PAD_AFTER, dur),
         os.path.join(media_dir, f"{base}_{s.index + 1:04d}.wav"))
        for s in transcript.segments
    ]
    offset = extract_audio_clips(src, clips, done_audio, should_stop)

    if should_stop and should_stop():
        return
    if image:
        name = shared_copy(image, media_dir)
        for s in transcript.segments:
            done_shot(s.index, os.path.join(media_dir, name))
        return
    if not has_video(src):
        return
    try:
        import PIL  # noqa: F401
    except ImportError:
        status("Screenshots skipped: run setup.bat once to install Pillow.")
        return
    status("Taking screenshots...")
    shots = [
        (s.index, (s.start + s.end) / 2,
         os.path.join(media_dir, f"{base}_{s.index + 1:04d}.jpg"))
        for s in transcript.segments
    ]
    extract_screenshots(src, shots, offset, done_shot, should_stop, size=shot_size)
