"""Self-contained HTML player: cast embedded as JSON + a tiny built-in VT emulator in JS.

No CDN, no external files — works offline, openable by humans and scriptable for agents.
Supports the ANSI subset terminals actually emit for screencasts: CUP/CUF/CUU/CUD, ED, EL,
SGR (colors 8/16/256/24-bit, bold, italic, underline, strikethrough, reverse), cursor hide,
scrolling, \\r \\n \\b \\t.
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import CastkitError, __version__
from ..core.model import Cast
from ..core.transform import transform
from ..themes import resolve_theme

__all__ = ["export_html"]

_PLAYER_JS = r"""
(function () {
  'use strict';
  var data = JSON.parse(document.getElementById('castkit-data').textContent);
  var screenEl = document.getElementById('screen');
  var bar = document.getElementById('bar');
  var timeEl = document.getElementById('time');
  var playBtn = document.getElementById('play');
  var speedSel = document.getElementById('speed');
  var markersEl = document.getElementById('markers');
  var COLS = data.cols, ROWS = data.rows;

  var cells, cx, cy, fg, bg, attrs, cursorHidden;
  function reset() {
    cells = []; for (var y = 0; y < ROWS; y++) { cells.push(newRow()); }
    cx = 0; cy = 0; fg = null; bg = null; attrs = {}; cursorHidden = false;
  }
  function newRow() { var r = []; for (var x = 0; x < COLS; x++) r.push({ch: ' ', fg: null, bg: null, at: {}}); return r; }
  function put(ch) {
    if (cx >= COLS) { cx = 0; cy++; if (cy >= ROWS) { cells.shift(); cells.push(newRow()); cy = ROWS - 1; } }
    cells[cy][cx++] = {ch: ch, fg: fg, bg: bg, at: Object.assign({}, attrs)};
  }
  var CSI = '';
  var state = 0; // 0 normal, 1 esc, 2 csi
  function feed(text) {
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (state === 0) {
        if (c === '\x1b') { state = 1; continue; }
        if (c === '\r') { cx = 0; continue; }
        if (c === '\n') { cy++; if (cy >= ROWS) { cells.shift(); cells.push(newRow()); cy = ROWS - 1; } continue; }
        if (c === '\b') { if (cx > 0) cx--; continue; }
        if (c === '\t') { cx = Math.min(COLS - 1, (Math.floor(cx / 8) + 1) * 8); continue; }
        if (c === '\x07') continue;
        // rough wide-char handling: CJK ranges take 2 cells
        var code = text.codePointAt(i);
        put(c);
        if (code > 0x1100 && ((code >= 0x1100 && code <= 0x115f) || (code >= 0x2e80 && code <= 0xa4cf) || (code >= 0xac00 && code <= 0xd7a3) || (code >= 0xf900 && code <= 0xfaff) || (code >= 0xfe30 && code <= 0xfe6f) || (code >= 0xff00 && code <= 0xff60) || (code >= 0xffe0 && code <= 0xffe6) || (code >= 0x20000 && code <= 0x3fffd))) { put(''); i++; }
        continue;
      }
      if (state === 1) {
        if (c === '[') { state = 2; CSI = ''; continue; }
        state = 0; continue;
      }
      if (state === 2) {
        var m = /^([0-9;:?]*)([A-Za-z])$/.exec(CSI + c);
        if (!m) { CSI += c; if (CSI.length > 32) { state = 0; } continue; }
        state = 0;
        handleCsi(m[1], m[2]);
      }
    }
  }
  function params(def, max) {
    return CSI.length === 0 ? [def] : CSI.split(';').map(function (p) { var n = parseInt(p, 10); return isNaN(n) ? def : n; });
  }
  function handleCsi(ps, final) {
    var p = ps === '' ? [0] : ps.split(';').map(function (x) { var n = parseInt(x, 10); return isNaN(n) ? 0 : n; });
    switch (final) {
      case 'A': cy = Math.max(0, cy - Math.max(1, p[0])); break;
      case 'B': cy = Math.min(ROWS - 1, cy + Math.max(1, p[0])); break;
      case 'C': cx = Math.min(COLS - 1, cx + Math.max(1, p[0])); break;
      case 'D': cx = Math.max(0, cx - Math.max(1, p[0])); break;
      case 'E': cy = Math.min(ROWS - 1, cy + Math.max(1, p[0])); cx = 0; break;
      case 'F': cy = Math.max(0, cy - Math.max(1, p[0])); cx = 0; break;
      case 'G': cx = Math.min(COLS - 1, Math.max(0, (p[0] || 1) - 1)); break;
      case 'H': case 'f':
        cy = Math.min(ROWS - 1, Math.max(0, (p[0] || 1) - 1));
        cx = Math.min(COLS - 1, Math.max(0, (p[1] || 1) - 1)); break;
      case 'J':
        var mode = p[0] || 0;
        if (mode === 2 || mode === 3) { cells = []; for (var y = 0; y < ROWS; y++) cells.push(newRow()); }
        else if (mode === 0) { clearLine(cy, cx, COLS); for (var yy = cy + 1; yy < ROWS; yy++) cells[yy] = newRow(); }
        else { clearLine(cy, 0, cx); for (var y2 = 0; y2 < cy; y2++) cells[y2] = newRow(); }
        break;
      case 'K':
        var km = p[0] || 0;
        if (km === 0) clearLine(cy, cx, COLS);
        else if (km === 1) clearLine(cy, 0, cx + 1);
        else cells[cy] = newRow();
        break;
      case 'm': sgr(p); break;
      case 'h': case 'l':
        if (p[0] === 25) cursorHidden = final === 'l' ? false : true;
        break;
      default: break;
    }
  }
  function clearLine(y, from, to) { for (var x = from; x < Math.min(to, COLS); x++) cells[y][x] = {ch: ' ', fg: null, bg: null, at: {}}; }
  function sgr(p) {
    for (var i = 0; i < p.length; i++) {
      var n = p[i] || 0;
      if (n === 0) { fg = bg = null; attrs = {}; }
      else if (n === 1) attrs.bold = true;
      else if (n === 2) attrs.dim = true;
      else if (n === 3) attrs.italic = true;
      else if (n === 4) attrs.underline = true;
      else if (n === 9) attrs.strike = true;
      else if (n === 22) { attrs.bold = attrs.dim = false; }
      else if (n === 23) attrs.italic = false;
      else if (n === 24) attrs.underline = false;
      else if (n === 29) attrs.strike = false;
      else if (n === 7) attrs.reverse = true;
      else if (n === 27) attrs.reverse = false;
      else if (n === 39) fg = null;
      else if (n === 49) bg = null;
      else if ((n >= 30 && n <= 37) || (n >= 90 && n <= 97)) fg = n - (n >= 90 ? 60 : 30);
      else if ((n >= 40 && n <= 47) || (n >= 100 && n <= 107)) bg = n - (n >= 100 ? 60 : 40);
      else if (n === 38 || n === 48) {
        var target = n === 38 ? 'fg' : 'bg';
        if (p[i + 1] === 5) { set(target, p[i + 2]); i += 2; }
        else if (p[i + 1] === 2) { set(target, [p[i + 2], p[i + 3], p[i + 4]]); i += 4; }
      }
    }
  }
  function set(which, v) { if (which === 'fg') fg = v; else bg = v; }
  function colorOf(v, def) {
    if (v === null || v === undefined) return def;
    if (typeof v === 'object') return 'rgb(' + v.join(',') + ')';
    var pal = data.palette;
    var hex = (v < 8 ? pal[v] : pal[v] || pal[(v - 8) % 8]);
    // 256-color approximation using palette for 0-15, grayscale/cube for the rest
    if (v >= 16 && v <= 231) {
      var steps = [0, 95, 135, 175, 215, 255];
      var r = steps[Math.floor((v - 16) / 36)], g = steps[Math.floor(((v - 16) % 36) / 6)], b = steps[(v - 16) % 6];
      return 'rgb(' + r + ',' + g + ',' + b + ')';
    }
    if (v >= 232) { var gr = 8 + (v - 232) * 10; return 'rgb(' + gr + ',' + gr + ',' + gr + ')'; }
    return hex || def;
  }
  function render() {
    var html = '';
    for (var y = 0; y < ROWS; y++) {
      var line = '';
      for (var x = 0; x < COLS; x++) {
        var cell = cells[y][x];
        var cfg = colorOf(cell.fg, data.fg), cbg = colorOf(cell.bg, data.bg);
        if (cell.at.reverse) { var t = cfg; cfg = cbg; cbg = t; }
        var st = 'color:' + cfg + ';background:' + cbg;
        if (cell.at.bold) st += ';font-weight:bold';
        if (cell.at.italic) st += ';font-style:italic';
        if (cell.at.underline) st += ';text-decoration:underline';
        if (cell.at.strike) st += ';text-decoration:line-through';
        line += '<span style="' + st + '">' + esc(cell.ch === '' ? ' ' : cell.ch) + '</span>';
        if (cell.ch !== '' && isWide(cell.ch)) { x++; }
      }
      html += line + '\n';
      if (y === cy && !cursorHidden) {
        // cursor rendered by CSS overlay below
      }
    }
    screenEl.innerHTML = html;
    var cur = document.getElementById('cursor');
    cur.style.display = cursorHidden ? 'none' : 'block';
    cur.style.left = (cx * data.cw) + 'px';
    cur.style.top = (cy * data.chh) + 'px';
  }
  function isWide(ch) {
    var c = ch.codePointAt(0);
    return c >= 0x1100 && ((c <= 0x115f) || (c >= 0x2e80 && c <= 0xa4cf) || (c >= 0xac00 && c <= 0xd7a3) || (c >= 0xf900 && c <= 0xfaff) || (c >= 0xfe30 && c <= 0xfe6f) || (c >= 0xff00 && c <= 0xff60) || (c >= 0xffe0 && c <= 0xffe6) || (c >= 0x20000 && c <= 0x3fffd));
  }
  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  // --- playback ---------------------------------------------------------
  var t = 0, playing = false, speed = 1, raf = null, lastTick = 0, evIdx = 0, done = false;
  function fmtTime(s) {
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
    var mm = (m < 10 && h ? '0' : '') + m, ss = (sec < 10 ? '0' : '') + sec;
    return (h ? h + ':' : '') + mm + ':' + ss;
  }
  function applyEvents(upto) {
    var evs = data.events;
    while (evIdx < evs.length && evs[evIdx][0] <= upto + 1e-9) {
      var e = evs[evIdx];
      if (e[1] === 'o') feed(e[2]);
      evIdx++; t = e[0];
    }
  }
  function tick(now) {
    if (!playing) return;
    var dt = (now - lastTick) / 1000 * speed;
    lastTick = now;
    var target = Math.min(t + dt, data.duration);
    applyEvents(target);
    t = target;
    if (t >= data.duration) { playing = false; done = true; playBtn.textContent = '▶'; }
    update();
    if (playing) raf = requestAnimationFrame(tick);
  }
  function update() {
    bar.value = t;
    timeEl.textContent = fmtTime(t) + ' / ' + fmtTime(data.duration);
    render();
  }
  function play() {
    if (done) { seek(0); done = false; }
    playing = true; playBtn.textContent = '❚❚'; lastTick = performance.now();
    raf = requestAnimationFrame(tick);
  }
  function pause() { playing = false; playBtn.textContent = '▶'; if (raf) cancelAnimationFrame(raf); }
  function seek(nt) {
    evIdx = 0; reset();
    t = 0; applyEvents(nt); t = nt; done = nt >= data.duration; update();
  }
  playBtn.addEventListener('click', function () { playing ? pause() : play(); });
  bar.addEventListener('input', function () { pause(); seek(parseFloat(bar.value)); });
  speedSel.addEventListener('change', function () { speed = parseFloat(speedSel.value); });
  document.addEventListener('keydown', function (e) {
    if (e.key === ' ') { e.preventDefault(); playing ? pause() : play(); }
    if (e.key === 'ArrowRight') { pause(); seek(Math.min(data.duration, t + 5)); }
    if (e.key === 'ArrowLeft') { pause(); seek(Math.max(0, t - 5)); }
  });
  (data.markers || []).forEach(function (m, i) {
    var b = document.createElement('button');
    b.className = 'marker';
    b.textContent = '◆ ' + (m[1] || ('marker ' + (i + 1)));
    b.title = fmtTime(m[0]);
    b.addEventListener('click', function () { pause(); seek(m[0]); });
    markersEl.appendChild(b);
  });

  reset(); render(); update();
})();
"""


def export_html(
    cast: Cast,
    out: str | Path,
    title: str | None = None,
    theme: str = "auto",
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    idle_limit: float | None = None,
    autoplay: bool = False,
    font_family: str = "'JetBrains Mono','Fira Code',Menlo,Consolas,'DejaVu Sans Mono',monospace",
    font_size: int = 16,
    margin_fill: str | None = None,
    cursor_blink: int = 1200,
) -> Path:
    tcast = transform(cast, start=start, end=end, speed=speed, idle_limit=idle_limit)
    if not tcast.events:
        raise CastkitError("recording has no events — nothing to export")
    resolved = resolve_theme(cast, theme)
    h = tcast.header

    payload = {
        "cols": h.term.cols,
        "rows": h.term.rows,
        "duration": round(tcast.duration, 3),
        "title": title or h.title or "terminal recording",
        "events": [[round(e.time, 3), e.etype, e.data] for e in tcast.events if e.etype in ("o", "m")],
        "markers": [[round(t, 3), label] for t, label in tcast.markers()],
        "fg": resolved.fg,
        "bg": resolved.bg,
        "palette": resolved.palette,
        "cw": round(font_size * 0.6, 2),
        "chh": round(font_size * 1.25, 2),
    }
    data_json = json.dumps(payload, ensure_ascii=True).replace("</", "<\\/")

    width = payload["cols"] * payload["cw"] + 2 * 8

    html = f"""<!doctype html>
