"""Shared ffmpeg plumbing: binary discovery, raw frame piping, progress."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time

from .. import CastkitError

__all__ = ["Progress", "ffmpeg_binary", "require_ffmpeg", "run_ffmpeg"]


def ffmpeg_binary() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise CastkitError(
            "ffmpeg not found on PATH. Install it (brew install ffmpeg / apt install ffmpeg) "
            "— it is required for video, GIF and APNG export."
        )
    return path


def run_ffmpeg(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    cmd = [require_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args]
    try:
        return subprocess.run(cmd, capture_output=capture, text=True)
    except FileNotFoundError as e:
        raise CastkitError(f"failed to run ffmpeg: {e}") from e


class Progress:
    """Simple stderr progress reporter (throttled)."""

    def __init__(self, total: int, label: str, quiet: bool = False):
        self.total = max(1, total)
        self.label = label
        self.quiet = quiet
        self.last = 0.0
        self.done = 0

    def step(self, n: int = 1) -> None:
        self.done += n
        if self.quiet:
            return
        now = time.monotonic()
        if now - self.last >= 1.0 or self.done >= self.total:
            self.last = now
            pct = 100 * self.done // self.total
            sys.stderr.write(f"\rcastkit: {self.label} {pct:3d}% ({self.done}/{self.total})")
            sys.stderr.flush()

    def finish(self) -> None:
        if not self.quiet:
            sys.stderr.write(f"\rcastkit: {self.label} 100% ({self.done}/{self.total})\n")
