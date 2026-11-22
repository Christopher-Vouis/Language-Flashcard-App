# Multilingual Transcriber

Transcribes speech from an audio **or video** file in ~100 languages and shows a
timestamped transcript. Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(OpenAI Whisper, optimized). Runs fully offline after the model is downloaded.

## Setup

Install **64-bit Python 3.10–3.14** from python.org (3.13 recommended; 3.15, 32-bit and ARM64
builds are not supported by the speech engine yet). Other Python versions can stay installed.

That's all: there's no setup step. Start the app (below) and the first time it sets itself up —
a small window shows it finding a suitable Python, creating a private `.venv` folder and installing
the packages (a few hundred MB, several minutes), then the app opens. If that's interrupted, starting
the app again carries on. It works the same when `app.py` is started from an editor such as Visual
Studio: if the packages aren't there, it sets up `.venv` and restarts itself with it.

## Use

Double-click **`run.bat`** (or run `app.py`). The app opens at the **main menu**:

- **⚙ gear** (top right) — a small **Settings** window: the **window size when the app opens**
  (type a width and height, or **Use the current size**; it applies the next time the app opens).
- **Welcome, <profile>** (top left) — **change** opens the Profiles screen; **sign out** returns to it and
  locks the rest of the app until a profile signs in.
- **Deck** — the name of the deck being studied, with its New / Due / Total.
- **Change Deck** — a menu of your decks (and **All cards**); under them **＋ New deck...**,
  **✎ Rename this deck...** and **✕ Delete this deck...**.
  Deleting a deck never deletes its cards — they stay in All cards and their other decks.
