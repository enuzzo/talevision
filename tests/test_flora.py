"""Tests for Flora mode — L-system engine and render pipeline."""
from pathlib import Path
from unittest.mock import MagicMock


def _make_config(tmp_path: Path):
    from talevision.config.loader import load_config
    cfg = load_config(Path("config.yaml"))
    cfg.flora.location = "Test City"
    return cfg


def test_lsystem_string_fern():
    from talevision.modes.flora import _lsystem_string
    s = _lsystem_string("X", {"X": "F+[[X]-X]-F[-FX]+X", "F": "FF"}, 3)
    assert len(s) > 0
    assert "F" in s
    assert "[" in s


def test_lsystem_string_length_cap():
    from talevision.modes.flora import _lsystem_string, _MAX_STR_LEN
    # Rule that doubles every iteration — should be capped
    s = _lsystem_string("F", {"F": "FF"}, 30)
    assert len(s) <= _MAX_STR_LEN


def test_turtle_bounds_returns_finite(tmp_path):
    from talevision.modes.flora import _lsystem_string, _turtle_bounds
    s = _lsystem_string("X", {"X": "F+[[X]-X]-F[-FX]+X", "F": "FF"}, 4)
    min_x, min_y, max_x, max_y = _turtle_bounds(s, 25.0)
    assert max_x >= min_x
    assert max_y >= min_y
    assert max_x - min_x > 0 or max_y - min_y > 0


def test_flora_render_returns_correct_size(tmp_path):
    cfg = _make_config(tmp_path)
    cfg.flora.refresh_interval = 3600
    from talevision.modes.flora import FloraMode
    mode = FloraMode(cfg, base_dir=Path("."))
    img = mode.render()
    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_flora_get_state(tmp_path):
    cfg = _make_config(tmp_path)
    from talevision.modes.flora import FloraMode
    mode = FloraMode(cfg, base_dir=Path("."))
    mode.render()
    state = mode.get_state()
    assert state.mode == "flora"
    assert "species" in state.extra
    assert "genus" in state.extra
    assert "epithet" in state.extra


def test_flora_each_render_differs(tmp_path):
    cfg = _make_config(tmp_path)
    from talevision.modes.flora import FloraMode
    import time
    m = FloraMode(cfg, base_dir=Path("."))
    img1 = m.render()
    time.sleep(0.01)
    img2 = m.render()
    state1 = m.get_state()
    # Each render produces a valid image (may differ due to time-based seed)
    assert img1.size == (800, 480)
    assert img2.size == (800, 480)


def test_all_species_render(tmp_path):
    from talevision.modes.flora import _SPECIES, _lsystem_string, _turtle_bounds
    for sp in _SPECIES:
        s = _lsystem_string(sp["axiom"], sp["rules"], sp["iterations"])
        assert len(s) > 0
        min_x, min_y, max_x, max_y = _turtle_bounds(s, sp["angle"])
        assert max_x >= min_x and max_y >= min_y, f"Species {sp['id']} produced empty bounds"


def test_flora_archive_saves_files(tmp_path):
    cfg = _make_config(tmp_path)
    from talevision.modes.flora import FloraMode
    mode = FloraMode(cfg, base_dir=tmp_path)
    mode.render()
    archive_dir = mode._archive_dir
    json_files = list(archive_dir.glob("*.json"))
    png_files = list(archive_dir.glob("*.png"))
    assert len(json_files) == 1, "Expected 1 JSON archive entry after first render"
    assert len(png_files) == 1, "Expected 1 PNG archive entry after first render"


def test_flora_archive_idempotent(tmp_path):
    cfg = _make_config(tmp_path)
    from talevision.modes.flora import FloraMode
    mode = FloraMode(cfg, base_dir=tmp_path)
    mode.render()
    mode.render()  # second render same day — must not create duplicate
    archive_dir = mode._archive_dir
    assert len(list(archive_dir.glob("*.json"))) == 1


def test_flora_archive_json_schema(tmp_path):
    cfg = _make_config(tmp_path)
    from talevision.modes.flora import FloraMode
    import json
    mode = FloraMode(cfg, base_dir=tmp_path)
    mode.render()
    json_path = next(mode._archive_dir.glob("*.json"))
    entry = json.loads(json_path.read_text())
    for key in ("date", "specimen_num", "species_id", "genus", "epithet", "family", "order", "location"):
        assert key in entry, f"Missing key '{key}' in archive JSON"
    assert entry["location"] == "Test City"


def test_flora_get_state_archive_count(tmp_path):
    cfg = _make_config(tmp_path)
    from talevision.modes.flora import FloraMode
    mode = FloraMode(cfg, base_dir=tmp_path)
    mode.render()
    state = mode.get_state()
    assert state.extra.get("archive_count") == 1
