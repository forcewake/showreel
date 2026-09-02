"""User themes: import from terminal configs, save under a config dir, list.

`themes import` understands:
- Windows Terminal scheme JSON ({"background": "#...", "foreground": "#...", "black": ...})
- generic JSON ({"fg": "#...", "bg": "#...", "palette": ["#hex", ... 16]})
- iTerm2 .itermcolors plist files
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .. import ShowreelError

__all__ = ["themes_dir", "import_theme", "load_user_theme", "list_user_themes"]

WT_KEYS = [
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "purple",
    "cyan",
    "white",
    "brightBlack",
    "brightRed",
    "brightGreen",
    "brightYellow",
    "brightBlue",
    "brightPurple",
    "brightCyan",
    "brightWhite",
]
ITERM_KEYS = [
    "Ansi 0 Color",
    "Ansi 1 Color",
    "Ansi 2 Color",
    "Ansi 3 Color",
    "Ansi 4 Color",
    "Ansi 5 Color",
    "Ansi 6 Color",
    "Ansi 7 Color",
    "Ansi 8 Color",
    "Ansi 9 Color",
    "Ansi 10 Color",
    "Ansi 11 Color",
    "Ansi 12 Color",
    "Ansi 13 Color",
    "Ansi 14 Color",
    "Ansi 15 Color",
]


def themes_dir() -> Path:
    d = Path.home() / ".config" / "showreel" / "themes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_user_theme(name: str) -> dict | None:
    path = themes_dir() / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_user_themes() -> list[str]:
    return sorted(p.stem for p in themes_dir().glob("*.json"))


def import_theme(source: Path, name: str) -> Path:
    """Parse a terminal theme file and store it as a castkit-style theme JSON."""
    text = source.read_text(encoding="utf-8", errors="replace")
    suffix = source.suffix.lower()
    try:
        if suffix == ".itermcolors" or "Ansi 0 Color" in text:
            theme = _from_iterm(text)
        else:
            data = json.loads(text)
            theme = _from_wt_or_generic(data)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise ShowreelError(f"could not parse theme file {source}: {e}") from e
    if not theme.get("palette"):
        raise ShowreelError(f"no palette found in {source}")
    out = themes_dir() / f"{name}.json"
    out.write_text(json.dumps(theme, indent=2) + "\n", encoding="utf-8")
    return out


def _norm(value: str | None) -> str | None:
    if not value:
        return None
    value = value.lstrip("#").lower()
    return f"#{value}" if value else None


def _from_wt_or_generic(data: dict) -> dict:
    fg = _norm(data.get("foreground") or data.get("fg"))
    bg = _norm(data.get("background") or data.get("bg"))
    palette = [_norm(data.get(k)) for k in WT_KEYS]
    if not all(palette):
        generic = data.get("palette")
        if isinstance(generic, list) and len(generic) >= 8:
            fg, bg, palette = fg or generic[7], bg or generic[0], generic
        else:
            raise ValueError("expected 16 color keys or a 'palette' array")
    return {"fg": fg, "bg": bg, "palette": [p for p in palette]}


def _from_iterm(text: str) -> dict:
    # plist XML: pull the body dicts even without plistlib (files may be binary;
    # for binary we still try plistlib first)
    try:
        import plistlib

        data = plistlib.loads(text.encode("utf-8", "replace"))
        if isinstance(data, dict) and data:
            raw = data
        else:
            raise ValueError("empty plist")
    except Exception:
        raw = _parse_iterm_xml(text)

    def component(color_dict: dict, key: str) -> float:
        return float(color_dict.get(key, 0.0))

    def hexof(d: dict) -> str:
        if "Red Component" not in d:
            return "000000"
        r, g, b = (round(component(d, k) * 255) for k in ("Red Component", "Green Component", "Blue Component"))
        return f"#{r:02x}{g:02x}{b:02x}"

    palette = []
    for key in ITERM_KEYS:
        d = raw.get(key) or {}
        palette.append(hexof(d))
    fg = hexof(raw.get("Foreground Color") or {})
    bg = hexof(raw.get("Background Color") or {})
    return {"fg": fg, "bg": bg, "palette": palette}


def _parse_iterm_xml(text: str) -> dict:
    out: dict[str, dict] = {}
    for block in re.finditer(
        r"<key>(Ansi \d+ Color|Foreground Color|Background Color)</key>\s*<dict>(.*?)</dict>", text, re.S
    ):
        name, body = block.group(1), block.group(2)
        d: dict = {}
        keys = re.findall(r"<key>(Red|Green|Blue) Component</key>\s*<real>([\d.]+)</real>", body)
        for k, v in keys:
            d[f"{k} Component"] = float(v)
        out[name] = d
    return out
