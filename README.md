<div align="center">

# 🎬 castkit

**One CLI to turn terminal recordings into everything.**

[![CI](https://github.com/forcewake/castkit/actions/workflows/ci.yml/badge.svg)](https://github.com/forcewake/castkit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/castkit)](https://pypi.org/project/castkit/)
[![Python](https://img.shields.io/pypi/pyversions/castkit)](https://pypi.org/project/castkit/)
[![License](https://img.shields.io/github/license/forcewake/castkit)](LICENSE)
[![Stars](https://img.shields.io/github/stars/forcewake/castkit?style=flat)](https://github.com/forcewake/castkit/stargazers)

Reads asciicast **v1 / v2 / v3** (including asciinema 3.x recordings that most tools can't touch).
Writes animated **SVG**, **MP4 / WebM / MKV with real chapters**, **GIF / APNG**, a self-contained
**HTML player**, transcripts, subtitles and more — with vhs-style beauty presets on top.

```bash
uv tool install castkit
```

**This is not a video and not a GIF — it's a single animated SVG.** It is typing itself
character by character right now: watch the loading bar fill in place and the cursor run
ahead of the text. One `.svg` file, zero JavaScript, exported with one command.

<img src="examples/demo.svg" alt="Animated typewriter SVG: a production-deploy session typing itself character by character inside a decorated terminal window with ring traffic lights, purple gradient margin, drop shadow and a live cursor" width="800">

```bash
castkit svg demo.cast -o demo.svg --preset pretty --chrome "castkit demo" \
  --watermark "made with castkit" --typewriter 50 --cursor-blink 530
```

Prefer pixels? The same recording as a GIF:

<p>
<img src="assets/demo.gif" alt="The same deploy session rendered as a GIF with window chrome, gradient margin and rounded corners" width="620">
</p>

**Built for humans and AI agents.** Every text command prints to stdout, every file command
prints its path, `castkit info` gives stable JSON — and ships with a
[skill](skills/castkit/SKILL.md) that teaches coding agents how to drive it.

</div>

## Why

You recorded your terminal with [asciinema](https://asciinema.org) — a perfect `.cast` file.
Now what? asciinema itself has no SVG/video export, and the existing converters are stuck in the past:

| Tool | Status | Reads v3 | SVG | Video | Chapters |
|---|---|:-:|:-:|:-:|:-:|
| **castkit** | ✅ active | ✅ | ✅ | ✅ mp4/webm/mkv/mov | ✅ real (mkv/mp4) + YouTube/VTT/JSON |
| [agg](https://github.com/asciinema/agg) | ✅ official | ✅ | ❌ | ❌ (gif only) | ❌ |
| [svg-term-cli](https://github.com/marionebl/svg-term-cli) | 😴 2017 | ❌ v2-only | ✅ | ❌ | ❌ |
| [termtosvg](https://github.com/nbedos/termtosvg) | 🗄️ archived | ❌ | ✅ | ❌ | ❌ |
| [terminalizer](https://github.com/faressoft/terminalizer) | 😴 dormant | ❌ | ❌ | ❌ | ❌ |

castkit keeps the good ideas (agg's knob set, svg-term's CSS animation, termtosvg's window frames,
vhs's aesthetics) in one dependency-light Python tool.

## Install

```bash
uv tool install castkit        # fast
pipx install castkit           # classic
pip install castkit            # boring
```

Needs Python ≥ 3.10. Video/GIF/APNG export needs [`ffmpeg`](https://ffmpeg.org) on `PATH`
(`brew install ffmpeg` / `apt install ffmpeg`).

## Quick start

```bash
asciinema rec demo.cast              # record something

castkit info demo.cast               # metadata + markers as JSON
castkit svg demo.cast                # → demo.svg   self-contained animated SVG
castkit video demo.cast              # → demo.mp4   H.264 with chapters
castkit gif demo.cast                # → demo.gif   palette-optimized, loops
castkit html demo.cast               # → demo.html  offline player, no CDN
castkit all demo.cast -o out/        # → everything + manifest.json
```

Text commands (`text`, `md`, `subs`, `chapters`) print **content to stdout** unless you pass `-o`;
file commands print the **output path**. Progress goes to stderr, exit codes are 0/1 — pipe freely.

## Commands

| Command | Output | Highlights |
|---|---|---|
| `info` | JSON | duration, markers, event stats, env, first prompt — the agent entrypoint |
| `video` | mp4 / mkv / mov / webm | **chapters embedded from marker events**, `--audio` background music, `--crf`, `--fps` |
| `gif` | gif / apng | two-pass palette (`stats_mode=diff`, `diff_mode=rectangle`), `--hold` last frame |
| `svg` | animated SVG | SMIL-timed, no JS, per-glyph grid alignment — embed anywhere |
| `html` | offline player | embedded mini terminal emulator, seek bar, speed 0.5–8×, marker buttons |
| `poster` | PNG still | any `--at SECONDS`, final screen by default |
| `text` | txt | `stream` (raw), `screen` (final), **`timed`** (`[hh:mm:ss]` prefixes — feed an LLM) |
| `md` | Markdown | front matter + final screen + chapter list |
| `html-transcript` | colored HTML | every screen change, timestamped |
| `subs` | srt / vtt | transcript as captions — makes recordings searchable |
| `chapters` | ffmetadata / youtube / vtt / json / text | from markers or `--auto 30` |
| `convert` | asciicast v1/v2/v3 | version conversion + trim/speed/idle/gzip, `--strip-input` |
| `all` | directory | full bundle + `manifest.json` with sha256 + `README.txt` |

## Examples — one recording, every format

Everything below lives in [`examples/`](examples/) and was produced by **two commands** (see
[examples/README.md](examples/README.md) for the exact ones). The animated SVG at the top of
this page is [`examples/demo.svg`](examples/demo.svg) — the same file your terminal exports.

Then compare the same recording across formats:

| Watch | Read | Data |
|---|---|---|
| [demo.mp4](examples/demo.mp4) · [demo.mkv](examples/demo.mkv) (chapters!) · [demo.webm](examples/demo.webm) · [demo.apng](examples/demo.apng) | [demo.txt](examples/demo.txt) · [demo.timed.txt](examples/demo.timed.txt) · [demo.md](examples/demo.md) · [demo.transcript.html](examples/demo.transcript.html) | [demo.v3.cast](examples/demo.v3.cast) · [demo.v2.cast](examples/demo.v2.cast) · [demo.summary.json](examples/demo.summary.json) |
| [demo.html](examples/demo.html) (offline player) · [demo.poster.png](examples/demo.poster.png) | [demo.srt](examples/demo.srt) · [demo.transcript.vtt](examples/demo.transcript.vtt) | [demo.chapters.json](examples/demo.chapters.json) · [.youtube.txt](examples/demo.chapters.youtube.txt) · [.ffmeta.txt](examples/demo.chapters.ffmeta.txt) · [manifest.json](examples/manifest.json) |

### Time control (every command)

```bash
--start 10 --end 25   # trim; pre-start history still shapes the first frame
--from-marker build --to-marker deploy   # agg-style marker selection (exact or unique prefix)
--speed 2             # faster playback
--idle-limit 3        # compress pauses longer than 3s
```

## Make it beautiful

One flag for the full look, or compose your own:

```bash
castkit gif demo.cast -o demo.gif --preset pretty --chrome "deploy" --watermark "@you"
```

<img src="assets/demo-poster.png" alt="A decorated terminal frame: window bar with ring traffic lights, rounded corners, drop shadow, purple gradient margin and a watermark" width="720">

| Option | What it does |
|---|---|
| `--preset pretty / clean / minimal` | curated defaults; explicit flags always win |
| `--theme` | `dracula`, `nord`, `monokai`, `gruvbox-dark`, `solarized-dark/light`, `tango-light`, `asciinema`, or `auto` (from the cast header) |
| `--chrome "title"` + `--chrome-style mac/rings/right` | window bar with traffic lights (vhs `WindowBar`) |
| `--margin N --margin-fill "#6B50FF,#241a66"` | outer margin, solid or vertical gradient (vhs `Margin/MarginFill`) |
| `--radius 12` | rounded corners (vhs `BorderRadius`) |
| `--shadow` | drop shadow behind the panel |
| `--watermark "@you"` | corner watermark |
| `--typewriter [CPS]` | re-time output character by character (default 40 chars/sec) |
| `--cursor-blink 530` | blinking cursor in rendered frames |
| `--font /path/Mono.ttf --font-size 24 --padding 16` | typography & spacing |
| `--cursor block/underline/off --bold-is-bright` | cursor & color quirks |

## Chapters, properly

Touch the `m` key during `asciinema rec` (v3) and castkit turns markers into:

- **Matroska/MOV chapters** inside MKV/MP4 — VLC, mpv and IINA show them, seeking is instant;
- **YouTube chapter lists** (`0:00` entry added automatically, as YouTube requires);
- **WebVTT chapter tracks** and JSON;
- **seek buttons** in the exported HTML player.

No markers? `--chapters auto:30` (video) or `chapters --auto 30` cuts one every 30 seconds.

## For AI agents 🤖

castkit ships with a ready-made skill — copy [`skills/castkit/SKILL.md`](skills/castkit/SKILL.md)
into your agent's skill directory (or point it at this repo) and it will know how to:
convert recordings, extract timestamped transcripts for context, cut clips by marker,
and embed demos in docs. Highlights agents rely on:

```bash
castkit info rec.cast                 # stable JSON schema
castkit text rec.cast --mode timed    # [hh:mm:ss] ANSI-free transcript on stdout
castkit all rec.cast -o out/          # deterministic names + sha256 manifest
cat rec.cast | castkit gif - -o r.gif # stdin works
```

Exit codes 0/1, progress on stderr, paths/content on stdout. The full contract lives in
[AGENTS.md](AGENTS.md) — for building castkit *and* for driving it.

## How the SVG works

Each output event is replayed through the [pyte](https://github.com/selectel/pyte) terminal
emulator; the screen is diffed row by row, and every changed row becomes a `<g>` group —
background `<rect>` plus styled runs — popped in by a declarative SMIL `<set>` at the event's
timestamp. Every glyph gets an absolute x position on the cell grid, so nothing shifts or
jitters regardless of the viewer's fonts. The cursor is a live element: it follows the typing
inside per-event visibility windows, then settles at the prompt and blinks forever. Later rows
paint over earlier ones, so history accumulates like a real terminal. One file, zero JavaScript,
plays anywhere SVG animates — browsers, `<img>` tags, README embeds.

## Limitations

- The emulator keeps the header's terminal size; mid-recording resizes are recorded but not re-flowed.
- Full-screen TUI apps (vim, htop) can render with artifacts — pyte doesn't swap the alternate screen buffer.
- WebM carries no chapters (not in the spec) — use MKV/MP4.
- No emoji font fallback in rendered frames yet.

## Development

```bash
git clone https://github.com/forcewake/castkit && cd castkit
uv sync                # deps + editable install
uv run pytest          # test suite (ffmpeg tests auto-skip)
```

Architecture and hard-won gotchas are documented in [AGENTS.md](AGENTS.md).
PRs welcome — especially new themes and output formats.

## Acknowledgements

- [asciinema](https://asciinema.org) by Marcin Kulik — the recording format and the reference [agg](https://github.com/asciinema/agg)
- [pyte](https://github.com/selectel/pyte) — the terminal emulator core
- [vhs](https://github.com/charmbracelet/vhs) — the aesthetics bar this project steals from, openly

## License

[MIT](LICENSE) © Pavel Nasovich

<div align="center">

**If castkit saved you an afternoon, drop a ⭐ — it helps others find it.**

</div>
