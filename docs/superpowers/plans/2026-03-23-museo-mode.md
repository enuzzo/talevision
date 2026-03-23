# Museo Mode Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Museo display mode that shows random public-domain artworks from 3 museum APIs (Met, AIC, Cleveland) as full-bleed images with overlay metadata on the 800x480 e-ink display.

**Architecture:** Three museum providers behind an ABC, cycling round-robin. Each render fetches a random artwork, cover-crops to 800x480, applies PIL enhancement, draws an overlay (title/artist/date/museum/QR) matching SlowMovie's pattern. Caches catalogue data locally with 24h refresh.

**Tech Stack:** Python 3.11, Pillow, urllib.request, qrcode, existing DisplayMode ABC + AppConfig dataclass pattern.

**Spec:** `docs/superpowers/specs/2026-03-23-museo-mode.md`

---

## File Structure

```
talevision/modes/
    museo.py                    # MuseoMode class — render pipeline, round-robin, overlay
    museo_cache.py              # MuseoCache — file-based cache with 24h TTL
    museo_providers/
        __init__.py             # PROVIDERS list + re-exports
        base.py                 # MuseoProvider ABC + normalised ArtworkInfo dataclass
        met.py                  # MetProvider
        aic.py                  # AICProvider
        cleveland.py            # ClevelandProvider
talevision/config/schema.py    # Add MuseoFontsConfig, MuseoConfig, wire into AppConfig
config.yaml                    # Add museo section
main.py                        # Register MuseoMode
tests/test_museo.py            # Unit tests
```

---

## Task 0: Config schema + config.yaml

**Files:**
- Modify: `talevision/config/schema.py`
- Modify: `config.yaml`

- [ ] **Step 1: Add MuseoFontsConfig and MuseoConfig to schema.py**

Add before `AppConfig`:

```python
@dataclass
class MuseoFontsConfig:
    dir: str = "assets/fonts"
    bold: str = "Signika-Bold.ttf"
    light: str = "Signika-Light.ttf"
    mono: str = "InconsolataNerdFontMono-Regular.ttf"


@dataclass
class MuseoConfig:
    refresh_interval: int = 300
    timeout: int = 60
    cache_max_age: int = 86400
    brightness: float = 1.1
    contrast: float = 1.2
    color: float = 1.3
    overlay: OverlayConfig = field(default_factory=lambda: OverlayConfig(
        qr_content="museo_page",
    ))
    fonts: MuseoFontsConfig = field(default_factory=MuseoFontsConfig)
```

Add `museo: MuseoConfig = field(default_factory=MuseoConfig)` to `AppConfig`.

- [ ] **Step 2: Add museo section to config.yaml**

```yaml
museo:
  refresh_interval: 300
  timeout: 60
```

- [ ] **Step 3: Verify config loads**

Run: `python -c "from talevision.config.loader import load_config; from pathlib import Path; c = load_config(Path('config.yaml')); print(c.museo)"`
Expected: prints MuseoConfig with defaults.

- [ ] **Step 4: Commit**

```bash
git add talevision/config/schema.py config.yaml
git commit -m "config: add MuseoConfig schema and config.yaml section"
```

---

## Task 1: Provider ABC + ArtworkInfo dataclass

**Files:**
- Create: `talevision/modes/museo_providers/__init__.py`
- Create: `talevision/modes/museo_providers/base.py`

- [ ] **Step 1: Create base.py with ABC and ArtworkInfo**

```python
"""Abstract base for museum data providers."""
import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class ArtworkInfo:
    title: str
    artist: str
    date: str
    department: str
    museum: str
    image_url: str
    object_url: str
    provider: str
    artwork_id: str


class MuseoProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def museum_display_name(self) -> str: ...

    @abc.abstractmethod
    def fetch_catalogue_meta(self, timeout: int = 30) -> dict: ...

    @abc.abstractmethod
    def pick_random_id(self, cache_data: dict) -> str: ...

    @abc.abstractmethod
    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]: ...
```

- [ ] **Step 2: Create __init__.py**

```python
from .base import MuseoProvider, ArtworkInfo
from .met import MetProvider
from .aic import AICProvider
from .cleveland import ClevelandProvider

PROVIDERS = [MetProvider(), AICProvider(), ClevelandProvider()]
```

