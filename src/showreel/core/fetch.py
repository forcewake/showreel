"""Input sources: download .cast recordings from https URLs (incl. asciinema.org)."""

from __future__ import annotations

import tempfile
from urllib.request import Request, urlopen

__all__ = ["is_url", "download", "normalize_asciinema_url"]


def is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def normalize_asciinema_url(url: str) -> str:
    """asciinema.org/a/<id> pages embed a player; the recording lives at <id>.cast."""
    url = url.rstrip("/")
    if url.startswith("https://asciinema.org/a/") and not url.endswith(".cast"):
        url += ".cast"
    return url


def download(url: str, timeout: int = 30) -> str:
    """Download url to a temp file and return its path."""
    url = normalize_asciinema_url(url)
    req = Request(url, headers={"User-Agent": "showreel"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    suffix = ".cast" if not url.endswith(".gz") else ".cast.gz"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name
