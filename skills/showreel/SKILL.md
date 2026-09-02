---
name: showreel
description: Convert asciinema terminal recordings (.cast) to SVG, MP4/MKV video with chapters, GIF, HTML player, transcripts and more via the showreel CLI. TRIGGERS - cast file, asciinema convert, cast to svg, cast to mp4, cast to gif, terminal recording, asciicast, screencast export, recording chapters, cast transcript, analyze cast.
---

# showreel

Convert asciinema `.cast` recordings (asciicast **v1/v2/v3**, plain or gzip) to everything:
animated SVG, MP4/WebM/MKV/MOV video **with chapters**, GIF/APNG, a self-contained
HTML player, poster PNG, plain/timestamped transcripts, SRT/VTT subtitles and format
conversion. Built for humans **and** AI agents: text commands print to stdout, `info`
emits stable JSON, progress goes to stderr.

## First check

```bash
showreel --version            # installed?
```

If missing: `uv tool install showreel` (or from source: `uv tool install /path/to/showreel-repo`).
Video/GIF/APNG also need `ffmpeg` on PATH (`brew install ffmpeg` / `apt install ffmpeg`).

## The recipes

```bash
# What is in this recording? (JSON: duration, markers, event stats, env)
showreel info rec.cast

# Transcript for LLM analysis — timestamped, ANSI-free, straight to stdout
showreel text rec.cast --mode timed > rec.timed.txt
showreel text rec.cast --mode screen        # final screen contents only

# Everything at once into out/ (+ manifest.json with sha256 of each file)
showreel all rec.cast -o out/

# Animated SVG — one self-contained file, CSS animation, works in READMEs via <img>
showreel svg rec.cast -o demo.svg

# Video with chapters from asciinema marker events (VLC/mpv/IINA show them)
showreel video rec.cast -o demo.mp4
showreel video rec.cast -o demo.mkv --chapters auto:30     # no markers? cut every 30s

# GIF (palette-optimized) and a self-contained offline HTML player
showreel gif rec.cast -o demo.gif
showreel html rec.cast -o demo.html

# Poster frame, Markdown page, caption subtitles, YouTube chapters
showreel poster rec.cast -o poster.png
showreel md rec.cast -o page.md
showreel subs rec.cast --format srt
showreel chapters rec.cast --format youtube      # 0:00 intro prepended automatically

# asciinema 3.x (v3 cast) → v2 for older tools
showreel convert rec.cast -o rec.v2.cast --to v2

# Trim / retime
showreel gif rec.cast -o clip.gif --start 10 --end 25 --speed 2 --idle-limit 1
showreel gif rec.cast -o clip.gif --from-marker build --to-marker deploy
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
- **stderr**: progress + warnings. **exit codes**: 0 ok, 1 error with `showreel: error: …` message.
- `showreel all rec.cast -o out/` → deterministic names `STEM.<ext>` + `manifest.json`
  (bytes + sha256 per file) + `README.txt`.
- `info` JSON keys: `asciicast_version, title, command, recorded_at, duration_seconds,
  terminal{cols,rows,type}, env, tags, events{total,by_type}, markers[{time,label}], first_prompt`.
- Input `-` reads stdin: `cat x.cast | showreel gif - -o x.gif`.

## Pitfalls

- `duration_seconds` is the last event time; recordings recorded with Ctrl-D on an idle
  shell can look much longer than the interesting part — use `--idle-limit 3`.
- svg/html keep millisecond timing; video/gif quantize to fps (raise `--fps 30` for
  fast typewriter effects).
- v3 casts (asciinema 3.x) are NOT readable by svg-term and old players — convert with
  `showreel convert --to v2`.
- No markers in the recording? `chapters --auto 30` and `video --chapters auto:30`
  synthesize them; otherwise those commands return empty output.
- Full-screen TUI apps (vim/htop) may render with artifacts: the pyte engine does not
  swap the alternate screen buffer.
