"""Typewriter effect: re-time a cast so output appears character by character."""

from __future__ import annotations

import re

from .. import ShowreelError
from .model import Cast, Event

__all__ = ["typewriter"]

# escape sequences move as atomic units, never split mid-sequence
_ESCAPE = re.compile(
    r"\x1b\[[0-9;:?]*[A-Za-z]"  # CSI
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC
    r"|\x1b[PX^_][^\x1b]*\x1b\\"  # DCS/SOS/PM/APC
    r"|\x1b[@-Z\\-_]"  # other two-byte escapes
)
_MAX_TOKENS = 200_000


def _tokens(data: str) -> list[tuple[str, bool]]:
    """Split event data into (token, visible) pairs. Escape runs and newline
    groups are atomic; every other character is its own token."""
    out: list[tuple[str, bool]] = []
    i = 0
    for m in _ESCAPE.finditer(data):
        if m.start() > i:
            out.extend(_text_tokens(data[i : m.start()]))
        out.append((m.group(), False))
        i = m.end()
    if i < len(data):
        out.extend(_text_tokens(data[i:]))
    return out


def _text_tokens(s: str) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    i = 0
    while i < len(s):
        if s[i] in "\r\n":
            j = i
            while j < len(s) and s[j] in "\r\n":
                j += 1
            out.append((s[i:j], True))  # newline group = one beat
            i = j
        else:
            out.append((s[i], True))
            i += 1
    return out


def typewriter(cast: Cast, cps: float = 40.0) -> Cast:
    """Re-time output so visible characters appear at `cps` characters per second.

    Original gaps are replaced by the uniform typing rhythm (combine with
    --speed to scale globally). Escape sequences ride along with the next
    visible token so styles stay attached; markers/exit events keep their order.
    """
    cps = max(float(cps), 1.0)
    per = 1.0 / cps

    total = sum(len(_tokens(e.data)) if e.etype == "o" else 0 for e in cast.events)
    if total > _MAX_TOKENS:
        raise ShowreelError(f"typewriter: {total} tokens is too fine-grained; raise --typewriter cps")

    out: list[Event] = []
    t = 0.0
    for e in cast.events:
        if e.etype != "o" or not e.data:
            out.append(Event(t, e.etype, e.data))
            continue
        prefix = ""
        for tok, visible in _tokens(e.data):
            if not visible:
                prefix += tok  # SGR/escapes attach to the next visible beat
                continue
            out.append(Event(t, "o", prefix + tok))
            t += per
            prefix = ""
        if prefix:  # trailing resets don't cost a beat
            out.append(Event(t, "o", prefix))
    return Cast(header=cast.header, events=out)
