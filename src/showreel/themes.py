"""Built-in terminal themes and resolution from cast header / CLI choice."""

from __future__ import annotations

import re

from . import ShowreelError
from .core.model import Cast, Theme

__all__ = ["BUILTIN_THEMES", "THEME_NAMES", "resolve_theme"]

_HEX6 = re.compile(r"^[0-9a-fA-F]{6}$")

_XTERM16 = [
    "#000000",
    "#cd0000",
    "#00cd00",
    "#cdcd00",
    "#0000ee",
    "#cd00cd",
    "#00cdcd",
    "#e5e5e5",
    "#7f7f7f",
    "#ff0000",
    "#00ff00",
    "#ffff00",
    "#5c5cff",
    "#ff00ff",
    "#00ffff",
    "#ffffff",
]


def _t(fg: str, bg: str, palette: list[str], cursor: str | None = None) -> dict:
    return {"fg": fg, "bg": bg, "palette": palette, "cursor": cursor or fg}


BUILTIN_THEMES: dict[str, dict] = {
    "asciinema": _t("#cccccc", "#000000", _XTERM16),
    "dracula": _t(
        "#f8f8f2",
        "#282a36",
        [
            "#21222c",
            "#ff5555",
            "#50fa7b",
            "#f1fa8c",
            "#bd93f9",
            "#ff79c6",
            "#8be9fd",
            "#f8f8f2",
            "#6272a4",
            "#ff6e6e",
            "#69ff94",
            "#ffffa5",
            "#d6acff",
            "#ff92df",
            "#a4ffff",
            "#ffffff",
        ],
        cursor="#f8f8f2",
    ),
    "nord": _t(
        "#d8dee9",
        "#2e3440",
        [
            "#3b4252",
            "#bf616a",
            "#a3be8c",
            "#ebcb8b",
            "#81a1c1",
            "#b48ead",
            "#88c0d0",
            "#e5e9f0",
            "#4c566a",
            "#bf616a",
            "#a3be8c",
            "#ebcb8b",
            "#81a1c1",
            "#b48ead",
            "#8fbcbb",
            "#eceff4",
        ],
    ),
    "solarized-dark": _t(
        "#839496",
        "#002b36",
        [
            "#073642",
            "#dc322f",
            "#859900",
            "#b58900",
            "#268bd2",
            "#d33682",
            "#2aa198",
            "#eee8d5",
            "#002b36",
            "#cb4b16",
            "#586e75",
            "#657b83",
            "#839496",
            "#6c71c4",
            "#93a1a1",
            "#fdf6e3",
        ],
    ),
    "solarized-light": _t(
        "#657b83",
        "#fdf6e3",
        [
            "#073642",
            "#dc322f",
            "#859900",
            "#b58900",
            "#268bd2",
            "#d33682",
            "#2aa198",
            "#eee8d5",
            "#002b36",
            "#cb4b16",
            "#586e75",
            "#657b83",
            "#839496",
            "#6c71c4",
            "#93a1a1",
            "#fdf6e3",
        ],
    ),
    "monokai": _t(
        "#f8f8f2",
        "#272822",
        [
            "#272822",
            "#f92672",
            "#a6e22e",
            "#f4bf75",
            "#ae81ff",
            "#fd971f",
            "#a1efe1",
            "#f8f8f2",
            "#75715e",
            "#f92672",
            "#a6e22e",
            "#f4bf75",
            "#ae81ff",
            "#fd971f",
            "#a1efe1",
            "#f9f8f5",
        ],
    ),
    "gruvbox-dark": _t(
        "#ebdbb2",
        "#282828",
        [
            "#282828",
            "#cc241d",
            "#98971a",
            "#d79921",
            "#458588",
            "#b16286",
            "#689d6a",
            "#a89984",
            "#928374",
            "#fb4934",
            "#b8bb26",
            "#fabd2f",
            "#83a598",
            "#d3869b",
            "#8ec07c",
            "#ebdbb2",
        ],
    ),
    "tango-light": _t(
        "#2e3436",
        "#ffffff",
        [
            "#2e3436",
            "#cc0000",
            "#4e9a06",
            "#c4a000",
            "#3465a4",
            "#75507b",
            "#06989a",
            "#d3d7cf",
            "#555753",
            "#ef2929",
            "#8ae234",
            "#fce94f",
            "#729fcf",
            "#ad7fa8",
            "#34e2e2",
            "#eeeeec",
        ],
    ),
}

THEME_NAMES = sorted(BUILTIN_THEMES)


class ResolvedTheme:
    """Fully resolved theme: hex colors for fg/bg/palette/cursor."""

    def __init__(self, fg: str, bg: str, palette: list[str], cursor: str):
        self.fg = fg
        self.bg = bg
        self.palette = palette
        self.cursor = cursor

    @property
    def default_fg(self) -> str:
        return self.fg

    @property
    def default_bg(self) -> str:
        return self.bg

    def index_color(self, idx: int) -> str:
        return self.palette[idx % len(self.palette)]

    def named(self, name: str) -> str | None:
        from .core.model import _NAMED

        base = name.replace("bright", "").replace("bright-", "").replace("-", "")
        idx = _NAMED.get(base)
        if idx is None:
            return None
        if name.startswith("bright") and len(self.palette) >= 16:
            idx += 8
        return self.palette[idx % len(self.palette)]

    def resolve(self, value: str | None, default: str) -> str:
        """Resolve a pyte cell color ('default', named, or bare 6-hex) to a hex color."""
        if not value or value == "default":
            return default
        if value.startswith("#"):
            return value
        if _HEX6.match(value):
            return "#" + value.lower()
        return self.named(value) or default


def resolve_theme(cast: Cast | None, choice: str) -> ResolvedTheme:
    """choice: theme name, or 'auto' — use the theme embedded in the cast header."""
    if choice != "auto":
        if choice not in BUILTIN_THEMES:
            raise ShowreelError(f"unknown theme '{choice}'. Available: {', '.join(THEME_NAMES)}, auto")
        t = BUILTIN_THEMES[choice]
    else:
        theme: Theme | None = cast.header.term.theme if cast else None
        if theme and (theme.bg or theme.palette):
            fg = theme.fg or "#cccccc"
            bg = theme.bg or "#000000"
            palette = theme.palette or _XTERM16
            if len(palette) < 16:
                palette = palette + _XTERM16[len(palette) :]
            return ResolvedTheme(fg, bg, palette, BUILTIN_THEMES["asciinema"]["cursor"])
        t = BUILTIN_THEMES["asciinema"]
    return ResolvedTheme(t["fg"], t["bg"], list(t["palette"]), t["cursor"])
