"""Tests for marker-based selection and beauty presets."""

from __future__ import annotations

from pathlib import Path

import pytest

from castkit import CastkitError
from castkit.core.parser import parse
from castkit.core.transform import marker_bounds, transform
from tests.fixtures import write_v3


@pytest.fixture()
def cast(tmp_path: Path):
    path = write_v3(tmp_path / "v3.cast")
    c = parse(path)
    # give it a second marker for range tests
    c.events.insert(3, type(c.events[0])(time=0.90, etype="m", data="step two"))
    return c


def test_marker_bounds_exact(cast):
    start, end = marker_bounds(cast, "step one", "step two")
    assert start == 0.55
    assert end == 0.90


def test_marker_bounds_prefix_unique(cast):
    start, _ = marker_bounds(cast, "step on", None)  # unique prefix of "step one"
    assert start == 0.55


def test_marker_bounds_ambiguous_prefix_raises(cast):
    with pytest.raises(CastkitError, match="ambiguous"):
        marker_bounds(cast, "step", None)


def test_marker_bounds_unknown_raises(cast):
    with pytest.raises(CastkitError, match="Available markers"):
        marker_bounds(cast, "nope", None)


def test_marker_selection_via_transform(cast):
    start, end = marker_bounds(cast, "step one", "step two")
    cut = transform(cast, start=start, end=end)
    assert cut.duration == pytest.approx(0.90 - 0.55, abs=0.4)
    # first frame still shows the screen as it was at the marker


def test_cli_preset_resolution(cast):
    from types import SimpleNamespace

    from castkit.cli import _beauty_kwargs

    base = dict(
        preset="pretty",
        typewriter=None,
        margin=None,
        margin_fill=None,
        radius=None,
        shadow=None,
        watermark=None,
        chrome_style=None,
        cursor_blink=None,
    )
    args = SimpleNamespace(**base)
    b = _beauty_kwargs(args)
    assert b["margin"] == 48
    assert b["shadow"] is True
    assert b["chrome_style"] == "rings"
    assert b["cursor_blink"] == 530

    # explicit flag beats the preset
    args.margin = 10
    args.shadow = False
    b2 = _beauty_kwargs(args)
    assert b2["margin"] == 10
    assert b2["shadow"] is False

    # clean preset is subtle
    args2 = SimpleNamespace(**{**base, "preset": "clean"})
    assert _beauty_kwargs(args2)["radius"] == 8
    # minimal kills everything
    args3 = SimpleNamespace(**{**base, "preset": "minimal"})
    assert _beauty_kwargs(args3)["shadow"] is False
    assert _beauty_kwargs(args3)["radius"] == 0


def test_cli_marker_selection_folds_into_start_end(cast):
    """Smoke: the CLI-level fold helper."""
    from types import SimpleNamespace

    from castkit.cli import _apply_marker_selection

    args = SimpleNamespace(from_marker="step", to_marker=None, start=None, end=None)
    with pytest.raises(CastkitError):
        _apply_marker_selection(args, cast)  # ambiguous prefix

    args2 = SimpleNamespace(from_marker="step two", to_marker=None, start=None, end=None)
    _apply_marker_selection(args2, cast)
    assert args2.start == 0.90

    # explicit --start wins over the marker
    args3 = SimpleNamespace(from_marker="step two", to_marker=None, start=0.1, end=None)
    _apply_marker_selection(args3, cast)
    assert args3.start == 0.1
