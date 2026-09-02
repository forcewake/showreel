"""Time transformations: trim, speed, idle-time compression, marker selection."""

from __future__ import annotations

from .. import ShowreelError
from .model import Cast, Event

__all__ = ["marker_bounds", "transform"]


def marker_bounds(cast: Cast, from_marker: str | None, to_marker: str | None) -> tuple[float | None, float | None]:
    """Resolve marker names (exact, then unique prefix) to a (start, end) time window."""
    if not from_marker and not to_marker:
        return None, None
    markers = cast.markers()
    if not markers:
        raise ShowreelError("recording has no markers; add them with asciinema's marker key or use --start/--end")

    def resolve(name: str) -> float:
        exact = [t for t, label in markers if label == name]
        if exact:
            return exact[0]
        prefix = [t for t, label in markers if label.startswith(name)]
        if len(prefix) == 1:
            return prefix[0]
        if len(prefix) > 1:
            labels = ", ".join(label for _, label in markers if label.startswith(name))
            raise ShowreelError(f"marker prefix '{name}' is ambiguous: {labels}")
        available = ", ".join(label or "<unlabeled>" for _, label in markers)
        raise ShowreelError(f"marker '{name}' not found. Available markers: {available}")

    start = resolve(from_marker) if from_marker else None
    end = resolve(to_marker) if to_marker else None
    if start is not None and end is not None and end <= start:
        raise ShowreelError("to-marker must come after from-marker")
    return start, end


def transform(
    cast: Cast,
    start: float | None = None,
    end: float | None = None,
    speed: float = 1.0,
    idle_limit: float | None = None,
    drop_before_start: bool = False,
) -> Cast:
    """Return a copy of cast with times transformed.

    - start/end trim: events before `start` are kept (they shaped the screen)
      but compressed to t=0, so exports start from the correct screen state.
      Set drop_before_start to remove them instead (right for plain transcripts).
    - speed: playback rate multiplier (>1 = faster).
    - idle_limit: cap the gap between consecutive events (like asciinema -i).
    """
    start = max(0.0, start or 0.0)
    end = cast.duration if end is None else min(end, cast.duration)
    if end <= start:
        end = cast.duration
    if speed <= 0:
        speed = 1.0

    out: list[Event] = []
    prev = 0.0
    for e in cast.events:
        if drop_before_start and e.time < start:
            continue
        t = min(max(e.time, start), end) - start
        if e.time < start:
            t = 0.0
        if idle_limit is not None and out:
            gap = t - prev
            if gap > idle_limit:
                t = prev + idle_limit
        t /= speed
        out.append(Event(time=t, etype=e.etype, data=e.data))
        prev = t
    return Cast(header=cast.header, events=out)
