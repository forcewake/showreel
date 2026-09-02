#!/usr/bin/env python3
"""Generate a realistic demo .cast (v3) exercising colors, cursor moves, markers, resize."""

import json
import sys
from pathlib import Path

W, H = 80, 24

header = {
    "version": 3,
    "term": {
        "cols": W,
        "rows": H,
        "type": "xterm-256color",
        "theme": {
            "fg": "#d0d0d0",
            "bg": "#101014",
            "palette": ":".join([
                "#151515", "#ac4142", "#7e8e50", "#e5b567",
                "#6c99bb", "#9f4e85", "#50a5a5", "#d0d0d0",
                "#505050", "#ac4142", "#7e8e50", "#e5b567",
                "#6c99bb", "#9f4e85", "#50a5a5", "#f5f5f5",
            ]),
        },
    },
    "timestamp": 1725264000,
    "title": "castkit demo — deploying webapp",
    "env": {"SHELL": "/bin/zsh"},
    "tags": ["demo", "deploy"],
}

E = []  # (interval, code, data)


def out(data, dt=0.1):
    E.append([dt, "o", data])


def marker(label, dt=0.05):
    E.append([dt, "m", label])


out("\x1b[1;36m~/projects/webapp\x1b[0m \x1b[1;32m❯\x1b[0m ", 0.4)
out("git status\r\n", 0.6)
out("\x1b[32mOn branch main\x1b[0m\r\nYour branch is up to date with 'origin/main'.\r\n\r\nnothing to commit, working tree clean\r\n", 0.3)
marker("build")
out("\r\n\x1b[1;36m~/projects/webapp\x1b[0m \x1b[1;32m❯\x1b[0m ", 0.5)
out("npm run build\r\n", 0.7)
out("\r\n\x1b[1m> webapp@1.4.2 build\x1b[0m\r\n> vite build\r\n\r\n", 0.4)
for i, pct in enumerate(range(0, 101, 10)):
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    out(f"\r\x1b[2K\x1b[90m{bar}\x1b[0m transforming modules… {pct:3d}%", 0.22)
out("\r\n\x1b[32m✓\x1b[0m 428 modules transformed.\r\n", 0.3)
out("\x1b[32m✓\x1b[0m built in \x1b[1m1.42s\x1b[0m\r\n\r\n", 0.25)
marker("deploy")
out("\x1b[1;36m~/projects/webapp\x1b[0m \x1b[1;32m❯\x1b[0m ", 0.6)
out("kubectl rollout status deploy/webapp\r\n", 0.8)
out("Waiting for deployment \"webapp\" rollout to finish: 2 of 3 updated replicas are available…\r\n", 0.9)
out("deployment \"webapp\" successfully rolled out\r\n\r\n", 0.4)
out("\x1b[1;36m~/projects/webapp\x1b[0m \x1b[1;32m❯\x1b[0m ", 0.5)
out("curl -s https://webapp.example.com/health\r\n", 0.7)
out('\x1b[42;30m OK \x1b[0m \x1b[90m{"status":"ok","uptime":86402,"version":"1.4.2"}\x1b[0m\r\n', 0.4)
marker("palette", 0.6)
out("\r\n\x1b[1m256-color preview:\x1b[0m\r\n", 0.2)
for row in range(2):
    line = ""
    for i in range(36):
        n = 16 + row * 36 + i
        line += f"\x1b[48;5;{n}m "
    out(line + "\x1b[0m\r\n", 0.15)
out("\r\n\x1b[7m reversed \x1b[0m \x1b[1m bold \x1b[0m \x1b[3m italic \x1b[0m \x1b[4m underline \x1b[0m \x1b[9m strike \x1b[0m\r\n", 0.4)
out("\r\n\x1b[90m$ echo 'два слова — unicode works'\x1b[0m\r\n", 0.3)
out("два слова — unicode works\r\n", 0.3)
E.append([0.2, "x", "0"])

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/demo.cast")
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header) + "\n")
    for dt, code, data in E:
        f.write(json.dumps([dt, code, data]) + "\n")
print(f"wrote {path} ({len(E)} events, {sum(d for d, _, _ in E):.2f}s)")
