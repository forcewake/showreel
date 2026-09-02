# AGENTS.md — showreel

Guidance for AI agents: both for **working on this repo** and for **using the showreel CLI programmatically**.

## Using showreel (as a tool)

showreel converts asciinema `.cast` recordings (asciicast v1/v2/v3, plain or gzip) to other formats.
Stable, scriptable behaviors:

- **stdout/stderr discipline**: progress and warnings → stderr. Single-file commands print the produced **path** to stdout. Text commands (`text`, `md`, `subs`, `chapters`) print **content** to stdout unless `-o` is given. `info` prints JSON.
- **Exit codes**: `0` success, `1` error (human-readable message on stderr, `showreel: error: …`).
- **Determinism**: `showreel all` writes `<stem>.<ext>` files into the target dir plus `manifest.json` listing every file with byte size and sha256. `stem` = output directory name.

### JSON: `showreel info REC.cast`

```json
{
  "tool": "showreel",
  "source": "rec.cast",
  "asciicast_version": 3,
  "title": "string|null",
  "command": "string|null",
  "recorded_at": 1725264000,
  "duration_seconds": 12.57,
  "terminal": {"cols": 80, "rows": 24, "type": "xterm-256color|null"},
  "env": {"SHELL": "/bin/zsh"},
  "tags": ["demo"],
  "events": {"total": 36, "by_type": {"o": 32, "m": 3, "x": 1}},
  "markers": [{"time": 1.35, "label": "build"}],
  "first_prompt": "string|null"
}
```

### Recipes

```bash
# transcript for LLM analysis (timestamped, ANSI-free)
showreel text rec.cast --mode timed > rec.timed.txt

# everything at once
showreel all rec.cast -o out/

# trim 10s..25s, 2x faster, pauses compressed to 1s
showreel video rec.cast -o clip.mp4 --start 10 --end 25 --speed 2 --idle-limit 1

# asciinema 3.x recording → v2 for an old tool (svg-term etc.)
showreel convert rec.v3.cast -o rec.v2.cast --to v2

# chapters for YouTube description
showreel chapters rec.cast --format youtube

# pick a theme / window chrome for a poster
showreel poster rec.cast -o p.png --theme dracula --chrome "my demo" --at 5
```

### Stable file set of `showreel all`

`STEM.mp4`, `STEM.mkv` (both with chapters), `STEM.gif`, `STEM.svg`, `STEM.html`,
`STEM.poster.png`, `STEM.txt`, `STEM.timed.txt`, `STEM.md`, `STEM.transcript.vtt`,
`STEM.chapters.txt`, `STEM.chapters.youtube.txt`, `STEM.chapters.json`,
`STEM.v3.cast`, `STEM.v2.cast`, `STEM.summary.json`, `manifest.json`, `README.txt`.

## Working on this repo

### Setup & commands

```bash
uv sync                 # install deps + editable showreel
uv run pytest           # all tests; ffmpeg-dependent ones skip themselves
uv run showreel …        # run the CLI
uv run python scripts/make_demo_cast.py tests/fixtures/demo.cast   # regenerate the demo cast
```

Python ≥ 3.10. Runtime deps: `pyte`, `Pillow` — keep it that way; ffmpeg is an external optional binary.

### Architecture map

