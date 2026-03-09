"""ANSi Art display mode — renders BBS .ans files via pyte + BlockZone TTF."""
import logging
import random
from pathlib import Path
from typing import List, Optional

import pyte
from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

# CGA 16-colour index → Inky 7-colour native RGB
# Index = CGA colour number (0-7 standard, 8-15 bright/bold variants)
CGA_TO_INKY = [
    (0,   0,   0),    # 0  black        → Black
    (0,   0,   255),  # 1  dark blue    → Blue
    (0,   255, 0),    # 2  dark green   → Green
    (0,   255, 0),    # 3  dark cyan    → Green  (closest native)
    (255, 0,   0),    # 4  dark red     → Red
    (255, 0,   0),    # 5  dark magenta → Red    (closest native)
    (255, 128, 0),    # 6  brown        → Orange
    (255, 255, 255),  # 7  light gray   → White
    (0,   0,   0),    # 8  dark gray    → Black
    (0,   0,   255),  # 9  light blue   → Blue
    (0,   255, 0),    # 10 light green  → Green
    (0,   255, 0),    # 11 light cyan   → Green  (closest native)
    (255, 0,   0),    # 12 light red    → Red
    (255, 0,   0),    # 13 lt magenta   → Red    (closest native)
    (255, 255, 0),    # 14 yellow       → Yellow
    (255, 255, 255),  # 15 white        → White
]

# pyte named colour → CGA index (foreground; default = white)
PYTE_FG_TO_CGA = {
    'default': 7, 'white': 7, 'black': 0,
    'red': 4, 'green': 2, 'brown': 6, 'blue': 1,
    'magenta': 5, 'cyan': 3,
}
# pyte named colour → CGA index (background; default = black)
PYTE_BG_TO_CGA = {
    'default': 0, 'black': 0, 'white': 7,
    'red': 4, 'green': 2, 'brown': 6, 'blue': 1,
    'magenta': 5, 'cyan': 3,
}

SCREEN_COLS = 80
SCREEN_ROWS = 300   # generous — most ANS art is 25-100 rows


def _strip_sauce(data: bytes) -> bytes:
    """Strip SAUCE metadata record and CP437 EOF marker (0x1A) from ANS data."""
    eof = data.find(b'\x1a')
    if eof != -1:
        data = data[:eof]
    sauce = data.rfind(b'SAUCE')
    if sauce != -1 and len(data) - sauce <= 200:
        data = data[:sauce]
    return data


def _fg_rgb(cell) -> tuple:
    name = cell.fg if isinstance(cell.fg, str) else 'default'
    idx = PYTE_FG_TO_CGA.get(name, 7)
    if cell.bold and idx < 8:
        idx += 8
    return CGA_TO_INKY[idx]


def _bg_rgb(cell) -> tuple:
    name = cell.bg if isinstance(cell.bg, str) else 'default'
    idx = PYTE_BG_TO_CGA.get(name, 0)
    return CGA_TO_INKY[idx]


def _render_ans(path: Path, font: ImageFont.FreeTypeFont,
                char_w: int, char_h: int,
                canvas_w: int, canvas_h: int) -> Image.Image:
    """Parse a .ans file and render it as a PIL Image fitted to canvas size."""
    raw = path.read_bytes()
    data = _strip_sauce(raw)

    # Decode as CP437 — handles extended ASCII (block chars, box drawing, etc.)
    # Feed as Unicode string to pyte.Stream (not ByteStream)
    text = data.decode('cp437', errors='replace')

    screen = pyte.Screen(SCREEN_COLS, SCREEN_ROWS)
    stream = pyte.Stream(screen)
    stream.feed(text)

    used_rows = max(1, min(screen.cursor.y + 1, SCREEN_ROWS))

    # Render character grid to a bitmap
    art_w = SCREEN_COLS * char_w
    art_h = used_rows * char_h
    art = Image.new("RGB", (art_w, art_h), (0, 0, 0))
    draw = ImageDraw.Draw(art)

    for row_idx in range(used_rows):
        row = screen.buffer[row_idx]
        for col_idx in range(SCREEN_COLS):
            cell = row[col_idx]
            fg = _fg_rgb(cell)
            bg = _bg_rgb(cell)
            x = col_idx * char_w
            y = row_idx * char_h
            if bg != (0, 0, 0):
                draw.rectangle([x, y, x + char_w - 1, y + char_h - 1], fill=bg)
            ch = cell.data
            if ch and ch != ' ':
                draw.text((x, y), ch, font=font, fill=fg, anchor="lt")

    # Contain in canvas (scale to fit, centre on black)
    scale = min(canvas_w / art_w, canvas_h / art_h)
    new_w = max(1, int(art_w * scale))
    new_h = max(1, int(art_h * scale))
    scaled = art.resize((new_w, new_h), Image.NEAREST)
    result = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
    result.paste(scaled, ((canvas_w - new_w) // 2, (canvas_h - new_h) // 2))
    return result


class AnsiMode(DisplayMode):
    """Cycles through .ans BBS artscene files, rendered via BlockZone TTF."""

    def __init__(self, config: AppConfig, base_dir: Path):
        self._cfg = config.ansi
        self._display = config.display
        self._base_dir = base_dir
        self._art_dir = base_dir / self._cfg.art_dir
        self._files: List[Path] = []
        self._index: int = 0
        self._font: Optional[ImageFont.FreeTypeFont] = None
        self._char_w: int = 8
        self._char_h: int = 16

    @property
    def name(self) -> str:
        return "ansi"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        self._files = sorted(self._art_dir.glob("*.ans"))
        if not self._files:
            log.warning(f"ANSi: no .ans files found in {self._art_dir}")
            return
        if self._cfg.order == "random":
            random.shuffle(self._files)
        else:
            self._files = sorted(self._files)
        self._index = 0
        self._font = self._load_font()
        self._char_w, self._char_h = self._measure_cell()
        log.info(f"ANSi mode activated: {len(self._files)} files, "
                 f"cell={self._char_w}×{self._char_h}px")

    def _load_font(self) -> ImageFont.FreeTypeFont:
        candidates = [
            self._base_dir / "assets" / "BlockZone-master" / "BlockZone.ttf",
        ]
        for p in candidates:
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), 16)
                except Exception as exc:
                    log.warning(f"Failed to load BlockZone: {exc}")
        log.warning("ANSi: BlockZone.ttf not found, falling back to default font")
        return ImageFont.load_default(size=16)

    def _measure_cell(self) -> tuple:
        """Measure actual char cell dimensions from the loaded font."""
        if self._font is None:
            return 8, 16
        try:
            bbox = self._font.getbbox("M")
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            return max(w, 1), max(h, 1)
        except Exception:
            return 8, 16

    def render(self) -> Image.Image:
        if not self._files or self._font is None:
            return Image.new("RGB", (self._display.width, self._display.height), (0, 0, 0))

        path = self._files[self._index % len(self._files)]
        log.info(f"ANSi: rendering {path.name} ({self._index + 1}/{len(self._files)})")
        try:
            img = _render_ans(
                path, self._font,
                self._char_w, self._char_h,
                self._display.width, self._display.height,
            )
        except Exception as exc:
            log.error(f"ANSi render error ({path.name}): {exc}", exc_info=True)
            img = Image.new("RGB", (self._display.width, self._display.height), (0, 0, 0))

        self._index = (self._index + 1) % len(self._files)
        return img

    def get_state(self) -> ModeState:
        current = self._files[self._index % len(self._files)].name if self._files else ""
        return ModeState(
            mode="ansi",
            extra={
                "file": current,
                "index": self._index,
                "total": len(self._files),
            },
        )
