"""Suspend screen renderer — BBS/NFO style ASCII art for the e-ink display."""
import csv
import datetime
import logging
import random
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

DAYS_ABBR = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

# Inky Impression 7-colour native palette
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
RED    = (255, 0, 0)
GREEN  = (0, 255, 0)
BLUE   = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 128, 0)

# Box-drawing characters
H = "═"
V = "║"
TL, TR, BL, BR = "╔", "╗", "╚", "╝"
LM, RM = "╠", "╣"


def _load_font(base_dir: Path, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if bold:
        candidates = [
            base_dir / "assets" / "fonts" / "DejaVuSansMono-Bold.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
        ]
    else:
        candidates = []
    candidates += [
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


def _load_lobster(base_dir: Path, size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        base_dir / "assets" / "fonts" / "Lobster-Regular.ttf",
        base_dir / "assets" / "fonts" / "Taviraj-Black.ttf",
    ]
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)  # type: ignore[call-arg]


def _load_serif(base_dir: Path, size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    name = "Taviraj-Italic.ttf" if italic else "Taviraj-Regular.ttf"
    p = base_dir / "assets" / "fonts" / name
    if p.exists():
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            pass
    return ImageFont.load_default(size=size)  # type: ignore[call-arg]


def _random_quote(base_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    """Pick a random short literary quote from assets/lang/ CSV files."""
    lang_dir = base_dir / "assets" / "lang"
    # Prefer Italian; fall back to any language file
    candidates: List[Path] = []
    it = lang_dir / "quotes-it.csv"
    if it.exists():
        candidates.append(it)
    candidates += sorted(p for p in lang_dir.glob("quotes-*.csv") if p != it)
    if not candidates:
        return None, None

    for csv_path in candidates:
        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = [
                    r for r in reader
                    if r.get("quote") and 30 <= len(r["quote"]) <= 130
                ]
            if rows:
                row = random.choice(rows)
                quote = row["quote"].replace("<em>", "").replace("</em>", "").strip()
                author = row.get("author", "").strip()
                return quote, author
        except Exception:
            continue
    return None, None


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    draw: ImageDraw.Draw,
    max_width: int,
    max_lines: int = 3,
) -> List[str]:
    """Word-wrap text to fit max_width px; limit to max_lines lines."""
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    # Truncate last line with ellipsis if text was cut
    if lines and len(" ".join(words)) > len(" ".join(lines)):
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last + "…"
    return lines


def _box_line(inner: str, width: int) -> str:
    return f"{V} {inner:<{width}} {V}"


def _separator(width: int) -> str:
    return f"{LM}{H * (width + 2)}{RM}"


def _top(width: int) -> str:
    return f"{TL}{H * (width + 2)}{TR}"


def _bottom(width: int) -> str:
    return f"{BL}{H * (width + 2)}{BR}"


def _load_frame(base_dir: Path) -> "Image.Image | None":
    p = base_dir / "assets" / "img" / "talevision-frame.png"
    if p.exists():
        try:
            return Image.open(p).convert("RGBA")
        except Exception:
            pass
    return None


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
    img = Image.new("RGB", (W, H_px), WHITE)
    frame = _load_frame(base_dir)
    if frame:
        img.paste(frame, (0, 0), frame)
    draw = ImageDraw.Draw(img)

    font_lobster = _load_lobster(base_dir, 65)
    font_quote   = _load_serif(base_dir, 21, italic=True)
    font_author  = _load_serif(base_dir, 17)
    font_md      = _load_font(base_dir, 19, bold=True)
    font_sm      = _load_font(base_dir, 16, bold=True)

    def text_w(txt: str, fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), txt, font=fnt)
        return bb[2] - bb[0]

    def text_h(fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), "Ay", font=fnt)
        return bb[3] - bb[1]

    lh_lobster = text_h(font_lobster) + 4
    lh_quote   = text_h(font_quote) + 4
    lh_author  = text_h(font_author) + 3
    lh_md      = text_h(font_md) + 4
    lh_sm      = text_h(font_sm) + 3

    now = datetime.datetime.now()

    # ── BBS info box content ──────────────────────────────────────────────────
    inner_w = 60

    day_str = " ".join(
        f"[{DAYS_ABBR[i]}]" if i in days else f" {DAYS_ABBR[i]} "
        for i in range(7)
    )

    _h_prefix = f"  ACTIVE HOURS   {start}  "
    _h_suffix = f"  {end}"
    _dashes = "─" * max(inner_w - len(_h_prefix) - len(_h_suffix), 4)
    hours_line = _h_prefix + _dashes + _h_suffix

    if next_wake:
        today = now.date()
        if next_wake.date() == today:
            resume_str = f"{next_wake.strftime('%H:%M')}  (today)"
        elif next_wake.date() == today + datetime.timedelta(days=1):
            resume_str = f"{next_wake.strftime('%H:%M')}  (tomorrow)"
        else:
            resume_str = next_wake.strftime("%H:%M  %a %d %b")
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

    # ── Random quote ──────────────────────────────────────────────────────────
    quote_text, author = _random_quote(base_dir)
    quote_lines = []
    if quote_text:
        quote_lines = _wrap_text(quote_text, font_quote, draw, W - 80, max_lines=2)

    # ── Vertical centering ────────────────────────────────────────────────────
    quote_block_h = len(quote_lines) * lh_quote + (lh_author + 4 if author else 0) if quote_lines else 0
    total_h = (
        lh_lobster + 8
        + quote_block_h + (14 if quote_block_h else 0)
        + len(box_lines) * lh_sm
        + 14
        + lh_sm  # now line
    )
    y = max((H_px - total_h) // 2, 28)  # 28 = frame inner top margin

    # ── TaleVision in Lobster ─────────────────────────────────────────────────
    title = "TaleVision"
    draw.text(((W - text_w(title, font_lobster)) // 2, y), title,
              font=font_lobster, fill=BLACK)
    y += lh_lobster + 8

    # ── Quote + author ────────────────────────────────────────────────────────
    if quote_lines:
        for line in quote_lines:
            draw.text(((W - text_w(line, font_quote)) // 2, y), line,
                      font=font_quote, fill=BLACK)
            y += lh_quote
        if author:
            author_str = f"— {author}"
            draw.text(((W - text_w(author_str, font_author)) // 2, y), author_str,
                      font=font_author, fill=(100, 90, 80))
            y += lh_author + 4
        y += 14

    # ── BBS info box ──────────────────────────────────────────────────────────
    for line in box_lines:
        draw.text(((W - text_w(line, font_sm)) // 2, y), line,
                  font=font_sm, fill=BLACK)
        y += lh_sm

    y += 14

    # ── NOW line ──────────────────────────────────────────────────────────────
    draw.text(((W - text_w(now_str, font_sm)) // 2, y), now_str,
              font=font_sm, fill=(80, 80, 80))

    return img
