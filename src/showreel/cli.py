"""showreel command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from . import ShowreelError, __version__

if TYPE_CHECKING:
    from .core.model import Cast
from .core.parser import parse
from .themes import THEME_NAMES

PROG = "showreel"


def _add_common_time(p: argparse.ArgumentParser) -> None:
    p.add_argument("--start", type=float, default=None, help="trim: start at N seconds")
    p.add_argument("--end", type=float, default=None, help="trim: end at N seconds")
    p.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier (>1 = faster)")
    p.add_argument(
        "--idle-limit", type=float, default=None, metavar="SEC", help="cap idle gaps at SEC seconds (compresses pauses)"
    )
    p.add_argument(
        "--from-marker", default=None, metavar="NAME", help="start at this marker (exact name or unique prefix)"
    )
    p.add_argument("--to-marker", default=None, metavar="NAME", help="end at this marker (exact name or unique prefix)")


def _add_theme(p: argparse.ArgumentParser, default: str = "auto") -> None:
    p.add_argument("--theme", default=default, help=f"theme: auto (from cast header), or: {', '.join(THEME_NAMES)}")


def _add_font(p: argparse.ArgumentParser) -> None:
    p.add_argument("--font", default=None, help="path to a monospace TTF/TTC font file")
    p.add_argument("--font-size", type=int, default=24, help="font size in px (default 24)")
    p.add_argument("--padding", type=int, default=16, help="padding around the terminal (default 16)")


def _add_chrome(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--chrome",
        nargs="?",
        const="default",
        default=None,
        metavar="TITLE",
        help="draw a window title bar (optional custom title)",
    )


def _auto_out(input_path: str, ext: str) -> str:
    stem = Path(input_path).stem
    stem = stem.removesuffix(".cast")
    return stem + ext


def _default_ext(args) -> str:
    return {
        "video": ".mp4",
        "gif": ".gif" if getattr(args, "format", "gif") == "gif" else ".png",
        "svg": ".svg",
        "html": ".html",
        "poster": ".png",
        "text": ".txt",
        "md": ".md",
        "html-transcript": ".transcript.html",
        "subs": f".{getattr(args, 'format', 'srt')}",
        "chapters": {
            "ffmetadata": ".ffmeta.txt",
            "youtube": ".youtube.txt",
            "vtt": ".vtt",
            "json": ".json",
            "text": ".chapters.txt",
        }[getattr(args, "format", "text")],
        "convert": f".v{getattr(args, 'to', 'v3')[1]}.cast",
    }[args.cmd]


def _require_out(args, ext: str) -> str:
    out = getattr(args, "out", None)
    return out or _auto_out(args.input, ext)


PRESETS: dict[str, dict] = {
    "pretty": dict(
        margin=48, margin_fill="#6B50FF,#241a66", radius=12, shadow=True, chrome_style="rings", cursor_blink=530
    ),
    "clean": dict(margin=0, radius=8, shadow=True, chrome_style="mac", cursor_blink=0),
    "minimal": dict(margin=0, radius=0, shadow=False, chrome_style="mac", cursor_blink=0),
}


def _beauty_kwargs(args) -> dict:
    """Resolve decoration options: explicit flags win, then the preset, then defaults."""
    preset = PRESETS.get(getattr(args, "preset", None) or "", {})

    def pick(name: str, fallback):
        v = getattr(args, name, None)
        return fallback if v is None else v

    return dict(
        margin=pick("margin", preset.get("margin", 0)),
        margin_fill=pick("margin_fill", preset.get("margin_fill")),
        radius=pick("radius", preset.get("radius", 0)),
        shadow=pick("shadow", preset.get("shadow", False)),
        watermark=pick("watermark", None),
        chrome_style=pick("chrome_style", preset.get("chrome_style", "mac")),
        cursor_blink=pick("cursor_blink", preset.get("cursor_blink", 0)),
    )


def _apply_marker_selection(args, cast) -> None:
    """Fold --from-marker/--to-marker into args.start/args.end (flags still win)."""
    fm = getattr(args, "from_marker", None)
    tm = getattr(args, "to_marker", None)
    if not fm and not tm:
        return
    from .core.transform import marker_bounds

    s, e = marker_bounds(cast, fm, tm)
    if s is not None and args.start is None:
        args.start = s
    if e is not None and args.end is None:
        args.end = e


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=PROG,
        description="Convert asciinema .cast recordings (asciicast v1/v2/v3) to SVG, MP4, WebM, "
        "MKV with chapters, GIF, APNG, HTML, transcripts and more.",
        epilog="""examples:
  showreel info demo.cast                     # metadata + markers, JSON
  showreel svg   demo.cast -o demo.svg        # self-contained animated SVG
  showreel video demo.cast -o demo.mp4        # h264 video with chapters
  showreel video demo.cast -o demo.mkv --chapters auto:30
  showreel gif   demo.cast -o demo.gif        # quality palette GIF
  showreel html  demo.cast -o demo.html       # self-contained offline player
  showreel text  demo.cast --mode timed       # [hh:mm:ss]-stamped transcript
  showreel all   demo.cast -o out/            # everything + manifest
  showreel convert demo.cast -o demo.v2.cast --to v2 --idle-limit 3""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-q", "--quiet", action="store_true", help="suppress progress/warnings")
    # vhs-inspired panel decorations + typewriter effect
    beauty = argparse.ArgumentParser(add_help=False)
    beauty.add_argument(
        "--preset",
        default=None,
        choices=["pretty", "clean", "minimal"],
        help="beauty preset: pretty (gradient margin, rings, shadow, radius, blink), "
        "clean (shadow + rounded), minimal (plain)",
    )
    beauty.add_argument(
        "--typewriter",
        nargs="?",
        const="40",
        default=None,
        metavar="CPS",
        help="re-time output to appear character by character at CPS chars/sec (default 40)",
    )
    beauty.add_argument("--margin", type=int, default=None, metavar="PX", help="outer margin around the terminal panel")
    beauty.add_argument(
        "--margin-fill", default=None, metavar="COLOR", help='margin color "#hex" or vertical gradient "#hex1,#hex2"'
    )
    beauty.add_argument("--radius", type=int, default=None, metavar="PX", help="rounded panel corners")
    beauty.add_argument(
        "--shadow",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="drop shadow behind the panel (--no-shadow to disable)",
    )
    beauty.add_argument("--watermark", default=None, metavar="TEXT", help="small corner watermark text")
    beauty.add_argument(
        "--chrome-style",
        default=None,
        choices=["mac", "rings", "mac-right", "rings-right"],
        help="traffic-light style and side (needs --chrome)",
    )
    beauty.add_argument(
        "--cursor-blink",
        type=int,
        default=None,
        metavar="MS",
        help="cursor blink period in ms (0 = steady; svg/html blink by default)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_input(p):
        p.add_argument("input", help=".cast file (v1/v2/v3, plain or .gz), '-' for stdin")

    # info
    p = sub.add_parser("info", parents=[common], help="recording summary as JSON (for humans and agents)")
    add_input(p)
    p.add_argument("-o", "--out", default=None, help="write JSON to file instead of stdout")

    # video
    p = sub.add_parser("video", parents=[common, beauty], help="export to mp4 / mkv / webm / mov (with chapters)")
    add_input(p)
    p.add_argument("-o", "--out", default=None, help="output file (extension picks the codec)")
    p.add_argument("--fps", type=int, default=20, help="frames per second (default 20)")
    p.add_argument(
        "--width", type=int, default=None, metavar="PX", help="target pixel width; derives the font size automatically"
    )
    p.add_argument("--crf", type=int, default=20, help="quality, lower = better (default 20)")
    p.add_argument(
        "--chapters", default="markers", metavar="MODE", help="chapters: markers (default), auto[:SECONDS], off"
    )
    p.add_argument("--audio", default=None, metavar="FILE", help="mux background audio (loops, trimmed to video)")
    p.add_argument("--cursor", choices=["block", "underline", "off"], default="block")
    p.add_argument("--bold-is-bright", action="store_true", help="render bold 8-color text with bright palette")
    _add_common_time(p)
    _add_theme(p)
    _add_font(p)
    _add_chrome(p)

    # gif
    p = sub.add_parser("gif", parents=[common, beauty], help="export to GIF or APNG (palette-optimized)")
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--format", choices=["gif", "apng", "webp"], default="gif")
    p.add_argument("--fps", type=int, default=12, help="frames per second (default 12)")
    p.add_argument("--width", type=int, default=None, help="target pixel width (picks font size)")
    p.add_argument("--max-colors", type=int, default=256)
    p.add_argument("--dither", default="bayer", help="paletteuse dither mode (bayer, sierra2_4a, none…)")
    p.add_argument("--bayer-scale", type=int, default=4, help="bayer_scale 0-5 when dither=bayer")
    p.add_argument("--hold", type=float, default=2.0, help="seconds to hold the last frame (default 2)")
    p.add_argument("--cursor", choices=["block", "underline", "off"], default="block")
    p.add_argument("--bold-is-bright", action="store_true")
    _add_common_time(p)
    _add_theme(p)
    _add_font(p)
    _add_chrome(p)

    # svg
    p = sub.add_parser(
        "svg", parents=[common, beauty], help="export to a self-contained animated SVG (CSS animation, no JS)"
    )
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--font-size", type=int, default=20, help="font size in px (default 20)")
    p.add_argument("--line-height", type=float, default=1.2)
    p.add_argument("--padding", type=int, default=16)
    p.add_argument("--no-cursor", action="store_true", help="omit the blinking cursor")
    _add_common_time(p)
    _add_theme(p)
    _add_chrome(p)

    # html
    p = sub.add_parser("html", parents=[common, beauty], help="export to a self-contained offline HTML player")
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--title", default=None, help="player title")
    p.add_argument("--font-size", type=int, default=16)
    p.add_argument("--autoplay", action="store_true")
    _add_common_time(p)
    _add_theme(p)

    # poster
    p = sub.add_parser("poster", parents=[common, beauty], help="export a single frame as PNG")
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--at", type=float, default=None, help="time position (default: final screen)")
    p.add_argument("--width", type=int, default=None, metavar="PX", help="target pixel width")
    p.add_argument("--cursor", choices=["block", "underline", "off"], default="block")
    p.add_argument("--bold-is-bright", action="store_true")
    _add_theme(p)
    _add_font(p)
    _add_chrome(p)

    # text
    p = sub.add_parser("text", parents=[common], help="export transcript / final screen as text")
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument(
        "--mode",
        choices=["stream", "screen", "timed"],
        default="stream",
        help="stream: raw output; screen: final screen; timed: [hh:mm:ss] prefixes",
    )
    _add_common_time(p)

    # md
    p = sub.add_parser("md", parents=[common], help="export a Markdown page (front matter + final screen + chapters)")
    add_input(p)
    p.add_argument("-o", "--out", default=None)

    # html-transcript
    p = sub.add_parser(
        "html-transcript", parents=[common], help="colored HTML transcript (every screen change, timestamped)"
    )
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    _add_common_time(p)
    _add_theme(p)

    # subs
    p = sub.add_parser("subs", parents=[common], help="export transcript as SRT/VTT subtitles (searchable captions)")
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--format", choices=["srt", "vtt"], default="srt")
    _add_common_time(p)

    # chapters
    p = sub.add_parser("chapters", parents=[common], help="export chapters from marker events")
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--format", choices=["ffmetadata", "youtube", "vtt", "json", "text"], default="text")
    p.add_argument(
        "--auto", type=float, default=None, metavar="SEC", help="ignore markers, make a chapter every SEC seconds"
    )

    # convert
    p = sub.add_parser("convert", parents=[common], help="convert between asciicast v1/v2/v3 (+ trim/speed/idle)")
    add_input(p)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--to", choices=["v2", "v3", "v1"], default="v3")
    p.add_argument("--strip-input", action="store_true", help="drop 'i' (keystroke) events")
    p.add_argument("--strip-markers", action="store_true", help="drop 'm' (marker) events")
    p.add_argument("--gzip", action="store_true", help="gzip the output")
    _add_common_time(p)

    # all
    p = sub.add_parser(
        "all", parents=[common, beauty], help="export a full bundle (video/gif/svg/html/text/data) + manifest"
    )
    add_input(p)
    p.add_argument("-o", "--out", required=True, help="output directory")
    p.add_argument("--stem", default=None, help="base name for generated files (default: directory name)")
    p.add_argument(
        "--groups",
        default="video,animated,svg,web,text,data",
        help="comma-separated subset: video,animated,svg,web,text,data",
    )
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--cursor", choices=["block", "underline", "off"], default="block")
    p.add_argument("--bold-is-bright", action="store_true")
    _add_common_time(p)
    _add_theme(p)
    _add_font(p)
    _add_chrome(p)

    # join
    p = sub.add_parser("join", parents=[common], help="concatenate several .cast files into one")
    p.add_argument("inputs", nargs="+", help="two or more .cast files (v1/v2/v3)")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--gap", type=float, default=0.5, help="seconds between recordings (default 0.5)")
    p.add_argument("--to", choices=["v2", "v3"], default="v3", dest="to_format")

    # cut
    p = sub.add_parser("cut", parents=[common], help="remove time ranges from a recording")
    add_input(p)
    p.add_argument("-o", "--out", required=True)
    p.add_argument(
        "--remove",
        action="append",
        default=[],
        metavar="START-END",
        help="range to remove, seconds or hh:mm:ss (repeatable)",
    )

    # script
    p = sub.add_parser(
        "script",
        parents=[common, beauty],
        help="turn a showreel script (Type/Run/Sleep/Marker) into a deterministic .cast",
    )
    p.add_argument("input", help="script file (see docs)")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--cols", type=int, default=80)
    p.add_argument("--rows", type=int, default=24)
    p.add_argument("--title", default="showreel demo")

    # themes
    p = sub.add_parser("themes", parents=[common], help="import / list custom themes")
    tsp = p.add_subparsers(dest="themes_cmd", required=True)
    imp = tsp.add_parser(
        "import", help="import a theme file (Windows Terminal json, generic json, iTerm2 .itermcolors)"
    )
    imp.add_argument("file", help="theme file")
    imp.add_argument("--name", required=True, help="theme name to save under")
    tsp.add_parser("list", help="list imported themes")

    # mcp
    sub.add_parser("mcp", parents=[common], help="run the Model Context Protocol server on stdio (for AI agents)")

    return ap


def _read_input(args) -> Cast:
    if args.input == "-":
        import tempfile

        data = sys.stdin.buffer.read()
        with tempfile.NamedTemporaryFile(suffix=".cast", delete=False) as tmp:
            tmp.write(data)
        return parse(tmp.name)
    return parse(args.input)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd in ("mcp", "themes", "join"):
            cast = None  # these commands read their own inputs
        else:
            cast = _read_input(args)
        if cast is not None:
            _apply_marker_selection(args, cast)
            cps = getattr(args, "typewriter", None)
            if cps:
                from .core.typewriter import typewriter

                cast = typewriter(cast, cps=float(cps))

        if args.cmd == "info":
            from .exporters.info import summary, write_summary

            s = summary(cast, source=args.input if args.input != "-" else "<stdin>")
            if args.out:
                write_summary(cast, args.out, source=args.input)
                print(f"showreel: wrote {args.out}", file=sys.stderr)
            else:
                print(json.dumps(s, indent=2))
            return 0

        if args.cmd == "video":
            from .exporters.video import export_video

            out = _require_out(args, ".mp4")
            fmt = Path(out).suffix.lstrip(".") or "mp4"
            export_video(
                cast,
                out,
                fmt=fmt,
                fps=args.fps,
                speed=args.speed,
                start=args.start,
                end=args.end,
                idle_limit=args.idle_limit,
                crf=args.crf,
                theme=args.theme,
                font=args.font,
                font_size=args.font_size,
                padding=args.padding,
                cursor=args.cursor,
                chrome_title=args.chrome,
                width=args.width,
                audio=args.audio,
                chapters=args.chapters,
                bold_is_bright=args.bold_is_bright,
                **_beauty_kwargs(args),
                quiet=args.quiet,
            )
            print(out)
        elif args.cmd == "gif":
            from .exporters.gif import export_gif

            out = _require_out(args, ".gif")
            export_gif(
                cast,
                out,
                fmt=args.format,
                fps=args.fps,
                speed=args.speed,
                start=args.start,
                end=args.end,
                idle_limit=args.idle_limit,
                width=args.width,
                theme=args.theme,
                font=args.font,
                max_colors=args.max_colors,
                dither=args.dither,
                bayer_scale=args.bayer_scale,
                hold=args.hold,
                cursor=args.cursor,
                chrome_title=args.chrome,
                bold_is_bright=args.bold_is_bright,
                **_beauty_kwargs(args),
                quiet=args.quiet,
            )
            print(out)
        elif args.cmd == "svg":
            from .exporters.svg import export_svg

            out = _require_out(args, ".svg")
            svg_beauty = _beauty_kwargs(args)
            export_svg(
                cast,
                out,
                speed=args.speed,
                start=args.start,
                end=args.end,
                idle_limit=args.idle_limit,
                theme=args.theme,
                font_size=args.font_size,
                padding=args.padding,
                cursor=not args.no_cursor,
                chrome_title=args.chrome,
                line_height=args.line_height,
                cursor_blink=svg_beauty.pop("cursor_blink") or 1200,
                **svg_beauty,
            )
            print(out)
        elif args.cmd == "html":
            from .exporters.html import export_html

            out = _require_out(args, ".html")
            beauty = _beauty_kwargs(args)
            export_html(
                cast,
                out,
                title=args.title,
                theme=args.theme,
                speed=args.speed,
                start=args.start,
                end=args.end,
                idle_limit=args.idle_limit,
                autoplay=args.autoplay,
                font_size=args.font_size,
                margin_fill=beauty["margin_fill"],
                cursor_blink=beauty["cursor_blink"] or 1200,
            )
            print(out)
        elif args.cmd == "poster":
            from .exporters.poster import export_poster

            out = _require_out(args, ".png")
            poster_beauty = _beauty_kwargs(args)
            poster_beauty.pop("cursor_blink")
            export_poster(
                cast,
                out,
                at=args.at,
                theme=args.theme,
                font=args.font,
                font_size=args.font_size,
                padding=args.padding,
                width=args.width,
                cursor=args.cursor,
                chrome_title=args.chrome,
                bold_is_bright=args.bold_is_bright,
                **poster_beauty,
            )

        def _text_like(producer, default_ext: str) -> None:
            """Run a text producer with -o FILE or print the result to stdout."""
            import tempfile

            if args.out:
                producer(cast, args.out)
                print(args.out)
            else:
                tmp = Path(tempfile.mkstemp(suffix=default_ext)[1])
                producer(cast, tmp)
                sys.stdout.write(tmp.read_text(encoding="utf-8"))
                tmp.unlink()

        if args.cmd == "text":
            from .exporters.text import write_text

            _text_like(
                lambda c, p: write_text(
                    c, p, mode=args.mode, speed=args.speed, start=args.start, end=args.end, idle_limit=args.idle_limit
                ),
                ".txt",
            )
        elif args.cmd == "md":
            from .exporters.text import write_markdown

            _text_like(lambda c, p: write_markdown(c, p, source_name=args.input), ".md")
        elif args.cmd == "html-transcript":
            from .exporters.text import write_transcript_html

            out = _require_out(args, ".transcript.html")
            write_transcript_html(cast, out, theme=args.theme, speed=args.speed, start=args.start, end=args.end)
            print(out)
        elif args.cmd == "subs":
            from .exporters.text import write_subtitles

            _text_like(
                lambda c, p: write_subtitles(c, p, fmt=args.format, speed=args.speed, start=args.start, end=args.end),
                f".{args.format}",
            )
        elif args.cmd == "chapters":
            from .exporters.chapters import (
                chapters_json,
                chapters_text,
                chapters_vtt,
                extract_chapters,
                ffmetadata,
                youtube_list,
            )

            chapters = extract_chapters(cast, auto=args.auto)
            if args.format == "ffmetadata":
                content = ffmetadata(chapters, title=cast.header.title)
            elif args.format == "youtube":
                content = youtube_list(chapters)
            elif args.format == "vtt":
                content = chapters_vtt(chapters)
            elif args.format == "json":
                content = chapters_json(chapters)
            else:
                content = chapters_text(chapters)
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(content, encoding="utf-8")
                print(args.out)
            else:
                sys.stdout.write(content)
        elif args.cmd == "convert":
            from .exporters.convert import convert

            to = int(args.to[1])
            default_ext = f".v{to}.cast"
            out = _require_out(args, default_ext)
            convert(
                cast,
                out,
                to=to,
                speed=args.speed,
                start=args.start,
                end=args.end,
                idle_limit=args.idle_limit,
                strip_input=args.strip_input,
                strip_markers=args.strip_markers,
                gzip_out=args.gzip,
            )
            print(out)
        elif args.cmd == "join":
            from .core.ops import join

            casts = [parse(src) for src in args.inputs]
            merged = join(casts, gap=args.gap)
            to = int(args.to_format[1])
            merged.header.version = to
            from .core.writer import write as _write

            _write(merged, args.out, version=to)
            print(args.out)
        elif args.cmd == "cut":
            from .core.ops import cut, parse_ranges
            from .exporters.convert import convert

            ranges = parse_ranges(args.remove)
            cut_cast = cut(cast, ranges)
            out = args.out
            cut_cast.header.version = 3
            convert(cut_cast, out, to=3)
            print(out)
        elif args.cmd == "script":
            from .core.script import script_to_cast

            out = args.out
            cast = script_to_cast(args.input, cols=args.cols, rows=args.rows)
            cast.header.title = args.title
            from .core.writer import write as _w

            _w(cast, out, version=3)
            print(out)
        elif args.cmd == "themes":
            from .core.themes_io import import_theme, list_user_themes

            if args.themes_cmd == "import":
                saved = import_theme(Path(args.file), args.name)
                print(f"theme '{args.name}' saved to {saved}")
            else:
                themes = list_user_themes()
                print("\n".join(themes) if themes else "no user themes imported yet")
        elif args.cmd == "mcp":
            from .mcp import serve

            sys.exit(serve())
        elif args.cmd == "all":
            from .exporters.bundle import export_bundle

            export_bundle(
                cast,
                args.out,
                stem=args.stem,
                groups=[g.strip() for g in args.groups.split(",") if g.strip()],
                speed=args.speed,
                idle_limit=args.idle_limit,
                fps=args.fps,
                theme=args.theme,
                font=args.font,
                font_size=args.font_size,
                cursor=args.cursor,
                bold_is_bright=args.bold_is_bright,
                typewriter_cps=args.typewriter,
                **_beauty_kwargs(args),
                quiet=args.quiet,
            )

        return 0
    except ShowreelError as e:
        print(f"{PROG}: error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"{PROG}: error: {e}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
