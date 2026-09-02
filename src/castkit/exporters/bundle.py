"""`castkit all`: export everything into one directory + manifest.json."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from .. import __version__
from ..core.model import Cast
from .chapters import (
    chapters_json,
    chapters_text,
    extract_chapters,
    youtube_list,
)
from .convert import convert
from .gif import export_gif
from .html import export_html
from .poster import export_poster
from .svg import export_svg
from .text import write_markdown, write_subtitles, write_text

__all__ = ["GROUPS", "export_bundle"]

GROUPS = {
    "video": "mp4, mkv (both with chapters from markers)",
    "animated": "gif",
    "svg": "animated svg",
    "web": "html player, poster png",
    "text": "txt, md (with chapters), transcript vtt subtitles",
    "data": "cast v3 + cast v2, summary json, chapters json",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def export_bundle(
    cast: Cast,
    outdir: str | Path,
    stem: str | None = None,
    groups: list[str] | None = None,
    speed: float = 1.0,
    idle_limit: float | None = None,
    fps: int = 20,
    theme: str = "auto",
    font: str | None = None,
    font_size: int = 24,
    chrome_title: str | None = "default",
    cursor: str = "block",
    bold_is_bright: bool = False,
    radius: int = 0,
    shadow: bool = False,
    margin: int = 0,
    margin_fill: str | None = None,
    watermark: str | None = None,
    chrome_style: str = "mac",
    cursor_blink: int = 0,
    typewriter_cps: str | None = None,
    quiet: bool = False,
) -> Path:
    groups = groups or list(GROUPS)
    deco = dict(
        radius=radius,
        shadow=shadow,
        margin=margin,
        margin_fill=margin_fill,
        watermark=watermark,
        chrome_style=chrome_style,
    )
    deco_frames = {**deco, "cursor_blink": cursor_blink}
    deco_svg = {**deco, "cursor_blink": cursor_blink or 1200}
    if typewriter_cps:
        from ..core.typewriter import typewriter

        cast = typewriter(cast, cps=float(typewriter_cps))
    out_path = Path(outdir)
    stem = stem or out_path.name or "recording"
    out_path.mkdir(parents=True, exist_ok=True)
    chrome = stem if chrome_title == "default" else (chrome_title or None)

    def log(msg: str) -> None:
        if not quiet:
            print(f"castkit: {msg}", file=sys.stderr)

    made: list[Path] = []

    if "video" in groups:
        from .video import export_video

        log("exporting mp4 (with chapters)…")
        made.append(
            export_video(
                cast,
                out_path / f"{stem}.mp4",
                fps=fps,
                speed=speed,
                idle_limit=idle_limit,
                theme=theme,
                font=font,
                font_size=font_size,
                chrome_title=chrome,
                cursor=cursor,
                bold_is_bright=bold_is_bright,
                **deco_frames,
                quiet=quiet,
            )
        )
        log("exporting mkv (with chapters)…")
        made.append(
            export_video(
                cast,
                out_path / f"{stem}.mkv",
                fmt="mkv",
                fps=fps,
                speed=speed,
                idle_limit=idle_limit,
                theme=theme,
                font=font,
                font_size=font_size,
                chrome_title=chrome,
                cursor=cursor,
                bold_is_bright=bold_is_bright,
                **deco_frames,
                quiet=quiet,
            )
        )
    if "animated" in groups:
        log("exporting gif…")
        made.append(
            export_gif(
                cast,
                out_path / f"{stem}.gif",
                speed=speed,
                idle_limit=idle_limit,
                theme=theme,
                font=font,
                chrome_title=chrome,
                cursor=cursor,
                bold_is_bright=bold_is_bright,
                **deco_frames,
                quiet=quiet,
            )
        )
    if "svg" in groups:
        log("exporting animated svg…")
        made.append(
            export_svg(
                cast,
                out_path / f"{stem}.svg",
                speed=speed,
                idle_limit=idle_limit,
                theme=theme,
                chrome_title=chrome,
                **deco_svg,
            )
        )
    if "web" in groups:
        log("exporting html player…")
        made.append(
            export_html(
                cast,
                out_path / f"{stem}.html",
                theme=theme,
                speed=speed,
                idle_limit=idle_limit,
                margin_fill=margin_fill,
            )
        )
        log("exporting poster…")
        made.append(
            export_poster(
                cast,
                out_path / f"{stem}.poster.png",
                theme=theme,
                font=font,
                font_size=font_size,
                chrome_title=chrome,
                cursor=cursor,
                bold_is_bright=bold_is_bright,
                **deco,
            )
        )
    if "text" in groups:
        log("exporting text formats…")
        made.append(write_text(cast, out_path / f"{stem}.txt", mode="stream"))
        made.append(write_text(cast, out_path / f"{stem}.timed.txt", mode="timed"))
        made.append(write_markdown(cast, out_path / f"{stem}.md", source_name=stem))
        made.append(write_subtitles(cast, out_path / f"{stem}.transcript.vtt", fmt="vtt"))
        chapters = extract_chapters(cast)
        if chapters:
            (out_path / f"{stem}.chapters.txt").write_text(chapters_text(chapters), encoding="utf-8")
            (out_path / f"{stem}.chapters.youtube.txt").write_text(youtube_list(chapters), encoding="utf-8")
            made += [out_path / f"{stem}.chapters.txt", out_path / f"{stem}.chapters.youtube.txt"]
    if "data" in groups:
        log("exporting data formats…")
        made.append(convert(cast, out_path / f"{stem}.v3.cast", to=3))
        made.append(convert(cast, out_path / f"{stem}.v2.cast", to=2))
        from .info import write_summary

        made.append(write_summary(cast, out_path / f"{stem}.summary.json", source=stem))
        chapters = extract_chapters(cast)
        if chapters:
            (out_path / f"{stem}.chapters.json").write_text(chapters_json(chapters), encoding="utf-8")
            made.append(out_path / f"{stem}.chapters.json")

    manifest = {
        "tool": f"castkit {__version__}",
        "source_stem": stem,
        "groups": groups,
        "files": [{"name": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p)} for p in sorted(set(made))],
    }
    (out_path / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme = ["# castkit export\n", f"Source: `{stem}.cast` — converted with castkit {__version__}.\n"]
    for group, desc in GROUPS.items():
        if group in groups:
            readme.append(f"- **{group}**: {desc}")
    readme.append("\nSee `manifest.json` for checksums. HTML/SVG files are self-contained: open or embed anywhere.\n")
    (out_path / "README.txt").write_text("\n".join(readme), encoding="utf-8")
    return out_path
