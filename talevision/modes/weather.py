"""Weather display mode — renders wttr.in ANSI output on e-ink via PIL."""
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)

ANSI_COLOR_MAP = {
    30: COLOR_BLACK,
    31: (255, 0, 0),
    32: (0, 0, 255),
    33: (255, 165, 0),
    34: (0, 0, 255),
    35: (255, 0, 0),
    36: (0, 0, 255),
    37: COLOR_BLACK,
    39: COLOR_BLACK,
    90: (110, 110, 110),
    91: (255, 0, 0),
    92: (0, 0, 255),
    93: (255, 165, 0),
    94: (0, 0, 255),
    95: (255, 0, 0),
    96: (0, 0, 255),
    97: COLOR_BLACK,
}

ANSI_RE = re.compile(r"\033\[([0-9;]*)m")

FONT_SIZE = 12
LINE_GAP = 0


def _fetch_ansi(lat: float, lon: float, lang: str = "it",
                units: str = "m", timeout: int = 10) -> str:
    loc = f"{lat:.4f},{lon:.4f}"
    encoded = urllib.parse.quote(loc)
    url = f"http://wttr.in/{encoded}?A&F&lang={lang}&{units}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


Cell = Tuple[str, Tuple[int, int, int], bool]


def _parse_ansi(text: str) -> List[List[Cell]]:
    lines_out: List[List[Cell]] = []
    current_color = COLOR_BLACK
    current_bold = False

    lines = text.split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines and ("Località:" in lines[-1] or "Location:" in lines[-1]
                  or "Ubicación:" in lines[-1] or "Localisation:" in lines[-1]
                  or "Standort:" in lines[-1] or "Localização:" in lines[-1]):
        lines.pop()

    for raw_line in lines:
        cells: List[Cell] = []
        pos = 0
        for m in ANSI_RE.finditer(raw_line):
            before = raw_line[pos:m.start()]
            for ch in before:
                cells.append((ch, current_color, current_bold))
            params_str = m.group(1)
            if not params_str:
                params = [0]
            else:
                params = [int(p) for p in params_str.split(";") if p.isdigit()]
            for p in params:
                if p == 0:
                    current_color = COLOR_BLACK
                    current_bold = False
                elif p == 1:
                    current_bold = True
                elif p == 4:
                    pass
                elif p in ANSI_COLOR_MAP:
                    current_color = ANSI_COLOR_MAP[p]
            pos = m.end()
        remainder = raw_line[pos:]
        for ch in remainder:
            cells.append((ch, current_color, current_bold))
        lines_out.append(cells)

    return lines_out


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default(size=size)


class WeatherMode(DisplayMode):
    """Displays wttr.in ANSI weather output rendered with monospace font."""

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.weather
        self._display = config.display
        self._base_dir = base_dir
        self._city = self._cfg.city
        self._lat = self._cfg.lat
        self._lon = self._cfg.lon
        self._units = self._cfg.units
        self._language = self._cfg.language
        self._last_ansi: Optional[str] = None
        self._font_dir = base_dir / "assets" / "fonts"

    @property
    def name(self) -> str:
        return "weather"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info(f"Weather mode activated (city={self._city}, "
                 f"lat={self._lat}, lon={self._lon})")

    def set_location(self, city: str, lat: float, lon: float) -> None:
        self._city = city.strip()
        self._lat = lat
        self._lon = lon
        log.info(f"Weather location set to: {self._city} ({self._lat}, {self._lon})")

    def set_units(self, units: str) -> None:
        if units in ("m", "u", "M"):
            self._units = units
            log.info(f"Weather units set to: {self._units}")

    def set_language(self, lang: str) -> None:
        self._language = lang
        log.info(f"Weather language set to: {self._language}")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height

        try:
            ansi_text = _fetch_ansi(
                self._lat, self._lon,
                lang=self._language,
                units=self._units,
                timeout=self._cfg.timeout,
            )
            self._last_ansi = ansi_text
        except Exception as exc:
            log.error(f"Weather ANSI fetch failed: {exc}")
            ansi_text = self._last_ansi

        img = Image.new("RGB", (w, h), COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        if ansi_text is None:
            font_err = _load_font(self._font_dir / "Signika-Bold.ttf", 28)
            draw.text((30, 200), "Weather unavailable", font=font_err, fill=COLOR_BLACK)
            return img

        font_regular = _load_font(
            self._font_dir / "InconsolataNerdFontMono-Bold.ttf", FONT_SIZE)
        font_bold = font_regular

        parsed = _parse_ansi(ansi_text)

        bbox = font_regular.getbbox("M")
        char_w = bbox[2] - bbox[0]
        char_h = FONT_SIZE + LINE_GAP

        max_cols = max((len(line) for line in parsed), default=0)
        total_w = max_cols * char_w
        total_h = len(parsed) * char_h
        offset_x = max(0, (w - total_w) // 2)
        offset_y = max(0, (h - total_h) // 2)

        for row_idx, line_cells in enumerate(parsed):
            y = offset_y + row_idx * char_h
            if y > h:
                break
            for col_idx, (ch, color, bold) in enumerate(line_cells):
                x = offset_x + col_idx * char_w
                if x > w:
                    break
                if ch == " ":
                    continue
                font = font_bold if bold else font_regular
                draw.text((x, y), ch, font=font, fill=color)

        return img

    def get_state(self) -> ModeState:
        return ModeState(
            mode="weather",
            extra={
                "city": self._city,
                "lat": self._lat,
                "lon": self._lon,
                "units": self._units,
                "language": self._language,
            },
        )
