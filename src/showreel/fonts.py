"""Locate a suitable monospace TTF font for frame rendering."""

from __future__ import annotations

import platform
from pathlib import Path

from . import ShowreelError

__all__ = ["DEFAULT_CANDIDATES", "find_font"]

DEFAULT_CANDIDATES: list[str] = [
    # explicit user-ish locations first (JetBrains Mono / Fira if installed)
    "/usr/local/share/fonts/JetBrainsMono-Regular.ttf",
    str(Path.home() / ".local/share/fonts/JetBrainsMono-Regular.ttf"),
]

_SYSTEM_CANDIDATES: dict[str, list[str]] = {
    "Darwin": [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.dfont",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/JetBrainsMono-Regular.ttf",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
    ],
    "Windows": [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
    ],
}


def find_font(explicit: str | None = None) -> str:
    """Return a font file path. explicit wins; else search system monospace fonts."""
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise ShowreelError(f"font not found: {p}")
        return str(p)

    candidates = DEFAULT_CANDIDATES + _SYSTEM_CANDIDATES.get(platform.system(), [])
    for c in candidates:
        if Path(c).exists():
            return c
    raise ShowreelError(
        "no monospace font found on this system. Install one (e.g. `brew install --cask font-jetbrains-mono`) "
        "or pass --font /path/to/Mono.ttf"
    )
