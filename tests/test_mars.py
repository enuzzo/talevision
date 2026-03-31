"""Tests for Mars Rover Photos mode (JPL API)."""
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


def _fake_photo(photo_id: int = 1234567, instrument: str = "MAST_RIGHT",
                sol: int = 4234) -> dict:
    return {
        "id": photo_id,
        "sol": sol,
        "instrument": instrument,
        "title": f"Sol {sol}: Mast Camera (Mastcam)",
        "https_url": "https://example.com/mars.jpg",
        "date_taken":    "2026-03-31T10:00:00.000Z",
        "date_received": "2026-03-31T23:00:00.000Z",
        "image_credit": "NASA/JPL-Caltech/MSSS",
        "mission": "msl",
        "_total": 1444379,
    }


def _fake_image() -> Image.Image:
    return Image.new("RGB", (1024, 768), (120, 60, 30))


# ── Utility ───────────────────────────────────────────────────────────────────

def test_camera_score_ordering():
    from talevision.modes.mars import _camera_score
    assert _camera_score("MAST_RIGHT") < _camera_score("NAV_LEFT_B")
    assert _camera_score("NAV_LEFT_B") < _camera_score("FHAZ_LEFT_B")
    assert _camera_score("FHAZ_LEFT_B") < _camera_score("UNKNOWN_CAM")


def test_fmt_date_iso_datetime():
    from talevision.modes.mars import _fmt_date
    assert _fmt_date("2026-03-31T23:00:00.000Z") == "31 March 2026"


def test_fmt_date_date_only():
    from talevision.modes.mars import _fmt_date
    assert _fmt_date("2026-03-31") == "31 March 2026"


def test_fmt_count():
    from talevision.modes.mars import _fmt_count
    assert _fmt_count(1444379) == "1,444,379"


def test_camera_full_name():
    from talevision.modes.mars import _camera_full_name
    photo = {"title": "Sol 4234: Mast Camera (Mastcam)", "instrument": "MAST_RIGHT"}
    assert _camera_full_name(photo) == "Mast Camera (Mastcam)"


def test_camera_full_name_fallback():
    from talevision.modes.mars import _camera_full_name
    photo = {"title": "", "instrument": "MAST_RIGHT"}
    assert _camera_full_name(photo) == "MAST_RIGHT"


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
    mode._save_cached_photos(photos, date.today().isoformat())

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
    photos = [_fake_photo(photo_id=111), _fake_photo(photo_id=222, instrument="NAV_LEFT_B")]

    def fetch_image_side_effect(url):
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
    mode._save_cached_photos(photos, today)

    loaded = mode._load_cached_photos(today)
    assert len(loaded) == 1
    assert loaded[0]["id"] == 1234567


def test_photos_cache_stale_returns_empty(tmp_path):
    mode   = _make_mode(tmp_path)
    photos = [_fake_photo()]
    mode._save_cached_photos(photos, "2026-03-30")

    loaded = mode._load_cached_photos("2026-03-31")
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
    assert state.extra["total_photos"] == 1444379
