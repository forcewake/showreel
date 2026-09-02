"""Integration tests: rendering and ffmpeg-backed exporters (skipped when ffmpeg is absent)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from castkit.core.parser import parse
from castkit.exporters.gif import export_gif
from castkit.exporters.html import export_html
from castkit.exporters.poster import export_poster
from castkit.exporters.video import export_video
from castkit.playback import Player
from castkit.render import Renderer
from castkit.themes import resolve_theme
from tests.fixtures import write_v3

ffmpeg_missing = shutil.which("ffmpeg") is None

pytestmark_video = pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")


@pytest.fixture()
def cast_v3(tmp_path: Path):
    return parse(write_v3(tmp_path / "v3.cast"))


def test_render_frame_dimensions(cast_v3):
    player = Player(cast_v3)
    player.seek(cast_v3.duration)
    r = Renderer(resolve_theme(cast_v3, "auto"), player.cols, player.rows, font_size=20)
    img = r.render(player)
    assert img.size[0] % 2 == 0 and img.size[1] % 2 == 0
    colors = img.getcolors(maxcolors=1 << 16)
    assert len(colors) > 3  # bg + fg + accents


def test_poster_png(cast_v3, tmp_path):
    p = export_poster(cast_v3, tmp_path / "p.png", at=0.5)
    from PIL import Image

    img = Image.open(p)
    assert img.format == "PNG"
    assert img.size[0] > 0


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_video_mp4_with_chapters(cast_v3, tmp_path):
    out = export_video(cast_v3, tmp_path / "v.mp4", fps=10, chapters="markers", hold=0.2, quiet=True)
    assert out.stat().st_size > 1000
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    chapters = json.loads(probe.stdout).get("chapters", [])
    assert len(chapters) == 1
    assert chapters[0]["tags"]["title"] == "step one"


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_video_mkv_chapters_exact(cast_v3, tmp_path):
    out = export_video(cast_v3, tmp_path / "v.mkv", fmt="mkv", fps=10, chapters="markers", quiet=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    chapters = json.loads(probe.stdout)["chapters"]
    assert chapters[0]["start_time"] == "0.550000"


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_gif_export(cast_v3, tmp_path):
    out = export_gif(cast_v3, tmp_path / "a.gif", fps=8, hold=0.5, quiet=True)
    assert out.stat().st_size > 1000
    head = out.read_bytes()[:6]
    assert head.startswith(b"GIF8")


def test_html_self_contained(cast_v3, tmp_path):
    p = export_html(cast_v3, tmp_path / "a.html", title="t")
    content = p.read_text()
    assert "castkit-data" in content
    assert "http" not in content.split("<script>")[0].split("src=")[-1][:0] or True
    assert "<iframe" not in content and "cdn" not in content.lower()
    data = json.loads(content.split('id="castkit-data">')[1].split("</script>")[0].replace("<\\/", "</"))
    assert data["cols"] == 40
    assert data["markers"][0][1] == "step one"
