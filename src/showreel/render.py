"""Render terminal screen state to PIL images.

Panel decorations (vhs-inspired): window chrome (mac "Colorful" / "Rings",
left or right), rounded corners, drop shadow, outer margin with solid or
gradient fill, watermark text, optional cursor blink.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import ShowreelError
from .fonts import find_font
from .playback import Player
from .themes import ResolvedTheme

__all__ = ["Renderer", "hex_to_rgb", "lerp_rgb", "measure_font"]


def measure_font(font_path: str, font_size: int) -> tuple[float, int, int]:
    """Return (char_width, cell_height, ascent) for a monospace font at size."""
    font = ImageFont.truetype(font_path, font_size)
    w = font.getlength("M")
    ascent, descent = font.getmetrics()
    return w, ascent + descent, ascent


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise ShowreelError(f"color must be #rrggbb, got '{color}'")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def lerp_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


class Renderer:
    """Renders a Player's screen state as a PIL RGB image with panel decorations."""

    def __init__(
        self,
        theme: ResolvedTheme,
        cols: int,
        rows: int,
        font_size: int = 24,
        font_path: str | None = None,
        padding: int = 16,
        chrome_title: str | None = None,
        cursor: str = "block",  # block | underline | off
        bold_is_bright: bool = False,
        radius: int = 0,
        shadow: bool = False,
        margin: int = 0,
        margin_fill: str | None = None,  # "#hex" or "#hex,#hex" vertical gradient
        watermark: str | None = None,
        chrome_style: str = "mac",  # mac | rings | mac-right | rings-right
    ):
        self.theme = theme
        self.cols = cols
        self.rows = rows
        self.padding = padding
        self.cursor_mode = cursor
        self.bold_is_bright = bold_is_bright
        self.font_path = find_font(font_path)
        self.font_size = font_size
        self.font = ImageFont.truetype(self.font_path, font_size)
        self.bold_stroke = max(1, round(font_size / 28))
        self.char_w, self.cell_h, self.ascent = measure_font(self.font_path, font_size)
        self.radius = max(0, radius)
        self.margin = max(0, margin)
        self.shadow = shadow
        self.watermark = watermark
        self.chrome_style = chrome_style

        self.shadow_pad = round(font_size * 1.1) if shadow else 0
        self.term_h = round(font_size * 0.45) if chrome_title else 0
        self.chrome_title = chrome_title
        self.margin_fill = margin_fill
        self.panel_w = padding * 2 + round(cols * self.char_w)
        self.panel_h = padding * 2 + rows * self.cell_h + self.term_h
        # even canvas: libx264 (yuv420p) requires it
        self.width = (self.margin * 2 + self.panel_w + self.shadow_pad * 2 + 1) // 2 * 2
        self.height = (self.margin * 2 + self.panel_h + self.shadow_pad * 2 + 1) // 2 * 2
        self._panel_origin = (self.margin + self.shadow_pad, self.margin + self.shadow_pad)
        self._hash_cache: dict[tuple, Image.Image] = {}

    # -- color helpers ----------------------------------------------------

    def _resolve(self, color: str | None, default: str) -> str:
        return self.theme.resolve(color, default)

    def _margin_colors(self) -> tuple[tuple[int, int, int], tuple[int, int, int] | None]:
        if fill := self.margin_fill:
            parts = [p.strip() for p in fill.split(",")]
            c1 = hex_to_rgb(parts[0])
            c2 = hex_to_rgb(parts[1]) if len(parts) > 1 else None
            return c1, c2
        return hex_to_rgb(self.theme.bg), None

    # -- public API --------------------------------------------------------

    def render(self, player: Player, cache: bool = False, show_cursor: bool | None = None) -> Image.Image:
        key = (player.state_hash() if cache else None, show_cursor)
        if cache:
            cached = self._hash_cache.get(key)
            if cached is not None:
                return cached
        img = self._render_uncached(player, show_cursor)
        if cache:
            if len(self._hash_cache) > 4:
                self._hash_cache.clear()
            self._hash_cache[key] = img
        return img

    # -- internals ---------------------------------------------------------

    def _render_uncached(self, player: Player, show_cursor: bool | None) -> Image.Image:
        mc1, mc2 = self._margin_colors()
        canvas = Image.new("RGB", (self.width, self.height), mc1)
        if mc2 is not None:  # vertical gradient
            grad = Image.new("RGB", (1, self.height))
            for y in range(self.height):
                grad.putpixel((0, y), lerp_rgb(mc1, mc2, y / max(1, self.height - 1)))
            canvas.paste(grad.resize((self.width, self.height)), (0, 0))

        px, py = self._panel_origin
        if self.shadow:
            sh = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            sd.rounded_rectangle(
                [px + 2, py + 6, px + self.panel_w + 2, py + self.panel_h + 6],
                radius=self.radius + 4,
                fill=(0, 0, 0, 150),
            )
            sh = sh.filter(ImageFilter.GaussianBlur(max(3, self.font_size // 3)))
            canvas.paste(sh, (0, 0), sh)

        panel = self._render_panel(player, show_cursor)
        mask = None
        if self.radius > 0:
            mask = Image.new("L", (self.panel_w, self.panel_h), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, self.panel_w - 1, self.panel_h - 1], radius=self.radius, fill=255
            )
        canvas.paste(panel, (px, py), mask if self.radius > 0 else None)

        if self.watermark:
            self._draw_watermark(canvas)
        return canvas

    def _render_panel(self, player: Player, show_cursor: bool | None) -> Image.Image:
        img = Image.new("RGB", (self.panel_w, self.panel_h), self.theme.bg)
        draw = ImageDraw.Draw(img)

        if self.term_h:
            self._draw_chrome(draw)

        ox = self.padding
        oy = self.padding + self.term_h
        fg_d, bg_d = self.theme.fg, self.theme.bg

        fills: list[tuple[int, int, int, int, str]] = []
        glyphs: list[tuple[int, int, str, str, bool, bool, bool]] = []
        for y, x, ch in player.cells():
            fg = self._resolve(ch.fg, fg_d)
            if self.bold_is_bright and ch.bold and ch.fg and ch.fg not in ("default",) and not ch.fg.startswith("#"):
                fg = self.theme.named("bright" + ch.fg) or fg
            bg = self._resolve(ch.bg, bg_d)
            if ch.reverse:
                fg, bg = bg, fg
                if fg == bg_d and bg == fg_d:
                    fg, bg = bg_d, fg_d
            cx = ox + round(x * self.char_w)
            cy = oy + y * self.cell_h
            if bg != bg_d:
                fills.append((cx, cy, round(self.char_w) + 1, self.cell_h, bg))
            glyphs.append((cx, cy, ch.data, fg, bool(ch.bold), bool(ch.underscore), bool(ch.strikethrough)))

        for x, y, w, h, color in fills:
            draw.rectangle([x, y, x + w - 1, y + h - 1], fill=color)
        for x, y, text, color, bold, under, strike in glyphs:
            draw.text((x, y), text, font=self.font, fill=color, stroke_width=self.bold_stroke if bold else 0)
            if under:
                ly = y + self.ascent + 2
                draw.line([x, ly, x + round(self.char_w) - 1, ly], fill=color, width=1)
            if strike:
                ly = y + self.ascent - self.font_size // 3
                draw.line([x, ly, x + round(self.char_w) - 1, ly], fill=color, width=1)

        cursor_visible = (
            self.cursor_mode != "off" if show_cursor is None else (show_cursor and self.cursor_mode != "off")
        )
        if cursor_visible:
            cx_pos, cy_pos, hidden = player.cursor()
            if (not hidden or show_cursor is not None) and cy_pos < self.rows and cx_pos < self.cols:
                self._draw_cursor(draw, player, cx_pos, cy_pos, ox, oy)
        return img

    def _draw_cursor(self, draw: ImageDraw.Draw, player: Player, cx: int, cy: int, ox: int, oy: int) -> None:
        x = ox + round(cx * self.char_w)
        y = oy + cy * self.cell_h
        if self.cursor_mode == "underline":
            draw.rectangle(
                [x, y + self.cell_h - max(2, self.font_size // 12), x + round(self.char_w) - 1, y + self.cell_h - 1],
                fill=self.theme.cursor,
            )
            return
        draw.rectangle([x, y, x + round(self.char_w) - 1, y + self.cell_h - 1], fill=self.theme.cursor)
        ch = player.screen.buffer.get(cy, {}).get(cx)
        if ch and ch.data != " ":
            # glyph knocked out in the panel background color
            draw.text((x, y), ch.data, font=self.font, fill=self.theme.bg)

    def _draw_chrome(self, draw: ImageDraw.Draw) -> None:
        h = self.term_h
        draw.rectangle([0, 0, self.panel_w - 1, h - 1], fill="#1d1f21")
        r = max(6, h // 3)
        right = self.chrome_style.endswith("-right")
        filled = not self.chrome_style.startswith("rings")
        for i, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            cxc = (h // 2 + i * (r + 6)) if not right else (self.panel_w - h // 2 - (2 - i) * (r + 6))
            bbox = [cxc - r // 2, h // 2 - r // 2, cxc + r // 2, h // 2 + r // 2]
            if filled:
                draw.ellipse(bbox, fill=color)
            else:
                draw.ellipse(bbox, outline=color, width=max(2, r // 4))
        if self.chrome_title:
            font = _title_font(self.font_path, max(11, h // 2))
            tw = draw.textlength(self.chrome_title, font=font)
            asc, desc = font.getmetrics()
            draw.text(((self.panel_w - tw) / 2, (h - (asc + desc)) / 2), self.chrome_title, font=font, fill="#9a9a9a")

    def _draw_watermark(self, canvas: Image.Image) -> None:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        font = _title_font(self.font_path, max(12, self.font_size // 2))
        d = ImageDraw.Draw(layer)
        tw = d.textlength(self.watermark, font=font)
        asc, desc = font.getmetrics()
        pad = max(8, self.margin // 2 or 8)
        x = self.width - tw - pad
        y = self.height - (asc + desc) - pad
        d.text((x + 1, y + 1), self.watermark, font=font, fill=(0, 0, 0, 90))
        d.text((x, y), self.watermark, font=font, fill=(255, 255, 255, 130))
        canvas.paste(layer, (0, 0), layer)


@lru_cache(maxsize=8)
def _title_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, size)
