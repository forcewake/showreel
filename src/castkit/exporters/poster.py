"""Poster: single still frame (PNG) rendered at a chosen time."""

from __future__ import annotations

from pathlib import Path

from .. import CastkitError
from ..core.model import Cast
from ..core.transform import transform
from ..playback import Player
from ..render import Renderer
from ..themes import resolve_theme

__all__ = ["export_poster"]


def export_poster(
    cast: Cast,
    out: str | Path,
    at: float | None = None,
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    theme: str = "auto",
    font: str | None = None,
    font_size: int = 24,
    padding: int = 16,
    cursor: str = "block",
    chrome_title: str | None = None,
    bold_is_bright: bool = False,
    radius: int = 0,
    shadow: bool = False,
    margin: int = 0,
    margin_fill: str | None = None,
    watermark: str | None = None,
    chrome_style: str = "mac",
) -> Path:
    """Render one frame as PNG. Default time: the end of the recording (final screen)."""
    tcast = transform(cast, start=start, end=end, speed=speed)
    if not tcast.events:
        raise CastkitError("recording has no events — nothing to export")
    t = tcast.duration if at is None else min(max(at, 0.0), tcast.duration)

    resolved = resolve_theme(cast, theme)
    player = Player(tcast)
    player.seek(t)
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
    img = renderer.render(player)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path
