"""
Command-line version.

  python transcribe_cli.py video.mp4
  python transcribe_cli.py audio.mp3 --model medium --language ja --out subs.srt
"""
import argparse
import sys

import subtitles
import transcriber as tr


def main():
    ap = argparse.ArgumentParser(description="Transcribe an audio or video file.")
    ap.add_argument("file")
    ap.add_argument("--model", default="small", choices=tr.MODEL_SIZES)
    ap.add_argument("--language", default=None, help="ISO code, e.g. en, es, ja (default: auto-detect)")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--music", action="store_true", help="music mode: for songs / music videos")
    ap.add_argument("--subs", help="use this subtitle file (.srt/.vtt/.ass) instead of AI transcription")
    ap.add_argument("--subs-offset", type=float, default=0.0,
                    help="shift subtitles by this many seconds (positive = later)")
    ap.add_argument("--out", help="Save to .srt / .vtt / .json / .txt")
    a = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # so non-Latin scripts print on Windows

    show = lambda s, p: print(f"[{tr.fmt_time(s.start)} --> {tr.fmt_time(s.end)}]  {s.text}", flush=True)  # noqa: E731
    status = lambda m: print(f"# {m}", file=sys.stderr, flush=True)  # noqa: E731
    if a.subs:
        result = subtitles.load(a.file, a.subs, a.language, a.subs_offset, on_segment=show, on_status=status)
    else:
        result = tr.transcribe(a.file, a.model, a.language, a.device, music=a.music,
                               on_segment=show, on_status=status)
    if a.out:
        result.save(a.out)
        print(f"# Saved {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