<!-- Generated by castkit v{__version__} — fully self-contained, no network required. -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{(title or h.title or "terminal recording")}</title>
<style>
  body {{ margin:0; background:{margin_fill or "#111318"}; color:#e8e8e8; font-family:system-ui,sans-serif;
         display:flex; flex-direction:column; align-items:center; padding:24px; }}
  .term {{ position:relative; background:{resolved.bg}; border-radius:8px; overflow:hidden;
          box-shadow:0 8px 40px rgba(0,0,0,.5); }}
  pre#screen {{ margin:6px 8px; font-family:{font_family}; font-size:{font_size}px; line-height:{payload["chh"] / font_size};
               white-space:pre; overflow:hidden; }}
  #cursor {{ position:absolute; width:{payload["cw"]}px; height:{payload["chh"]}px;
            background:{resolved.cursor}; pointer-events:none;
            {f"animation: ck-blink {cursor_blink}ms steps(1) infinite;" if cursor_blink > 0 else ""} }}
  @keyframes ck-blink {{ 50% {{ opacity: 0; }} }}
  .ui {{ display:flex; gap:10px; align-items:center; margin-top:14px; width:min(96vw,{width + 20}px); }}
  .ui button, .ui select {{ background:#1e222b; color:#e8e8e8; border:1px solid #333;
        border-radius:6px; padding:6px 10px; cursor:pointer; font-size:14px; }}
  .ui button:hover {{ background:#2a2f3a; }}
  #bar {{ flex:1; accent-color:#5ac8fa; }}
  #time {{ font-variant-numeric:tabular-nums; color:#9aa; font-size:13px; min-width:12ch; text-align:center; }}
  #markers {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; width:min(96vw,{width + 20}px); }}
  .marker {{ background:#1e222b; color:#9cd; border:1px solid #334; border-radius:999px;
            padding:3px 10px; cursor:pointer; font-size:12px; }}
  .hint {{ color:#667; font-size:12px; margin-top:10px; }}
</style>
</head>
<body>
<div class="term">
  <pre id="screen"></pre>
  <div id="cursor" style="display:none"></div>
</div>
<div class="ui">
  <button id="play"{' data-autoplay="1"' if autoplay else ""}>▶</button>
  <input id="bar" type="range" min="0" max="{payload["duration"]}" step="0.01" value="0">
  <span id="time">0:00 / 0:00</span>
  <select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option>
  <option value="2">2×</option><option value="4">4×</option><option value="8">8×</option></select>
</div>
<div id="markers"></div>
<div class="hint">space = play/pause · ←/→ = ±5s · generated by castkit</div>
<script type="application/json" id="castkit-data">{data_json}</script>
<script>{_PLAYER_JS}</script>
<script>
  (function() {{
    var btn = document.getElementById('play');
    if (btn.dataset.autoplay) {{ setTimeout(function() {{ btn.click(); }}, 300); }}
  }})();
</script>
</body>
</html>
"""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
