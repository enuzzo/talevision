"""Weather display mode — fetches current conditions from wttr.in and renders with PIL."""
import datetime
import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

COLOR_WHITE  = (255, 255, 255)
COLOR_BLACK  = (0,   0,   0)
COLOR_ACCENT = (0,   181, 116)   # green — weather mode color
COLOR_MUTED  = (110, 110, 110)
COLOR_BLUE   = (57,  184, 255)


def _fetch_weather(location: str, timeout: int = 10) -> Dict:
    """Fetch current weather from wttr.in for the given location (format=j1)."""
    encoded = urllib.parse.quote(location)
    url = f"https://wttr.in/{encoded}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _wrap_text(text: str, font, draw: ImageDraw.Draw, max_width: int) -> List[str]:
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
    if current:
        lines.append(current)
    return lines


class WeatherMode(DisplayMode):
    """Displays current weather and 3-day forecast from wttr.in."""

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.weather
        self._display = config.display
        self._base_dir = base_dir
        self._location = self._cfg.location
        self._last_data: Optional[Dict] = None
        self._font_dir = base_dir / "assets" / "fonts"

    @property
    def name(self) -> str:
        return "weather"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info(f"Weather mode activated (location={self._location})")

    def set_location(self, location: str) -> None:
        self._location = location.strip()
        log.info(f"Weather location set to: {self._location}")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height
        try:
            data = _fetch_weather(self._location, timeout=self._cfg.timeout)
            self._last_data = data
        except Exception as exc:
            log.error(f"Weather fetch failed ({self._location}): {exc}")
            data = self._last_data

        img = Image.new("RGB", (w, h), COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        if data is None:
            font = _load_font(self._font_dir / "Signika-Bold.ttf", 28)
            draw.text((30, 200), "Weather unavailable", font=font, fill=COLOR_BLACK)
            return img

        font_bold  = _load_font(self._font_dir / "Signika-Bold.ttf", 32)
        font_large = _load_font(self._font_dir / "Signika-Bold.ttf", 80)
        font_body  = _load_font(self._font_dir / "Taviraj-Regular.ttf", 22)
        font_small = _load_font(self._font_dir / "Taviraj-Regular.ttf", 18)

        pad = 30
        now = datetime.datetime.now()

        # ── Header: time + location ───────────────────────────────────────────
        y = pad
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%A, %d %B %Y")

        draw.text((pad, y), time_str, font=font_bold, fill=COLOR_BLACK)
        loc_w = draw.textlength(self._location, font=font_body)
        draw.text((w - pad - loc_w, y + 6), self._location, font=font_body, fill=COLOR_ACCENT)
        y += 38
        draw.text((pad, y), date_str, font=font_small, fill=COLOR_MUTED)
        y += 26
        draw.line([(pad, y), (w - pad, y)], fill=COLOR_ACCENT, width=2)
        y += 16

        # ── Current conditions ────────────────────────────────────────────────
        cond = data.get("current_condition", [{}])[0]
        temp_c = cond.get("temp_C", "?")
        feels  = cond.get("FeelsLikeC", "?")
        desc   = (cond.get("weatherDesc") or [{}])[0].get("value", "")
        wind   = cond.get("windspeedKmph", "?")
        humidity = cond.get("humidity", "?")

        # Big temperature on left
        temp_str = f"{temp_c}°"
        draw.text((pad, y), temp_str, font=font_large, fill=COLOR_BLACK)
        temp_w = int(draw.textlength(temp_str, font=font_large))

        # Condition + details to the right of temp
        rx = pad + temp_w + 20
        ry = y + 10
        draw.text((rx, ry),      desc,                          font=font_bold,  fill=COLOR_BLACK)
        draw.text((rx, ry + 40), f"Feels like {feels}°C",      font=font_body,  fill=COLOR_MUTED)
        draw.text((rx, ry + 66), f"Wind {wind} km/h  ·  Humidity {humidity}%",
                  font=font_small, fill=COLOR_MUTED)

        # Move y below the current-conditions block (large font is ~90px)
        y += 106

        # ── 3-day forecast ────────────────────────────────────────────────────
        draw.line([(pad, y), (w - pad, y)], fill=(210, 210, 210), width=1)
        y += 14

        forecast = data.get("weather", [])[:3]
        col_w = (w - 2 * pad) // max(len(forecast), 1)

        for i, day in enumerate(forecast):
            cx = pad + i * col_w
            try:
                d = datetime.datetime.strptime(day["date"], "%Y-%m-%d")
                day_label = d.strftime("%a %d %b")
            except Exception:
                day_label = day.get("date", "")

            mx = day.get("maxtempC", "?")
            mn = day.get("mintempC", "?")
            hourly = day.get("hourly", [])
            mid = hourly[len(hourly) // 2] if hourly else {}
            day_desc = (mid.get("weatherDesc") or [{}])[0].get("value", "")[:14]

            draw.text((cx, y),      day_label,        font=font_body,  fill=COLOR_BLACK)
            draw.text((cx, y + 28), f"{mx}° / {mn}°", font=font_bold,  fill=COLOR_BLUE)
            draw.text((cx, y + 58), day_desc,          font=font_small, fill=COLOR_MUTED)

        return img

    def get_state(self) -> ModeState:
        cond = {}
        if self._last_data:
            cond = (self._last_data.get("current_condition") or [{}])[0]
        return ModeState(
            mode="weather",
            extra={
                "location": self._location,
                "temp_c": cond.get("temp_C"),
                "desc": (cond.get("weatherDesc") or [{}])[0].get("value"),
            },
        )
