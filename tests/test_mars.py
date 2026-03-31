"""Tests for Mars Rover Photos mode."""
import io
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image


def _make_config():
    from talevision.config.loader import load_config
    return load_config(Path("config.yaml"))


def _make_mode(tmp_path: Path):
    from talevision.modes.mars import MarsMode
    return MarsMode(_make_config(), base_dir=tmp_path, api_key="DEMO_KEY")


def _fake_photo(photo_id: int = 1234567, camera: str = "MAST",
                camera_full: str = "Mast Camera", sol: int = 4234) -> dict:
    return {
        "id": photo_id,
        "sol": sol,
        "camera": {"id": 20, "name": camera, "rover_id": 5, "full_name": camera_full},
        "img_src": "https://example.com/mars.jpg",
        "earth_date": "2026-03-31",
        "rover": {
            "id": 5, "name": "Curiosity",
            "landing_date": "2012-08-06", "launch_date": "2011-11-26",
            "status": "active", "max_sol": 4234,
            "max_date": "2026-03-31", "total_photos": 695423,
        },
    }


def _fake_image() -> Image.Image:
    return Image.new("RGB", (1024, 768), (120, 60, 30))


# ── Utility ───────────────────────────────────────────────────────────────────

def test_camera_score_ordering():
    from talevision.modes.mars import _camera_score
    assert _camera_score("MAST") < _camera_score("NAVCAM")
    assert _camera_score("NAVCAM") < _camera_score("FHAZ")
    assert _camera_score("FHAZ") < _camera_score("UNKNOWN_CAM")


def test_fmt_date():
    from talevision.modes.mars import _fmt_date
    assert _fmt_date("2026-03-31") == "31 March 2026"


def test_fmt_count():
    from talevision.modes.mars import _fmt_count
    assert _fmt_count(695423) == "695,423"


# ── Render ────────────────────────────────────────────────────────────────────

def test_render_returns_correct_size(tmp_path):
    mode   = _make_mode(tmp_path)
    photos = [_fake_photo()]

    with patch.object(mode, "_fetch_latest_photos", return_value=photos), \
         patch.object(mode, "_fetch_image", return_value=_fake_image()):
        img = mode.render()

    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_render_uses_cached_photos(tmp_path):
    mode   = _make_mode(tmp_path)
    photos = [_fake_photo()]
    from datetime import date
    mode._save_cached_photos(photos, date.today().isoformat(), "curiosity")

    with patch.object(mode, "_fetch_latest_photos") as mock_fetch, \
         patch.object(mode, "_fetch_image", return_value=_fake_image()):
        mode.render()
        mock_fetch.assert_not_called()


def test_render_error_when_no_photos(tmp_path):
    mode = _make_mode(tmp_path)

    with patch.object(mode, "_fetch_latest_photos", return_value=[]):
        img = mode.render()

    assert img.size == (800, 480)


def test_render_falls_back_to_alt_photo(tmp_path):
    mode = _make_mode(tmp_path)
    photos = [_fake_photo(photo_id=111), _fake_photo(photo_id=222, camera="NAVCAM")]

    def fetch_image_side_effect(url):
        # Fail first call, succeed second
        fetch_image_side_effect.calls = getattr(fetch_image_side_effect, "calls", 0) + 1
        if fetch_image_side_effect.calls == 1:
            return None
        return _fake_image()

    with patch.object(mode, "_fetch_latest_photos", return_value=photos), \
         patch.object(mode, "_fetch_image", side_effect=fetch_image_side_effect):
        img = mode.render()

    assert img.size == (800, 480)


def test_render_uses_stale_image_cache_on_network_failure(tmp_path):
    mode = _make_mode(tmp_path)
    # Pre-populate stale image cache
    _fake_image().save(str(mode._image_cache), format="JPEG")
    photos = [_fake_photo()]

    with patch.object(mode, "_fetch_latest_photos", return_value=photos), \
         patch.object(mode, "_fetch_image", return_value=None):
        img = mode.render()

    assert img.size == (800, 480)


# ── Cache ─────────────────────────────────────────────────────────────────────

def test_photos_cache_roundtrip(tmp_path):
    mode   = _make_mode(tmp_path)
    photos = [_fake_photo()]
    from datetime import date
    today = date.today().isoformat()
    mode._save_cached_photos(photos, today, "curiosity")

    loaded = mode._load_cached_photos(today, "curiosity")
    assert len(loaded) == 1
    assert loaded[0]["id"] == 1234567


def test_photos_cache_rover_mismatch(tmp_path):
    mode   = _make_mode(tmp_path)
    photos = [_fake_photo()]
    from datetime import date
    today = date.today().isoformat()
    mode._save_cached_photos(photos, today, "curiosity")

    loaded = mode._load_cached_photos(today, "perseverance")
    assert loaded == []


# ── get_state ─────────────────────────────────────────────────────────────────

def test_get_state(tmp_path):
    mode   = _make_mode(tmp_path)
    photos = [_fake_photo()]

    with patch.object(mode, "_fetch_latest_photos", return_value=photos), \
         patch.object(mode, "_fetch_image", return_value=_fake_image()):
        mode.render()

    state = mode.get_state()
    assert state.mode == "mars"
    assert state.extra["rover"] == "Curiosity"
    assert state.extra["sol"] == 4234
    assert state.extra["photo_id"] == 1234567
    assert state.extra["total_photos"] == 695423
