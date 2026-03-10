"""Tests for WikipediaMode."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image


def _make_config():
    from talevision.config.loader import load_config
    return load_config(Path("config.yaml"))


def test_fetch_article_returns_title_and_extract():
    """_fetch_article() returns dict with title, extract, and content_urls."""
    payload = {
        "title": "Test",
        "extract": "Some text.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Test"}},
    }
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(payload).encode()
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=fake_response):
        from talevision.modes.wikipedia import _fetch_article
        result = _fetch_article("en", timeout=5)

    assert result["title"] == "Test"
    assert result["extract"] == "Some text."
    assert "content_urls" in result


def test_render_returns_correct_size():
    """WikipediaMode.render() returns an 800x480 RGB image (no thumbnail)."""
    cfg = _make_config()
    from talevision.modes.wikipedia import WikipediaMode
    mode = WikipediaMode(cfg, base_dir=Path("."))

    fake_article = {
        "title": "Roma",
        "extract": "Roma e la capitale d'Italia.",
        "content_urls": {"desktop": {"page": "https://it.wikipedia.org/wiki/Roma"}},
        "lang": "it",
    }
    with patch("talevision.modes.wikipedia._fetch_article", return_value=fake_article):
        with patch("talevision.modes.wikipedia._fetch_thumbnail", return_value=None):
            img = mode.render()

    assert isinstance(img, Image.Image)
    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_render_with_thumbnail():
    """WikipediaMode.render() composites thumbnail when available."""
    cfg = _make_config()
    from talevision.modes.wikipedia import WikipediaMode
    mode = WikipediaMode(cfg, base_dir=Path("."))

    fake_thumb = Image.new("RGB", (200, 150), (128, 0, 0))
    fake_article = {
        "title": "Roma",
        "extract": "Roma e la capitale d'Italia.",
        "content_urls": {"desktop": {"page": "https://it.wikipedia.org/wiki/Roma"}},
        "thumbnail": {"source": "https://example.com/img.jpg", "width": 200, "height": 150},
        "lang": "it",
    }
    with patch("talevision.modes.wikipedia._fetch_article", return_value=fake_article):
        with patch("talevision.modes.wikipedia._fetch_thumbnail", return_value=fake_thumb):
            img = mode.render()

    assert img.size == (800, 480)


def test_set_language_updates_state():
    """set_language() changes the active language."""
    cfg = _make_config()
    from talevision.modes.wikipedia import WikipediaMode
    mode = WikipediaMode(cfg, base_dir=Path("."))
    mode.set_language("en")
    assert mode._language == "en"
