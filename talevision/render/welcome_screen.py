"""Welcome screen renderer — BBS/NFO style boot splash for the e-ink display."""
import logging
import socket
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# Inky Impression 7-colour native palette (pure, no dithering)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 128, 0)

# ASCII art logo — backslash/pipe style with decorative strokes
LOGO_LINES = [
    " _________  ________  ___       _______   ___      ___ ___  ________  ___  ________  ________",
    "|\\___   ___\\\\   __  \\|\\  \\     |\\  ___ \\ |\\  \\    /  /|\\  \\|\\   ____\\|\\  \\|\\   __  \\|\\   ___  \\",
    "\\|___ \\  \\_\\ \\  \\|\\  \\ \\  \\    \\ \\   __/|\\ \\  \\  /  / | \\  \\ \\  \\___|\\ \\  \\ \\  \\|\\  \\ \\  \\\\ \\  \\",
    "     \\ \\  \\ \\ \\   __  \\ \\  \\    \\ \\  \\_|/_\\ \\  \\/  / / \\ \\  \\ \\_____  \\ \\  \\ \\  \\\\\\  \\ \\  \\\\ \\  \\",
    "      \\ \\  \\ \\ \\  \\ \\  \\ \\  \\____\\ \\  \\_|\\ \\ \\    / /   \\ \\  \\|____|\\  \\ \\  \\ \\  \\\\\\  \\ \\  \\\\ \\  \\",
    "       \\ \\__\\ \\ \\__\\ \\__\\ \\_______\\ \\_______\\ \\__/ /     \\ \\__\\____\\_\\  \\ \\__\\ \\_______\\ \\__\\\\ \\__\\",
    "        \\|__|  \\|__|\\|__|\\|_______|\\|_______|\\|__|/       \\|__|\\_________\\|__|\\|_______|\\|__| \\|__|",
    "                                                              \\|_________|",
]

# Decorative strokes in red, backslash/pipe structure in blue
LOGO_STROKE_COLOR = RED
LOGO_FRAME_COLOR = BLUE

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
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
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

    font_logo = _load_font(base_dir, 10)
    font_md = _load_font(base_dir, 16)
    font_sm = _load_font(base_dir, 13)

    def text_w(txt: str, fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), txt, font=fnt)
        return bb[2] - bb[0]

    def text_h(fnt: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), "Ay", font=fnt)
        return bb[3] - bb[1]

    lh_logo = text_h(font_logo) + 1
    lh_md = text_h(font_md) + 4
    lh_sm = text_h(font_sm) + 3

    # ── Network info ──────────────────────────────────────────────────
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

    # ── Decorative top border ─────────────────────────────────────────
    border_colors = [RED, ORANGE, YELLOW, GREEN, BLUE, RED, ORANGE]
    bar_h = 4
    segment_w = W // len(border_colors)
    for i, color in enumerate(border_colors):
        x0 = i * segment_w
        x1 = (i + 1) * segment_w if i < len(border_colors) - 1 else W
        draw.rectangle([(x0, 0), (x1, bar_h - 1)], fill=color)

    # ── Calculate total height for vertical centering ─────────────────
    total_h = (
        len(LOGO_LINES) * lh_logo  # ASCII logo
        + 10                        # gap after logo
        + lh_md                     # subhead
        + 20                        # gap before box
        + len(info_lines) * lh_sm   # info box
        + 20                        # gap before footer
        + lh_md                     # SYSTEM READY
        + lh_sm                     # version line
    )

    y = max((H_px - total_h) // 2, bar_h + 10)

    # ── Draw ASCII art logo — two-tone (frame=blue, strokes=red) ────
    char_w = text_w("M", font_logo)
    for line in LOGO_LINES:
        x_logo = (W - len(line) * char_w) // 2
        cx = x_logo
        for ch in line:
            if ch in ("\\", "|", "/"):
                draw.text((cx, y), ch, font=font_logo, fill=LOGO_FRAME_COLOR)
            elif ch == "_":
                draw.text((cx, y), ch, font=font_logo, fill=LOGO_STROKE_COLOR)
            elif ch != " ":
                draw.text((cx, y), ch, font=font_logo, fill=BLACK)
            cx += char_w
        y += lh_logo
    y += 10

    # Subheader
    subhead = "S Y S T E M   B O O T"
    x_sub = (W - text_w(subhead, font_md)) // 2
    draw.text((x_sub, y), subhead, font=font_md, fill=BLACK)
    y += lh_md + 20

    # ── Info box (green text on white, box in black) ──────────────────
    for i, line in enumerate(info_lines):
        x_box = (W - text_w(line, font_sm)) // 2
        # Box frame chars in black, content in green
        if line.startswith(V):
            draw.text((x_box, y), line, font=font_sm, fill=BLACK)
        elif line.startswith(LM):
            draw.text((x_box, y), line, font=font_sm, fill=BLACK)
        else:
            draw.text((x_box, y), line, font=font_sm, fill=BLACK)
        y += lh_sm

    y += 18

    # ── Footer: SYSTEM READY in red ───────────────────────────────────
    ready = "■  S Y S T E M   R E A D Y  ■"
    x_ready = (W - text_w(ready, font_md)) // 2
    draw.text((x_ready, y), ready, font=font_md, fill=RED)
    y += lh_md + 4

    # Version / credit line
    ver = "TaleVision v1.0  ·  Netmilk Studio"
    x_ver = (W - text_w(ver, font_sm)) // 2
    draw.text((x_ver, y), ver, font=font_sm, fill=BLUE)

    # ── Bottom decorative border ──────────────────────────────────────
    for i, color in enumerate(border_colors):
        x0 = i * segment_w
        x1 = (i + 1) * segment_w if i < len(border_colors) - 1 else W
        draw.rectangle([(x0, H_px - bar_h), (x1, H_px - 1)], fill=color)

    return img
