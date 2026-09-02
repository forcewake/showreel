"""Synthetic cast fixtures for tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_v3(path: Path) -> Path:
    """Small cast: colors, a marker, progress-bar \\r, unicode, exit code."""
    header = {
        "version": 3,
        "term": {"cols": 40, "rows": 8, "type": "xterm-256color"},
        "timestamp": 1700000000,
        "title": "test cast",
        "env": {"SHELL": "/bin/zsh"},
        "tags": ["test"],
    }
    events = [
        [0.10, "o", "\x1b[1;32m$\x1b[0m echo hi\r\n"],
        [0.20, "o", "hi\r\n"],
        [0.25, "m", "step one"],
        [0.30, "o", "\r\x1b[2Kloading… 50%"],
        [0.20, "o", "\r\x1b[2Kloading… 100%\r\n"],
        [0.15, "o", "\x1b[48;5;208m bg \x1b[0m \x1b[38;2;10;200;30mtruecolor\x1b[0m"],
        [0.05, "x", "0"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        for dt, code, data in events:
            f.write(json.dumps([dt, code, data]) + "\n")
    return path


def write_v2(path: Path) -> Path:
    header = {"version": 2, "width": 40, "height": 8, "timestamp": 1700000000}
    events = [
        [0.10, "o", "hello "],
        [0.30, "o", "world\r\n"],
        [0.40, "m", "only marker"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        for t, code, data in events:
            f.write(json.dumps([t, code, data]) + "\n")
    return path


def write_v1(path: Path) -> Path:
    payload = {
        "version": 1,
        "width": 40,
        "height": 8,
        "duration": 1.0,
        "stdout": [[0.10, "hello "], [0.20, "world\r\n"]],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
