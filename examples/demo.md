---
title: "castkit demo — production deploy"
duration: 24.820
size: "80x28"
recorded: 2024-09-02T08:00:00+00:00
tags: [demo, deploy]
chapters:
  - "build" @ 00:00:04
  - "test" @ 00:00:13
  - "deploy" @ 00:00:14
  - "palette" @ 00:00:18
  - "done" @ 00:00:21
---

# Terminal recording

```text
╭──────────────────────────────────────────────────╮
│  ◆ castkit demo — production deploy, in style    │
╰──────────────────────────────────────────────────╯

~/projects/webapp ❯ castkit deploy --env production
✓ 428 modules bundled in 1.42s

  ██████████████████████████████100%
running test suite
●●●●●●●●●●●●●●●●●●●●●●●●
✓ 42 passing  ● 1 skipped  0 failing  (0.9s)

→ uploading artifacts…        done
→ rolling out replicas        2/3 → 3/3
→ waiting for health checks   passing
 OK  {"status":"ok","uptime":86402,"version":"1.4.2"}

256 colors, as rendered:


 reversed    bold    italic    underline    strike

╭──────────────────────────────────────────────────╮
│ ✓ deployed in 12.4s → https://webapp.example.com │
╰──────────────────────────────────────────────────╯

~/projects/webapp ❯
```

## Chapters

1. **build** — 00:00:04–00:00:13
2. **test** — 00:00:13–00:00:14
3. **deploy** — 00:00:14–00:00:18
4. **palette** — 00:00:18–00:00:21
5. **done** — 00:00:21–00:00:24
