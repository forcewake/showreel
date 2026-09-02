"""Recording editing: join several casts and cut time ranges out of one."""

from __future__ import annotations

import re

from .. import ShowreelError
from .model import Cast, Event

__all__ = ["join", "cut", "parse_ranges"]


def join(casts: list[Cast], gap: float = 0.5) -> Cast:
    """Concatenate casts back to back. Each next cast starts `gap` seconds after
    the previous one ends. Header comes from the first cast; all events kept."""
    if not casts:
        raise ShowreelError("join needs at least one cast")
    out: list[Event] = []
    base = casts[0]
    cursor = 0.0
    for i, cast in enumerate(casts):
        if i > 0:
            cursor += gap
        for e in cast.events:
            out.append(Event(time=cursor + e.time, etype=e.etype, data=e.data))
        cursor += cast.duration
    return Cast(header=base.header, events=out)


def parse_ranges(specs: list[str]) -> list[tuple[float, float]]:
    """Parse --remove entries like "3:8" (seconds) or "mm:ss:mm:ss" pairs."""
    ranges: list[tuple[float, float]] = []
    for spec in specs:
        parts = [p.strip() for p in spec.split("-") if p.strip() != ""]
        if len(parts) != 2:
            raise ShowreelError(f"--remove expects START-END, got '{spec}'")
        ranges.append((_ts(parts[0]), _ts(parts[1])))
    return ranges


def _ts(text: str) -> float:
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    chunks = [float(x) for x in text.split(":")]
    while len(chunks) < 3:
        chunks.insert(0, 0.0)
    h, m, s = chunks
    return h * 3600 + m * 60 + s


def cut(cast: Cast, ranges: list[tuple[float, float]]) -> Cast:
    """Remove [start, end) windows from the timeline, re-timing the rest."""
    if not ranges:
        return cast
    ranges = sorted(ranges)
    for a, b in ranges:
        if b <= a:
            raise ShowreelError(f"invalid range ({a}, {b}): end must be after start")

    def removed_before(t: float) -> float:
        return sum(max(0.0, min(b, t) - a) for a, b in ranges)

    out: list[Event] = []
    for e in cast.events:
        lost_start = removed_before(e.time)
        if any(a <= e.time < b for a, b in ranges):
            continue  # inside a removed window
        # an event spanning a removed window keeps the content it had; its time
        # shifts by everything removed before it
        out.append(Event(time=e.time - lost_start, etype=e.etype, data=e.data))
    return Cast(header=cast.header, events=out)
