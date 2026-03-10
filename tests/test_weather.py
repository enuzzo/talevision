"""Tests for WeatherMode."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image


def _make_config():
    from talevision.config.loader import load_config
    return load_config(Path("config.yaml"))


FAKE_WTTR = {
    "current_condition": [{
        "temp_C": "18",
        "FeelsLikeC": "16",
        "weatherDesc": [{"value": "Partly cloudy"}],
        "windspeedKmph": "15",
        "humidity": "60",
    }],
    "weather": [
        {
            "date": "2026-03-10",
            "maxtempC": "20",
            "mintempC": "12",
            "hourly": [{"weatherDesc": [{"value": "Sunny"}]}],
        },
        {
            "date": "2026-03-11",
            "maxtempC": "17",
            "mintempC": "10",
            "hourly": [{"weatherDesc": [{"value": "Cloudy"}]}],
        },
        {
            "date": "2026-03-12",
            "maxtempC": "15",
            "mintempC": "9",
            "hourly": [{"weatherDesc": [{"value": "Rain"}]}],
        },
    ],
    "nearest_area": [{"areaName": [{"value": "Rome"}], "country": [{"value": "Italy"}]}],
}


def test_fetch_weather_returns_structured_data():
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps(FAKE_WTTR).encode()
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=fake_resp):
        from talevision.modes.weather import _fetch_weather
        result = _fetch_weather("Roma", timeout=5)

    assert result["current_condition"][0]["temp_C"] == "18"
    assert len(result["weather"]) == 3


def test_render_returns_correct_size():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))

    with patch("talevision.modes.weather._fetch_weather", return_value=FAKE_WTTR):
        img = mode.render()

    assert isinstance(img, Image.Image)
    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_set_location_updates_config():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))
    mode.set_location("Milano")
    assert mode._location == "Milano"
