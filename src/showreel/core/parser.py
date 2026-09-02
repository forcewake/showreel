"""Parse .cast files: asciicast v1, v2 and v3 (optionally gzip-compressed)."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

from .model import Cast, Event, Header, TermInfo, Theme

__all__ = ["parse"]


def _warn(msg: str) -> None:
    print(f"showreel: warning: {msg}", file=sys.stderr)


def _open(path: Path):
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _parse_header(d: dict, source_version: int) -> Header:
    theme = Theme.from_dict(d.get("theme"))
    if source_version >= 3:
        term_d = d.get("term") or {}
        term = TermInfo(
            cols=int(term_d.get("cols", d.get("width", 80))),
            rows=int(term_d.get("rows", d.get("height", 24))),
            type=term_d.get("type"),
            version=term_d.get("version"),
            theme=Theme.from_dict(term_d.get("theme")) or theme or None,
        )
    else:
        term = TermInfo(
            cols=int(d.get("width", 80)),
            rows=int(d.get("height", 24)),
            type=(d.get("env") or {}).get("TERM"),
            theme=theme or None,
        )
    return Header(
        version=source_version,
        term=term,
        timestamp=d.get("timestamp"),
        idle_time_limit=d.get("idle_time_limit"),
        command=d.get("command"),
        title=d.get("title"),
        env=d.get("env") or {},
        tags=d.get("tags") or [],
    )


def _parse_v1(d: dict) -> Cast:
    header = _parse_header(d, 1)
    events = []
    t = 0.0
    for rec in d.get("stdout") or []:
        if not isinstance(rec, (list, tuple)) or len(rec) != 2:
            continue
        delay, data = rec
        t += float(delay)  # v1 stdout entries are deltas from the previous frame
        events.append(Event(time=t, etype="o", data=str(data)))
    events.sort(key=lambda e: e.time)
    return Cast(header=header, events=events)


def parse(path: str | Path) -> Cast:
    """Parse a .cast file (v1/v2/v3, plain or gzipped) into a normalised Cast."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no such file: {path}")

    with _open(path) as f:
        first = f.readline()
        if not first.strip():
            raise ValueError(f"{path}: empty file")
        try:
            head = json.loads(first)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}: first line is not JSON ({e})") from e

        # v1 is a single JSON object containing the whole recording.
        if isinstance(head, dict) and "stdout" in head:
            return _parse_v1(head)
        if not isinstance(head, dict) or "version" not in head:
            raise ValueError(f"{path}: not an asciicast file (missing 'version')")

        version = int(head["version"])
        if version not in (2, 3):
            raise ValueError(f"{path}: unsupported asciicast version {version}")
        header = _parse_header(head, version)

        events: list[Event] = []
        line_no = 1
        t = 0.0
        for line in f:
            line_no += 1
            line = line.strip()
            if not line or line.startswith("#"):  # v3 allows comments
                continue
            try:
                rec = json.loads(line)
                etime, etype, data = rec
            except (json.JSONDecodeError, ValueError, TypeError):
                _warn(f"{path}:{line_no}: skipping malformed event line")
                continue
            if version == 3:  # relative intervals -> absolute time
                t += float(etime)
            else:
                t = float(etime)
            events.append(Event(time=t, etype=str(etype), data=data if isinstance(data, str) else json.dumps(data)))

    if len({e.time for e in events}) != len(events) and any(b.time < a.time for a, b in zip(events, events[1:])):
        _warn(f"{path}: events not in time order, sorting")
        events.sort(key=lambda e: e.time)
    return Cast(header=header, events=events)
