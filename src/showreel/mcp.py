"""MCP server: expose showreel to AI agents over stdio (Model Context Protocol).

Speaks JSON-RPC 2.0 line-delimited on stdin/stdout with zero dependencies:
initialize, tools/list, tools/call. Run with `showreel mcp`.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from . import ShowreelError, __version__
from .core.fetch import download, is_url
from .core.parser import parse
from .exporters.info import summary

__all__ = ["serve", "TOOLS"]

VIDEO_FORMATS = ("mp4", "webm", "mkv", "mov")
IMAGE_FORMATS = ("gif", "apng", "webp")


def _resolve(source: str) -> str:
    if is_url(source):
        return download(source)
    if not Path(source).exists():
        raise ShowreelError(f"no such file: {source}")
    return source


def _tool_info(args: dict) -> str:
    cast = parse(_resolve(args["source"]))
    return json.dumps(summary(cast, source=args["source"]), indent=2)


def _tool_transcript(args: dict) -> str:
    cast = parse(_resolve(args["source"]))
    mode = args.get("mode", "timed")
    from .core.transform import transform

    tcast = transform(cast, speed=args.get("speed", 1.0), idle_limit=args.get("idle_limit"), drop_before_start=True)
    if mode == "screen":
        from .playback import Player

        player = Player(tcast)
        player.seek(tcast.duration)
        return "\n".join(line.rstrip() for line in player.display())
    from .exporters.text import strip_ansi

    out = []
    for e in tcast.events:
        if e.etype != "o":
            continue
        text = strip_ansi(e.data)
        if not text:
            continue
        h, rem = divmod(int(e.time), 3600)
        m, s = divmod(rem, 60)
        out.append(f"[{h:02d}:{m:02d}:{s:02d}] {text}" if mode == "timed" else text)
    return "\n".join(out)


def _tool_export(args: dict) -> str:
    """Export to any supported format; returns the written file path."""
    from .exporters.gif import export_gif
    from .exporters.poster import export_poster
    from .exporters.video import export_video

    cast = parse(_resolve(args["source"]))
    out = Path(args.get("out") or Path(tempfile.mkdtemp()) / "output")
    fmt = args.get("format", "mp4").lower()
    beauty = {k: args[k] for k in ("theme", "preset") if k in args}
    common = dict(
        speed=args.get("speed", 1.0),
        start=args.get("start"),
        end=args.get("end"),
        idle_limit=args.get("idle_limit"),
        **beauty,
    )
    if fmt in VIDEO_FORMATS:
        export_video(cast, out.with_suffix(f".{fmt}"), fmt=fmt, chapters=args.get("chapters", "markers"), **common)
    elif fmt in IMAGE_FORMATS:
        export_gif(cast, out.with_suffix(f".{fmt}"), fmt=fmt, **common)
    elif fmt == "png":
        export_poster(cast, out.with_suffix(".png"), **common)
    else:
        raise ShowreelError(f"unsupported export format '{fmt}'")
    return str(out.with_suffix(f".{fmt}"))


def _tool_subtitles(args: dict) -> str:
    from .exporters.text import write_subtitles

    cast = parse(_resolve(args["source"]))
    out = Path(tempfile.mkstemp(suffix=f".{args.get('format', 'srt')}")[1])
    write_subtitles(cast, out, fmt=args.get("format", "srt"))
    return out.read_text(encoding="utf-8")


TOOLS = [
    {
        "name": "showreel_info",
        "description": "Summarize an asciinema .cast recording (any version): duration, markers, event stats, terminal size.",
        "inputSchema": {
            "type": "object",
            "required": ["source"],
            "properties": {"source": {"type": "string", "description": "path, URL or asciinema.org link"}},
        },
    },
    {
        "name": "showreel_transcript",
        "description": "ANSI-free transcript of the recording. Modes: timed ([hh:mm:ss] prefixes), stream, screen (final screen).",
        "inputSchema": {
            "type": "object",
            "required": ["source"],
            "properties": {
                "source": {"type": "string"},
                "mode": {"type": "string", "enum": ["timed", "stream", "screen"]},
                "speed": {"type": "number"},
                "idle_limit": {"type": "number"},
            },
        },
    },
    {
        "name": "showreel_export",
        "description": "Render a recording to mp4/webm/mkv/mov (with chapters), gif/apng/webp or a png poster. Returns the output path.",
        "inputSchema": {
            "type": "object",
            "required": ["source"],
            "properties": {
                "source": {"type": "string"},
                "format": {"type": "string", "enum": ["mp4", "webm", "mkv", "mov", "gif", "apng", "webp", "png"]},
                "out": {"type": "string"},
                "theme": {"type": "string"},
                "preset": {"type": "string"},
                "speed": {"type": "number"},
                "start": {"type": "number"},
                "end": {"type": "number"},
                "idle_limit": {"type": "number"},
                "chapters": {"type": "string"},
            },
        },
    },
    {
        "name": "showreel_subtitles",
        "description": "Transcript as SRT/VTT caption text.",
        "inputSchema": {
            "type": "object",
            "required": ["source"],
            "properties": {"source": {"type": "string"}, "format": {"type": "string", "enum": ["srt", "vtt"]}},
        },
    },
]

_HANDLERS = {
    "showreel_info": _tool_info,
    "showreel_transcript": _tool_transcript,
    "showreel_export": _tool_export,
    "showreel_subtitles": _tool_subtitles,
}


def _reply(msg_id, result=None, error=None) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, **({"result": result} if error is None else {"error": error})}


def handle(msg: dict) -> dict | None:
    method = msg.get("method", "")
    if method == "initialize":
        return _reply(
            msg.get("id"),
            {
                "protocolVersion": msg.get("params", {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "showreel", "version": __version__},
            },
        )
    if method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return _reply(msg.get("id"), {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name", "")
        if name not in _HANDLERS:
            return _reply(msg.get("id"), error={"code": -32602, "message": f"unknown tool '{name}'"})
        try:
            text = _HANDLERS[name](params.get("arguments") or {})
            return _reply(msg.get("id"), {"content": [{"type": "text", "text": text}]})
        except ShowreelError as e:
            return _reply(msg.get("id"), {"content": [{"type": "text", "text": str(e)}], "isError": True})
    return _reply(msg.get("id"), error={"code": -32601, "message": f"method not found: {method}"})


def serve() -> int:
    """Read line-delimited JSON-RPC from stdin, write replies to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=True) + "\n")
            sys.stdout.flush()
    return 0