- **Edit Deck** — the **View Deck**
  window: the deck's cards with their status (New / Learning / Review) and when each is due.
  - **Add cards...** opens a list of all your cards (search, or filter by deck; ✓ = already in this deck):
    select some (Ctrl / Shift for several) and press **Add to deck**.
  - **Remove selected** (or Delete) takes cards out of this deck — they aren't deleted, they stay in
    All cards and any other decks.
  - **Reset progress...** makes every card in the deck New and due today again (asks first; this
    can't be undone, and a card in several decks is reset in all of them).
- **New / Due / Total** for the chosen deck: *New* = cards never studied, *Due* = studied cards whose
  due date is today or earlier, *Total* = all its cards.
- **Study** — review the cards in the chosen deck (see *Study mode* below).
- **Create** — transcribe a video or song, save lines and make cards (everything below).
  The buttons work with the mouse or the keyboard (Tab to one, then Enter or Space).

The app has no menu bar: everything is on its screens, and Study and Create have a **← Main menu**
button. Keyboard shortcuts: Ctrl+1 main menu · Ctrl+2 Study · Ctrl+3 Create · Ctrl+4 Profiles ·
Ctrl+L Create Cards · Ctrl+K all cards · Ctrl+O open a file.

### Profiles

- Each profile has its own **saved lines, cards and decks** (transcripts in `output\` are shared).
- **change** (under Welcome on the main menu, or Ctrl+4) opens the Profiles
  screen: **Sign in** (or double-click), **New profile...**, **Rename...**, **Delete...**.
- **★ Make default** chooses the profile signed in automatically when the app starts;
  **No default (ask at startup)** makes the app open on the Profiles screen instead.
- Deleting a profile permanently deletes its saved lines, cards and decks (you're asked first; the
  profile you're signed in to can't be deleted).
- Your data from before profiles existed is the **Main** profile (still in `saved\` and `cards\`);
  new profiles keep their data in `profiles\<id>\`. The list is in `profiles.json`.

The Create screen has two tabs: **Import Content** (transcribe a file and save lines) and
**Create Cards** (your saved lines, where cards are made).

On **Import Content**: **Browse...** → pick a file → **Transcribe**.

- Lines appear in the table as they're transcribed.
- With **Audio clips + screenshots** ticked (default), each line then gets an audio clip
  and, for video files, a screenshot from the middle of the line. The **Media** column shows
  ♪ (clip) and ▣ (screenshot) as they're ready.
- **Use one image for all** (instead of **Audio clips + screenshots**; ticking one unticks the other):
  an **Image:** line appears — **Browse...** for a picture (PNG, JPG, GIF, WebP, BMP). Every line still
  gets its audio clip, and that one picture as its screenshot. The picture is copied into the
  transcript's `media\` folder once (not if it's already there) and all the lines share that file;
  saved lines and cards made from them share one copy too, which is only deleted once nothing uses it.
- **Screenshot Resolution** (under the preview, above Play): with **Match input resolution** ticked
  (the default) screenshots are the video's own size; untick it and type **X** and **Y** (in pixels)
  to save them at that size instead. Your choice is remembered (`settings.json`).
- **Select a line** to see its screenshot and text in the preview panel on the right.
  **▶ Play** (or Space / double-click) plays its clip; ↑/↓ move between lines;
  "Auto-play on select" plays each line as you move to it.
- Everything is saved to `output\<file name>\`:
  - `<name>.json` — lines, word-level timings, and each line's `audio_clip` / `screenshot` path
  - `<name>.srt`, `<name>.txt`
  - `media\<name>_0001.wav`, `media\<name>_0001.jpg`, ... (one per line)
- **Save as...** also exports `.vtt`.

### Using a subtitle file instead of AI transcription

- Under the file row, choose a **Subtitles (optional)** file (`.srt`, `.vtt`, `.ass` or `.ssa`).
  The main button changes to **Use subtitles**: each subtitle becomes a line, with its timing, and
  audio clips and screenshots are cut for it exactly as for transcribed lines. **Clear** goes back to AI
  transcription. Model, Device and Music mode are ignored when subtitles are used.
- **Offset (s)** shifts all subtitles if they're out of sync: positive = later (subtitles appear too
  early), negative = earlier.
- Multi-line subtitles are joined into one line and formatting tags are removed. UTF-8/UTF-16 files
  work as is; for older encodings (e.g. Shift-JIS) set **Language** so the right one is used.
- CLI: `--subs file.srt [--subs-offset 1.5]`.

### Saving lines

- After transcription finishes, tick the **☐** box of each line you want (Shift-click a box to tick a
  range, Enter ticks the highlighted line, the ☐ column header or **Select all** / Ctrl+A ticks every line),
  then **★ Save selected lines** (Ctrl+S). Clicking elsewhere on a row only changes the preview.
  Ticked lines are tinted blue in the full transcript. Saved lines get a ★; saving a line twice is ignored.
- The **Create Cards** tab (or **Create Cards →** under the table, or Ctrl+L) is your collection of saved
  lines from every file you've transcribed.
  Click a line to see its screenshot, **▶ Play** / Space / double-click to hear it, search by text,
  and **Delete selected** to remove lines.
- **Fixing a line's text** — select the line and press **F2** (or **✎ Edit text...**, or right-click),
  on either Create tab. Type the correction; Enter saves it.
  - On the Create screen the transcript files in `output\` are rewritten with the new text.
  - A line that's in both places is changed in both, whichever one you edit.
  - Cards already made from a saved line keep the sentence they were made with; a saved line
    remembers the text it was saved with (`original_text` in `saved_lines.json`).
- Saved lines live in `saved\`: `saved_lines.json` plus their own copies of the clips and
  screenshots in `saved\media\`, so they're kept even if you re-transcribe or delete `output\`.

### Flashcards

- On **Create → Create Cards**, select a line and click **＋ New card...** (or Enter / Ctrl+N / right-click).
  The card editor shows the screenshot, a **▶ Play** button and the sentence. Highlight a word in the
  sentence and click **Use selection as target word**, or type it, then fill in **Reading** and
  **Definition**, tick the **Decks** it belongs in (one or more; the deck chosen on the main menu is
  ticked for you, and **＋ New deck...** makes one on the spot), then click **Save card** (Ctrl+Enter).
  You can make several cards from one line;
  the **Cards** column shows how many each line has.
- **Ctrl+K** lists every card with the same search, screenshot preview and
  playback as Saved lines, plus the word, reading and definition. The **Deck** filter shows one deck;
  the **Decks** column shows where each card is. **✎ Edit card...** (or Enter) changes the three fields,
  the card's decks and its images. **Add to deck ▾** (also on right-click) adds the selected card(s) to a deck,
  keeping their other decks; decks they're already in are shown ✓, and **＋ New deck...** makes one.
  **Delete selected** removes cards.
- Cards live in `cards\`: `cards.json` (the decks, plus each card's fields: `target_word`, `reading`, `definition`, `sentence`,
  `audio_clip`, `screenshot`, `images`, `decks`, an optional own `layout`, source file and times) and their own media copies in `cards\media\`,
  so deleting a saved line doesn't affect its cards.

### Study mode

- **Study** on the main menu (Ctrl+2 or Ctrl+T), or **Study cards** in the Cards window.
- **Front:** the target word and its sentence (the word highlighted in red). **Flip** (Space / Enter)
  shows the **back**: reading, definition, screenshot, and plays the audio clip automatically
  (**▶ Replay audio** or R to hear it again).
- Only **due** cards are shown: every card has a due date, and it's due when that date is today or
  earlier. Cards being learned come first, then reviews (most overdue first), then new cards.
- After flipping, answer with **Again** (1), **Hard** (2) or **Correct** (3, Space or Enter). Under each
  button is when the card would come back.
  - **Again** — due today: the card comes back a few cards later in this session.
  - **Correct** on a new card — it needs **3 Corrects** (in a row; Again starts over) before it's due on
    a later day, then it's due tomorrow.
  - **Correct** on a learned card — pushed forward **2.5 × the days since you last studied it**, so a card
    you still remember after a long gap goes much further out. **Hard** = 1.2 × (at least 1 day).
  - A learned card that gets **Again** on a later day is relearned: its next **Correct** makes it due tomorrow.
- When nothing is left: "All caught up", with the date the next card is due.
  **← Main menu** or Esc goes back. Cards added, edited or deleted while studying are picked up straight away.
  Cards studied before due dates existed start out due today.

### Card layout editor

- **✎ Edit layout** (top right of the Study screen), or
  **Card layout...** in the Cards window. Each profile has its own layout.
- **Blocks** (left): Target word, Reading, Definition, Sentence, Audio button, Source (file & time),
  Divider line and Custom text — and the **▾ Images** section (click its title to fold it):
  a block for each image, **＋ Add image...**, and a **Slideshow** block when the card has more than one
  image (one image at a time with ◀ ▶ and a counter). Select a slideshow to set **Autoplay**:
  *Change image every [n] seconds* (any value from 0.5 to 120; type it or use the arrows) and
  *Loop back to the first image* (off = stop on the last one). While it autoplays, a ⏸ / ⏵ button
  pauses and resumes it. Autoplay runs in study mode and the Test preview (not while editing).
  In the default layout, *Image 1* means each card's first image (its screenshot), *Image 2* its
  second, and so on; in one card's own layout, image blocks are that card's specific pictures.
- **Drag** blocks from the block list onto the **preview** or the **Front / Back** lists, and drag
  blocks around in either place (or between sides). Where you drop decides the layout:
  - at the **top or bottom edge** of a row → a **new row** there (a horizontal blue line shows it);
  - in the **middle** of a row → **side by side** with that row's blocks, left or right of the one
    you're pointing at (a vertical blue line shows it). Rows of several blocks are outlined in the lists.
  Drag a block back onto the block list (or click its **✕**) to remove it. Double-clicking a block in
  the list adds it on a new row at the bottom of the side shown in the preview.
- **Preview: ✎ Edit / ▶ Test.** In **Edit**, every block is a handle: press and hold to drag it, click
  to select it — buttons such as *Play audio* don't press. In **Test**, the card works like study mode:
  buttons press, **Flip** / **Next card →** step through your cards, and audio plays automatically
  where switched on. **Front / Back** picks the side and **◀ ▶** the card.
- Select a block (click it in the preview or a list) to change its **size, alignment, colour, bold**
  (sentence: highlight the target word or not; Custom text: the text). Its buttons move it
  **← →** within its row and **↑ ↓** between rows (a block sharing a row is first given a row of its
  own), duplicate it, send it to the other side, or remove it. Ctrl+arrow keys do the same moves;
  Delete removes it.
- **Layouts for single cards.** **Customize this card...** in the Cards window (also on right-click), or
  **Edit layout ▾ → This card only...** on the Study screen, opens the editor for just that card (a blue
  banner says so). Saving gives that card its own layout; every other card keeps the default. The Cards
  window's **Layout** column shows *custom*, and study mode notes "This card has its own layout".
  **Use the default layout for this card** (top right of the editor) removes it again.
  **Edit layout ▾ → All cards (default layout)...** edits the default.
- **Images on a card.** **＋ Add image...** copies pictures (PNG, JPG, GIF, WebP, BMP) into the card.
  To **delete** one: **✎ Edit card...** in the Cards window shows the card's images as thumbnails, each with
  **✕ Delete** (and **＋ Add image...**); or in the layout editor click the **✕** on an image in the Images
  section, or select an image block and click **✕ Delete this picture from the card**. You're asked first;
  the picture file is deleted. The card's original screenshot is Image 1 (it can be deleted too).
  The Cards window's Media column shows ▣×3 etc.
- **Play audio automatically** can be switched on for either side (e.g. a listening card: audio on the front).
- **↶ Undo** (Ctrl+Z) undoes any step; **Reset to default layout** brings back the original look;
  **Save** (Ctrl+S) applies it to study mode straight away. Closing with unsaved changes asks first.
- Blocks with nothing to show on a card (e.g. no reading, or an audio-only card's screenshot) are
  skipped in study mode. The layout is saved as `template.json` in the profile's cards folder.

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
- `settings.py` — settings remembered between runs (`settings.json`): the window size and the screenshot size.
- `bootstrap.py` — the first-run setup (creates `.venv`, installs `requirements.txt`, restarts the app in it).
- `media.py` — cuts audio clips (44.1 kHz WAV, with 0.2 s / 0.3 s padding) and screenshots.
- `saved.py` — the saved-lines library.
- `cards.py` — the flashcard deck.
- `srs.py` — spaced repetition: due dates and what Again / Hard / Correct do (the numbers are at the top).
- `profiles.py` — user profiles and the default profile.
- `home.py` — the main menu (positions are in the background picture's 1200 × 1500 pixels).
- `backdrop.py` — the background picture behind the main menu, Study and Create. Nothing is stretched:
  a wider window shows more of the dots band (`assets\menu_dots.png`, 3840 px wide), the A / あ drift
  to the right as the window widens, and the stripes stay in the bottom-left corner. On Study the card
  sits on a raised panel, and on Create the controls sit on one panel, with the picture around them.
  `draw_tabs` draws Create's tabs on the white line, with the line's shadow following their outline.
- `assets\` — the background picture, the dots band and the main menu's button picture.
- The window opens at 1280 × 1000 (change it in Settings, the gear on the main menu). If it is narrower than 1180 px, it widens by itself for the Create screen and goes back afterwards.
- `subtitles.py` — reads .srt / .vtt / .ass subtitle files as lines.
- `theme.py` — the dark color scheme; every color is defined at the top, so it's easy to adjust.
- `templates.py`, `card_view.py`, `template_editor.py` — card layouts: the data, drawing a card, and the drag-and-drop editor.
- `audio.py` — plays the clips.
- `app.py` — desktop window.
- `transcribe_cli.py` — command-line version.
