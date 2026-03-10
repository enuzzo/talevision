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

TAGLINES = [
    "The best thing a screen can do is earn its update.",
    "One Pi. One wall. An unreasonable amount of thought.",
    "Updates every five minutes. Refreshes never.",
    "Literary quotes and slow cinema, sharing a wall politely.",
    "A clock that reads. A cinema that waits. One device that doesn't care.",
    "The Pis were already there. The reasoning was air-tight.",
    "Each frame costs 30 seconds of e-ink patience.",
    "Typeset in Taviraj. Rendered on a Tuesday.",
    "Six languages. Seven colours. Zero hurry.",
    "The screen earns its right to exist, one minute at a time.",
    "Built to impress guests who didn't ask to be impressed.",
    "A confession of over-engineering disguised as a clock.",
    "SlowMovie: because films deserve to be watched at 1 frame per minute.",
    "No streaming. No notifications. Just the wall, being interesting.",
    "It updates less often than your opinions. And it's more reliable.",
    "Borges, Calvino, Woolf — and a random Wikipedia article. Niche.",
    "Powered by a chip the size of a stamp and a questionable amount of free time.",
    "A dashboard for a device that doesn't need one.",
    "The font survived the migration. Not everything does.",
    "Four buttons on the side. None of them labelled correctly.",
]

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


def _load_frame(base_dir: Path) -> "Image.Image | None":
    p = base_dir / "assets" / "img" / "talevision-frame.png"
    if p.exists():
        try:
            return Image.open(p).convert("RGBA")
        except Exception:
            pass
    return None


def render_welcome_screen(
    port: int,
    mode: str,
    playlist: list,
    canvas_size: tuple,
    base_dir: Path,
) -> Image.Image:
    W, H_px = canvas_size
    img = Image.new("RGB", (W, H_px), WHITE)
    frame = _load_frame(base_dir)
    if frame:
        img.paste(frame, (0, 0), frame)
    draw = ImageDraw.Draw(img)

    font_lobster = _load_lobster(base_dir, 75)
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

    inner_w = 64  # wide enough for 4-mode playlist + 6 chars breathing room per side

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

    import random
    tagline = random.choice(TAGLINES)

    # ── Vertical centering ────────────────────────────────────────────────────
    subhead = "S Y S T E M   B O O T"
    TITLE_GAP = 14          # extra space between Lobster title and tagline
    TAGLINE_TO_BOOT_GAP = 28  # generous gap: tagline → SYSTEM BOOT
    BOOT_TO_TABLE_GAP = 6     # tight: SYSTEM BOOT sits close to its table
    total_h = (
        lh_lobster + TITLE_GAP
        + lh_tagline + TAGLINE_TO_BOOT_GAP
        + lh_md + BOOT_TO_TABLE_GAP       # [ starting in 30 seconds ]
        + len(info_lines) * lh_sm
        + 8
        + lh_sm                           # version
    )
    y = max((H_px - total_h) // 2, 28)  # 28 = frame inner top margin

    # ── TaleVision in Lobster ─────────────────────────────────────────────────
    title = "TaleVision"
    draw.text(((W - text_w(title, font_lobster)) // 2, y), title,
              font=font_lobster, fill=BLACK)
    y += lh_lobster + TITLE_GAP

    # ── Tagline in Taviraj Italic ─────────────────────────────────────────────
    draw.text(((W - text_w(tagline, font_tagline)) // 2, y), tagline,
              font=font_tagline, fill=BLACK)
    y += lh_tagline + TAGLINE_TO_BOOT_GAP

    # ── [ Starting in 30 seconds ] ───────────────────────────────────────────
    starting = "[  S T A R T I N G   I N   3 0   S E C O N D S  ]"
    draw.text(((W - text_w(starting, font_md)) // 2, y), starting,
              font=font_md, fill=RED)
    y += lh_md + BOOT_TO_TABLE_GAP

    # ── Info box ──────────────────────────────────────────────────────────────
    for line in info_lines:
        draw.text(((W - text_w(line, font_sm)) // 2, y), line,
                  font=font_sm, fill=BLACK)
        y += lh_sm

    y += 8

    # ── Version / credit ──────────────────────────────────────────────────────
    ver = "TaleVision v1.5  ·  Netmilk Studio"
    draw.text(((W - text_w(ver, font_sm)) // 2, y), ver,
              font=font_sm, fill=BLUE)

    return img
