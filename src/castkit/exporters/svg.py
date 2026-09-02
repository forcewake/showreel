"""Animated SVG export: one self-contained file, CSS-keyframes animation (no JS, no SMIL).

Model: the screen is repainted row by row. Each time an output event changes a row,
a <g> group (background rect + styled text runs) is emitted with animation-delay=t.
Later groups paint over earlier ones, so history accumulates like a real terminal.
Decorations mirror the frame renderer (vhs-inspired): window chrome (mac/rings,
left/right), rounded corners via clip-path, CSS drop shadow, outer margin with
solid/gradient fill, watermark, blinking cursor.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .. import CastkitError
from ..core.model import Cast
from ..core.transform import transform
from ..playback import Player
from ..themes import ResolvedTheme, resolve_theme

__all__ = ["export_svg"]

_FONT_STACK = "'JetBrains Mono','Fira Code','SF Mono',Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"


def _runs_for_row(player: Player, y: int, theme: ResolvedTheme, bold_is_bright: bool = False):
    """Group a row into styled runs: [(col, fg, bg, bold, under, strike, text)]."""
    buf = player.screen.buffer.get(y, {})
    runs = []
    cur = None
    for x in range(player.cols):
        ch = buf.get(x)
        # a cell is drawable if it has a glyph OR a non-default background (e.g. color strips)
        if ch is None or (ch.data == " " and ch.bg in (None, "default")):
            if cur:
                runs.append(cur)
                cur = None
            continue
        fg = ch.fg
        if bold_is_bright and ch.bold and fg and fg != "default" and not fg.startswith("#"):
            fg = theme.named("bright" + fg) or fg
        fg_hex = _color(theme, fg, theme.fg)
        bg_hex = _color(theme, ch.bg, theme.bg)
        key = (bool(ch.bold), bool(ch.underscore), bool(ch.strikethrough))
        if cur and (cur[1], cur[2], cur[3], cur[4], cur[5]) == (fg_hex, bg_hex, *key):
            cur = (cur[0], fg_hex, bg_hex, cur[3], cur[4], cur[5], cur[6] + ch.data)
        else:
            if cur:
                runs.append(cur)
            cur = (x, fg_hex, bg_hex, bool(ch.bold), bool(ch.underscore), bool(ch.strikethrough), ch.data)
    if cur:
        runs.append(cur)
    return runs


def _color(theme: ResolvedTheme, value: str | None, default: str) -> str:
    return theme.resolve(value, default)


def export_svg(
    cast: Cast,
    out: str | Path,
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    idle_limit: float | None = None,
    theme: str = "auto",
    font_size: int = 20,
    padding: int = 16,
    cursor: bool = True,
    cursor_blink: int = 1200,  # blink period in ms; 0 = steady
    chrome_title: str | None = None,
    chrome_style: str = "mac",  # mac | rings | mac-right | rings-right
    line_height: float = 1.2,
    radius: int = 0,
    shadow: bool = False,
    margin: int = 0,
    margin_fill: str | None = None,
    watermark: str | None = None,
    warn_size_mb: float = 10.0,
) -> Path:
    tcast = transform(cast, start=start, end=end, speed=speed, idle_limit=idle_limit)
    if not tcast.events:
        raise CastkitError("recording has no events — nothing to export")

    resolved = resolve_theme(cast, theme)
    player = Player(tcast)
    cols, rows = player.cols, player.rows
    cw = round(font_size * 0.6, 2)  # monospace advance assumption; textLength pins it below
    ch_h = round(font_size * line_height, 2)
    term_h = round(font_size * 1.9) if chrome_title else 0
    radius = max(0, radius)
    margin = max(0, margin)
    shadow_pad = round(font_size * 1.1) if shadow else 0

    panel_w = padding * 2 + round(cols * cw)
    panel_h = padding * 2 + term_h + round(rows * ch_h)
    width = margin * 2 + panel_w + shadow_pad * 2
    height = margin * 2 + panel_h + shadow_pad * 2
    ox = margin + shadow_pad + padding
    oy = margin + shadow_pad + padding + term_h
    px, py = margin + shadow_pad, margin + shadow_pad

    # margin fill: solid or two-color vertical gradient
    fill_parts = [p.strip() for p in (margin_fill or "").split(",") if p.strip()]
    margin_defs = ""
    if fill_parts:
        margin_fill_attr = 'fill="url(#mgrad)"'
        if len(fill_parts) > 1:
            margin_defs = (
                f'<linearGradient id="mgrad" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{fill_parts[0]}"/>'
                f'<stop offset="1" stop-color="{fill_parts[1]}"/>'
                f"</linearGradient>"
            )
        else:
            margin_fill_attr = f'fill="{fill_parts[0]}"'
    else:
        margin_fill_attr = f"fill={quoteattr(resolved.bg)}"

    def _y_baseline(row: int) -> float:
        return round(oy + row * ch_h + font_size * 0.95, 2)

    groups: list[str] = []
    cursor_windows: list[str] = []
    prev_rows: list = [None] * rows
    prev_cursor: tuple | None = None
    idx = 0
    events = [e for e in tcast.events if e.etype == "o"]
    for ei, e in enumerate(events):
        while idx < len(tcast.events) and tcast.events[idx].time <= e.time + 1e-9:
            if tcast.events[idx].etype == "o":
                player.stream.feed(tcast.events[idx].data.encode("utf-8"))
            idx += 1
        delay = round(e.time, 3)
        for y in range(rows):
            runs = _runs_for_row(player, y, resolved)
            if runs == prev_rows[y]:
                continue
            prev_rows[y] = runs
            # SMIL <set> pops the row in instantly at its timestamp (fill=freeze
            # keeps it). No per-element CSS animations for browsers to drop.
            parts = [
                f'<g opacity="0"><set attributeName="opacity" to="1" begin="{delay}s" fill="freeze"/>',
                f'<rect x="{ox}" y="{round(oy + y * ch_h)}" width="{panel_w - padding * 2}" height="{round(ch_h)}" fill={quoteattr(resolved.bg)}/>',
            ]
            for col, fg_hex, bg_hex, bold, under, strike, text in runs:
                x = round(ox + col * cw, 2)
                if bg_hex != resolved.bg:
                    parts.append(
                        f'<rect x="{x}" y="{round(oy + y * ch_h)}" width="{round(len(text) * cw)}" height="{round(ch_h)}" fill={quoteattr(bg_hex)}/>'
                    )
                style = []
                if bold:
                    style.append("font-weight:bold")
                if under or strike:
                    deco = "underline" if under else ""
                    if strike:
                        deco += (" " if deco else "") + "line-through"
                    style.append(f"text-decoration:{deco}")
                style_attr = f' style="{";".join(style)}"' if style else ""

                # absolute x per glyph: exact cell grid under any viewer font,
                # no textLength/letter-spacing re-flow, nothing shifts on repaint
                def _fmt(v: float) -> str:
                    return str(int(v)) if v == int(v) else str(v)

                xs = " ".join(_fmt(round(ox + (col + k) * cw, 2)) for k in range(len(text)))
                parts.append(
                    f'<text x="{xs}" y="{_y_baseline(y)}" fill={quoteattr(fg_hex)}{style_attr}>{escape(text)}</text>'
                )
            parts.append("</g>")
            groups.append("".join(parts))

        if cursor:
            # the cursor "lives" only during this event's window, so it follows
            # the typing instead of sitting at the final position from t=0
            cx, cy, hidden = player.cursor()
            state = (cx, cy, hidden)
            if state != prev_cursor:
                prev_cursor = state
                if not hidden and cy < rows and cx < cols:
                    next_t = events[ei + 1].time if ei + 1 < len(events) else tcast.duration
                    dur = round(max(next_t - e.time, 0.05), 3)
                    x = round(ox + cx * cw, 2)
                    y = round(margin + shadow_pad + padding + term_h + cy * ch_h)
                    cursor_windows.append(
                        f'<rect x="{x}" y="{y}" width="{cw}" height="{round(ch_h)}" '
                        f'fill={quoteattr(resolved.cursor)} opacity="0">'
                        f'<animate attributeName="opacity" values="1;0" keyTimes="0;0.999" '
                        f'calcMode="discrete" begin="{delay}s" dur="{dur}s" fill="freeze"/></rect>'
                    )

    cursor_svg = ""
    if cursor:
        cx, cy, hidden = player.cursor()
        if not hidden and cy < rows and cx < cols:
            x = round(ox + cx * cw, 2)
            y = round(margin + shadow_pad + padding + term_h + cy * ch_h)
            # final cursor: hidden until the recording ends, then blinks forever
            begin = round(tcast.duration + 0.05, 3)
            blink = cursor_blink if cursor_blink > 0 else 1200
            blink_anim = (
                f'<animate attributeName="opacity" values="1;0" keyTimes="0;0.5" '
                f'calcMode="discrete" begin="{begin}s" dur="{blink / 1000:.3f}s" repeatCount="indefinite"/>'
            )
            cursor_svg = (
                f'<g opacity="0"><set attributeName="opacity" to="1" begin="{begin}s" fill="freeze"/>'
                f'<rect x="{x}" y="{y}" width="{cw}" height="{round(ch_h)}" '
                f"fill={quoteattr(resolved.cursor)}>{blink_anim}</rect></g>"
            )

    # window chrome bar (inside the panel, on top of content area)
    chrome_svg = ""
    if term_h:
        bar_y = py
        right = chrome_style.endswith("-right")
        filled = not chrome_style.startswith("rings")
        r = max(5, term_h // 3)
        dots = []
        for i, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            cxc = (px + term_h // 2 + i * (r + 6)) if not right else (px + panel_w - term_h // 2 - (2 - i) * (r + 6))
            cyc = bar_y + term_h // 2
            if filled:
                dots.append(f'<circle cx="{cxc}" cy="{cyc}" r="{r // 2}" fill="{color}"/>')
            else:
                dots.append(
                    f'<circle cx="{cxc}" cy="{cyc}" r="{r // 2}" fill="none" stroke="{color}" stroke-width="{max(1.5, r // 5)}"/>'
                )
        title_svg = ""
        if chrome_title:
            title_svg = (
                f'<text x="{px + panel_w // 2}" y="{bar_y + round(term_h * 0.62)}" text-anchor="middle" '
                f'fill="#9a9a9a" font-size="{round(font_size * 0.55)}">{escape(chrome_title)}</text>'
            )
        chrome_svg = (
            f'<g clip-path="url(#clip)"><rect x="{px}" y="{bar_y}" width="{panel_w}" height="{term_h}" fill="#1d1f21"/>'
            + "".join(dots)
            + title_svg
            + "</g>"
        )

    watermark_svg = ""
    if watermark:
        watermark_svg = (
            f'<text x="{width - margin - round(font_size * 0.4)}" y="{height - margin - round(font_size * 0.4)}" '
            f'text-anchor="end" fill="#ffffff" opacity="0.5" font-size="{round(font_size * 0.5)}">{escape(watermark)}</text>'
        )

    shadow_css = "filter: drop-shadow(0 6px 18px rgba(0,0,0,.45));" if shadow else ""
    title = escape(tcast.header.title or "")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family={quoteattr(_FONT_STACK)} font-size="{font_size}">
<title>{title or "terminal recording"}</title>
<defs>
  <clipPath id="clip"><rect x="{px}" y="{py}" width="{panel_w}" height="{panel_h}" rx="{radius}"/></clipPath>
  {margin_defs}
</defs>
<style>
  /* timing is declarative SMIL (set/animate elements) — reliable for thousands of
     timed elements, works in img tags, no per-element CSS animations to drop */
  .panel {{ {shadow_css} }}
  text {{ white-space: pre; }}
</style>
<rect width="{width}" height="{height}" {margin_fill_attr}/>
<g class="panel"><rect x="{px}" y="{py}" width="{panel_w}" height="{panel_h}" rx="{radius}" fill={quoteattr(resolved.bg)}/></g>
<g clip-path="url(#clip)">
<rect x="{px}" y="{py}" width="{panel_w}" height="{panel_h}" fill={quoteattr(resolved.bg)}/>
{chrome_svg}
{"".join(groups)}
{"".join(cursor_windows)}
{cursor_svg}
</g>
{watermark_svg}
</svg>
'''

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    size_mb = out_path.stat().st_size / 1_000_000
    if size_mb > warn_size_mb:
        print(
            f"castkit: warning: {out_path.name} is {size_mb:.1f} MB — consider --idle-limit, --speed 2 or --end to shrink it",
            flush=True,
        )
        from .. import CastkitError as _  # noqa: F401  (kept: warning only)

    return out_path