```
src/showreel/
  core/model.py       Cast/Header/TermInfo/Theme/Event — the normalised model
  core/parser.py      v1 (single JSON, delta times) / v2 (NDJSON, absolute) / v3 (NDJSON, intervals) → Cast
  core/writer.py      Cast → v1/v2/v3 (v3 uses ms intervals with error diffusion; v1 stdout = deltas)
  core/transform.py   trim / speed / idle_limit (drop_before_start for plain transcripts)
  core/typewriter.py  typewriter(cast, cps): re-times output char by char; escape sequences are
                      atomic and ride with the next visible token; raises ShowreelError >200k tokens
  themes.py           built-in themes; ResolvedTheme.resolve() maps pyte colors ('default',
                      names like 'red', bare 6-hex like 'ff8700') → '#rrggbb'
  playback.py         Player: pyte replay, forward-only seek(t), state_hash for frame dedupe
  render.py           Renderer: PIL frames, even dimensions (libx264!), decorations:
                      radius (rounded mask), shadow (blurred RGBA), margin (+gradient via
                      1px-resize trick), watermark, chrome styles mac|rings|mac-right|rings-right,
                      render(player, show_cursor=…) drives cursor blink in frame loops
  exporters/
    video.py    rawvideo pipe → ffmpeg; formats mp4/mkv/mov/webm; chapters via ffmetadata
                (-map_metadata 1 -map_chapters 1, -write_tmcd 0 for mp4/mov); optional looping audio
    gif.py      palettegen stats_mode=diff + paletteuse dither=bayer diff_mode=rectangle; apng
    svg.py      SMIL-timed animated SVG: per-event row diff → <g opacity=0> + <set to=1
                begin=t fill=freeze>; every glyph gets an absolute x (x-list) so nothing
                re-flows — do NOT use textLength/dx (jitter / double-shift); cursor lives
                in per-event <animate> windows [t, t_next) and a final blinking cursor
                appears at duration; spaces with non-default bg must still paint;
                decorations = clipPath (radius), .panel drop-shadow, gradient margin, watermark.
                CSS keyframes are a known-bad approach here: Chrome drops/freeze-throttles
                thousands of tiny keyframe animations — SMIL is reliable.
    html.py     self-contained player: JSON payload + mini VT emulator (CUP/ED/EL/SGR/cursor hide);
                margin_fill sets page bg, cursor blinks via CSS
    text.py     strip_ansi, stream/screen/timed text, markdown, colored transcript, srt/vtt
    chapters.py marker/auto chapters → ffmetadata (escape = ; # \ ), youtube (0:00 intro), vtt, json, text
    convert.py  version conversion + transform options
    info.py     summary JSON (stable schema — do not rename keys casually)
    bundle.py   showreel all + manifest sha256; accepts every decoration option + typewriter_cps
  cli.py              argparse; keep stdout/stderr/exit-code contract; three shared parent
                      parsers: `common` (-q), `time` (--start/--end/--speed/--idle-limit/
                      --from-marker/--to-marker), `beauty` (--preset/--typewriter/--margin/
                      --margin-fill/--radius/--shadow/--watermark/--chrome-style/--cursor-blink).
                      _beauty_kwargs() resolves preset-vs-flag precedence (explicit wins);
                      _apply_marker_selection() folds marker names into start/end via
                      core.transform.marker_bounds (exact match, then unique prefix).
```

### Gotchas learned the hard way

- pyte 0.8.x returns 256/24-bit colors as **bare hex strings** (`'ff8700'`, no `#`) and basic colors as names — always resolve through `ResolvedTheme.resolve()`.
- v1 stdout records are **delta** times, v2 absolute, v3 intervals. Writers must convert back.
- Video frames must have even width/height (yuv420p) — Renderer rounds the whole canvas, decorations included.
- ffmpeg `paletteuse` takes `dither=bayer` and `bayer_scale=4` as **separate** options.
- ffmetadata escapes `= ; # \` and newlines with backslash; always set `TIMEBASE=1/1000`.
- MP4 muxer pads the first chapter to 0.0 (fine, YouTube-like) and adds a chapter `bin_data` stream — that is the chapter track, not a bug. MKV keeps exact times.
- YouTube chapters require the first entry at `0:00` — `youtube_list` prepends an "Intro".
- Trim keeps pre-`start` events (compressed to t=0) so screens/video open on the right state; transcripts use `drop_before_start=True` instead.
- typewriter: escape sequences must stay atomic and ride with the following visible char, or SGR styles leak into the wrong beat.
- Marker selection (`--from-marker/--to-marker`) folds into `args.start/args.end` before export; explicit `--start/--end` flags still win. Ambiguous prefixes raise with the available names.
- Beauty presets (`--preset pretty|clean|minimal`) only fill options the user left at `None` (flags use `default=None` + `BooleanOptionalAction` for `--shadow`), so explicit flags always win.
- `uvx ruff check src tests` + `uvx ruff format --check` run in CI — keep them green (config in pyproject: E4/E7/E9/F/I).

### Conventions

- No new runtime dependencies without strong justification.
- Every exporter function takes `cast: Cast` first and returns the output `Path` (or writes to stdout via the CLI layer).
- Errors raise `ShowreelError` with a message meant for the user; `cli.main` turns them into exit code 1.
- Tests live in `tests/` (`fixtures.py` builds synthetic casts; `test_render.py` auto-skips without ffmpeg). Add a test per bug fix.
- Demo cast for manual checks: `uv run showreel all tests/fixtures/demo.cast -o /tmp/demo-out`.
