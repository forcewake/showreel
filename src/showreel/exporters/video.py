"""Video export: MP4 / WebM / MKV / MOV via ffmpeg raw-pipe, with chapters and optional audio."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .. import ShowreelError
from ..core.model import Cast
from ..core.transform import transform
from ..fonts import find_font
from ..playback import Player
from ..render import Renderer
from ..themes import resolve_theme
from .chapters import extract_chapters, ffmetadata
from .ffmpeg_base import Progress, require_ffmpeg

__all__ = ["VIDEO_FORMATS", "export_video"]

VIDEO_FORMATS = {
    "mp4": {
        "codec": ["-c:v", "libx264", "-preset", "medium", "-crf", "{crf}", "-pix_fmt", "yuv420p"],
        "extra": ["-movflags", "+faststart"],
        "chapters": True,
        "audio": "aac",
    },
    "mkv": {
        "codec": ["-c:v", "libx264", "-preset", "medium", "-crf", "{crf}"],
        "extra": [],
        "chapters": True,
        "audio": "aac",
    },
    "mov": {
        "codec": ["-c:v", "libx264", "-preset", "medium", "-crf", "{crf}", "-pix_fmt", "yuv420p"],
        "extra": ["-movflags", "+faststart"],
        "chapters": True,
        "audio": "aac",
    },
    "webm": {
        # CRF for VP9 runs 0-63, so we bias it from the x264-style value
        "codec": ["-c:v", "libvpx-vp9", "-crf", "{crf_vp9}", "-b:v", "0", "-row-mt", "1", "-cpu-used", "4"],
        "extra": [],
        "chapters": False,  # chapters are not part of the WebM spec; keep files strictly valid
        "audio": "libopus",
    },
}


def _build_args(
    renderer: Renderer, fps: int, fmt: str, crf: int, meta: str | None, audio: str | None, out: Path
) -> list[str]:
    spec = VIDEO_FORMATS[fmt]
    codec = [a.replace("{crf}", str(crf)).replace("{crf_vp9}", str(crf + 10)) for a in spec["codec"]]
    args: list[str] = [
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{renderer.width}x{renderer.height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",  # 0: video frames
    ]
    if meta:
        args += ["-i", meta]  # 1: ffmetadata chapters
    if audio:
        args += ["-stream_loop", "-1", "-i", audio]  # n: looping background audio
    args += ["-map", "0:v"]
    if meta:
        args += ["-map_metadata", "1", "-map_chapters", "1"]
        if fmt in ("mp4", "mov"):
            args += ["-write_tmcd", "0"]  # suppress the tmcd data track the mov muxer adds with chapters
    if audio:
        args += ["-map", f"{2 if meta else 1}:a?"]
        args += codec + spec["extra"]
        args += ["-c:a", spec["audio"], "-b:a", "128k", "-shortest"]
    else:
        args += codec + spec["extra"] + ["-an"]
    args += [str(out)]
    return args


def export_video(
    cast: Cast,
    out: str | Path,
    fmt: str = "mp4",
    fps: int = 20,
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    idle_limit: float | None = None,
    crf: int = 20,
    theme: str = "auto",
    font: str | None = None,
    font_size: int = 24,
    padding: int = 16,
    cursor: str = "block",
    chrome_title: str | None = None,
    width: int | None = None,
    audio: str | None = None,
    chapters: str = "markers",  # markers | auto[:N] | off
    hold: float = 0.5,  # extra seconds on the final frame
    bold_is_bright: bool = False,
    radius: int = 0,
    shadow: bool = False,
    margin: int = 0,
    margin_fill: str | None = None,
    watermark: str | None = None,
    chrome_style: str = "mac",
    cursor_blink: int = 0,  # blink period in ms; 0 = steady cursor
    quiet: bool = False,
) -> Path:
    """Render the cast to a video file frame-by-frame and pipe into ffmpeg."""
    fmt = fmt.lower().lstrip(".")
    if fmt not in VIDEO_FORMATS:
        raise ShowreelError(f"unsupported video format '{fmt}'. Available: {', '.join(VIDEO_FORMATS)}")
    spec = VIDEO_FORMATS[fmt]
    require_ffmpeg()

    tcast = transform(cast, start=start, end=end, speed=speed, idle_limit=idle_limit)
    if not tcast.events:
        raise ShowreelError("recording has no events — nothing to export")
    duration = tcast.duration
    total_frames = max(1, int(duration * fps) + 1 + int(max(0.0, hold) * fps))

    resolved = resolve_theme(cast, theme)
    player = Player(tcast)
    if width:
        from ..render import font_size_for_width

        font_size = font_size_for_width(
            player.cols,
            width,
            find_font(font),
            padding=padding,
            margin=margin,
            shadow=shadow,
            chrome=bool(chrome_title),
        )
    renderer = Renderer(
        resolved,
        player.cols,
        player.rows,
        font_size=font_size,
        font_path=font,
        padding=padding,
        chrome_title=chrome_title,
        cursor=cursor,
        bold_is_bright=bold_is_bright,
        radius=radius,
        shadow=shadow,
        margin=margin,
        margin_fill=margin_fill,
        watermark=watermark,
        chrome_style=chrome_style,
        target_width=width,
    )

    meta_path: Path | None = None
    if chapters != "off" and spec["chapters"]:
        auto: float | None = None
        if chapters.startswith("auto"):
            auto = float(chapters.split(":", 1)[1]) if ":" in chapters else 30.0
        chapter_list = extract_chapters(tcast, auto=auto)
        if chapter_list:
            fd, meta_name = tempfile.mkstemp(suffix=".ffmeta")
            meta_path = Path(meta_name)
            with open(fd, "w", encoding="utf-8") as f:
                f.write(ffmetadata(chapter_list, title=tcast.header.title))

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = _build_args(renderer, fps, fmt, crf, str(meta_path) if meta_path else None, audio, out_path)

    proc = subprocess.Popen(
        [require_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None

    prog = Progress(total_frames, f"rendering {fmt} {renderer.width}x{renderer.height}", quiet)
    try:
        for i in range(total_frames):
            player.seek(i / fps)
            show = ((i * 1000 // fps) // cursor_blink) % 2 == 0 if cursor_blink > 0 else None
            img = renderer.render(player, cache=True, show_cursor=show)
            try:
                proc.stdin.write(img.tobytes())
            except BrokenPipeError:
                break
            prog.step()
        proc.stdin.close()
    except KeyboardInterrupt:
        proc.kill()
        raise
    finally:
        prog.finish()

    stderr = proc.stderr.read().decode() if proc.stderr else ""
    rc = proc.wait()
    if meta_path and meta_path.exists():
        meta_path.unlink()
    if rc != 0:
        raise ShowreelError(f"ffmpeg failed ({rc}):\n{stderr.strip()}")
    return out_path