(This will fail until we create the 3 provider files — that's fine, we import lazily.)

- [ ] **Step 3: Commit**

```bash
git add talevision/modes/museo_providers/
git commit -m "museo: add provider ABC and ArtworkInfo dataclass"
```

---

## Task 2: Met provider

**Files:**
- Create: `talevision/modes/museo_providers/met.py`
- Create: `tests/test_museo.py`

- [ ] **Step 1: Write test for Met provider normalisation**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_museo.py::test_met_normalize_artwork -v`

- [ ] **Step 3: Implement MetProvider**

```python
"""Metropolitan Museum of Art provider."""
import json
import logging
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://collectionapi.metmuseum.org/public/collection/v1"


class MetProvider(MuseoProvider):
    @property
    def name(self) -> str:
        return "met"

    @property
    def museum_display_name(self) -> str:
        return "The Met"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        url = f"{_API}/search?hasImages=true&isPublicDomain=true&q=*"
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"objectIDs": data.get("objectIDs", [])}

    def pick_random_id(self, cache_data: dict) -> str:
        ids = cache_data.get("objectIDs", [])
        if not ids:
            raise RuntimeError("Met cache is empty")
        return str(random.choice(ids))

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        url = f"{_API}/objects/{artwork_id}"
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"Met fetch failed for {artwork_id}: {exc}")
            return None
        img = raw.get("primaryImageSmall", "")
        if not img:
            return None
        return self._normalize(raw)

    def _normalize(self, raw: dict) -> ArtworkInfo:
        return ArtworkInfo(
            title=raw.get("title", "Untitled"),
            artist=raw.get("artistDisplayName", "Unknown"),
            date=raw.get("objectDate", ""),
            department=raw.get("department", ""),
            museum="The Met",
            image_url=raw.get("primaryImageSmall", ""),
            object_url=raw.get("objectURL", ""),
            provider="met",
            artwork_id=str(raw.get("objectID", "")),
        )
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_museo.py::test_met_normalize_artwork -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add talevision/modes/museo_providers/met.py tests/test_museo.py
git commit -m "museo: implement Met provider with normalisation"
```

---

## Task 3: AIC provider

**Files:**
- Create: `talevision/modes/museo_providers/aic.py`
- Modify: `tests/test_museo.py`

- [ ] **Step 1: Write test for AIC normalisation (artist cleanup)**

```python
def test_aic_normalize_strips_biography():
    from talevision.modes.museo_providers.aic import AICProvider
    p = AICProvider()
    raw = {
        "id": 28560,
        "title": "Composition VII",
        "artist_display": "Vasily Kandinsky\nBorn Moscow, 1866; died France, 1944",
        "date_display": "1913",
        "image_id": "abc123",
        "department_title": "Modern Art",
    }
    info = p._normalize(raw)
    assert info.artist == "Vasily Kandinsky"
    assert "\n" not in info.artist
    assert info.image_url == "https://www.artic.edu/iiif/2/abc123/full/843,/0/default.jpg"
    assert info.provider == "aic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_museo.py::test_aic_normalize_strips_biography -v`

- [ ] **Step 3: Implement AICProvider**

```python
"""Art Institute of Chicago provider."""
import json
import logging
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://api.artic.edu/api/v1"
_IIIF = "https://www.artic.edu/iiif/2"
_FIELDS = "id,title,artist_display,date_display,image_id,department_title"
_BATCH_PAGES = 100
_BATCH_LIMIT = 100


class AICProvider(MuseoProvider):
    @property
    def name(self) -> str:
        return "aic"

    @property
    def museum_display_name(self) -> str:
        return "Art Institute of Chicago"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        ids = []
        for page in range(1, _BATCH_PAGES + 1):
            url = (f"{_API}/artworks/search"
                   f"?query[term][is_public_domain]=true"
                   f"&limit={_BATCH_LIMIT}&page={page}&fields=id")
            req = urllib.request.Request(url, headers=_UA)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                batch = [str(item["id"]) for item in data.get("data", [])]
                ids.extend(batch)
                if len(batch) < _BATCH_LIMIT:
                    break
            except Exception as exc:
                log.warning(f"AIC catalogue page {page} failed: {exc}")
                break
        log.info(f"AIC catalogue: cached {len(ids)} IDs")
        return {"ids": ids}

    def pick_random_id(self, cache_data: dict) -> str:
        ids = cache_data.get("ids", [])
        if not ids:
            raise RuntimeError("AIC cache is empty")
        return random.choice(ids)

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        url = f"{_API}/artworks/{artwork_id}?fields={_FIELDS}"
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"AIC fetch failed for {artwork_id}: {exc}")
            return None
        raw = data.get("data", {})
        if not raw.get("image_id"):
            return None
        return self._normalize(raw)

    def _normalize(self, raw: dict) -> ArtworkInfo:
        artist = raw.get("artist_display", "Unknown")
        if "\n" in artist:
            artist = artist.split("\n")[0].strip()
        image_id = raw.get("image_id", "")
        return ArtworkInfo(
            title=raw.get("title", "Untitled"),
            artist=artist,
            date=raw.get("date_display", ""),
            department=raw.get("department_title", ""),
            museum="Art Institute of Chicago",
            image_url=f"{_IIIF}/{image_id}/full/843,/0/default.jpg" if image_id else "",
            object_url=f"https://www.artic.edu/artworks/{raw.get('id', '')}",
            provider="aic",
            artwork_id=str(raw.get("id", "")),
        )
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_museo.py::test_aic_normalize_strips_biography -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add talevision/modes/museo_providers/aic.py tests/test_museo.py
git commit -m "museo: implement AIC provider with artist biography cleanup"
```

