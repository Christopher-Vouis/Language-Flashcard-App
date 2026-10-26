"""
Core transcription engine.

Uses faster-whisper (an optimized OpenAI Whisper) which:
  * handles ~100 languages and auto-detects the spoken language
  * decodes audio AND video files directly (mp3, wav, m4a, flac, ogg,
    mp4, mkv, mov, webm, avi, ...) via the bundled PyAV library,
    so no separate ffmpeg install is needed
  * returns segment- and word-level timestamps

The result is a plain data structure (see `Transcript`) so later stages of
the project (audio clips, screenshots, SRS cards) can build on it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]

# Common languages shown in the UI. Whisper supports many more; any
# ISO-639-1 code can be typed in.
LANGUAGES = {
    "Auto-detect": None,
    "English": "en", "Spanish": "es", "French": "fr", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Dutch": "nl", "Russian": "ru",
    "Ukrainian": "uk", "Polish": "pl", "Greek": "el", "Turkish": "tr",
    "Arabic": "ar", "Hebrew": "he", "Hindi": "hi", "Japanese": "ja",
    "Korean": "ko", "Chinese": "zh", "Vietnamese": "vi", "Thai": "th",
    "Indonesian": "id", "Swedish": "sv", "Norwegian": "no", "Danish": "da",
    "Finnish": "fi", "Czech": "cs", "Romanian": "ro", "Hungarian": "hu",
}


@dataclass
class Word:
    start: float
    end: float
    text: str
    probability: float


@dataclass
class Segment:
    index: int
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)
    audio_clip: str = ""   # path relative to the transcript's folder
    screenshot: str = ""   # "" for audio-only input


@dataclass
class Transcript:
    source_file: str
    language: str
    language_probability: float
    duration: float
    model: str
    segments: list[Segment] = field(default_factory=list)

    # ---------- exports ----------
    def to_text(self, timestamps: bool = True) -> str:
        if not timestamps:
            return "\n".join(s.text for s in self.segments)
        return "\n".join(
            f"[{fmt_time(s.start)} --> {fmt_time(s.end)}]  {s.text}"
            for s in self.segments
        )

    def to_srt(self) -> str:
        blocks = []
        for i, s in enumerate(self.segments, 1):
            blocks.append(
                f"{i}\n{fmt_time(s.start, srt=True)} --> "
                f"{fmt_time(s.end, srt=True)}\n{s.text}\n"
            )
        return "\n".join(blocks)

    def to_vtt(self) -> str:
        lines = ["WEBVTT", ""]
        for s in self.segments:
            lines.append(f"{fmt_time(s.start, vtt=True)} --> {fmt_time(s.end, vtt=True)}")
            lines.append(s.text)
            lines.append("")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def save(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        content = {
            ".srt": self.to_srt,
            ".vtt": self.to_vtt,
            ".json": self.to_json,
        }.get(ext, self.to_text)()
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def fmt_time(seconds: float, srt: bool = False, vtt: bool = False) -> str:
    """Format seconds as HH:MM:SS.mmm (SRT uses a comma before ms)."""
    ms_total = int(round(max(seconds, 0) * 1000))
    h, rem = divmod(ms_total, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    sep = "," if srt else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


# ---------- audio decoding ----------
SAMPLE_RATE = 16000  # what Whisper expects


def decode_audio(path: str, sampling_rate: int = SAMPLE_RATE):
    """Decode the first audio track of any audio/video file to a mono
    float32 numpy array at 16 kHz.

    Mirrors faster_whisper.audio.decode_audio, minus the
    av.open(..., metadata_errors=...) argument that PyAV 19 removed,
    so it works with PyAV 11 through 19+.
    """
    import gc
    import av
    import numpy as np

    resampler = av.audio.resampler.AudioResampler(
        format="s16", layout="mono", rate=sampling_rate
    )
    chunks = []
    with av.open(path, mode="r") as container:
        if not container.streams.audio:
            raise ValueError("This file has no audio track.")
        frames = container.decode(audio=0)
        while True:
            try:
                frame = next(frames)
            except StopIteration:
                break
            except av.error.InvalidDataError:
                continue  # skip a corrupt frame, keep going
            frame.pts = None  # ignore timestamp checks
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # flush
            chunks.append(out.to_ndarray().reshape(-1))

    del resampler
    gc.collect()  # PyAV resampler objects otherwise linger (faster-whisper #390)

    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def is_junk(text: str) -> bool:
    """True for lines with no actual words: only music symbols/punctuation."""
    return not any(ch.isalnum() for ch in text)


# ---------- model handling ----------
_model_cache: dict[tuple, object] = {}


def load_model(size: str, device: str = "auto"):
    """Load (and cache) a Whisper model. The first use of each size
    downloads it from Hugging Face (tiny ~75MB ... large-v3 ~3GB)."""
    from faster_whisper import WhisperModel

    if device == "auto":
        device = "cuda" if _cuda_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    key = (size, device, compute_type)
    if key not in _model_cache:
        _model_cache[key] = WhisperModel(size, device=device, compute_type=compute_type)
    return _model_cache[key]


def _cuda_available() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def transcribe(
    path: str,
    model_size: str = "small",
    language: Optional[str] = None,
    device: str = "auto",
    on_segment: Optional[Callable[[Segment, float], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    music: bool = False,
) -> Transcript:
    """Transcribe an audio/video file.

    music=True is for songs / music videos: it turns off the voice-activity
    filter (trained on speech, it drops most singing) and Whisper's
    "no speech" skipping, and instead guards against text invented during
    instrumental breaks.

    on_segment(segment, progress_0_to_1) is called as each segment is ready.
    on_status(message) receives human-readable status updates.
    should_stop() lets a caller cancel mid-way.
    """
    status = on_status or (lambda m: None)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    status(f"Loading '{model_size}' model (first run downloads it)...")
    try:
        model = load_model(model_size, device)
    except Exception as e:
        # GPU present but CUDA/cuDNN libraries missing -> fall back to CPU.
        if device != "cpu":
            status(f"GPU unavailable ({e.__class__.__name__}); using CPU...")
            model = load_model(model_size, "cpu")
        else:
            raise

    status("Decoding audio...")
    audio = decode_audio(path)
    if audio.size == 0:
        raise ValueError("No audio could be decoded from this file.")

    status("Detecting language...")
    options = dict(
        language=language,
        word_timestamps=True,
        beam_size=5,
        condition_on_previous_text=False,  # reduces repetition loops
    )
    if music:
        options.update(
            vad_filter=False,                    # Silero VAD treats singing as non-speech
            no_speech_threshold=None,            # don't skip windows that "sound like music"
            hallucination_silence_threshold=2.0, # but skip invented text in long vocal gaps
        )
    else:
        options.update(vad_filter=True)          # skip silence / music-only parts
    seg_iter, info = model.transcribe(audio, **options)

    result = Transcript(
        source_file=os.path.abspath(path),
        language=info.language,
        language_probability=round(info.language_probability, 3),
        duration=round(info.duration, 3),
        model=model_size,
    )
    status(f"Language: {info.language} ({info.language_probability:.0%}). Transcribing...")

    for s in seg_iter:
        if should_stop and should_stop():
            status("Stopped.")
            break
        if music and is_junk(s.text):
            continue  # e.g. "♪ ♪" for an instrumental passage
        seg = Segment(
            index=len(result.segments),
            start=round(s.start, 3),
            end=round(s.end, 3),
            text=s.text.strip(),
            words=[
                Word(round(w.start, 3), round(w.end, 3), w.word.strip(), round(w.probability, 3))
                for w in (s.words or [])
            ],
        )
        result.segments.append(seg)
        if on_segment:
            progress = min(seg.end / info.duration, 1.0) if info.duration else 0.0
            on_segment(seg, progress)

    return result
