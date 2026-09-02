"""Format conversion: v1/v2/v3 <-> v2/v3, with trim/speed/idle/gzip options."""

from __future__ import annotations

from pathlib import Path

from ..core.model import Cast
from ..core.transform import transform
from ..core.writer import write

__all__ = ["convert"]


def convert(
    cast: Cast,
    out: str | Path,
    to: int = 3,
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    idle_limit: float | None = None,
    strip_input: bool = False,
    strip_markers: bool = False,
    gzip_out: bool = False,
) -> Path:
    tcast = transform(cast, start=start, end=end, speed=speed, idle_limit=idle_limit)
    if strip_input:
        tcast.events = [e for e in tcast.events if e.etype != "i"]
    if strip_markers:
        tcast.events = [e for e in tcast.events if e.etype != "m"]
    tcast.header.version = to
    write(tcast, out, version=to, gzip_out=gzip_out)
    return Path(out)
