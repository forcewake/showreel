# Examples — one recording, every format

All files below were generated from the same recording
([`tests/fixtures/demo.cast`](../tests/fixtures/demo.cast), asciicast v3, ~14s)
with two commands. This is the exact output you get — no hand-touching.

```bash
castkit all tests/fixtures/demo.cast -o examples --stem demo \
  --preset pretty --chrome "castkit demo" --watermark "made with castkit" \
  --typewriter 50 --cursor-blink 530

# plus a few standalone formats
castkit subs tests/fixtures/demo.cast -o examples/demo.srt
castkit html-transcript tests/fixtures/demo.cast -o examples/demo.transcript.html
castkit chapters tests/fixtures/demo.cast -o examples/demo.chapters.ffmeta.txt --format ffmetadata
castkit chapters tests/fixtures/demo.cast -o examples/demo.chapters.vtt --format vtt
castkit video tests/fixtures/demo.cast -o examples/demo.webm --preset pretty --typewriter 50
castkit gif tests/fixtures/demo.cast -o examples/demo.apng --format apng --preset pretty --typewriter 50
```

## Watch / read

| File | What it is |
|---|---|
| [demo.svg](demo.svg) | ⭐ **animated SVG** — self-contained, typewriter playback, live cursor, blinking at the end, SMIL-timed, no JS. Open it. |
| [demo.html](demo.html) | self-contained offline player: seek bar, speed 0.5–8×, marker buttons, keyboard |
| [demo.mp4](demo.mp4) / [demo.mkv](demo.mkv) | H.264 video **with embedded chapters** (from marker events) — check VLC/mpv chapter menu |
| [demo.webm](demo.webm) | VP9 for the web (chapters are not in the WebM spec) |
| [demo.gif](demo.gif) / [demo.apng](demo.apng) | palette-optimized animations, loops forever |
| [demo.poster.png](demo.poster.png) | single decorated frame — GitHub README ready |
| [demo.txt](demo.txt) / [demo.timed.txt](demo.timed.txt) | plain transcript / `[hh:mm:ss]`-stamped for LLM analysis |
| [demo.md](demo.md) | Markdown page: front matter + final screen + chapters |
| [demo.transcript.html](demo.transcript.html) | colored HTML transcript, every screen change timestamped |
| [demo.srt](demo.srt) / [demo.transcript.vtt](demo.transcript.vtt) | caption subtitles (searchable on video platforms) |

## Data

| File | What it is |
|---|---|
| [demo.v3.cast](demo.v3.cast) / [demo.v2.cast](demo.v2.cast) | the recording converted to asciicast v3 and v2 |
| [demo.summary.json](demo.summary.json) | machine-readable summary (for agents & CI) |
| [demo.chapters.json](demo.chapters.json) / [.txt](demo.chapters.txt) / [.youtube.txt](demo.chapters.youtube.txt) / [.vtt](demo.chapters.vtt) / [.ffmeta.txt](demo.chapters.ffmeta.txt) | chapters in every flavor: JSON, plain list, YouTube description, WebVTT track, raw ffmetadata |
| [manifest.json](manifest.json) | every file with byte size and sha256 — deterministic builds |

`README.txt` is the human summary castkit drops into every bundle.
