"""Chapters: from 'm' marker events (or auto-split) to ffmpeg/YT/VTT/JSON formats."""

from __future__ import annotations

from ..core.model import Cast

__all__ = ["chapters_json", "chapters_vtt", "escape_ffmetadata", "extract_chapters", "ffmetadata", "youtube_list"]


def extract_chapters(cast: Cast, auto: float | None = None) -> list[tuple[float, float, str]]:
    """Return [(start, end, title)]. Uses marker events; auto=N splits every N seconds."""
    duration = cast.duration or 0.0
    if auto:
        marks: list[tuple[float, str]] = []
        t = 0.0
        n = 1
        while t < duration:
            marks.append((t, f"Chapter {n}"))
            t += auto
            n += 1
    else:
        marks = cast.markers()
        for i, (t, label) in enumerate(marks):
            if not label.strip():
                marks[i] = (t, f"Marker {i + 1}")
    if not marks:
        return []
    chapters = []
    for i, (start, label) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else duration
        if end <= start:
            end = start + 0.001
        chapters.append((start, end, label))
    return chapters


def escape_ffmetadata(text: str) -> str:
    out = []
    for ch in text:
        if ch in "=;#\\\n":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def ffmetadata(chapters: list[tuple[float, float, str]], title: str | None = None) -> str:
    lines = [";FFMETADATA1"]
    if title:
        lines.append(f"title={escape_ffmetadata(title)}")
    for start, end, name in chapters:
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={int(start * 1000)}",
            f"END={int(end * 1000)}",
            f"title={escape_ffmetadata(name)}",
        ]
    return "\n".join(lines) + "\n"


def _ts_hms(t: float, ms: bool = False) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    if ms:
        frac = int(round((t - int(t)) * 1000))
        if frac >= 1000:
            frac = 999
        return f"{h:02d}:{m:02d}:{s:02d}.{frac:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def youtube_list(chapters: list[tuple[float, float, str]]) -> str:
    """YouTube description chapter list. YouTube requires the first chapter to start at 0:00."""
    if chapters and chapters[0][0] > 0.5:
        chapters = [(0.0, chapters[0][0], "Intro")] + list(chapters)
    lines = []
    for start, _end, name in chapters:
        h, rem = divmod(int(start), 3600)
        m, s = divmod(rem, 60)
        stamp = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        lines.append(f"{stamp} {name}")
    return "\n".join(lines) + "\n"


def chapters_vtt(chapters: list[tuple[float, float, str]]) -> str:
    lines = ["WEBVTT", ""]
    for i, (start, end, name) in enumerate(chapters, 1):
        lines += [f"{i}", f"{_ts_hms(start, ms=True)} --> {_ts_hms(end, ms=True)}", name, ""]
    return "\n".join(lines)


def chapters_json(chapters: list[tuple[float, float, str]]) -> str:
    import json

    return (
        json.dumps(
            [
                {"start": round(s, 3), "end": round(e, 3), "title": t, "duration": round(e - s, 3)}
                for s, e, t in chapters
            ],
            indent=2,
        )
        + "\n"
    )


def chapters_text(chapters: list[tuple[float, float, str]]) -> str:
    lines = []
    for start, _end, name in chapters:
        lines.append(f"{_ts_hms(start)}  {name}")
    return "\n".join(lines) + "\n"
