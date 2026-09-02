#!/usr/bin/env python3
"""Generate a polished, English-only demo .cast (v3) for showreel.

Scenes: banner -> typed command -> build (spinner + progress bar) -> tests
(colored dots) -> deploy -> 256-color palette -> style samples -> final box.
Timing is "real pace"; pass --typewriter to exports for char-by-char playback.
"""

import json
import sys
from pathlib import Path

W, H = 80, 28

THEME_PALETTE = ":".join([
    "#151515", "#ac4142", "#7e8e50", "#e5b567",
    "#6c99bb", "#9f4e85", "#50a5a5", "#d0d0d0",
    "#505050", "#ac4142", "#7e8e50", "#e5b567",
    "#6c99bb", "#9f4e85", "#50a5a5", "#f5f5f5",
])

header = {
    "version": 3,
    "term": {
        "cols": W,
        "rows": H,
        "type": "xterm-256color",
        "theme": {
            "fg": "#d0d0d0",
            "bg": "#101014",
            "palette": THEME_PALETTE,
        },
    },
    "timestamp": 1725264000,
    "title": "showreel demo — production deploy",
    "env": {"SHELL": "/bin/zsh"},
    "tags": ["demo", "deploy"],
}

E = []  # (interval, code, data)

PROMPT = "\x1b[1;36m~/projects/webapp\x1b[0m \x1b[1;32m❯\x1b[0m "


def out(data, dt=0.1):
    E.append([dt, "o", data])


def marker(label, dt=0.05):
    E.append([dt, "m", label])


def newline(dt=0.05):
    out("\r\n", dt)


# ── banner ────────────────────────────────────────────────────────────────────
out("\x1b[1;36m╭──────────────────────────────────────────────────╮\x1b[0m\r\n", 0.05)
out("\x1b[1;36m│\x1b[0m  \x1b[1;33m◆ showreel demo\x1b[0m — production deploy, in style    \x1b[1;36m│\x1b[0m\r\n", 0.15)
out("\x1b[1;36m╰──────────────────────────────────────────────────╯\x1b[0m\r\n", 0.05)
newline(0.3)

# ── typed command ─────────────────────────────────────────────────────────────
out(PROMPT, 0.35)
for ch in "showreel deploy --env production":
    out(ch, 0.055)
newline(0.4)

# ── build ─────────────────────────────────────────────────────────────────────
marker("build")
spin = "▖▘▝▗"
for i in range(12):
    frame = spin[i % len(spin)]
    out(f"\r\x1b[2K\x1b[36m{frame}\x1b[0m bundling modules…", 0.09)
out(f"\r\x1b[2K\x1b[32m✓\x1b[0m 428 modules bundled in \x1b[1m1.42s\x1b[0m\r\n", 0.25)
newline(0.2)

# loading bar: draw the empty track ONCE, then fill cells in place and tick
# the percentage — with typewriter playback this reads as a real loading bar
# (no full-line re-typing, no width breathing)
WIDTH = 30
out(f"  {'░' * WIDTH} 0%", 0.3)
prev_filled = 0
for pct in range(5, 101, 5):
    filled = round(pct / 100 * WIDTH)
    delta = filled - prev_filled
    start_col = 2 + prev_filled  # 0-based first new cell
    prev_filled = filled
    seq = f"\r\x1b[{start_col + 1}G\x1b[32m" + "█" * delta + "\x1b[0m"
    seq += f"\x1b[33G{pct:>3d}%"  # tick the percentage in place
    out(seq, 0.18)
newline(0.2)

# ── tests ─────────────────────────────────────────────────────────────────────
marker("test")
out("\x1b[1mrunning test suite\x1b[0m\r\n", 0.25)
for i in range(24):
    color = "\x1b[32m" if i != 9 else "\x1b[33m"
    out(f"{color}●\x1b[0m", 0.045)
newline(0.35)
out("\x1b[32m✓\x1b[0m 42 passing  \x1b[33m●\x1b[0m 1 skipped  \x1b[90m0 failing\x1b[0m  \x1b[90m(0.9s)\x1b[0m\r\n", 0.4)
newline(0.2)

# ── deploy ────────────────────────────────────────────────────────────────────
marker("deploy")
out(f"\x1b[90m→\x1b[0m uploading artifacts…        \x1b[32mdone\x1b[0m\r\n", 0.5)
out(f"\x1b[90m→\x1b[0m rolling out replicas        \x1b[36m2/3 → 3/3\x1b[0m\r\n", 0.7)
out(f"\x1b[90m→\x1b[0m waiting for health checks   \x1b[32mpassing\x1b[0m\r\n", 0.55)
out("\x1b[42;30m OK \x1b[0m \x1b[90m{\"status\":\"ok\",\"uptime\":86402,\"version\":\"1.4.2\"}\x1b[0m\r\n", 0.45)
newline(0.25)

# ── palette ───────────────────────────────────────────────────────────────────
marker("palette")
out("\x1b[1m256 colors, as rendered:\x1b[0m\r\n", 0.2)
for row in range(2):
    line = "".join(f"\x1b[48;5;{16 + row * 36 + i}m " for i in range(36))
    out(line + "\x1b[0m\r\n", 0.12)
out("\x1b[7m reversed \x1b[0m  \x1b[1m bold \x1b[0m  \x1b[3m italic \x1b[0m  \x1b[4m underline \x1b[0m  \x1b[9m strike \x1b[0m\r\n", 0.35)
newline(0.2)

# ── final box ─────────────────────────────────────────────────────────────────
marker("done")
out("\x1b[1;32m╭──────────────────────────────────────────────────╮\x1b[0m\r\n", 0.05)
out("\x1b[1;32m│\x1b[0m ✓ deployed in \x1b[1m12.4s\x1b[0m → \x1b[4;34mhttps://webapp.example.com\x1b[0m \x1b[1;32m│\x1b[0m\r\n", 0.2)
out("\x1b[1;32m╰──────────────────────────────────────────────────╯\x1b[0m\r\n", 0.05)
newline(0.3)
out(PROMPT, 0.4)
E.append([0.2, "x", "0"])

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/demo.cast")
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header) + "\n")
    for dt, code, data in E:
        f.write(json.dumps([dt, code, data]) + "\n")
print(f"wrote {path} ({len(E)} events, {sum(d for d, _, _ in E):.2f}s)")
