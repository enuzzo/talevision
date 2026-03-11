"""Tests for WeatherMode ANSI redesign."""
import re
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image


def _make_config():
    from talevision.config.loader import load_config
    return load_config(Path("config.yaml"))


# Sample ANSI output (minimal, simulates wttr.in structure)
FAKE_ANSI = (
    "\033[37mWeather report: Roma\033[0m\n"
    "\n"
    "     \\  /       \033[1;33mPartly cloudy\033[0m\n"
    "   _ /\"\".-.     \033[1;33m+18(16) °C\033[0m\n"
    "     \\_(   ).   \033[32m↗ 15 km/h\033[0m\n"
)


def test_parse_ansi_extracts_chars_and_colors():
    from talevision.modes.weather import _parse_ansi
    cells = _parse_ansi(FAKE_ANSI)
    assert len(cells) >= 3
    first_line_text = "".join(ch for ch, _, _ in cells[0])
    assert "Weather report" in first_line_text


def test_parse_ansi_maps_colors():
    from talevision.modes.weather import _parse_ansi
    cells = _parse_ansi(FAKE_ANSI)
    line2_colors = set(color for _, color, _ in cells[2] if color != (0, 0, 0))
    assert (255, 165, 0) in line2_colors


def test_parse_ansi_bold_flag():
    from talevision.modes.weather import _parse_ansi
    cells = _parse_ansi(FAKE_ANSI)
    bold_chars = [(ch, bold) for ch, _, bold in cells[2] if bold]
    assert len(bold_chars) > 0


def test_render_returns_correct_size():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))

    with patch("talevision.modes.weather._fetch_ansi", return_value=FAKE_ANSI):
        img = mode.render()

    assert isinstance(img, Image.Image)
    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_render_white_background():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))

    with patch("talevision.modes.weather._fetch_ansi", return_value=FAKE_ANSI):
        img = mode.render()

    assert img.getpixel((0, 0)) == (255, 255, 255)


def test_set_location_updates_all_fields():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))
    mode.set_location("Milano", 45.4642, 9.1900)
    assert mode._city == "Milano"
    assert mode._lat == 45.4642
    assert mode._lon == 9.1900


def test_set_units():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))
    mode.set_units("u")
    assert mode._units == "u"


FAKE_ANSI_WITH_FORECAST = (
    "     \\  /       \033[1;33mPartly cloudy\033[0m\n"
    "   _ /\"\".-.     \033[1;33m+18(16) °C\033[0m\n"
    "     \\_(   ).   \033[32m↗ 15 km/h\033[0m\n"
    "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510\n"
    "\u2502   Morning    \u2502\n"
    "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518\n"
)


def test_find_forecast_start_with_box_drawing():
    from talevision.modes.weather import _parse_ansi, _find_forecast_start
    parsed = _parse_ansi(FAKE_ANSI_WITH_FORECAST)
    idx = _find_forecast_start(parsed)
    assert idx == 3


def test_find_forecast_start_no_forecast():
    from talevision.modes.weather import _parse_ansi, _find_forecast_start
    parsed = _parse_ansi(FAKE_ANSI)
    idx = _find_forecast_start(parsed)
    assert idx == len(parsed)


def test_render_two_zone_with_forecast():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))

    with patch("talevision.modes.weather._fetch_ansi", return_value=FAKE_ANSI_WITH_FORECAST):
        img = mode.render()

    assert isinstance(img, Image.Image)
    assert img.size == (800, 480)
