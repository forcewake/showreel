"""GIF / APNG export via ffmpeg (two-pass palette for GIF)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .. import ShowreelError
from ..core.model import Cast
from ..core.transform import transform
from ..playback import Player
from ..render import Renderer
from ..themes import resolve_theme
from .ffmpeg_base import Progress, require_ffmpeg

__all__ = ["export_gif"]


def export_gif(
    cast: Cast,
    out: str | Path,
    fmt: str = "gif",  # gif | apng | webp
    fps: int = 12,
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    idle_limit: float | None = None,
    width: int | None = None,
    theme: str = "auto",
    font: str | None = None,
    font_size: int | None = None,
    padding: int = 12,
    cursor: str = "block",
    chrome_title: str | None = None,
    max_colors: int = 256,
    dither: str = "bayer",
    bayer_scale: int = 4,
    hold: float = 2.0,  # extra seconds on the final frame before looping
    bold_is_bright: bool = False,
    radius: int = 0,
    shadow: bool = False,
    margin: int = 0,
    margin_fill: str | None = None,
    watermark: str | None = None,
    chrome_style: str = "mac",
    cursor_blink: int = 0,
    quiet: bool = False,
) -> Path:
    fmt = fmt.lower()
    if fmt not in ("gif", "apng", "webp"):
        raise ShowreelError(f"unsupported animated-image format '{fmt}' (use gif, apng or webp)")
    require_ffmpeg()

    tcast = transform(cast, start=start, end=end, speed=speed, idle_limit=idle_limit)
    if not tcast.events:
        raise ShowreelError("recording has no events — nothing to export")
    duration = tcast.duration
    total_frames = max(1, int(duration * fps) + 1 + int(max(0.0, hold) * fps))

    if font_size is None:
        font_size = 20
    if width:
        # pick a font size so the rendered width lands close to `width`
        from ..fonts import find_font
        from ..render import measure_font

        probe_w = measure_font(find_font(font), 100)[0]
        font_size = max(8, min(72, round(width / (tcast.header.term.cols * probe_w / 100))))

    resolved = resolve_theme(cast, theme)
    player = Player(tcast)
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
    )

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    size = f"{renderer.width}x{renderer.height}"
    if fmt == "gif":
        vf = (
            f"fps={fps},split[s0][s1];"
            f"[s0]palettegen=max_colors={max_colors}:stats_mode=diff[p];"
            f"[s1][p]paletteuse=dither={dither}:bayer_scale={bayer_scale}:diff_mode=rectangle"
        )
        args = ["-vf", vf, "-loop", "0", str(out_path)]
    elif fmt == "webp":
        args = [
            "-vf",
            f"fps={fps}",
            "-c:v",
            "libwebp_anim",
            "-lossless",
            "0",
            "-q:v",
            "75",
            "-loop",
            "0",
            "-an",
            str(out_path),
        ]
    else:  # apng
        args = ["-f", "apng", "-plays", "0", "-vf", f"fps={fps}", str(out_path)]

    proc_args = [
        require_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        size,
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        *args,
    ]
    proc = subprocess.Popen(proc_args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    prog = Progress(total_frames, f"rendering {fmt} {size}", quiet)
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
    if rc != 0:
        raise ShowreelError(f"ffmpeg failed ({rc}):\n{stderr.strip()}")
    return out_path
