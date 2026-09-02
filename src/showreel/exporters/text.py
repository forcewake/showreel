"""Text outputs: plain transcript, final screen, Markdown, colored HTML transcript, SRT/VTT subtitles."""

from __future__ import annotations

import re
from pathlib import Path

from .. import ShowreelError
from ..core.model import Cast
from ..core.transform import transform
from ..playback import Player
from ..themes import resolve_theme

__all__ = ["strip_ansi", "write_markdown", "write_subtitles", "write_text", "write_transcript_html"]

_ANSI = re.compile(
    r"\x1b\[[0-9;?]*[A-Za-z]"  # CSI sequences
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences
    r"|\x1b[PX^_][^\x1b]*\x1b\\"  # DCS/SOS/PM/APC
    r"|\x1b[@-Z\\-_]"  # other 2-byte escapes
)


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def _ts(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_text(
    cast: Cast,
    out: str | Path,
    mode: str = "stream",  # stream | screen | timed
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    idle_limit: float | None = None,
) -> Path:
    """stream: raw output with ANSI stripped; screen: final screen contents;
    timed: stream with [HH:MM:SS] prefixes per event (great for AI analysis)."""
    tcast = transform(cast, start=start, end=end, speed=speed, idle_limit=idle_limit, drop_before_start=True)
    if mode == "screen":
        player = Player(tcast)
        player.seek(tcast.duration)
        lines = [line.rstrip() for line in player.display()]
        while lines and not lines[-1]:
            lines.pop()
        content = "\n".join(lines) + "\n"
    elif mode == "timed":
        lines = []
        for e in tcast.events:
            if e.etype != "o":
                continue
            text = strip_ansi(e.data)
            if not text:
                continue
            prefix = f"[{_ts(e.time)}] "
            first, *rest = text.split("\n")
            lines.append(prefix + first)
            lines.extend(rest)
        content = "\n".join(lines) + "\n"
    else:  # stream: concatenate raw output, keep original newlines
        content = "".join(strip_ansi(e.data) for e in tcast.events if e.etype == "o")

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def write_markdown(
    cast: Cast,
    out: str | Path,
    source_name: str | None = None,
) -> Path:
    h = cast.header
    duration = cast.duration
    meta = [
        "---",
        f'title: "{(h.title or Path(source_name or "recording").stem)}"',
        f"duration: {duration:.3f}",
        f'size: "{h.term.cols}x{h.term.rows}"',
    ]
    if h.timestamp:
        import datetime

        meta.append("recorded: " + datetime.datetime.fromtimestamp(h.timestamp, datetime.timezone.utc).isoformat())
    if h.command:
        meta.append(f'command: "{h.command}"')
    if h.tags:
        meta.append("tags: [" + ", ".join(h.tags) + "]")
    markers = cast.markers()
    if markers:
        meta.append("chapters:")
        meta += [f'  - "{label}" @ {_ts(t)}' for t, label in markers]
    meta.append("---")

    body = ["# Terminal recording\n", "```text"]
    player = Player(cast)
    player.seek(cast.duration)
    body += [line.rstrip() for line in player.display()]
    while body and body[-1] == "":
        body.pop()
    body.append("```")
    if markers:
        body.append("\n## Chapters\n")
        for i, (t, label) in enumerate(markers, 1):
            end = markers[i][0] if i < len(markers) else duration
            body.append(f"{i}. **{label}** — {_ts(t)}–{_ts(end)}")

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(meta) + "\n\n" + "\n".join(body) + "\n", encoding="utf-8")
    return out_path


