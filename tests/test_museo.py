"""Tests for Museo mode — provider normalisation and cache."""
import json
from pathlib import Path


def test_met_normalize_artwork():
    from talevision.modes.museo_providers.met import MetProvider
    p = MetProvider()
    raw = {
        "objectID": 45734,
        "title": "The Starry Night",
        "artistDisplayName": "Vincent van Gogh",
        "objectDate": "1889",
        "department": "European Paintings",
        "primaryImageSmall": "https://images.metmuseum.org/example.jpg",
        "objectURL": "https://www.metmuseum.org/art/collection/search/45734",
    }
    info = p._normalize(raw)
    assert info.title == "The Starry Night"
    assert info.artist == "Vincent van Gogh"
    assert info.museum == "The Met"
    assert info.image_url == "https://images.metmuseum.org/example.jpg"
    assert info.provider == "met"


def test_cleveland_normalize_artwork():
    from talevision.modes.museo_providers.cleveland import ClevelandProvider
    p = ClevelandProvider()
    raw = {
        "id": 129541,
        "title": "Twilight in the Wilderness",
        "creators": [{"description": "Frederic Edwin Church (American, 1826-1900)"}],
        "creation_date": "1860",
        "collection": "American Painting and Sculpture",
        "images": {"web": {"url": "https://openaccess-cdn.clevelandart.org/example.jpg"}},
        "url": "https://www.clevelandart.org/art/1965.233",
    }
    info = p._normalize(raw)
    assert info.title == "Twilight in the Wilderness"
    assert info.artist == "Frederic Edwin Church (American, 1826-1900)"
    assert info.museum == "Cleveland Museum of Art"
    assert info.provider == "cleveland"


def test_museo_cache_needs_refresh_missing(tmp_path):
    from talevision.modes.museo_cache import MuseoCache
    cache = MuseoCache(cache_dir=tmp_path, max_age=86400)
    assert cache.needs_refresh("met") is True


def test_museo_cache_needs_refresh_fresh(tmp_path):
    from talevision.modes.museo_cache import MuseoCache
    cache = MuseoCache(cache_dir=tmp_path, max_age=86400)
    cache.save("met", {"objectIDs": [1, 2, 3]})
    assert cache.needs_refresh("met") is False


def test_museo_cache_load_roundtrip(tmp_path):
    from talevision.modes.museo_cache import MuseoCache
    cache = MuseoCache(cache_dir=tmp_path, max_age=86400)
    cache.save("met", {"objectIDs": [10, 20, 30]})
    data = cache.load("met")
    assert data["objectIDs"] == [10, 20, 30]