---

## Task 4: Cleveland provider

**Files:**
- Create: `talevision/modes/museo_providers/cleveland.py`
- Modify: `tests/test_museo.py`

- [ ] **Step 1: Write test for Cleveland normalisation**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_museo.py::test_cleveland_normalize_artwork -v`

- [ ] **Step 3: Implement ClevelandProvider**

```python
"""Cleveland Museum of Art provider."""
import json
import logging
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://openaccess-api.clevelandart.org/api/artworks"


class ClevelandProvider(MuseoProvider):
    @property
    def name(self) -> str:
        return "cleveland"

    @property
    def museum_display_name(self) -> str:
        return "Cleveland Museum of Art"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        url = f"{_API}/?has_image=1&cc0=1&limit=1"
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("info", {}).get("total", 0)
        log.info(f"Cleveland catalogue: {total} artworks")
        return {"total": total}

    def pick_random_id(self, cache_data: dict) -> str:
        total = cache_data.get("total", 0)
        if total == 0:
            raise RuntimeError("Cleveland cache is empty")
        return str(random.randint(0, total - 1))

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        skip = int(artwork_id)
        url = f"{_API}/?has_image=1&cc0=1&limit=1&skip={skip}"
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"Cleveland fetch failed at skip={skip}: {exc}")
            return None
        items = data.get("data", [])
        if not items:
            return None
        raw = items[0]
        img_url = (raw.get("images") or {}).get("web", {}).get("url", "")
        if not img_url:
            return None
        return self._normalize(raw)

    def _normalize(self, raw: dict) -> ArtworkInfo:
        creators = raw.get("creators", [])
        artist = creators[0].get("description", "Unknown") if creators else "Unknown"
        img_url = (raw.get("images") or {}).get("web", {}).get("url", "")
        return ArtworkInfo(
            title=raw.get("title", "Untitled"),
            artist=artist,
            date=raw.get("creation_date", ""),
            department=raw.get("collection", ""),
            museum="Cleveland Museum of Art",
            image_url=img_url,
            object_url=raw.get("url", ""),
            provider="cleveland",
            artwork_id=str(raw.get("id", "")),
        )
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_museo.py::test_cleveland_normalize_artwork -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add talevision/modes/museo_providers/cleveland.py tests/test_museo.py
git commit -m "museo: implement Cleveland provider"
```

---

## Task 5: Cache system

**Files:**
- Create: `talevision/modes/museo_cache.py`
- Modify: `tests/test_museo.py`

- [ ] **Step 1: Write cache tests**

```python
import time

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_museo.py -k cache -v`

- [ ] **Step 3: Implement MuseoCache**

```python
"""File-based cache for museum catalogue data with TTL."""
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class MuseoCache:
    def __init__(self, cache_dir: Path, max_age: int = 86400):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_age = max_age

    def _path(self, provider: str) -> Path:
        return self._dir / f"museo_{provider}.json"

    def needs_refresh(self, provider: str) -> bool:
        p = self._path(provider)
        if not p.exists():
            return True
        age = time.time() - os.path.getmtime(str(p))
        return age > self._max_age

    def save(self, provider: str, data: dict) -> None:
        p = self._path(provider)
        with open(str(p), "w", encoding="utf-8") as f:
            json.dump(data, f)
        log.info(f"Museo cache saved: {p.name}")

    def load(self, provider: str) -> Optional[dict]:
        p = self._path(provider)
        if not p.exists():
            return None
        try:
            with open(str(p), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning(f"Museo cache load failed for {provider}: {exc}")
            return None
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_museo.py -k cache -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add talevision/modes/museo_cache.py tests/test_museo.py
git commit -m "museo: implement file-based cache with TTL"
```

---

## Task 6: MuseoMode — main class with render pipeline

**Files:**
- Create: `talevision/modes/museo.py`

- [ ] **Step 1: Implement MuseoMode**

This is the core file. It implements:
- Round-robin provider cycling (`_provider_index`)
- Deduplication ring buffer (`_recent_ids`, deque maxlen=50)
- Cache management (refresh if stale before render)
- Artwork fetch with retry loop (up to 5 re-picks)
- Image download + PIL enhancement (Brightness/Contrast/Color)
- Full-bleed cover crop (`ImageOps.fit`)
- Overlay drawing (title/artist/date + museum/dept + QR) — same RGBA pattern as SlowMovie
- Warm fallback (last frame) + cold fallback (text screen)
- `get_state()` for dashboard

The complete file follows the patterns from `wikipedia.py` (constructor, font loading, render, get_state) and `slowmovie.py` (overlay drawing, QR generation, PIL enhancement).

Key implementation details:
- Constructor: `__init__(self, config: AppConfig, base_dir: Path)` — loads fonts, inits cache, inits provider list
- `_fetch_image(url, timeout)` — urllib download, returns PIL Image or None
- `_enhance(img)` — Brightness(1.1) → Contrast(1.2) → Color(1.3)
- `_draw_overlay(img, artwork)` — RGBA layer, rounded_rectangle, alpha_composite (same constants as SlowMovie: radius=8, fill=(0,0,0,190), pad=10)
- `_make_qr(url, size)` — same QR pattern as SlowMovie (white-on-transparent inside dark box)
- Title truncation: measure with `draw.textlength()`, truncate with ` ...` if > max width
- `_fallback_image()` — try warm (`cache/museo_last_frame.png`), else cold (Lobster text)
- After successful render: save frame to `cache/museo_last_frame.png`, timestamp to `cache/museo_last_success.txt` (ISO 8601)

- [ ] **Step 2: Commit**

```bash
git add talevision/modes/museo.py
git commit -m "museo: implement MuseoMode with render pipeline and overlay"
```

---

## Task 7: Wire into main.py + config.yaml + providers __init__

**Files:**
- Modify: `main.py`
- Modify: `config.yaml`
- Finalize: `talevision/modes/museo_providers/__init__.py`

- [ ] **Step 1: Update providers __init__.py**

Now that all 3 providers exist:

```python
from .base import MuseoProvider, ArtworkInfo
from .met import MetProvider
from .aic import AICProvider
from .cleveland import ClevelandProvider

PROVIDERS = [MetProvider(), AICProvider(), ClevelandProvider()]

__all__ = ["MuseoProvider", "ArtworkInfo", "PROVIDERS",
           "MetProvider", "AICProvider", "ClevelandProvider"]
```

- [ ] **Step 2: Register MuseoMode in main.py**

Add import and registration alongside existing modes:

```python
from talevision.modes.museo import MuseoMode

modes = {
    "litclock":  LitClockMode(config, base_dir=BASE_DIR),
    "slowmovie": SlowMovieMode(config, base_dir=BASE_DIR),
    "wikipedia": WikipediaMode(config, base_dir=BASE_DIR),
    "weather":   WeatherMode(config, base_dir=BASE_DIR),
    "museo":     MuseoMode(config, base_dir=BASE_DIR),
}
```

Update `--mode` help text to include `museo`.

- [ ] **Step 3: Verify config comment includes museo**

In `config.yaml` line 2: `# litclock | slowmovie | wikipedia | weather | museo`

- [ ] **Step 4: Commit**

```bash
git add main.py talevision/modes/museo_providers/__init__.py config.yaml
git commit -m "museo: register mode in main.py and finalize provider imports"
```

---

## Task 8: Smoke test — render-only

- [ ] **Step 1: Run render-only**

Run: `python main.py --render-only --mode museo`
Expected: `talevision_frame.png` produced (800x480 with artwork + overlay).

- [ ] **Step 2: Verify output visually**

Open `talevision_frame.png` — should show a full-bleed artwork with overlay bar at bottom.

- [ ] **Step 3: Run all existing tests to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: all existing tests still pass.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "museo: smoke test passed, mode fully wired"
```
