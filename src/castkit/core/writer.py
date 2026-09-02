"""Write normalised casts back to asciicast v2 or v3 (or legacy v1)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from .model import Cast, Header

__all__ = ["header_to_dict_v2", "header_to_dict_v3", "write"]


def _round6(x: float) -> float:
    return round(x, 6)


def header_to_dict_v2(h: Header, duration: float | None = None) -> dict:
    d: dict = {"version": 2, "width": h.term.cols, "height": h.term.rows}
    if h.timestamp is not None:
        d["timestamp"] = h.timestamp
    if duration is not None:
        d["duration"] = _round6(duration)
    if h.idle_time_limit is not None:
        d["idle_time_limit"] = h.idle_time_limit
    if h.command:
        d["command"] = h.command
    if h.title:
        d["title"] = h.title
    if h.env:
        d["env"] = h.env
    if h.term.theme and h.term.theme.to_dict():
        d["theme"] = h.term.theme.to_dict()
    return d


def header_to_dict_v3(h: Header) -> dict:
    term: dict = {"cols": h.term.cols, "rows": h.term.rows}
    if h.term.type:
        term["type"] = h.term.type
    if h.term.version:
        term["version"] = h.term.version
    theme_d = (h.term.theme or None) and h.term.theme.to_dict()
    if theme_d:
        term["theme"] = theme_d
    d: dict = {"version": 3, "term": term}
    if h.timestamp is not None:
        d["timestamp"] = h.timestamp
    if h.idle_time_limit is not None:
        d["idle_time_limit"] = h.idle_time_limit
    if h.command:
        d["command"] = h.command
    if h.title:
        d["title"] = h.title
    if h.env:
        d["env"] = h.env
    if h.tags:
        d["tags"] = h.tags
    return d


def _dump_line(obj) -> str:
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"))


def write(cast: Cast, path: str | Path, version: int = 3, gzip_out: bool = False) -> None:
    """Write cast to path as asciicast v1/v2/v3. gzip_out adds a .gz-compatible stream."""
    path = Path(path)
    if version == 1:
        payload = header_to_dict_v2(cast.header, duration=cast.duration)
        payload["version"] = 1
        prev = 0.0
        stdout = []
        for e in cast.events:
            if e.etype != "o":
                continue
            stdout.append([_round6(e.time - prev), e.data])  # v1 wants deltas
            prev = e.time
        payload["stdout"] = stdout
        text = _dump_line(payload)
    else:
        lines = [
            _dump_line(
                header_to_dict_v2(cast.header, cast.duration) if version == 2 else header_to_dict_v3(cast.header)
            )
        ]
        if version == 2:
            lines += [_dump_line([_round6(e.time), e.etype, e.data]) for e in cast.events]
        else:
            # v3: relative intervals, millisecond precision via error diffusion
            prev_ms = 0
            for e in cast.events:
                target_ms = int(round(e.time * 1000))
                interval_ms = max(0, target_ms - prev_ms)
                prev_ms = target_ms
                lines.append(_dump_line([interval_ms / 1000.0, e.etype, e.data]))
        text = "\n".join(lines) + "\n"

    if gzip_out or str(path).endswith(".gz"):
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text, encoding="utf-8")
