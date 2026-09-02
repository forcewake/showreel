"""Terminal playback: feed cast events through pyte, sample the screen at any time."""

from __future__ import annotations

import re

import pyte

from .core.model import Cast

__all__ = ["Player"]

# private mode switches pyte ignores but we honour: alternate screen buffer
_ALT = re.compile(rb"(\x1b\[\?(?:1049|1047|47)[hl])")
_ALT_ENTER = {b"\x1b[?1049h", b"\x1b[?47h", b"\x1b[?1047h"}


class Player:
    """Replays output events through a pyte terminal emulator with forward-only seeking."""

    def __init__(self, cast: Cast, cols: int | None = None, rows: int | None = None):
        self.cast = cast
        self.cols = cols or cast.header.term.cols
        self.rows = rows or cast.header.term.rows
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.ByteStream(self.screen)  # bytes: handles UTF-8 across chunk boundaries
        self._saved: tuple[dict, int, int] | None = None  # primary buffer + cursor
        self._idx = 0
        self._time = 0.0

    @property
    def time(self) -> float:
        return self._time

    def feed(self, data: bytes) -> None:
        """Feed bytes, handling alternate-screen switches pyte doesn't know about."""
        for seg in _ALT.split(data):
            if not seg:
                continue
            if seg in _ALT_ENTER:
                self._save_primary()
            elif seg in (b"\x1b[?1049l", b"\x1b[?47l", b"\x1b[?1047l"):
                self._restore_primary()
            else:
                self.stream.feed(seg)

    def _save_primary(self) -> None:
        buf = {y: dict(row) for y, row in self.screen.buffer.items()}
        self._saved = (buf, self.screen.cursor.x, self.screen.cursor.y)
        self.screen.reset()

    def _restore_primary(self) -> None:
        if self._saved is None:
            self.screen.reset()
            return
        buf, cx, cy = self._saved
        # rows must stay pyte StaticDefaultDicts — display() relies on __missing__
        buffer = self.screen.buffer
        buffer.clear()
        for y, row in buf.items():
            restored = pyte.screens.StaticDefaultDict(self.screen.default_char)
            restored.update(row)
            buffer[y] = restored
        self.screen.cursor.x, self.screen.cursor.y = cx, cy

    def seek(self, t: float) -> None:
        """Advance the emulator to absolute time t (forward only)."""
        if t < self._time:
            raise ValueError(f"seek backwards requested ({self._time} -> {t}); create a new Player")
        events = self.cast.events
        while self._idx < len(events) and events[self._idx].time <= t:
            e = events[self._idx]
            if e.etype == "o":
                self.feed(e.data.encode("utf-8"))
            # 'm', 'i', 'r', 'x' don't affect the screen
            self._idx += 1
        self._time = max(self._time, t)

    # -- screen accessors -------------------------------------------------

    def display(self) -> list[str]:
        return self.screen.display[: self.rows]

    def cells(self):
        """Yield (row, col, Char) for every non-blank cell."""
        buf = self.screen.buffer
        default = pyte.screens.Char(" ", "default", "default")
        for y in range(self.rows):
            row = buf.get(y)
            if not row:
                continue
            for x in range(self.cols):
                ch = row.get(x, default)
                if ch.data != " " or ch.bg != "default":
                    yield y, x, ch

    def cursor(self) -> tuple[int, int, bool]:
        c = self.screen.cursor
        return c.x, c.y, bool(getattr(c, "hidden", False))

    def state_hash(self) -> bytes:
        """Cheap fingerprint of visible screen (chars + styles + cursor)."""
        parts = [b"|".join(line.encode("utf-8", "replace") for line in self.display())]
        styles = []
        for y, x, ch in self.cells():
            styles.append(
                f"{y},{x},{ch.fg},{ch.bg},{int(ch.bold)}{int(ch.italics)}{int(ch.underscore)}{int(ch.reverse)}{int(ch.strikethrough)}".encode()
            )
        parts.append(b";".join(styles))
        cx, cy, hidden = self.cursor()
        parts.append(f"{cx},{cy},{int(hidden)}".encode())
        return b"\n".join(parts)
