"""Tests for v0.3.0 features: join/cut, fetch URLs, themes import, script DSL,
alternate screen, MCP server, webp export."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from showreel import ShowreelError
from showreel.core.ops import cut, join, parse_ranges
from showreel.core.parser import parse
from showreel.core.script import script_to_cast
from showreel.core.themes_io import import_theme, list_user_themes
from tests.fixtures import write_v3


@pytest.fixture()
def cast(tmp_path: Path):
    return parse(write_v3(tmp_path / "v3.cast"))


def _mk(tmp_path: Path, events, version=3) -> object:
    p = tmp_path / f"m{abs(hash(tuple(map(str, events)))) % 99999}.cast"
    header = (
        {"version": version, "term": {"cols": 20, "rows": 4}}
        if version == 3
        else {"version": version, "width": 20, "height": 8}
    )
    p.write_text("\n".join([json.dumps(header)] + [json.dumps(e) for e in events]) + "\n", encoding="utf-8")
    return parse(p)


# ---------- join / cut ----------


def test_join_two_casts(tmp_path):
    a = _mk(tmp_path, [[0.0, "o", "a"], [0.5, "x", "0"]])
    b = _mk(tmp_path, [[0.0, "o", "b"]])
    merged = join([a, b], gap=1.0)
    assert merged.duration == pytest.approx(a.duration + 1.0 + b.duration)
    assert [e.data for e in merged.events if e.etype == "o"] == ["a", "b"]


def test_cut_removes_window_and_retimes(tmp_path):
    # v3 times are intervals: absolute times become 0.0, 1.0, 2.0
    cast = _mk(tmp_path, [[0.0, "o", "a"], [1.0, "o", "CUT"], [1.0, "o", "b"]])
    cut_cast = cut(cast, [(0.5, 1.5)])
    times = [round(e.time, 2) for e in cut_cast.events]
    assert times == [0.0, 1.0]  # the 1.0s event was inside the window
    assert [e.data for e in cut_cast.events] == ["a", "b"]


def test_parse_ranges_hhmmss():
    assert parse_ranges(["1:30-2:30"]) == [(90.0, 150.0)]
    assert parse_ranges(["3.5-8"]) == [(3.5, 8.0)]


def test_cut_invalid_range_raises(cast):
    with pytest.raises(ShowreelError):
        cut(cast, [(5.0, 1.0)])


# ---------- fetch (URL normalization only — no network) ----------


def test_normalize_asciinema_url():
    from showreel.core.fetch import is_url, normalize_asciinema_url

    assert is_url("https://asciinema.org/a/123")
    assert not is_url("demo.cast")
    assert normalize_asciinema_url("https://asciinema.org/a/123") == "https://asciinema.org/a/123.cast"
    assert normalize_asciinema_url("https://example.com/x.cast") == "https://example.com/x.cast"


# ---------- themes import ----------


def test_import_windows_terminal_theme(tmp_path):
    wt = tmp_path / "wt.json"
    wt.write_text(
        json.dumps(
            {
                "name": "Mine",
                "background": "#0C0C0C",
                "foreground": "#CCCCCC",
                "black": "#0C0C0C",
                "red": "#C50F1F",
                "green": "#13A10E",
                "yellow": "#C19C00",
                "blue": "#0037DA",
                "purple": "#881798",
                "cyan": "#3A96DD",
                "white": "#CCCCCC",
                "brightBlack": "#767676",
                "brightRed": "#E74856",
                "brightGreen": "#16C60C",
                "brightYellow": "#F9F1A5",
                "brightBlue": "#3B78FF",
                "brightPurple": "#B4009E",
                "brightCyan": "#61D6D6",
                "brightWhite": "#F2F2F2",
            }
        ),
        encoding="utf-8",
    )
    saved = import_theme(wt, "mine")
    data = json.loads(saved.read_text())
    assert data["palette"][1] == "#c50f1f"
    assert "mine" in list_user_themes()


def test_import_itermcolors(tmp_path):
    iterm = tmp_path / "t.itermcolors"
    iterm.write_text(
        """<?xml version="1.0"?><plist version="1.0"><dict>
        <key>Ansi 1 Color</key><dict><key>Red Component</key><real>1.0</real>
        <key>Green Component</key><real>0.0</real><key>Blue Component</key><real>0.2</real></dict>
        </dict></plist>""",
        encoding="utf-8",
    )
    data = json.loads(import_theme(iterm, "iterm_test").read_text())
    assert data["palette"][1] == "#ff0033"


# ---------- script DSL ----------


def test_script_basic(tmp_path):
    script = tmp_path / "demo.show"
    script.write_text(
        '# comment\nTitle  "tiny demo"\nType "echo hi"\nRun "echo hello world"\nSleep 300ms\nMarker  "the end"\n',
        encoding="utf-8",
    )
    cast = script_to_cast(script)
    text = "".join(e.data for e in cast.events if e.etype == "o")
    assert "echo hi" in text and "hello world" in text
    assert "exit 0" in text
    assert cast.markers()[-1][1] == "the end"
    # times are strictly increasing for output events
    times = [e.time for e in cast.events]
    assert times == sorted(times)


def test_script_bad_directive(tmp_path):
    script = tmp_path / "bad.show"
    script.write_text('Wat "nope"\n', encoding="utf-8")
    with pytest.raises(ShowreelError):
        script_to_cast(script)


# ---------- alternate screen ----------


def test_altscreen_roundtrip(tmp_path):
    cast = _mk(
        tmp_path,
        [
            [0.0, "o", "before"],
            [0.1, "o", "\x1b[?1049h"],
            [0.1, "o", "\x1b[2JVIM"],
            [0.1, "o", "\x1b[?1049l"],
            [0.1, "o", "!"],
        ],
    )
    from showreel.playback import Player

    player = Player(cast)
    player.seek(cast.duration)
    display = player.display()
    assert "VIM" not in display[0]
    assert "before!" in display[0]


# ---------- webp ----------


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg missing")
def test_webp_export(tmp_path, cast):
    from showreel.exporters.gif import export_gif

    out = export_gif(cast, tmp_path / "a.webp", fmt="webp", hold=0.2, quiet=True)
    assert out.read_bytes()[:4] == b"RIFF"


# ---------- MCP server ----------


def _rpc(proc, payload: dict) -> dict:
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def test_mcp_server(tmp_path, cast):
    src = write_v3(tmp_path / "m.cast")
    import shutil

    venv_exe = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "showreel"
    exe = str(venv_exe) if venv_exe.exists() else shutil.which("showreel")
    proc = subprocess.Popen(
        [exe, "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        init = _rpc(
            proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
        )
        assert init["result"]["serverInfo"]["name"] == "showreel"
        tools = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in tools["result"]["tools"]]
        assert "showreel_info" in names and "showreel_transcript" in names
        call = _rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "showreel_info", "arguments": {"source": str(src)}},
            },
        )
        summary = json.loads(call["result"]["content"][0]["text"])
        assert summary["duration_seconds"] == pytest.approx(1.25)
    finally:
        proc.kill()
