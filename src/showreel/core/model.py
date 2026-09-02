"""Internal data model for asciicast files (v1/v2/v3 normalised)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEX = re.compile(r"^[0-9a-fA-F]{6}$")

# pyte names 8/16 colors; map name -> palette index (0-15).
_NAMED = {
    "black": 0,
    "red": 1,
    "green": 2,
    "brown": 3,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
}


def _norm_color(value: str | None) -> str | None:
    """Normalise a color to '#rrggbb' or None for 'default'/unknown."""
    if not value or value == "default":
        return None
    v = value.lstrip("#")
    if _HEX.match(v):
        return "#" + v.lower()
    return value  # named color, resolved later against a palette


@dataclass
class Theme:
    """Terminal theme as captured in a cast header."""

    fg: str | None = None
    bg: str | None = None
    palette: list[str] = field(default_factory=list)  # 16 '#rrggbb' entries (may be empty)

    @classmethod
    def from_dict(cls, d: dict | None) -> Theme:
        if not d:
            return cls()
        pal: list[str] = []
        raw = d.get("palette")
        if isinstance(raw, str):
            pal = [_norm_color(p) or "" for p in raw.split(":")]
        elif isinstance(raw, list):
            pal = [_norm_color(p) or "" for p in raw]
        return cls(fg=_norm_color(d.get("fg")), bg=_norm_color(d.get("bg")), palette=pal)

    def to_dict(self) -> dict:
        d: dict = {}
        if self.fg:
            d["fg"] = self.fg
        if self.bg:
            d["bg"] = self.bg
        if self.palette:
            d["palette"] = ":".join(self.palette)
        return d

    def named(self, name: str) -> str | None:
        """Resolve a pyte color name to '#rrggbb' using the palette."""
        idx = _NAMED.get(name.replace("bright", "").replace("bright-", "").replace("-", ""))
        if idx is None:
            return None
        if name.startswith("bright") and len(self.palette) >= 16:
            return self.palette[8 + idx]
        if idx < len(self.palette):
            return self.palette[idx]
        return None


@dataclass
class TermInfo:
    cols: int = 80
    rows: int = 24
    type: str | None = None
    version: str | None = None
    theme: Theme | None = None


@dataclass
class Header:
    version: int = 3  # source format version
    term: TermInfo = field(default_factory=TermInfo)
    timestamp: int | None = None
    idle_time_limit: float | None = None
    command: str | None = None
    title: str | None = None
    env: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class Event:
    time: float  # absolute seconds from recording start
    etype: str  # 'o' output, 'i' input, 'm' marker, 'r' resize, 'x' exit
    data: str


@dataclass
class Cast:
    header: Header
    events: list[Event] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max((e.time for e in self.events), default=0.0)

    def markers(self) -> list[tuple[float, str]]:
        return [(e.time, e.data) for e in self.events if e.etype == "m"]

    def count(self, etype: str) -> int:
        return sum(1 for e in self.events if e.etype == etype)
