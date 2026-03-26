# Wikipedia Random + Weather (wttr.in) Modes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two new display modes — Wikipedia Random (PIL-rendered article with time header, thumbnail image, QR code to article) and Weather (wttr.in JSON → PIL, with location autocomplete in the web UI) — and clean up the dead ANSi/Teletext stubs from the registry.

**Architecture:**
- Both modes follow the exact same pattern as LitClock/SlowMovie: a `DisplayMode` subclass in `talevision/modes/`, a `*Config` dataclass in `schema.py`, a section in `config.yaml`, a frame path registered in the orchestrator, and a settings component in `App.tsx`.
- Wikipedia reuses the existing `/api/language` endpoint (the orchestrator's action queue dispatches `set_language` to the active mode via duck-typing on `hasattr(mode, "set_language")`).
- Weather adds two new API endpoints: `GET/POST /api/weather/location` and `GET /api/weather/search?q=` (Nominatim autocomplete).
- No new pip deps: `urllib.request` (stdlib) for HTTP; `qrcode[pil]` already in requirements (used by SlowMovie). No headless browser, no heavy ML.

**Tech Stack:** Python 3.11 + PIL + Flask + urllib.request | React 18 + TypeScript + Radix UI + TanStack Query

---

## Preliminary: How existing patterns work (read this before coding)

### Adding a mode — checklist
1. `talevision/config/schema.py` — new `FooConfig` dataclass + field on `AppConfig`
2. `config.yaml` — new `foo:` section with defaults
3. `talevision/modes/foo.py` — `FooMode(DisplayMode)` with `name`, `refresh_interval`, `on_activate()`, `render() -> Image.Image`, `get_state() -> ModeState`
4. `talevision/system/orchestrator.py` — add `"foo": base_dir / "cache" / "foo_frame.png"` to `_frame_paths`
5. `main.py` — import `FooMode`, add `"foo": FooMode(config, base_dir=BASE_DIR)` to `modes` dict
6. `frontend/src/App.tsx` — add `{ id: 'foo', label: 'Foo', icon: '…', color: '#…', available: true }` to `ALL_MODES`

### How set_language dispatches
In `orchestrator.py`, the action handler for `("set_language", lang)` currently calls `litclock_mode.set_language(lang)`. We need to change it to dispatch to the **currently active mode** if it has a `set_language` method. Wikipedia will have the same `set_language` signature.

### Render conventions
- White background: `Image.new("RGB", (800, 480), (255, 255, 255))`
- Header time: `datetime.datetime.now().strftime("%H:%M")` — draw with Signika-Bold.ttf size 32, top-left or centered
- Body text: Taviraj-Regular.ttf size 22–26, wrap at 700px using `talevision/render/typography.py:wrap_text_block()`
- Do NOT use `draw_header()` from layout.py (it takes LitClockConfig) — write a simpler inline header

---

## Task 1: Cleanup — remove ANSi/Teletext from mode registry

**Files:**
- Modify: `frontend/src/App.tsx:50-55` (ALL_MODES array)
- Modify: `config.yaml` (default_mode)

### Step 1: Update ALL_MODES in App.tsx

Replace the current `ALL_MODES` array:
```ts
const ALL_MODES: ModeInfo[] = [
  { id: 'litclock',  label: 'LitClock',   icon: '🕐', color: '#39B8FF', available: true },
  { id: 'slowmovie', label: 'SlowMovie',  icon: '🎬', color: '#FFB547', available: true },
  { id: 'wikipedia', label: 'Wikipedia',  icon: '📖', color: '#7551FF', available: true },
  { id: 'weather',   label: 'Weather',    icon: '🌤', color: '#01B574', available: true },
]
```

### Step 2: Set default_mode in config.yaml

Change `default_mode: ansi` → `default_mode: litclock`

### Step 3: Commit
```bash
git add frontend/src/App.tsx config.yaml
git commit -m "chore: remove ansi/teletext from mode registry, add wikipedia/weather stubs"
```

---

## Task 2: WikipediaConfig — schema + config.yaml

**Files:**
- Modify: `talevision/config/schema.py`
- Modify: `config.yaml`

### Step 1: Add WikipediaConfig to schema.py

Add after `AnsiConfig`:
```python
@dataclass
class WikipediaConfig:
    refresh_interval: int = 300
    language: str = "it"
    languages: List[str] = field(default_factory=lambda: ["it", "en", "de", "es", "fr", "pt"])
    timeout: int = 10
```

Add to `AppConfig`:
```python
wikipedia: WikipediaConfig = field(default_factory=WikipediaConfig)
```

### Step 2: Add to config.yaml

```yaml
wikipedia:
  refresh_interval: 300   # seconds between article changes
  language: "it"
  timeout: 10
```

### Step 3: Verify config loads

```bash
python -c "
from talevision.config.loader import load_config
from pathlib import Path
cfg = load_config(Path('config.yaml'))
print(cfg.wikipedia)
"
```
Expected: `WikipediaConfig(refresh_interval=300, language='it', ...)`

### Step 4: Commit
```bash
git add talevision/config/schema.py config.yaml
git commit -m "feat: add WikipediaConfig to schema and config.yaml"
```

---

## Task 3: Wikipedia mode — backend

**Files:**
- Create: `talevision/modes/wikipedia.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_wikipedia.py`

### Step 1: Write failing tests

Create `tests/__init__.py` (empty).

Create `tests/test_wikipedia.py`:
```python
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
    """WikipediaMode.render() returns an 800×480 RGB image (no thumbnail)."""
    cfg = _make_config()
    from talevision.modes.wikipedia import WikipediaMode
    mode = WikipediaMode(cfg, base_dir=Path("."))

    fake_article = {
        "title": "Roma",
        "extract": "Roma è la capitale d'Italia.",
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
        "extract": "Roma è la capitale d'Italia.",
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
```

Run: `python -m pytest tests/test_wikipedia.py -v`
Expected: `FAILED` with `ModuleNotFoundError` or `ImportError`.

### Step 2: Implement `talevision/modes/wikipedia.py`

Wikipedia summary API fields used:
- `title` — article title
- `extract` — plain-text first paragraph(s)
- `thumbnail.source` — URL of the lead image (may be absent)
- `content_urls.desktop.page` — full article URL for QR code

Layout (800×480, white background):
```
┌────────────────────────────────────────────────────────┐
│ 08:47   ────────────────────────   Wikipedia · IT      │  ← header row
│ Lunedì, 10 marzo 2026                                  │
│ ════════════════════════════════════════════════════   │  ← accent separator
│                                              ┌────────┐│
│ TITOLO ARTICOLO                              │        ││  ← title + thumbnail
│                                              │ 180×135││
│ Testo estratto che scorre su più righe...   │        ││  ← body text
│ altra riga di testo...                       └────────┘│
│ ancora testo...                                        │
│                                           ┌──┐         │
│                                           │QR│         │  ← QR bottom-right
│                                           └──┘         │
└────────────────────────────────────────────────────────┘
```

```python
"""Wikipedia Random display mode — fetches a random article and renders with PIL."""
import datetime
import io
import json
import logging
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

LANGS = ["it", "en", "de", "es", "fr", "pt"]
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_ACCENT = (117, 81, 255)
COLOR_MUTED = (110, 110, 110)

# Thumbnail column width (right side of canvas)
THUMB_W = 180
THUMB_H = 135
# QR code size in pixels
QR_SIZE = 80
QR_MARGIN = 10


def _fetch_article(lang: str, timeout: int = 10) -> Dict:
    """Fetch a random Wikipedia article summary. Returns the raw API dict."""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/random/summary"
    req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    data["lang"] = lang
    return data


def _fetch_thumbnail(url: str, timeout: int = 10) -> Optional[Image.Image]:
    """Download and return thumbnail image, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        log.warning(f"Wikipedia thumbnail fetch failed: {exc}")
        return None


def _make_qr(url: str, size: int) -> Image.Image:
    """Generate a QR code image for the given URL."""
    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=3,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((size, size), Image.NEAREST)


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _wrap_text(text: str, font, draw: ImageDraw.Draw, max_width: int) -> List[str]:
    """Word-wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class WikipediaMode(DisplayMode):
    """Displays a random Wikipedia article with thumbnail image and QR link."""

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.wikipedia
        self._display = config.display
        self._base_dir = base_dir
        self._language = self._cfg.language
        self._last_article: Optional[Dict] = None
        self._font_dir = base_dir / "assets" / "fonts"

    @property
    def name(self) -> str:
        return "wikipedia"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info(f"Wikipedia mode activated (lang={self._language})")

    def set_language(self, lang: str) -> None:
        if lang in LANGS:
            self._language = lang
            log.info(f"Wikipedia language set to: {lang}")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height
        timeout = self._cfg.timeout

        # Fetch article
        try:
            article = _fetch_article(self._language, timeout=timeout)
            self._last_article = article
        except Exception as exc:
            log.error(f"Wikipedia fetch failed: {exc}")
            article = self._last_article or {
                "title": "Wikipedia",
                "extract": "Could not load article. Check network connection.",
                "lang": self._language,
            }

        # Fetch thumbnail (non-blocking: if slow, we lose the image gracefully)
        thumb_url = (article.get("thumbnail") or {}).get("source")
        thumbnail: Optional[Image.Image] = None
        if thumb_url:
            thumbnail = _fetch_thumbnail(thumb_url, timeout=timeout)

        # Build QR for article URL
        article_url = (
            (article.get("content_urls") or {})
            .get("desktop", {})
            .get("page", "")
        )
        qr_img = _make_qr(article_url, QR_SIZE) if article_url else None

        img = Image.new("RGB", (w, h), COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        font_bold   = _load_font(self._font_dir / "Signika-Bold.ttf", 32)
        font_title  = _load_font(self._font_dir / "Signika-Bold.ttf", 26)
        font_body   = _load_font(self._font_dir / "Taviraj-Regular.ttf", 22)
        font_meta   = _load_font(self._font_dir / "Taviraj-Regular.ttf", 18)

        pad = 30
        now = datetime.datetime.now()
        y = pad

        # ── Time header ───────────────────────────────────────────────────────
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%A, %d %B %Y")
        lang_label = f"Wikipedia · {self._language.upper()}"

        draw.text((pad, y), time_str, font=font_bold, fill=COLOR_BLACK)
        draw.text(
            (w - pad - draw.textlength(lang_label, font=font_meta), y + 8),
            lang_label, font=font_meta, fill=COLOR_ACCENT,
        )
        y += 38
        draw.text((pad, y), date_str, font=font_meta, fill=COLOR_MUTED)
        y += 26
        draw.line([(pad, y), (w - pad, y)], fill=COLOR_ACCENT, width=2)
        y += 14

        content_top = y

        # ── Thumbnail (right column) ──────────────────────────────────────────
        thumb_x = w - pad - THUMB_W
        thumb_bottom = content_top

        if thumbnail is not None:
            # Crop to fixed aspect ratio (4:3) and paste
            thumb = thumbnail.copy()
            orig_w, orig_h = thumb.size
            target_ratio = THUMB_W / THUMB_H
            orig_ratio = orig_w / orig_h

            if orig_ratio > target_ratio:
                # wider than target — crop sides
                new_w = int(orig_h * target_ratio)
                left = (orig_w - new_w) // 2
                thumb = thumb.crop((left, 0, left + new_w, orig_h))
            else:
                # taller than target — crop top/bottom
                new_h = int(orig_w / target_ratio)
                thumb = thumb.crop((0, 0, orig_w, new_h))

            thumb = thumb.resize((THUMB_W, THUMB_H), Image.LANCZOS)
            img.paste(thumb, (thumb_x, content_top))
            thumb_bottom = content_top + THUMB_H + 8

        # ── Article title ─────────────────────────────────────────────────────
        title = article.get("title", "")
        text_max_w = (thumb_x - pad - 16) if thumbnail is not None else (w - 2 * pad)
        title_lines = _wrap_text(title, font_title, draw, text_max_w)

        y = content_top
        for line in title_lines[:2]:
            draw.text((pad, y), line, font=font_title, fill=COLOR_BLACK)
            y += 32
        y += 8

        # ── Extract body ──────────────────────────────────────────────────────
        extract = article.get("extract", "")
        body_lines = _wrap_text(extract, font_body, draw, text_max_w)

        # Reserve bottom margin for QR code
        qr_reserved = QR_SIZE + QR_MARGIN * 2 if qr_img else pad
        avail_h = h - y - qr_reserved
        line_h = 28
        max_lines = max(0, avail_h // line_h)

        for line in body_lines[:max_lines]:
            draw.text((pad, y), line, font=font_body, fill=COLOR_BLACK)
            y += line_h

        # ── QR code (bottom right) ────────────────────────────────────────────
        if qr_img:
            qr_x = w - pad - QR_SIZE
            qr_y = h - pad - QR_SIZE
            # White background behind QR
            draw.rectangle(
                [qr_x - 4, qr_y - 4, qr_x + QR_SIZE + 4, qr_y + QR_SIZE + 4],
                fill=COLOR_WHITE,
            )
            img.paste(qr_img, (qr_x, qr_y))

        return img

    def get_state(self) -> ModeState:
        article = self._last_article or {}
        return ModeState(
            mode="wikipedia",
            extra={
                "title": article.get("title", ""),
                "language": self._language,
                "url": (
                    (article.get("content_urls") or {})
                    .get("desktop", {})
                    .get("page", "")
                ),
            },
        )
```

### Step 3: Run tests
```bash
python -m pytest tests/test_wikipedia.py -v
```
Expected: all 3 tests PASS.

### Step 4: Smoke test
```bash
python main.py --render-only --mode wikipedia
```
Wait — this will fail because wikipedia is not yet registered. That happens in Task 4. Skip for now.

### Step 5: Commit
```bash
git add talevision/modes/wikipedia.py tests/__init__.py tests/test_wikipedia.py
git commit -m "feat: add WikipediaMode with PIL renderer and tests"
```

---

## Task 4: Register Wikipedia mode in orchestrator + main.py

**Files:**
- Modify: `talevision/system/orchestrator.py` — `_frame_paths` + `_handle_set_language` dispatch
- Modify: `main.py` — import and register WikipediaMode

### Step 1: Update orchestrator._frame_paths

In `orchestrator.py`, inside `__init__`, add to `_frame_paths`:
```python
"wikipedia": base_dir / "cache" / "wikipedia_frame.png",
```

### Step 2: Fix set_language dispatch in orchestrator

Find the action handler in `orchestrator.py` where `("set_language", lang)` is processed. It currently does something like `self._modes["litclock"].set_language(lang)`. Change it to:
```python
elif action == "set_language":
    active = self._modes.get(self._current_mode_name)
    if active and hasattr(active, "set_language"):
        active.set_language(lang)
        log.info(f"Language set to {payload} on {self._current_mode_name}")
    else:
        log.warning(f"Active mode {self._current_mode_name} does not support set_language")
    self._timer.interrupt()
```

To find the exact location, search for `set_language` in `orchestrator.py`.

### Step 3: Add WikipediaMode to main.py

```python
from talevision.modes.wikipedia import WikipediaMode

modes = {
    "litclock": LitClockMode(config, base_dir=BASE_DIR),
    "slowmovie": SlowMovieMode(config, base_dir=BASE_DIR),
    "wikipedia": WikipediaMode(config, base_dir=BASE_DIR),
}
```
Remove the `AnsiMode` import and registration.

### Step 4: Smoke test
```bash
python main.py --render-only --mode wikipedia
```
Expected: `talevision_frame.png` saved, no errors. Verify visually.

### Step 5: Commit
```bash
git add talevision/system/orchestrator.py main.py
git commit -m "feat: register WikipediaMode, fix set_language dispatch to active mode"
```

---

## Task 5: Wikipedia — API + frontend language selector

**Files:**
- Modify: `frontend/src/types.ts` — add `language` field to `Status`
- Modify: `frontend/src/App.tsx` — show language selector for `wikipedia` mode too, pass `current`

### Step 1: Add `language` to Status type

In `frontend/src/types.ts`, add to `Status`:
```ts
language?: string | null
```

### Step 2: Fix LanguageSelector and show for wikipedia

In `App.tsx`, find the language selector section (around line 911). Change:
```tsx
{currentMode === 'litclock' && (
  <section className="animate-fade-in bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
    <LanguageSelector current={undefined} />
  </section>
)}
```
To:
```tsx
{(currentMode === 'litclock' || currentMode === 'wikipedia') && (
  <section className="animate-fade-in bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
    <div className="label mb-3">Language</div>
    <LanguageSelector current={status?.language ?? undefined} />
  </section>
)}
```

Also fix `LanguageSelector` — the `current` prop was always `undefined`. Now pass the real value from `status.language`.

### Step 3: Update get_status() to expose language

The `status` API response needs a `language` field. In `orchestrator.py`, `_update_status_cache()` (or wherever the state is pushed to the cache) — add:
```python
state = active.get_state()
status["state"] = state.extra
status["language"] = state.extra.get("language")
```
Find the exact location by searching for `_status_cache` writes in orchestrator.py.

### Step 4: Build frontend
```bash
cd frontend && npm run build
```
Expected: no TypeScript errors, bundle built.

### Step 5: Smoke test — switch to wikipedia, check language selector appears in UI
Manual test: start daemon, open `http://localhost:5000`, switch mode to wikipedia, verify language dropdown appears.

### Step 6: Commit
```bash
git add frontend/src/types.ts frontend/src/App.tsx talevision/web/static/dist/ talevision/system/orchestrator.py
git commit -m "feat: show language selector for wikipedia mode, expose language in /api/status"
```

---

## Task 6: WeatherConfig — schema + config.yaml

**Files:**
- Modify: `talevision/config/schema.py`
- Modify: `config.yaml`

### Step 1: Add WeatherConfig to schema.py

```python
@dataclass
class WeatherConfig:
    refresh_interval: int = 600    # 10 minutes
    location: str = "Roma"
    timeout: int = 10
```

Add to `AppConfig`:
```python
weather: WeatherConfig = field(default_factory=WeatherConfig)
```

### Step 2: Add to config.yaml

```yaml
weather:
  refresh_interval: 600   # seconds between weather updates
  location: "Roma"
  timeout: 10
```

### Step 3: Verify config loads
```bash
python -c "
from talevision.config.loader import load_config
from pathlib import Path
cfg = load_config(Path('config.yaml'))
print(cfg.weather)
"
```
Expected: `WeatherConfig(refresh_interval=600, location='Roma', ...)`

### Step 4: Commit
```bash
git add talevision/config/schema.py config.yaml
git commit -m "feat: add WeatherConfig to schema and config.yaml"
```

---

## Task 7: Weather mode — backend

**Files:**
- Create: `talevision/modes/weather.py`
- Create: `tests/test_weather.py`

### Step 1: Write failing tests

Create `tests/test_weather.py`:
```python
"""Tests for WeatherMode."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
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
```

Run: `python -m pytest tests/test_weather.py -v`
Expected: FAIL with ImportError.

### Step 2: Implement `talevision/modes/weather.py`

```python
"""Weather display mode — fetches current conditions from wttr.in and renders with PIL."""
import datetime
import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Optional

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_ACCENT = (0, 181, 116)    # green — weather mode color from UI
COLOR_MUTED = (100, 100, 100)
COLOR_BLUE = (57, 184, 255)
COLOR_ORANGE = (255, 181, 71)


def _fetch_weather(location: str, timeout: int = 10) -> Dict:
    """Fetch current weather from wttr.in for the given location.

    Returns the raw wttr.in JSON dict (format=j1).
    """
    encoded = urllib.parse.quote(location)
    url = f"https://wttr.in/{encoded}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default(size=size)


class WeatherMode(DisplayMode):
    """Displays current weather + 3-day forecast from wttr.in."""

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.weather
        self._display = config.display
        self._base_dir = base_dir
        self._location = self._cfg.location
        self._last_data: Optional[Dict] = None
        self._font_dir = base_dir / "assets" / "fonts"

    @property
    def name(self) -> str:
        return "weather"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info(f"Weather mode activated (location={self._location})")

    def set_location(self, location: str) -> None:
        self._location = location.strip()
        log.info(f"Weather location set to: {self._location}")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height
        try:
            data = _fetch_weather(self._location, timeout=self._cfg.timeout)
            self._last_data = data
        except Exception as exc:
            log.error(f"Weather fetch failed ({self._location}): {exc}")
            data = self._last_data

        img = Image.new("RGB", (w, h), COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        if data is None:
            font = _load_font(self._font_dir / "Signika-Bold.ttf", 28)
            draw.text((30, 200), "Weather unavailable", font=font, fill=COLOR_BLACK)
            return img

        font_bold = _load_font(self._font_dir / "Signika-Bold.ttf", 32)
        font_large = _load_font(self._font_dir / "Signika-Bold.ttf", 72)
        font_body = _load_font(self._font_dir / "Taviraj-Regular.ttf", 22)
        font_small = _load_font(self._font_dir / "Taviraj-Regular.ttf", 18)

        pad = 30
        now = datetime.datetime.now()

        # ── Header: time + location ───────────────────────────────────────────
        y = pad
        time_str = now.strftime("%H:%M")
        draw.text((pad, y), time_str, font=font_bold, fill=COLOR_BLACK)
        loc_label = self._location
        draw.text((w - pad - draw.textlength(loc_label, font=font_body), y + 6),
                  loc_label, font=font_body, fill=COLOR_ACCENT)
        y += 38
        date_str = now.strftime("%A, %d %B %Y")
        draw.text((pad, y), date_str, font=font_small, fill=COLOR_MUTED)
        y += 24
        draw.line([(pad, y), (w - pad, y)], fill=COLOR_ACCENT, width=2)
        y += 16

        # ── Current conditions ────────────────────────────────────────────────
        cond = data.get("current_condition", [{}])[0]
        temp_c = cond.get("temp_C", "?")
        feels = cond.get("FeelsLikeC", "?")
        desc = cond.get("weatherDesc", [{}])[0].get("value", "")
        wind = cond.get("windspeedKmph", "?")
        humidity = cond.get("humidity", "?")

        # Big temp on left
        draw.text((pad, y), f"{temp_c}°", font=font_large, fill=COLOR_BLACK)
        temp_w = int(draw.textlength(f"{temp_c}°", font=font_large))

        # Condition + details to the right
        rx = pad + temp_w + 20
        draw.text((rx, y + 8), desc, font=font_bold, fill=COLOR_BLACK)
        draw.text((rx, y + 44), f"Feels like {feels}°C", font=font_body, fill=COLOR_MUTED)
        draw.text((rx, y + 70), f"Wind {wind} km/h · Humidity {humidity}%",
                  font=font_small, fill=COLOR_MUTED)
        y += 100

        # ── 3-day forecast ────────────────────────────────────────────────────
        draw.line([(pad, y), (w - pad, y)], fill=(220, 220, 220), width=1)
        y += 12

        forecast = data.get("weather", [])[:3]
        col_w = (w - 2 * pad) // max(len(forecast), 1)

        for i, day in enumerate(forecast):
            cx = pad + i * col_w
            try:
                d = datetime.datetime.strptime(day["date"], "%Y-%m-%d")
                day_label = d.strftime("%a %d")
            except Exception:
                day_label = day.get("date", "")
            mx = day.get("maxtempC", "?")
            mn = day.get("mintempC", "?")
            day_desc = day.get("hourly", [{}])[len(day.get("hourly", [{}])) // 2].get(
                "weatherDesc", [{}])[0].get("value", "")[:12]

            draw.text((cx, y), day_label, font=font_body, fill=COLOR_BLACK)
            draw.text((cx, y + 26), f"{mx}° / {mn}°", font=font_bold, fill=COLOR_BLUE)
            draw.text((cx, y + 54), day_desc, font=font_small, fill=COLOR_MUTED)

        return img

    def get_state(self) -> ModeState:
        cond = {}
        if self._last_data:
            cond = self._last_data.get("current_condition", [{}])[0]
        return ModeState(
            mode="weather",
            extra={
                "location": self._location,
                "temp_c": cond.get("temp_C"),
                "desc": (cond.get("weatherDesc") or [{}])[0].get("value"),
            },
        )
```

### Step 3: Run tests
```bash
python -m pytest tests/test_weather.py -v
```
Expected: all 3 tests PASS.

### Step 4: Commit
```bash
git add talevision/modes/weather.py tests/test_weather.py
git commit -m "feat: add WeatherMode with wttr.in fetch and PIL renderer"
```

---

## Task 8: Register Weather mode in orchestrator + main.py

**Files:**
- Modify: `talevision/system/orchestrator.py`
- Modify: `main.py`

### Step 1: Add frame path to orchestrator `_frame_paths`
```python
"weather": base_dir / "cache" / "weather_frame.png",
```

### Step 2: Add weather set_location to orchestrator

In `orchestrator.py`, add a public method:
```python
def set_weather_location(self, location: str) -> None:
    weather = self._modes.get("weather")
    if weather and hasattr(weather, "set_location"):
        weather.set_location(location)
    self._action_queue.put(("force_refresh", None))
    self._timer.interrupt()
```

### Step 3: Add WeatherMode to main.py
```python
from talevision.modes.weather import WeatherMode

modes = {
    "litclock":  LitClockMode(config, base_dir=BASE_DIR),
    "slowmovie": SlowMovieMode(config, base_dir=BASE_DIR),
    "wikipedia": WikipediaMode(config, base_dir=BASE_DIR),
    "weather":   WeatherMode(config, base_dir=BASE_DIR),
}
```

### Step 4: Smoke tests
```bash
python main.py --render-only --mode wikipedia && echo "WIKI OK"
python main.py --render-only --mode weather && echo "WEATHER OK"
```
Expected: both print OK, frames saved.

### Step 5: Commit
```bash
git add talevision/system/orchestrator.py main.py
git commit -m "feat: register WeatherMode in orchestrator and main.py"
```

---

## Task 9: Weather API endpoints

**Files:**
- Modify: `talevision/web/api.py`

### Step 1: Add weather endpoints to api.py

```python
@api_bp.get("/weather/location")
def get_weather_location():
    """GET /api/weather/location — current location setting."""
    weather = _orchestrator()._modes.get("weather")
    location = weather._location if weather and hasattr(weather, "_location") else ""
    return jsonify({"location": location})


@api_bp.post("/weather/location")
def set_weather_location():
    """POST /api/weather/location — {"location": "Milano"}"""
    body = request.get_json(silent=True) or {}
    location = body.get("location", "").strip()
    if not location:
        return jsonify({"error": "Missing 'location' field"}), 400
    try:
        _orchestrator().set_weather_location(location)
        return jsonify({"ok": True, "location": location})
    except Exception as exc:
        log.error(f"Set weather location error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/weather/search")
def search_weather_location():
    """GET /api/weather/search?q=Milano — autocomplete via Nominatim."""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"results": []})
    try:
        import urllib.parse
        encoded = urllib.parse.quote(q)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=5&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = [
            {
                "name": item.get("address", {}).get("city")
                     or item.get("address", {}).get("town")
                     or item.get("address", {}).get("village")
                     or item.get("display_name", "").split(",")[0],
                "display": item.get("display_name", ""),
            }
            for item in data
        ]
        return jsonify({"results": results})
    except Exception as exc:
        log.error(f"Weather search error: {exc}")
        return jsonify({"results": []})
```

Also add at the top of `api.py`:
```python
import json
import urllib.request
```

### Step 2: Manual test
```bash
curl http://localhost:5000/api/weather/location
curl "http://localhost:5000/api/weather/search?q=Milan"
```
Expected: JSON with location and search results.

### Step 3: Commit
```bash
git add talevision/web/api.py
git commit -m "feat: add weather location GET/POST and autocomplete search API endpoints"
```

---

## Task 10: Weather + Wikipedia frontend settings components

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`

### Step 1: Add weather API calls to api.ts

```ts
getWeatherLocation: () =>
  fetch('/api/weather/location').then(r => json<{ location: string }>(r)),

setWeatherLocation: (location: string) =>
  fetch('/api/weather/location', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ location }),
  }).then(r => json<{ ok: boolean }>(r)),

