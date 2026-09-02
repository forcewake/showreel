from __future__ import annotations

import json
from pathlib import Path

import pytest

from castkit import CastkitError
from castkit.core.model import Theme
from castkit.core.parser import parse
from castkit.core.transform import transform
from castkit.exporters.chapters import (
    chapters_json,
    chapters_text,
    chapters_vtt,
    extract_chapters,
    ffmetadata,
    youtube_list,
)
from castkit.exporters.convert import convert
from castkit.exporters.info import summary
from castkit.exporters.svg import export_svg
from castkit.exporters.text import strip_ansi, write_subtitles, write_text
from tests.fixtures import write_v1, write_v2, write_v3


@pytest.fixture()
def cast_v3(tmp_path: Path):
    return parse(write_v3(tmp_path / "v3.cast"))


# ---------- parsing ----------


def test_parse_v3(cast_v3):
    assert cast_v3.header.term.cols == 40
    assert cast_v3.header.term.rows == 8
    assert cast_v3.header.title == "test cast"
    assert cast_v3.duration == pytest.approx(1.25)
    assert cast_v3.count("o") == 5
    assert cast_v3.markers() == [(0.55, "step one")]


def test_parse_v2_absolute_times(tmp_path):
    cast = parse(write_v2(tmp_path / "v2.cast"))
    assert [e.time for e in cast.events] == [0.10, 0.30, 0.40]


def test_parse_v1_delta_times(tmp_path):
    cast = parse(write_v1(tmp_path / "v1.cast"))
    assert [round(e.time, 2) for e in cast.events] == [0.10, 0.30]


def test_parse_gz(tmp_path, cast_v3):

    import gzip

    src = write_v3(tmp_path / "plain.cast")
    data = src.read_bytes()
    with gzip.open(tmp_path / "rec.cast.gz", "wb") as f:
        f.write(data)
    cast = parse(tmp_path / "rec.cast.gz")
    assert cast.duration == pytest.approx(1.25)


def test_theme_palette_parsing():
    t = Theme.from_dict({"fg": "#ffffff", "bg": "#000000", "palette": "#111111:#222222"})
    assert t.palette[0] == "#111111"
    assert len(t.palette) == 2


# ---------- transforms ----------


def test_transform_speed_and_idle(cast_v3):
    fast = transform(cast_v3, speed=2.0)
    assert fast.duration == pytest.approx(cast_v3.duration / 2)

    capped = transform(cast_v3, idle_limit=0.05)
    gaps = [b.time - a.time for a, b in zip(capped.events, capped.events[1:])]
    assert all(g <= 0.05 + 1e-9 for g in gaps)


def test_transform_trim_keeps_history(cast_v3):
    cut = transform(cast_v3, start=0.5)
    assert cut.duration <= cast_v3.duration - 0.5 + 1e-9
    assert cut.events[0].time == 0.0  # history compressed to t=0
    dropped = transform(cast_v3, start=0.5, drop_before_start=True)
    assert all(e.data != "\x1b[1;32m$\x1b[0m echo hi\r\n" for e in dropped.events[:1])


# ---------- writers / convert ----------


def test_convert_roundtrip_v3_v2_v3(tmp_path, cast_v3):
    v2 = convert(cast_v3, tmp_path / "r.v2.cast", to=2)
    back = parse(v2)
    assert [e.data for e in back.events] == [e.data for e in cast_v3.events]
    assert back.duration == pytest.approx(cast_v3.duration, abs=1e-3)

    v3 = convert(back, tmp_path / "r.v3.cast", to=3)
    again = parse(v3)
    assert [e.data for e in again.events] == [e.data for e in cast_v3.events]
    assert again.duration == pytest.approx(cast_v3.duration, abs=1e-3)


def test_convert_v1_writes_deltas(tmp_path, cast_v3):
    v1_path = convert(cast_v3, tmp_path / "r.v1.cast", to=1)
    obj = json.loads(v1_path.read_text())
    assert obj["version"] == 1
    delays = [rec[0] for rec in obj["stdout"]]
    assert all(d >= 0 for d in delays)
    cast = parse(v1_path)
    assert cast.duration == pytest.approx(1.20, abs=1e-3)  # v1 keeps 'o' events only


# ---------- chapters ----------


def test_chapters_from_markers(cast_v3):
    ch = extract_chapters(cast_v3)
    assert len(ch) == 1
    start, end, title = ch[0]
    assert (start, title) == (0.55, "step one")
    assert end == pytest.approx(cast_v3.duration)


def test_chapters_auto(cast_v3):
    ch = extract_chapters(cast_v3, auto=0.5)
    assert len(ch) == 3
    assert ch[0][0] == 0.0


def test_ffmetadata_escaping():
    meta = ffmetadata([(0.0, 1.0, 'chap #1 = "x"')])
    assert 'title=chap \\#1 \\= "x"' in meta
    assert "TIMEBASE=1/1000" in meta


def test_youtube_intro_prepended():
    out = youtube_list([(5.0, 9.0, "late start")])
    assert out.splitlines()[0] == "0:00 Intro"


def test_chapters_formats_smoke(cast_v3):
    ch = extract_chapters(cast_v3)
    assert "WEBVTT" in chapters_vtt(ch)
    json.loads(chapters_json(ch))
    assert "00:00:00" in chapters_text(ch)


# ---------- text ----------


def test_strip_ansi():
    assert strip_ansi("\x1b[1;31mhi\x1b[0m") == "hi"
    assert strip_ansi("\x1b]0;title\x07ok") == "ok"


def test_write_text_modes(tmp_path, cast_v3):
    stream = write_text(cast_v3, tmp_path / "s.txt", mode="stream")
    assert "hi" in stream.read_text()
    assert "\x1b" not in stream.read_text()

    timed = write_text(cast_v3, tmp_path / "t.txt", mode="timed")
    assert "[00:00:00]" in timed.read_text()


def test_subtitles_no_zero_length(tmp_path, cast_v3):
    p = write_subtitles(cast_v3, tmp_path / "a.srt")
    content = p.read_text()
    for line in content.splitlines():
        if "-->" in line:
            a, b = line.split(" --> ")
            assert a != b, f"zero-length cue: {line}"


# ---------- svg ----------


def test_svg_export_valid_xml(tmp_path, cast_v3):
    p = export_svg(cast_v3, tmp_path / "a.svg")
    import xml.etree.ElementTree as ET

    root = ET.parse(p).getroot()
    assert root.tag.endswith("svg")
    content = p.read_text()
    assert "animation-delay" in content
    assert "@keyframes" in content


def test_svg_background_cells_rendered(tmp_path, cast_v3):
    """Cells that are only a background color (spaces) must still paint."""
    p = export_svg(cast_v3, tmp_path / "b.svg")
    content = p.read_text()
    # the demo feeds \x1b[48;5;208m bg — bg fill rect for the run must exist
    assert content.count("<rect") >= 3


# ---------- summary ----------


def test_summary_shape(cast_v3):
    s = summary(cast_v3, source="x.cast")
    assert s["asciicast_version"] == 3
    assert s["duration_seconds"] == pytest.approx(1.25)
    assert s["events"]["by_type"]["m"] == 1
    assert s["markers"][0]["label"] == "step one"


# ---------- errors ----------


def test_bad_file_raises(tmp_path):
    bad = tmp_path / "bad.cast"
    bad.write_text("not json\n")
    with pytest.raises(ValueError):
        parse(bad)
    from castkit.themes import resolve_theme

    c = parse(write_v3(tmp_path / "c.cast"))
    with pytest.raises(CastkitError):
        resolve_theme(c, "nope")
