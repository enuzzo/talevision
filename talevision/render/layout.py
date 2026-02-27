"""Layout rendering functions.

Preserves exact visual logic from archive/litclock/lc.py:
- draw_header(): Babel locale format, separator line
- draw_centered_text_block(): centered lines with configurable spacing
- draw_suspend_screen(): logo + message + detail centered on background
"""
import datetime
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Any

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import LitClockConfig, SuspendConfig
from .typography import FontManager, get_text_dimensions, calculate_wrapped_text_size

log = logging.getLogger(__name__)

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)

FontType = Any

try:
    from babel.dates import format_datetime as babel_format_datetime
    HAS_BABEL = True
except ImportError:
    HAS_BABEL = False
    log.warning("Babel not available; date formatting will use strftime fallback")


def draw_header(
    draw: ImageDraw.Draw,
    cfg: LitClockConfig,
    fonts: FontManager,
    canvas_w: int,
    text_color: Tuple[int, int, int],
    now: Optional[datetime.datetime] = None,
) -> int:
    """Draw the header (time + date + separator line).

    Returns the Y coordinate immediately after the header area.
    Preserves exact logic from lc.py DrawHelper.draw_header().
    """
    h_cfg = cfg.header
    pad = cfg.text_block_padding

    if not h_cfg.show:
        return pad

    h_font = fonts.get("header")
    if not h_font:
        log.error("Header font not loaded")
        return pad

    now = now or datetime.datetime.now()
    locale = h_cfg.babel_locale
    pattern = h_cfg.babel_format

    if HAS_BABEL and locale:
        try:
            h_text = babel_format_datetime(now, pattern, locale=locale)
        except Exception as exc:
            log.warning(f"Babel format failed: {exc}; using strftime fallback")
            h_text = now.strftime("%H:%M - %A %d %B %Y")
    else:
        h_text = now.strftime("%H:%M - %A %d %B %Y")

    line_sp = cfg.intra_line_spacing
    curr_y = float(pad)

    h_lines = h_text.splitlines()
    for line in h_lines:
        w, h = get_text_dimensions(line, h_font, draw)
        x = (canvas_w - w) // 2
        draw.text((x, int(curr_y)), line, fill=text_color, font=h_font, align="center")
        curr_y += h + line_sp
    if h_lines:
        curr_y -= line_sp

    if h_cfg.separator_line:
        thick = h_cfg.separator_line_thickness
        sep_sp = h_cfg.separator_line_spacing
        y_line = curr_y + sep_sp
        draw.line((pad, y_line, canvas_w - pad, y_line), fill=text_color, width=thick)
        curr_y = y_line + thick

    curr_y += h_cfg.header_bottom_spacing
    return int(curr_y)


def draw_centered_text_block(
    draw: ImageDraw.Draw,
    lines: List[str],
    font: FontType,
    start_y: int,
    canvas_w: int,
    line_spacing: int,
    fill: Tuple[int, int, int],
) -> int:
    """Draw centered text lines, returning Y after last line.

    Preserves exact logic from lc.py DrawHelper.draw_centered_text_block().
    """
    curr_y = start_y
    for i, line in enumerate(lines):
        w, h = get_text_dimensions(line, font, draw)
        x = (canvas_w - w) // 2
        draw.text((x, curr_y), line, fill=fill, font=font, align="center")
        curr_y += h
        if i < len(lines) - 1:
            curr_y += line_spacing
    return curr_y


def draw_suspend_screen(
    suspend_cfg: SuspendConfig,
    fonts: FontManager,
    width: int,
    height: int,
    base_dir: Path,
) -> Image.Image:
    """Render the suspend/sleep screen.

    Always white background, black text.
    Preserves exact logic from lc.py LiteratureClock._draw_suspend_screen().
    """
    bg_color = COLOR_WHITE
    text_color = COLOR_BLACK

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    msg = suspend_cfg.message
    start = suspend_cfg.start
    end = suspend_cfg.end
    detail = f"Suspended from {start} to {end}"

    h_font = fonts.get("header")
    d_font = fonts.get("quote")
    if not h_font:
        h_font = d_font
    if not d_font:
        log.error("Fonts missing for suspend screen")
        fallback_font = ImageFont.load_default()
        draw.text((10, height // 2), "Suspended", fill=text_color, font=fallback_font)
        return img

    msg_w, msg_h = get_text_dimensions(msg, h_font, draw)
    det_w, det_h = get_text_dimensions(detail, d_font, draw)

    # Load logo
    logo_w, logo_h = 0, 0
    logo_img = None
    target_w, target_h = 300, 150
    logo_path = base_dir / suspend_cfg.logo_path
    try:
        if logo_path.is_file():
            with Image.open(logo_path) as logo:
                logo_img = logo.resize((target_w, target_h)).convert("RGB")
                logo_w, logo_h = logo_img.size
        else:
            log.warning(f"Suspend logo not found: {logo_path}")
    except Exception as exc:
        log.error(f"Error loading suspend logo '{logo_path}': {exc}")

    spacing = 20
    total_h = msg_h + (spacing + logo_h if logo_img else 0) + spacing + det_h
    curr_y = (height - total_h) // 2

    x_msg = (width - msg_w) // 2
    draw.text((x_msg, curr_y), msg, fill=text_color, font=h_font, align="center")
    curr_y += msg_h + spacing

    if logo_img:
        x_logo = (width - logo_w) // 2
        try:
            img.paste(logo_img, (x_logo, curr_y))
        except Exception as exc:
            log.error(f"Error pasting logo: {exc}")
        curr_y += logo_h + spacing

    x_detail = (width - det_w) // 2
    draw.text((x_detail, curr_y), detail, fill=text_color, font=d_font, align="center")

    return img
