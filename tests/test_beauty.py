"""Tests for the typewriter effect and vhs-style decorations."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from castkit import CastkitError
from castkit.core.parser import parse
from castkit.core.typewriter import typewriter
from castkit.exporters.svg import export_svg
from castkit.playback import Player
from castkit.render import Renderer
from castkit.themes import resolve_theme
from tests.fixtures import write_v3


@pytest.fixture()
def cast_v3(tmp_path: Path):
    return parse(write_v3(tmp_path / "v3.cast"))


def _mk_cast(tmp_path: Path, events) -> object:
    import json

    p = tmp_path / "tw.cast"
    header = {"version": 3, "term": {"cols": 20, "rows": 4}}
    p.write_text(
        "\n".join([json.dumps(header)] + [json.dumps(e) for e in events]) + "\n",
        encoding="utf-8",
    )
    return parse(p)


def test_typewriter_splits_and_retimes(tmp_path):
    cast = _mk_cast(tmp_path, [[0.0, "o", "ab"], [1.0, "o", "c"], [0.1, "m", "mark"], [0.05, "x", "0"]])
    slow = typewriter(cast, cps=10)
    visible = [e for e in slow.events if e.etype == "o"]
    assert [e.data for e in visible] == ["a", "b", "c"]
    # one beat per char at 10 cps
    assert visible[1].time - visible[0].time == pytest.approx(0.1)
    assert visible[2].time - visible[1].time == pytest.approx(0.1)
    # marker follows the last char, monotonic timeline
    marker = next(e for e in slow.events if e.etype == "m")
    assert marker.time >= visible[-1].time


def test_typewriter_keeps_escape_sequences_atomic(tmp_path):
    import re

    data = "\x1b[1;31mRED\x1b[0m!"
    cast = _mk_cast(tmp_path, [[0.0, "o", data]])
    slow = typewriter(cast, cps=50)
    outs = [e.data for e in slow.events if e.etype == "o"]
    assert outs[0] == "\x1b[1;31mR"  # SGR rides with the first char
    assert outs[-1] == "\x1b[0m!"  # reset rides with the char it terminates
    for d in outs:  # no partial escape sequences anywhere
        assert not re.search(r"\x1b\[[0-9;?]*$", d) or d.startswith("\x1b[")


def test_typewriter_rejects_overly_fine_granularity(tmp_path):
    cast = _mk_cast(tmp_path, [[0.0, "o", "x" * 300_000]])
    with pytest.raises(CastkitError):
        typewriter(cast, cps=5)


def test_svg_decorations(tmp_path, cast_v3):
    p = export_svg(
        cast_v3,
        tmp_path / "d.svg",
        theme="dracula",
        chrome_title="demo",
        chrome_style="rings",
        radius=12,
        shadow=True,
        margin=40,
        margin_fill="#6B50FF,#241a66",
        watermark="wm",
    )
    root = ET.parse(p).getroot()
    content = p.read_text()
    assert 'rx="12"' in content
    assert "drop-shadow" in content
    assert "linearGradient" in content
    assert ">wm<" in content
    assert content.count("<circle") == 3  # rings traffic lights
    assert root.find("{http://www.w3.org/2000/svg}clipPath") is not None or "clipPath" in content


def test_renderer_decorated_dimensions(cast_v3, tmp_path):
    player = Player(cast_v3)
    player.seek(cast_v3.duration)
    r = Renderer(
        resolve_theme(cast_v3, "dracula"),
        player.cols,
        player.rows,
        font_size=20,
        radius=10,
        shadow=True,
        margin=30,
        margin_fill="#6B50FF,#241a66",
        watermark="x",
    )
    img = r.render(player)
    assert img.size[0] % 2 == 0 and img.size[1] % 2 == 0
    assert img.size[0] > 30 * 2 + player.cols * r.char_w  # margin grew the canvas
    img.save(tmp_path / "p.png")
    assert Image.open(tmp_path / "p.png").size == img.size


def test_renderer_cursor_blink_toggle(cast_v3):
    player = Player(cast_v3)
    player.seek(cast_v3.duration)
    r = Renderer(resolve_theme(cast_v3, "dracula"), player.cols, player.rows, font_size=20, cursor="block")
    shown = r.render(player, show_cursor=True)
    hidden = r.render(player, show_cursor=False)
    assert shown.tobytes() != hidden.tobytes()  # blink actually changes the frame
