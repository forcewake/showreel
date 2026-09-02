"""Recording summary for humans and AI agents (single JSON object on stdout or file)."""

from __future__ import annotations

import json
from pathlib import Path

from ..core.model import Cast

__all__ = ["summary", "write_summary"]


def summary(cast: Cast, source: str | None = None, strip_ansi_fn=None) -> dict:
    from .text import strip_ansi

    h = cast.header
    counts: dict[str, int] = {}
    for e in cast.events:
        counts[e.etype] = counts.get(e.etype, 0) + 1

    # first plausible command: first output line that ends with a prompt-ish '#'/''$'
    first_cmd = None
    for e in cast.events:
        if e.etype != "o":
            continue
        text = strip_ansi(e.data)
        for line in text.splitlines():
            line = line.strip()
            if line.endswith("$") or line.endswith("#"):
                tail = line[:-1].strip()
                if tail and not tail.endswith("\\"):
                    first_cmd = tail
                    break
        if first_cmd:
            break

    return {
        "tool": "showreel",
        "source": source,
        "asciicast_version": h.version,
        "title": h.title,
        "command": h.command,
        "recorded_at": h.timestamp,
        "duration_seconds": round(cast.duration, 3),
        "terminal": {
            "cols": h.term.cols,
            "rows": h.term.rows,
            "type": h.term.type,
        },
        "env": h.env,
        "tags": h.tags,
        "events": {"total": len(cast.events), "by_type": counts},
        "markers": [{"time": round(t, 3), "label": label} for t, label in cast.markers()],
        "first_prompt": first_cmd,
    }


def write_summary(cast: Cast, out: str | Path, source: str | None = None) -> Path:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary(cast, source), indent=2) + "\n", encoding="utf-8")
    return out_path
