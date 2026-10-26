# Multilingual Transcriber

Transcribes speech from an audio **or video** file in ~100 languages and shows a
timestamped transcript. Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(OpenAI Whisper, optimized). Runs fully offline after the model is downloaded.

## Setup (once)

1. Install **64-bit Python 3.10–3.14** from python.org (3.13 recommended; 3.15, 32-bit and ARM64 builds are not supported by the speech engine yet). Other Python versions can stay installed — setup picks a compatible one.
2. Double-click **`setup.bat`**. It creates a private `.venv` folder and installs packages.

## Use

Double-click **`run.bat`** → **Browse...** → pick a file → **Transcribe**.

- Lines appear in the table as they're transcribed.
- With **Audio clips + screenshots** ticked (default), each line then gets an audio clip
  and, for video files, a screenshot from the middle of the line. The **Media** column shows
  ♪ (clip) and ▣ (screenshot) as they're ready.
- **Select a line** to see its screenshot and text in the preview panel on the right.
  **▶ Play** (or Space / double-click) plays its clip; ↑/↓ move between lines;
  "Auto-play on select" plays each line as you move to it.
- Everything is saved to `output\<file name>\`:
  - `<name>.json` — lines, word-level timings, and each line's `audio_clip` / `screenshot` path
  - `<name>.srt`, `<name>.txt`
  - `media\<name>_0001.wav`, `media\<name>_0001.jpg`, ... (one per line)
- **Save as...** also exports `.vtt`.

### Saving lines

- After transcription finishes, pick lines with **Ctrl-click / Shift-click** (or **Select all**, Ctrl+A),
  then **★ Save selected lines** (Ctrl+S). Saved lines get a ★ in the table; saving a line twice is ignored.
- **Saved lines → View saved lines...** (Ctrl+L) opens your collection from every file you've transcribed.
  Click a line to see its screenshot, **▶ Play** / Space / double-click to hear it, search by text,
  and **Delete selected** to remove lines.
- Saved lines live in `saved\`: `saved_lines.json` plus their own copies of the clips and
  screenshots in `saved\media\`, so they're kept even if you re-transcribe or delete `output\`.

### Flashcards

- In **View saved lines**, select a line and click **＋ New card...** (or Enter / Ctrl+N / right-click).
  The card editor shows the screenshot, a **▶ Play** button and the sentence. Highlight a word in the
  sentence and click **Use selection as target word**, or type it, then fill in **Reading** and
  **Definition** and click **Save card** (Ctrl+Enter). You can make several cards from one line;
  the **Cards** column in Saved lines shows how many each line has.
- **Cards → View cards...** (Ctrl+K) lists every card with the same search, screenshot preview and
  playback as Saved lines, plus the word, reading and definition. **✎ Edit card...** (or Enter)
  changes the three fields; **Delete selected** removes cards.
- Cards live in `cards\`: `cards.json` (fields: `target_word`, `reading`, `definition`, `sentence`,
  `audio_clip`, `screenshot`, source file and times) and their own media copies in `cards\media\`,
  so deleting a saved line doesn't affect its cards.

### Study mode

- **Cards → Study cards...** (Ctrl+T), or **Study cards** in the Cards window.
- **Front:** the target word and its sentence (the word highlighted in red). **Flip** (Space / Enter)
  shows the **back**: reading, definition, screenshot, and plays the audio clip automatically
  (**▶ Replay audio** or R to hear it again).
- **Next card →** (Space / Enter) puts the card at the bottom of the stack and shows the next front.
  Cards added, edited or deleted while studying are picked up straight away.

Command line alternative:

```
.venv\Scripts\python transcribe_cli.py "C:\path\video.mp4" --model medium --language es --out subs.srt
```

## Options

| Option | Notes |
|---|---|
| **Model** | `tiny`/`base` fast but rough · `small` good default · `medium`/`large-v3` most accurate (slow on CPU) · `large-v3-turbo` near-large accuracy, much faster. The first use of each model downloads it (75 MB – 3 GB). |
| **Language** | Auto-detect works well, but choosing the language improves accuracy on short or noisy clips. You can type any ISO code (e.g. `ka`, `sw`). |
| **Music mode** | For songs and music videos. Normal mode uses a voice-activity filter that treats singing as non-speech, so most lyrics get skipped. Music mode turns that filter (and Whisper's "no speech" skipping) off, drops ♪-only lines, and skips invented text in long instrumental gaps. Leave it off for normal speech. Best results: also set the language and use `large-v3-turbo`. CLI: `--music`. |
| **Device** | `auto` uses an NVIDIA GPU if available and falls back to CPU. GPU needs CUDA 12 + cuDNN 9 installed. |

## Files

- `transcriber.py` — engine; returns a `Transcript` (segments → words, with times). Later stages (audio clips, screenshots, flashcards) build on this and on `output\*.json`.
- `media.py` — cuts audio clips (44.1 kHz WAV, with 0.2 s / 0.3 s padding) and screenshots.
- `saved.py` — the saved-lines library.
- `cards.py` — the flashcard deck.
- `app.py` — desktop window.
- `transcribe_cli.py` — command-line version.
