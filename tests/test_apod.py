"""Tests for APOD mode — cache, rendering, fallbacks."""
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image


def _make_config():
    from talevision.config.loader import load_config
    return load_config(Path("config.yaml"))


def _make_mode(tmp_path: Path, api_key: str = "DEMO_KEY"):
    from talevision.modes.apod import APODMode
    return APODMode(_make_config(), base_dir=tmp_path, api_key=api_key)


def _fake_image_bytes(w: int = 400, h: int = 300) -> bytes:
    img = Image.new("RGB", (w, h), (20, 20, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _fake_apod_data(media_type: str = "image") -> dict:
    return {
        "date": "2026-03-31",
        "title": "A Distant Galaxy",
        "explanation": "This is a beautiful galaxy far away. It contains billions of stars.",
        "url": "https://example.com/apod.jpg",
        "hdurl": "https://example.com/apod_hd.jpg",
        "media_type": media_type,
        "copyright": "NASA/ESA",
    }


# ── Utility ───────────────────────────────────────────────────────────────────

def test_first_sentence_with_period():
    from talevision.modes.apod import _first_sentence
    text = "First sentence. Second sentence is here. Third."
    result = _first_sentence(text, max_chars=160)
    assert result == "First sentence."


def test_first_sentence_short_text():
    from talevision.modes.apod import _first_sentence
    text = "Short text without period"
    assert _first_sentence(text, max_chars=160) == text


def test_first_sentence_truncates_long():
    from talevision.modes.apod import _first_sentence
    text = "a " * 100  # no period, very long
    result = _first_sentence(text, max_chars=40)
    assert len(result) <= 43  # max_chars + "…"
    assert result.endswith("…")


# ── Render with mocked network ────────────────────────────────────────────────

def test_render_returns_correct_size(tmp_path):
    mode = _make_mode(tmp_path)
    fake_data = _fake_apod_data()
    fake_img_bytes = _fake_image_bytes()

    with patch.object(mode, "_fetch_apod_data", return_value=fake_data), \
         patch.object(mode, "_fetch_image", return_value=Image.open(io.BytesIO(fake_img_bytes)).convert("RGB")):
        img = mode.render()

    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_render_uses_cache(tmp_path):
    mode = _make_mode(tmp_path)
    fake_data = _fake_apod_data()

    # Pre-populate cache
    mode._save_cached_data(fake_data)
    fake_img = Image.new("RGB", (400, 300), (20, 20, 60))
    fake_img.save(str(mode._image_cache), format="JPEG", quality=90)

    with patch.object(mode, "_fetch_apod_data") as mock_fetch:
        img = mode.render()
        mock_fetch.assert_not_called()

    assert img.size == (800, 480)


def test_render_video_fallback(tmp_path):
    mode = _make_mode(tmp_path)
    fake_data = _fake_apod_data(media_type="video")

    with patch.object(mode, "_fetch_apod_data", return_value=fake_data):
        img = mode.render()

    assert img.size == (800, 480)


def test_render_error_when_no_data(tmp_path):
    mode = _make_mode(tmp_path)

    with patch.object(mode, "_fetch_apod_data", return_value=None):
        img = mode.render()

    assert img.size == (800, 480)


def test_render_error_when_image_fetch_fails(tmp_path):
    mode = _make_mode(tmp_path)
    fake_data = _fake_apod_data()

    with patch.object(mode, "_fetch_apod_data", return_value=fake_data), \
         patch.object(mode, "_fetch_image", return_value=None):
        img = mode.render()

    assert img.size == (800, 480)


# ── Cache ─────────────────────────────────────────────────────────────────────

def test_cache_roundtrip(tmp_path):
    mode = _make_mode(tmp_path)
    fake_data = _fake_apod_data()
    mode._save_cached_data(fake_data)

    from datetime import date
    loaded = mode._load_cached_data(date.today().isoformat())
    assert loaded is not None
    assert loaded["title"] == "A Distant Galaxy"
    assert loaded["date"] == "2026-03-31"


def test_stale_cache_returns_none(tmp_path):
    mode = _make_mode(tmp_path)
    fake_data = _fake_apod_data()
    mode._save_cached_data(fake_data)

    loaded = mode._load_cached_data("2020-01-01")
    assert loaded is None


# ── get_state ─────────────────────────────────────────────────────────────────

def test_get_state(tmp_path):
    mode = _make_mode(tmp_path)
    fake_data = _fake_apod_data()

    with patch.object(mode, "_fetch_apod_data", return_value=fake_data), \
         patch.object(mode, "_fetch_image", return_value=Image.new("RGB", (400, 300), (0, 0, 0))):
        mode.render()

    state = mode.get_state()
    assert state.mode == "apod"
    assert state.extra["title"] == "A Distant Galaxy"
    assert state.extra["media_type"] == "image"