def write_transcript_html(
    cast: Cast,
    out: str | Path,
    theme: str = "auto",
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
) -> Path:
    """Colored HTML transcript: rows as they appeared, each stamped with its time."""
    tcast = transform(cast, start=start, end=end, speed=speed)
    resolved = resolve_theme(cast, theme)
    player = Player(tcast)
    rows = player.rows

    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def row_html(y: int) -> str:
        buf = player.screen.buffer.get(y, {})
        spans = []
        for x in range(player.cols):
            ch = buf.get(x)
            if ch is None:
                continue
            fg = resolved.resolve(ch.fg, resolved.fg)
            bg = resolved.resolve(ch.bg, resolved.bg)
            style = f"color:{fg};background:{bg}"
            if ch.bold:
                style += ";font-weight:bold"
            if ch.italics:
                style += ";font-style:italic"
            if ch.underscore:
                style += ";text-decoration:underline"
            spans.append(f'<span style="{style}">{esc(ch.data)}</span>')
        return "".join(spans)

    entries = []
    prev = [None] * rows
    for e in tcast.events:
        if e.etype != "o":
            continue
        player.seek(e.time)
        for y in range(rows):
            row = row_html(y)
            if row != prev[y]:
                prev[y] = row
                entries.append(f'<div class="row"><span class="t">{_ts(e.time)}</span><pre>{row}</pre></div>')
    final = "\n".join(f"<pre>{row_html(y)}</pre>" for y in range(rows))

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Transcript</title>
<style>
body {{ background:{resolved.bg}; color:{resolved.fg}; font-family:monospace; margin:2rem; }}
.row {{ display:flex; gap:1em; align-items:flex-start; }}
.t {{ color:#8888aa; min-width:9ch; text-align:right; user-select:none; }}
pre {{ margin:0; white-space:pre; }}
h2 {{ font-family:sans-serif; }}
</style></head><body>
<h2>Screen changes</h2>
{"".join(entries)}
<h2>Final screen</h2>
{final}
</body></html>
"""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _srt_ts(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    ms = int(round((t - int(t)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_ts(t: float) -> str:
    return _srt_ts(t).replace(",", ".")


def write_subtitles(
    cast: Cast,
    out: str | Path,
    fmt: str = "srt",  # srt | vtt
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    max_line: int = 42,
    max_lines: int = 2,
    max_dur: float = 5.0,
    gap: float = 1.2,
) -> Path:
    """Turn output events into caption cues — makes terminal recordings searchable."""
    fmt = fmt.lower()
    if fmt not in ("srt", "vtt"):
        raise ShowreelError("subtitle format must be srt or vtt")
    tcast = transform(cast, start=start, end=end, speed=speed, drop_before_start=True)
    events = [e for e in tcast.events if e.etype == "o" and strip_ansi(e.data).strip()]

    cues: list[tuple[float, float, str]] = []
    cur_text: list[str] = []
    cur_start: float | None = None
    last_t = 0.0

    def flush(end_t: float) -> None:
        nonlocal cur_text, cur_start
        if cur_start is None or not cur_text:
            cur_text = []
            return
        text = " ".join(cur_text).strip()
        cur_text = []
        end_t = max(end_t, cur_start + 0.4)  # never emit zero-length cues
        # soft-wrap into <=max_lines cue lines
        words, lines, line = text.split(), [], ""
        for w in words:
            if line and len(line) + 1 + len(w) > max_line:
                lines.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            lines.append(line)
        while len(lines) > max_lines:  # split overlong cues, sharing the time window
            mid = len(lines) // 2
            seg = max((end_t - cur_start) * (mid / len(lines)), 0.3)
            part_end = cur_start + seg
            cues.append((cur_start, part_end, "\n".join(lines[:mid])))
            lines = lines[mid:]
            cur_start = part_end
        cues.append((cur_start, max(end_t, cur_start + 0.3), "\n".join(lines)))
        cur_start = None

    for e in events:
        text = " ".join(strip_ansi(e.data).split())
        if not text:
            continue
        if cur_start is not None and (
            e.time - last_t > gap or sum(len(x) for x in cur_text) + len(text) > max_line * max_lines * 3
        ):
            flush(last_t)
        if cur_start is None:
            cur_start = e.time
        cur_text.append(text)
        last_t = e.time
        if e.time - cur_start >= max_dur:
            flush(e.time)
    flush(tcast.duration)

    out_lines = []
    ts = _srt_ts if fmt == "srt" else _vtt_ts
    if fmt == "vtt":
        out_lines.append("WEBVTT\n")
    for i, (a, b, text) in enumerate(cues, 1):
        if fmt == "srt":
            out_lines.append(str(i))
        out_lines += [f"{ts(a)} --> {ts(b)}", text, ""]
    content = "\n".join(out_lines)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path
