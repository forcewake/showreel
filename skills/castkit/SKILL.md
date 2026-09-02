---
name: castkit
description: Convert asciinema terminal recordings (.cast) to SVG, MP4/MKV video with chapters, GIF, HTML player, transcripts and more via the castkit CLI. TRIGGERS - cast file, asciinema convert, cast to svg, cast to mp4, cast to gif, terminal recording, asciicast, screencast export, recording chapters, cast transcript, analyze cast.
---

# castkit

Convert asciinema `.cast` recordings (asciicast **v1/v2/v3**, plain or gzip) to everything:
animated SVG, MP4/WebM/MKV/MOV video **with chapters**, GIF/APNG, a self-contained
HTML player, poster PNG, plain/timestamped transcripts, SRT/VTT subtitles and format
conversion. Built for humans **and** AI agents: text commands print to stdout, `info`
emits stable JSON, progress goes to stderr.

## First check

```bash
castkit --version            # installed?
```

If missing: `uv tool install castkit` (or from source: `uv tool install /path/to/castkit-repo`).
Video/GIF/APNG also need `ffmpeg` on PATH (`brew install ffmpeg` / `apt install ffmpeg`).

## The recipes

```bash
# What is in this recording? (JSON: duration, markers, event stats, env)
castkit info rec.cast

# Transcript for LLM analysis — timestamped, ANSI-free, straight to stdout
castkit text rec.cast --mode timed > rec.timed.txt
castkit text rec.cast --mode screen        # final screen contents only

# Everything at once into out/ (+ manifest.json with sha256 of each file)
castkit all rec.cast -o out/

# Animated SVG — one self-contained file, CSS animation, works in READMEs via <img>
castkit svg rec.cast -o demo.svg

# Video with chapters from asciinema marker events (VLC/mpv/IINA show them)
castkit video rec.cast -o demo.mp4
castkit video rec.cast -o demo.mkv --chapters auto:30     # no markers? cut every 30s

# GIF (palette-optimized) and a self-contained offline HTML player
castkit gif rec.cast -o demo.gif
castkit html rec.cast -o demo.html

# Poster frame, Markdown page, caption subtitles, YouTube chapters
castkit poster rec.cast -o poster.png
castkit md rec.cast -o page.md
castkit subs rec.cast --format srt
castkit chapters rec.cast --format youtube      # 0:00 intro prepended automatically

# asciinema 3.x (v3 cast) → v2 for older tools
castkit convert rec.cast -o rec.v2.cast --to v2

# Trim / retime
castkit gif rec.cast -o clip.gif --start 10 --end 25 --speed 2 --idle-limit 1
castkit gif rec.cast -o clip.gif --from-marker build --to-marker deploy
```

## Making it pretty (all visual commands)

```bash
--preset pretty              # gradient margin + rings chrome + shadow + radius + blink
--preset clean               # subtle: shadow + rounded corners
--theme dracula              # or: nord, monokai, gruvbox-dark, solarized-dark/light,
                             #     tango-light, asciinema, auto (from cast header)
--chrome "deploy" --chrome-style rings    # window bar with traffic lights
--margin 48 --margin-fill "#6B50FF,#241a66" --radius 12 --shadow
--watermark "@you" --typewriter 40        # char-by-char re-timing at 40 chars/sec
--cursor-blink 530 --cursor block|underline|off
```

`--preset` fills defaults; explicitly-passed flags always win.

## Agent contract (stable behavior — rely on it)

- **stdout**: output paths (file commands) or content (`text`, `md`, `subs`, `chapters`, `info` JSON).
- **stderr**: progress + warnings. **exit codes**: 0 ok, 1 error with `castkit: error: …` message.
- `castkit all rec.cast -o out/` → deterministic names `STEM.<ext>` + `manifest.json`
  (bytes + sha256 per file) + `README.txt`.
- `info` JSON keys: `asciicast_version, title, command, recorded_at, duration_seconds,
  terminal{cols,rows,type}, env, tags, events{total,by_type}, markers[{time,label}], first_prompt`.
- Input `-` reads stdin: `cat x.cast | castkit gif - -o x.gif`.

## Pitfalls

- `duration_seconds` is the last event time; recordings recorded with Ctrl-D on an idle
  shell can look much longer than the interesting part — use `--idle-limit 3`.
- svg/html keep millisecond timing; video/gif quantize to fps (raise `--fps 30` for
  fast typewriter effects).
- v3 casts (asciinema 3.x) are NOT readable by svg-term and old players — convert with
  `castkit convert --to v2`.
- No markers in the recording? `chapters --auto 30` and `video --chapters auto:30`
  synthesize them; otherwise those commands return empty output.
- Full-screen TUI apps (vim/htop) may render with artifacts: the pyte engine does not
  swap the alternate screen buffer.
