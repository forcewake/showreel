"""Scripted demos: a tiny vhs-inspired DSL that produces a deterministic cast.

Directives (one per line, `#` comments):
    Type "text"              simulate keystrokes (with Enter)
    Enter
    Run "command"            execute in a shell, capture combined output
    Output "text"            print literal output (no execution, \\n allowed)
    Sleep 500ms | 1.5        pause
    Clear
    Marker name              add a chapter marker
    Env KEY=value            extra env vars for Run

Example:
    Title  deploy demo
    Run "git status --short"
    Sleep 400ms
    Marker build
    Type "npm run build"
    Run "npm run build"
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .. import ShowreelError
from .model import Cast, Event, Header, TermInfo

__all__ = ["script_to_cast"]

_LINE = re.compile(r"^\s*(Type|Enter|Run|Output|Sleep|Clear|Marker|Env|Title)\s*(.*?)\s*(?:#.*)?$")


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def script_to_cast(path: str | Path, cols: int = 80, rows: int = 24) -> Cast:
    path = Path(path)
    if not path.exists():
        raise ShowreelError(f"script not found: {path}")

    events: list[Event] = []
    t = 0.0

    def emit(etype: str, data: str, dt: float) -> None:
        nonlocal t
        t += dt
        events.append(Event(time=t, etype=etype, data=data))

    title = "showreel demo"
    env_extra: dict[str, str] = {}

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        m = _LINE.match(raw)
        if not m:
            raise ShowreelError(f"{path}:{line_no}: cannot parse line: {raw.strip()!r}")
        directive, rest = m.group(1), m.group(2)

        if directive == "Title":
            title = _unquote(rest)
        elif directive == "Sleep":
            spec = rest.rstrip("ms").strip()
            try:
                seconds = float(spec) / 1000.0 if rest.rstrip().endswith("ms") else float(spec)
            except ValueError:
                raise ShowreelError(f"{path}:{line_no}: bad Sleep '{rest}'") from None
            emit("o", "", seconds)  # pure pause
        elif directive == "Clear":
            emit("o", "\x1b[2J\x1b[H", 0.05)
        elif directive == "Marker":
            emit("m", _unquote(rest) or f"chapter {len([e for e in events if e.etype == 'm']) + 1}", 0.05)
        elif directive == "Env":
            if "=" not in rest:
                raise ShowreelError(f"{path}:{line_no}: Env needs KEY=value")
            k, v = rest.split("=", 1)
            env_extra[k.strip()] = _unquote(v.strip())
        elif directive == "Type":
            text = _unquote(rest)
            for ch in text:
                emit("o", ch, 0.04)
            emit("o", "\r\n", 0.1)
        elif directive == "Enter":
            emit("o", "\r\n", 0.1)
        elif directive == "Output":
            emit("o", _unquote(rest).replace("\\n", "\n") + "\n", 0.1)
        elif directive == "Run":
            command = _unquote(rest)
            for ch in command:
                emit("o", ch, 0.035)
            emit("o", "\r\n", 0.12)
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    timeout=120,
                    env={**os.environ, "TERM": "xterm-256color", **env_extra},
                )
            except subprocess.TimeoutExpired:
                raise ShowreelError(f"{path}:{line_no}: command timed out after 120s: {command}") from None
            output = (proc.stdout + proc.stderr).decode("utf-8", "replace")
            if output:
                emit("o", output, 0.15)
            emit("o", f"\x1b[90m[exit {proc.returncode}]\x1b[0m\r\n", 0.1)

    header = Header(version=3, term=TermInfo(cols=cols, rows=rows, type="xterm-256color"), title=title)
    return Cast(header=header, events=[e for e in events if not (e.etype == "o" and e.data == "")])
