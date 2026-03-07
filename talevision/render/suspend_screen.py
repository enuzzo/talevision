"""Suspend screen renderer — BBS/NFO style ASCII art for the e-ink display."""
import datetime
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

DAYS_ABBR = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

# Box-drawing characters
H = "═"
V = "║"
TL, TR, BL, BR = "╔", "╗", "╚", "╝"
LM, RM = "╠", "╣"


def _load_font(base_dir: Path, size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        base_dir / "assets" / "fonts" / "DejaVuSansMono.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/Library/Fonts/Courier New.ttf"),
    ]
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)  # type: ignore[call-arg]


def _box_line(inner: str, width: int) -> str:
    """Pad inner string to width and wrap with box chars."""
    return f"{V} {inner:<{width}} {V}"


def _separator(width: int) -> str:
    return f"{LM}{H * (width + 2)}{RM}"


def _top(width: int) -> str:
    return f"{TL}{H * (width + 2)}{TR}"


def _bottom(width: int) -> str:
    return f"{BL}{H * (width + 2)}{BR}"


def render_suspend_screen(
    start: str,
    end: str,
    days: list,
    enabled: bool,
    next_wake: Optional[datetime.datetime],
    canvas_size: tuple,
    base_dir: Path,
) -> Image.Image:
    """Render a BBS/NFO-style suspend info screen for the e-ink display."""
    W, H_px = canvas_size
    img = Image.new("RGB", (W, H_px), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_lg = _load_font(base_dir, 20)
    font_md = _load_font(base_dir, 16)
    font_sm = _load_font(base_dir, 13)

    now = datetime.datetime.now()

    # ── build content lines ────────────────────────────────────────────
    inner_w = 60  # chars — wide enough for all 7 days with single-space separators

    # Active days row (single space between brackets so all 7 fit within inner_w)
    day_str = " ".join(
        f"[{DAYS_ABBR[i]}]" if i in days else f" {DAYS_ABBR[i]} "
        for i in range(7)
    )

    # Active hours line with dynamic dash fill
    _h_prefix = f"  ACTIVE HOURS   {start}  "
    _h_suffix = f"  {end}"
    _dashes = "─" * max(inner_w - len(_h_prefix) - len(_h_suffix), 4)
    hours_line = _h_prefix + _dashes + _h_suffix

    # Resume time
    if next_wake:
        resume_dt = next_wake
        today = now.date()
        if resume_dt.date() == today:
            resume_str = f"{resume_dt.strftime('%H:%M')}  (today)"
        elif resume_dt.date() == today + datetime.timedelta(days=1):
            resume_str = f"{resume_dt.strftime('%H:%M')}  (tomorrow)"
        else:
            resume_str = resume_dt.strftime("%H:%M  %a %d %b")
    else:
        resume_str = end + "  (next active window)"

    now_str = now.strftime("%H:%M  ·  %a %d %b %Y").upper()

    box_lines = [
        _top(inner_w),
        _box_line("", inner_w),
        _box_line(hours_line, inner_w),
        _box_line(f"  ACTIVE DAYS    {day_str}", inner_w),
        _box_line("", inner_w),
        _separator(inner_w),
        _box_line("", inner_w),
        _box_line(f"  RESUMES AT     {resume_str}", inner_w),
        _box_line("", inner_w),
        _bottom(inner_w),
    ]

    # ── measure and position ──────────────────────────────────────────
    # Header
    header = "T · A · L · E · V · I · S · I · O · N"
    subhead = "D I S P L A Y   S U S P E N D E D"

    def text_w(txt: str, fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), txt, font=fnt)
        return bb[2] - bb[0]

    def text_h(fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), "Ay", font=fnt)
        return bb[3] - bb[1]

    lh_lg = text_h(font_lg) + 6
    lh_md = text_h(font_md) + 4
    lh_sm = text_h(font_sm) + 3

    total_h = (
        lh_lg           # header
        + 6             # gap
        + lh_md         # subhead
        + 20            # gap before box
        + len(box_lines) * lh_sm
        + 18            # gap before now
        + lh_sm         # now line
    )

    y = (H_px - total_h) // 2

    # Draw header
    x_hdr = (W - text_w(header, font_lg)) // 2
    draw.text((x_hdr, y), header, font=font_lg, fill=(200, 146, 58))  # amber
    y += lh_lg + 6

    # Thin separator under header
    sep_x0 = (W - text_w(header, font_lg)) // 2
    sep_x1 = W - sep_x0
    draw.line([(sep_x0, y), (sep_x1, y)], fill=(80, 60, 20), width=1)
    y += 8

    # Subheader
    x_sub = (W - text_w(subhead, font_md)) // 2
    draw.text((x_sub, y), subhead, font=font_md, fill=(180, 180, 180))
    y += lh_md + 18

    # Box lines
    for line in box_lines:
        x_box = (W - text_w(line, font_sm)) // 2
        draw.text((x_box, y), line, font=font_sm, fill=(220, 220, 220))
        y += lh_sm

    y += 16

    # NOW line
    x_now = (W - text_w(now_str, font_sm)) // 2
    draw.text((x_now, y), now_str, font=font_sm, fill=(120, 120, 120))

    return img