searchWeatherLocation: (q: string) =>
  fetch(`/api/weather/search?${new URLSearchParams({ q })}`).then(
    r => json<{ results: Array<{ name: string; display: string }> }>(r)
  ),
```

### Step 2: Add weather location to Status type (types.ts)

```ts
weather_location?: string | null
```

### Step 3: Add WeatherSettings component to App.tsx

Add this component (before the `App` default export):

```tsx
// ─── Weather Settings ────────────────────────────────────────────────────────

function WeatherSettings({ currentLocation }: { currentLocation?: string }) {
  const qc = useQueryClient()
  const [input, setInput] = useState(currentLocation ?? '')
  const [suggestions, setSuggestions] = useState<Array<{ name: string; display: string }>>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [saved, setSaved] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (currentLocation) setInput(currentLocation)
  }, [currentLocation])

  const searchMut = useMutation({
    mutationFn: (q: string) => api.searchWeatherLocation(q),
    onSuccess: (data) => {
      setSuggestions(data.results)
      setShowSuggestions(data.results.length > 0)
    },
  })

  const saveMut = useMutation({
    mutationFn: () => api.setWeatherLocation(input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      setSaved(true)
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setSaved(false), 2500)
    },
  })

  const handleInputChange = (val: string) => {
    setInput(val)
    clearTimeout(debounceRef.current)
    if (val.length >= 2) {
      debounceRef.current = setTimeout(() => searchMut.mutate(val), 400)
    } else {
      setSuggestions([])
      setShowSuggestions(false)
    }
  }

  const selectSuggestion = (name: string) => {
    setInput(name)
    setSuggestions([])
    setShowSuggestions(false)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="label flex-shrink-0">Location</span>
        <div className="relative flex-1">
          <input
            type="text"
            value={input}
            onChange={e => handleInputChange(e.target.value)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="City name…"
            className="w-full bg-deep rounded-sm text-primary font-mono text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(255,255,255,0.1)' }}
            onFocus={e => e.target.style.borderColor = '#01B574'}
          />
          {showSuggestions && suggestions.length > 0 && (
            <div
              className="absolute top-full left-0 right-0 mt-1 bg-surface rounded-sm z-50 overflow-hidden"
              style={{ border: '1px solid rgba(255,255,255,0.1)' }}
            >
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => selectSuggestion(s.name)}
                  className="w-full text-left px-3 py-2 font-mono text-sm text-secondary hover:bg-surface-hover hover:text-accent transition-colors"
                >
                  <span className="text-primary">{s.name}</span>
                  <span className="text-muted text-xs ml-2 truncate">{s.display.slice(0, 60)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending || !input.trim()}
          className="font-mono text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-sm bg-accent text-white hover:bg-accent-hover transition-all duration-200 disabled:opacity-50"
          style={{ boxShadow: '0 0 20px rgba(117,81,255,0.15)' }}
        >
          {saveMut.isPending ? 'Saving…' : 'Set location'}
        </button>
        {saved && <span className="label animate-fade-in" style={{ color: '#01B574' }}>Saved</span>}
      </div>
    </div>
  )
}
```

### Step 4: Show WeatherSettings in App

Find the language selector section in `App.tsx` and add below it:
```tsx
{currentMode === 'weather' && (
  <section className="animate-fade-in bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
    <div className="label mb-3">Weather location</div>
    <WeatherSettings currentLocation={status?.weather_location ?? undefined} />
  </section>
)}
```

### Step 5: Expose weather_location in orchestrator status

In `orchestrator.py`, where the status cache is updated after each render, add:
```python
weather = self._modes.get("weather")
if weather and hasattr(weather, "_location"):
    self._status_cache["weather_location"] = weather._location
```

### Step 6: Build and verify TypeScript compiles
```bash
cd frontend && npm run build
```
Expected: no TypeScript errors.

### Step 7: Commit
```bash
git add frontend/src/api.ts frontend/src/types.ts frontend/src/App.tsx \
        talevision/web/static/dist/ talevision/system/orchestrator.py
git commit -m "feat: add WeatherSettings UI with autocomplete and save location"
```

---

## Task 11: Final integration smoke tests

### Step 1: Run all tests
```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

### Step 2: Full render smoke tests
```bash
python main.py --render-only --mode litclock  && echo "LITCLOCK OK"
python main.py --render-only --mode slowmovie && echo "SLOWMOVIE OK"
python main.py --render-only --mode wikipedia && echo "WIKIPEDIA OK"
python main.py --render-only --mode weather   && echo "WEATHER OK"
```
Expected: all 4 OK.

### Step 3: Pre-push checklist
```bash
grep -rn "tmdb_api_key\|password=\|api_key=\|token=" talevision/ config.yaml
git status | grep secrets.yaml
git status | grep "media/"
```
Expected: no secrets found.

### Step 4: Final commit
```bash
git add .
git commit -m "feat: complete wikipedia + weather modes, clean up ansi/teletext stubs"
```

### Step 5: Deploy to Pi
```bash
sshpass -p 'porcoddio' ssh enuzzo@talevision.local \
  "cd ~/talevision && git pull && sudo systemctl restart talevision"
```

---

## Task 12: Update project knowledge

**Files:**
- Modify: `knowledge/PROJECT_KNOWLEDGE.md` — mode registry + new modes sections
- Modify: memory MEMORY.md — update mode table

### What to update in PROJECT_KNOWLEDGE.md

1. Remove "ANSi Art Mode" section
2. Update "Wikipedia Random Mode" section: change from "planned" to "active", add API endpoint + render details
3. Add new "Weather Mode (wttr.in)" section:
   - API: `GET https://wttr.in/{location}?format=j1`
   - Languages: N/A (location-based)
   - Render: current temp, condition, wind, humidity + 3-day forecast, PIL only
   - Config: `weather.location`, `weather.refresh_interval`, `weather.timeout`
   - New API endpoints: `GET/POST /api/weather/location`, `GET /api/weather/search?q=`
4. Update "Playlist / Rotation System" mode count: 4 active modes
5. Update "Current Product Behaviors" section

### Commit
```bash
git add knowledge/PROJECT_KNOWLEDGE.md
git commit -m "docs: update knowledge for wikipedia+weather modes, remove ansi"
```

---

## Reference: SUPPORTED_LANGUAGES constant (both modes)

```python
LANGS = ["it", "en", "de", "es", "fr", "pt"]
```
Wikipedia uses these as the subdomain: `https://it.wikipedia.org/...`, `https://en.wikipedia.org/...` etc.

## Reference: wttr.in JSON structure (key fields used)

```json
{
  "current_condition": [{
    "temp_C": "18",
    "FeelsLikeC": "16",
    "weatherDesc": [{"value": "Partly cloudy"}],
    "windspeedKmph": "15",
    "humidity": "60"
  }],
  "weather": [
    {
      "date": "2026-03-10",
      "maxtempC": "20",
      "mintempC": "12",
      "hourly": [{"weatherDesc": [{"value": "Sunny"}]}]
    }
  ]
}
```
URL: `https://wttr.in/{location}?format=j1` — location is URL-encoded, no API key required.

## Reference: Wikipedia REST API

```
GET https://{lang}.wikipedia.org/api/rest_v1/page/random/summary
```
Returns JSON — fields used by TaleVision:
```json
{
  "title": "Roma",
  "extract": "Roma è la capitale d'Italia...",
  "thumbnail": {
    "source": "https://upload.wikimedia.org/wikipedia/commons/thumb/.../320px.jpg",
    "width": 320,
    "height": 240
  },
  "content_urls": {
    "desktop": { "page": "https://it.wikipedia.org/wiki/Roma" },
    "mobile":  { "page": "https://it.m.wikipedia.org/wiki/Roma" }
  }
}
```
`thumbnail` is absent for ~30% of articles — code must handle `None` gracefully.
No API key required. Throttle: 200 req/day per IP on the REST v1 endpoint — far more than TaleVision's ~288 req/day at 5-min intervals (in practice Wikipedia is generous with bots that set a User-Agent).

**QR code**: points to `content_urls.desktop.page`. Uses `qrcode[pil]` already in requirements.txt.
**Thumbnail**: fetched separately after the summary. Non-blocking failure — if it times out, the layout renders without image.
