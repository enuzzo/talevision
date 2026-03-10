"""Welcome screen renderer — BBS/NFO style boot splash for the e-ink display."""
import logging
import socket
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# Inky Impression 7-colour native palette (pure, no dithering)
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
RED    = (255, 0, 0)
GREEN  = (0, 255, 0)
BLUE   = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 128, 0)

TAGLINE = "The best thing on your wall since the clock."

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


def _box_line(inner: str, width: int) -> str:
    return f"{V} {inner:<{width}} {V}"


def _separator(width: int) -> str:
    return f"{LM}{H * (width + 2)}{RM}"


def _top(width: int) -> str:
    return f"{TL}{H * (width + 2)}{TR}"


def _bottom(width: int) -> str:
    return f"{BL}{H * (width + 2)}{BR}"


def _get_ip() -> str:
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        ips = [ip for ip in out.split() if ":" not in ip and not ip.startswith("127.")]
        return ips[0] if ips else "unknown"
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "unknown"


def render_welcome_screen(
    port: int,
    mode: str,
    playlist: list,
    canvas_size: tuple,
    base_dir: Path,
) -> Image.Image:
    W, H_px = canvas_size
    img = Image.new("RGB", (W, H_px), WHITE)
    draw = ImageDraw.Draw(img)

    font_lobster = _load_lobster(base_dir, 88)
    font_tagline = _load_serif(base_dir, 22, italic=True)
    font_md      = _load_font(base_dir, 17, bold=True)
    font_sm      = _load_font(base_dir, 14, bold=True)

    def text_w(txt: str, fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), txt, font=fnt)
        return bb[2] - bb[0]

    def text_h(fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), "Ay", font=fnt)
        return bb[3] - bb[1]

    lh_lobster = text_h(font_lobster) + 4
    lh_tagline = text_h(font_tagline) + 4
    lh_md      = text_h(font_md) + 4
    lh_sm      = text_h(font_sm) + 3

    hostname = socket.gethostname()
    ip = _get_ip()
    playlist_str = " → ".join(p.upper() for p in playlist) if playlist else mode.upper()
    dashboard_url = f"http://{ip}:{port}"

    inner_w = 52

    info_lines = [
        _top(inner_w),
        _box_line("", inner_w),
        _box_line(f"  HOSTNAME     {hostname}", inner_w),
        _box_line(f"  IP ADDRESS   {ip}", inner_w),
        _box_line(f"  DASHBOARD    {dashboard_url}", inner_w),
        _box_line("", inner_w),
        _separator(inner_w),
        _box_line("", inner_w),
        _box_line(f"  MODE         {mode.upper()}", inner_w),
        _box_line(f"  PLAYLIST     {playlist_str}", inner_w),
        _box_line("", inner_w),
        _bottom(inner_w),
    ]

    # ── Rainbow bars ──────────────────────────────────────────────────────────
    # Only use high-contrast colours — GREEN/YELLOW are too faint on white e-ink
    border_colors = [RED, ORANGE, RED, BLUE, ORANGE, RED, BLUE]
    bar_h = 6
    segment_w = W // len(border_colors)
    for i, color in enumerate(border_colors):
        x0 = i * segment_w
        x1 = (i + 1) * segment_w if i < len(border_colors) - 1 else W
        draw.rectangle([(x0, 0), (x1, bar_h - 1)], fill=color)

    # ── Vertical centering ────────────────────────────────────────────────────
    subhead = "S Y S T E M   B O O T"
    TITLE_GAP = 14          # extra space between Lobster title and tagline
    total_h = (
        lh_lobster + TITLE_GAP
        + lh_tagline + 12
        + lh_md + 16            # subhead + gap
        + len(info_lines) * lh_sm
        + 12
        + lh_md                 # SYSTEM READY
        + lh_sm                 # version
    )
    y = max((H_px - total_h) // 2, bar_h + 8)

    # ── TaleVision in Lobster ─────────────────────────────────────────────────
    title = "TaleVision"
    draw.text(((W - text_w(title, font_lobster)) // 2, y), title,
              font=font_lobster, fill=ORANGE)
    y += lh_lobster + TITLE_GAP

    # ── Tagline in Taviraj Italic ─────────────────────────────────────────────
    draw.text(((W - text_w(TAGLINE, font_tagline)) // 2, y), TAGLINE,
              font=font_tagline, fill=BLACK)
    y += lh_tagline + 12

    # ── S Y S T E M   B O O T ────────────────────────────────────────────────
    draw.text(((W - text_w(subhead, font_md)) // 2, y), subhead,
              font=font_md, fill=BLACK)
    y += lh_md + 16

    # ── Info box ──────────────────────────────────────────────────────────────
    for line in info_lines:
        draw.text(((W - text_w(line, font_sm)) // 2, y), line,
                  font=font_sm, fill=BLACK)
        y += lh_sm

    y += 12

    # ── ■ SYSTEM READY ■ ──────────────────────────────────────────────────────
    ready = "■  S Y S T E M   R E A D Y  ■"
    draw.text(((W - text_w(ready, font_md)) // 2, y), ready,
              font=font_md, fill=RED)
    y += lh_md + 4

    # ── Version / credit ──────────────────────────────────────────────────────
    ver = "TaleVision v1.0  ·  Netmilk Studio"
    draw.text(((W - text_w(ver, font_sm)) // 2, y), ver,
              font=font_sm, fill=BLUE)

    # ── Bottom rainbow bar ────────────────────────────────────────────────────
    for i, color in enumerate(border_colors):
        x0 = i * segment_w
        x1 = (i + 1) * segment_w if i < len(border_colors) - 1 else W
        draw.rectangle([(x0, H_px - bar_h), (x1, H_px - 1)], fill=color)

    return img
