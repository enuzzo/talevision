"""Tests for SlowMovieMode random video re-selection."""
import json
from pathlib import Path

from talevision.config.loader import load_config


def test_select_video_random_picks_multiple(tmp_path):
    """When video_file='random', _select_video() should pick different movies
    across multiple calls without manual reset of _current_video."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    names = [f"movie_{i}.mp4" for i in range(5)]
    for name in names:
        (media_dir / name).write_bytes(b"\x00" * 1024)
        sidecar = media_dir / name.replace(".mp4", ".json")
        sidecar.write_text(json.dumps({"title": name}))

    cfg = load_config(Path("config.yaml"))
    cfg.slowmovie.media_dir = "media"
    cfg.slowmovie.video_file = "random"
    cfg.slowmovie.cache_file = "cache/video_info_cache.json"

    from talevision.modes.slowmovie import SlowMovieMode
    mode = SlowMovieMode(cfg, base_dir=tmp_path)

    picked = set()
    for _ in range(20):
        v = mode._select_video()
        assert v is not None
        picked.add(v.name)

    assert len(picked) >= 2, f"Expected at least 2 unique movies, got {picked}"


def test_select_video_named_file_caches(tmp_path):
    """When video_file is a specific filename, _select_video() should cache it."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    for i in range(3):
        (media_dir / f"movie_{i}.mp4").write_bytes(b"\x00" * 1024)

    cfg = load_config(Path("config.yaml"))
    cfg.slowmovie.media_dir = "media"
    cfg.slowmovie.video_file = "movie_1.mp4"
    cfg.slowmovie.cache_file = "cache/video_info_cache.json"

    from talevision.modes.slowmovie import SlowMovieMode
    mode = SlowMovieMode(cfg, base_dir=tmp_path)

    picks = [mode._select_video() for _ in range(10)]
    assert all(p.name == "movie_1.mp4" for p in picks)


def test_select_video_single_movie_no_crash(tmp_path):
    """With only 1 movie and video_file='random', should work without errors."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    (media_dir / "only_movie.mp4").write_bytes(b"\x00" * 1024)

    cfg = load_config(Path("config.yaml"))
    cfg.slowmovie.media_dir = "media"
    cfg.slowmovie.video_file = "random"
    cfg.slowmovie.cache_file = "cache/video_info_cache.json"

    from talevision.modes.slowmovie import SlowMovieMode
    mode = SlowMovieMode(cfg, base_dir=tmp_path)

    for _ in range(5):
        v = mode._select_video()
        assert v is not None
        assert v.name == "only_movie.mp4"
