"""Weather display mode — renders wttr.in ANSI output on e-ink via PIL."""
import datetime
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

FONT_SIZE_CC = 14
FONT_SIZE_FC = 12
HEADER_FONT_SIZE = 16
LINE_GAP = 0


def _fetch_ansi(lat: float, lon: float, lang: str = "it",
                units: str = "m", timeout: int = 10) -> str:
    loc = f"{lat:.4f},{lon:.4f}"
    encoded = urllib.parse.quote(loc)
    url = f"http://wttr.in/{encoded}?AQF&lang={lang}&{units}"
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


def _find_forecast_start(parsed: List[List[Cell]]) -> int:
    for i, line in enumerate(parsed):
        for ch, _, _ in line:
            if ch == "\u250c":
                return i
    return len(parsed)


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

        parsed = _parse_ansi(ansi_text)

        fc_start = _find_forecast_start(parsed)
        cc_lines = parsed[:fc_start]
        fc_lines = parsed[fc_start:]

        while cc_lines and not any(ch != " " for ch, _, _ in cc_lines[0]):
            cc_lines.pop(0)
        while cc_lines and not any(ch != " " for ch, _, _ in cc_lines[-1]):
            cc_lines.pop()

        font_header = _load_font(
            self._font_dir / "Signika-Bold.ttf", HEADER_FONT_SIZE)
        font_cc = _load_font(
            self._font_dir / "InconsolataNerdFontMono-Bold.ttf", FONT_SIZE_CC)
        font_fc = _load_font(
            self._font_dir / "InconsolataNerdFontMono-Bold.ttf", FONT_SIZE_FC)

        cc_bbox = font_cc.getbbox("M")
        cc_char_w = cc_bbox[2] - cc_bbox[0]
        cc_char_h = FONT_SIZE_CC + LINE_GAP

        fc_bbox = font_fc.getbbox("M")
        fc_char_w = fc_bbox[2] - fc_bbox[0]
        fc_char_h = FONT_SIZE_FC + LINE_GAP

        now = datetime.datetime.now()
        header_text = f"{self._city} \u00b7 {now.strftime('%H:%M')}"
        h_bbox = font_header.getbbox(header_text)
        header_w = h_bbox[2] - h_bbox[0]
        header_h = h_bbox[3] - h_bbox[1]

        y = 4
        draw.text(((w - header_w) // 2, y), header_text,
                  font=font_header, fill=COLOR_BLACK)
        y += header_h + 6

        cc_max_cols = max((len(line) for line in cc_lines), default=0)
        cc_total_w = cc_max_cols * cc_char_w
        cc_offset_x = max(0, (w - cc_total_w) // 2)

        for row_idx, line_cells in enumerate(cc_lines):
            row_y = y + row_idx * cc_char_h
            if row_y > h:
                break
            for col_idx, (ch, color, bold) in enumerate(line_cells):
                x = cc_offset_x + col_idx * cc_char_w
                if x > w:
                    break
                if ch == " ":
                    continue
                draw.text((x, row_y), ch, font=font_cc, fill=color)

        y += len(cc_lines) * cc_char_h + 4

        fc_max_cols = max((len(line) for line in fc_lines), default=0)
        fc_total_w = fc_max_cols * fc_char_w
        fc_offset_x = max(0, (w - fc_total_w) // 2)

        for row_idx, line_cells in enumerate(fc_lines):
            row_y = y + row_idx * fc_char_h
            if row_y > h:
                break
            for col_idx, (ch, color, bold) in enumerate(line_cells):
                x = fc_offset_x + col_idx * fc_char_w
                if x > w:
                    break
                if ch == " ":
                    continue
                draw.text((x, row_y), ch, font=font_fc, fill=color)

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
