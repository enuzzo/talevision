# Weather ANSI Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom PIL weather layout with wttr.in's native ANSI terminal output, parsed and rendered char-by-char with Inconsolata Nerd Font Mono on white e-ink background.

**Architecture:** Fetch ANSI text from wttr.in using lat/lon coordinates, parse escape codes into (char, color, bold) tuples, render with PIL using monospace font. Geocoding switches from Nominatim to Open-Meteo. Frontend adds units toggle and stores lat/lon.

**Tech Stack:** Python 3, PIL/Pillow, Flask, React/TypeScript, wttr.in API, Open-Meteo Geocoding API

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `talevision/config/schema.py:142-146` | Add city/lat/lon/units to WeatherConfig |
| Modify | `config.yaml:109-112` | New weather config fields |
| Modify | `talevision/modes/weather.py` | Full rewrite: ANSI fetch, parse, PIL render |
| Modify | `talevision/web/api.py:162-213` | Update endpoints for lat/lon, Open-Meteo geocoding, units |
| Modify | `talevision/system/orchestrator.py:132-137,221-224` | Accept city/lat/lon, report units in status |
| Modify | `frontend/src/api.ts:56-69` | Update API client for lat/lon + units |
| Modify | `frontend/src/types.ts:27` | Add weather_units, weather_lat, weather_lon |
| Modify | `frontend/src/App.tsx:870-965` | Store lat/lon on select, add units toggle |
| Modify | `tests/test_weather.py` | Rewrite for ANSI parser + new render |

---

## Chunk 1: Backend Core

### Task 1: Update Config Schema

**Files:**
- Modify: `talevision/config/schema.py:142-146`
- Modify: `config.yaml:109-112`

- [ ] **Step 1: Update WeatherConfig dataclass**

In `talevision/config/schema.py`, replace the WeatherConfig:

```python
@dataclass
class WeatherConfig:
    refresh_interval: int = 600
    city: str = "Roma"
    lat: float = 41.8935
    lon: float = 12.4826
    units: str = "m"              # "m" metric, "u" USCS
    language: str = "it"
    timeout: int = 10
```

- [ ] **Step 2: Update config.yaml**

```yaml
weather:
  refresh_interval: 300
  city: "Ponte Capriasca"
  lat: 46.0667
  lon: 8.9667
  units: "m"
  language: "it"
  timeout: 10
```

- [ ] **Step 3: Commit**

```bash
git add talevision/config/schema.py config.yaml
git commit -m "feat(weather): update config schema with city/lat/lon/units/language"
```

---

### Task 2: Rewrite Weather Mode — ANSI Fetch + Parse + Render

**Files:**
- Modify: `talevision/modes/weather.py` (full rewrite)

- [ ] **Step 1: Write the ANSI parser test**

In `tests/test_weather.py`, replace the entire file:

```python
"""Tests for WeatherMode ANSI redesign."""
import re
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image


def _make_config():
    from talevision.config.loader import load_config
    return load_config(Path("config.yaml"))


# Sample ANSI output (minimal, simulates wttr.in structure)
FAKE_ANSI = (
    "\033[37mWeather report: Roma\033[0m\n"
    "\n"
    "     \\  /       \033[1;33mPartly cloudy\033[0m\n"
    "   _ /\"\".-.     \033[1;33m+18(16) °C\033[0m\n"
    "     \\_(   ).   \033[32m↗ 15 km/h\033[0m\n"
)


def test_parse_ansi_extracts_chars_and_colors():
    from talevision.modes.weather import _parse_ansi
    cells = _parse_ansi(FAKE_ANSI)
    # Should be a list of lines, each line a list of (char, color_rgb, bold) tuples
    assert len(cells) >= 3
    # First line should contain "Weather report: Roma"
    first_line_text = "".join(ch for ch, _, _ in cells[0])
    assert "Weather report" in first_line_text


def test_parse_ansi_maps_colors():
    from talevision.modes.weather import _parse_ansi
    cells = _parse_ansi(FAKE_ANSI)
    # Line 2 (index 2) has bold yellow text — should map to Orange
    line2_colors = set(color for _, color, _ in cells[2] if color != (0, 0, 0))
    assert (255, 165, 0) in line2_colors  # Orange mapped from yellow


def test_parse_ansi_bold_flag():
    from talevision.modes.weather import _parse_ansi
    cells = _parse_ansi(FAKE_ANSI)
    # Bold yellow "Partly cloudy" — bold should be True
    bold_chars = [(ch, bold) for ch, _, bold in cells[2] if bold]
    assert len(bold_chars) > 0


def test_render_returns_correct_size():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))

    with patch("talevision.modes.weather._fetch_ansi", return_value=FAKE_ANSI):
        img = mode.render()

    assert isinstance(img, Image.Image)
    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_render_white_background():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))

    with patch("talevision.modes.weather._fetch_ansi", return_value=FAKE_ANSI):
        img = mode.render()

    # Top-left corner should be white (background)
    assert img.getpixel((0, 0)) == (255, 255, 255)


def test_set_location_updates_all_fields():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))
    mode.set_location("Milano", 45.4642, 9.1900)
    assert mode._city == "Milano"
    assert mode._lat == 45.4642
    assert mode._lon == 9.1900


def test_set_units():
    cfg = _make_config()
    from talevision.modes.weather import WeatherMode
    mode = WeatherMode(cfg, base_dir=Path("."))
    mode.set_units("u")
    assert mode._units == "u"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_weather.py -v`
Expected: FAIL (old code has no `_parse_ansi`, `_fetch_ansi`, etc.)

- [ ] **Step 3: Write the full weather.py rewrite**

Replace entire `talevision/modes/weather.py`:

```python
"""Weather display mode — renders wttr.in ANSI output on e-ink via PIL."""
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)

# ANSI SGR code → e-ink RGB mapping (inverted: white bg, dark text)
ANSI_COLOR_MAP = {
    30: COLOR_BLACK,          # black → black
    31: (255, 0, 0),          # red → red
    32: (0, 0, 255),          # green → blue (green illegible on white)
    33: (255, 165, 0),        # yellow → orange (yellow illegible on white)
    34: (0, 0, 255),          # blue → blue
    35: (255, 0, 0),          # magenta → red
    36: (0, 0, 255),          # cyan → blue
    37: COLOR_BLACK,          # white → black (inverted)
    39: COLOR_BLACK,          # default → black
    90: (110, 110, 110),      # bright black (grey)
    91: (255, 0, 0),          # bright red
    92: (0, 0, 255),          # bright green → blue
    93: (255, 165, 0),        # bright yellow → orange
    94: (0, 0, 255),          # bright blue
    95: (255, 0, 0),          # bright magenta → red
    96: (0, 0, 255),          # bright cyan → blue
    97: COLOR_BLACK,          # bright white → black
}

ANSI_RE = re.compile(r"\033\[([0-9;]*)m")

FONT_SIZE = 12
LINE_GAP = 2


def _fetch_ansi(lat: float, lon: float, lang: str = "it",
                units: str = "m", timeout: int = 10) -> str:
    loc = f"{lat:.4f},{lon:.4f}"
    encoded = urllib.parse.quote(loc)
    url = f"http://wttr.in/{encoded}?A&F&2&lang={lang}&{units}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


Cell = Tuple[str, Tuple[int, int, int], bool]  # (char, rgb, is_bold)


def _parse_ansi(text: str) -> List[List[Cell]]:
    lines_out: List[List[Cell]] = []
    current_color = COLOR_BLACK
    current_bold = False

    # Strip trailing location line if present
    lines = text.split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines and ("Località:" in lines[-1] or "Location:" in lines[-1]
                  or "Ubicación:" in lines[-1] or "Localisation:" in lines[-1]
                  or "Standort:" in lines[-1] or "Localização:" in lines[-1]):
        lines.pop()

    for raw_line in lines:
        cells: List[Cell] = []
        pos = 0
        for m in ANSI_RE.finditer(raw_line):
            # Text before this escape
            before = raw_line[pos:m.start()]
            for ch in before:
                cells.append((ch, current_color, current_bold))
            # Parse SGR params
            params_str = m.group(1)
            if not params_str:
                params = [0]
            else:
                params = [int(p) for p in params_str.split(";") if p.isdigit()]
            for p in params:
                if p == 0:
                    current_color = COLOR_BLACK
                    current_bold = False
                elif p == 1:
                    current_bold = True
                elif p == 4:
                    pass  # underline — handled at render time if needed
                elif p in ANSI_COLOR_MAP:
                    current_color = ANSI_COLOR_MAP[p]
            pos = m.end()
        # Remaining text after last escape
        remainder = raw_line[pos:]
        for ch in remainder:
            cells.append((ch, current_color, current_bold))
        lines_out.append(cells)

    return lines_out


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default(size=size)


class WeatherMode(DisplayMode):
    """Displays wttr.in ANSI weather output rendered with monospace font."""

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.weather
        self._display = config.display
        self._base_dir = base_dir
        self._city = self._cfg.city
        self._lat = self._cfg.lat
        self._lon = self._cfg.lon
        self._units = self._cfg.units
        self._language = self._cfg.language
        self._last_ansi: Optional[str] = None
        self._font_dir = base_dir / "assets" / "fonts"

    @property
    def name(self) -> str:
        return "weather"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info(f"Weather mode activated (city={self._city}, "
                 f"lat={self._lat}, lon={self._lon})")

    def set_location(self, city: str, lat: float, lon: float) -> None:
        self._city = city.strip()
        self._lat = lat
        self._lon = lon
        log.info(f"Weather location set to: {self._city} ({self._lat}, {self._lon})")

    def set_units(self, units: str) -> None:
        if units in ("m", "u", "M"):
            self._units = units
            log.info(f"Weather units set to: {self._units}")

    def set_language(self, lang: str) -> None:
        self._language = lang
        log.info(f"Weather language set to: {self._language}")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height

        try:
            ansi_text = _fetch_ansi(
                self._lat, self._lon,
                lang=self._language,
                units=self._units,
                timeout=self._cfg.timeout,
            )
            self._last_ansi = ansi_text
        except Exception as exc:
            log.error(f"Weather ANSI fetch failed: {exc}")
            ansi_text = self._last_ansi

        img = Image.new("RGB", (w, h), COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        if ansi_text is None:
            font_err = _load_font(self._font_dir / "Signika-Bold.ttf", 28)
            draw.text((30, 200), "Weather unavailable", font=font_err, fill=COLOR_BLACK)
            return img

        font_regular = _load_font(
            self._font_dir / "InconsolataNerdFontMono-Regular.ttf", FONT_SIZE)
        font_bold = _load_font(
            self._font_dir / "InconsolataNerdFontMono-Bold.ttf", FONT_SIZE)

        parsed = _parse_ansi(ansi_text)

        # Measure char cell size
        bbox = font_regular.getbbox("M")
        char_w = bbox[2] - bbox[0]
        char_h = FONT_SIZE + LINE_GAP

        # Centre output on canvas
        max_cols = max((len(line) for line in parsed), default=0)
        total_w = max_cols * char_w
        total_h = len(parsed) * char_h
        offset_x = max(0, (w - total_w) // 2)
        offset_y = max(0, (h - total_h) // 2)

        for row_idx, line_cells in enumerate(parsed):
            y = offset_y + row_idx * char_h
            if y > h:
                break
            for col_idx, (ch, color, bold) in enumerate(line_cells):
                x = offset_x + col_idx * char_w
                if x > w:
                    break
                if ch == " ":
                    continue
                font = font_bold if bold else font_regular
                draw.text((x, y), ch, font=font, fill=color)

        return img

    def get_state(self) -> ModeState:
        return ModeState(
            mode="weather",
            extra={
                "city": self._city,
                "lat": self._lat,
                "lon": self._lon,
                "units": self._units,
                "language": self._language,
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_weather.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add talevision/modes/weather.py tests/test_weather.py
git commit -m "feat(weather): rewrite mode with ANSI parser + PIL mono renderer"
```

---

## Chunk 2: API + Orchestrator + Frontend

### Task 3: Update API Endpoints

**Files:**
- Modify: `talevision/web/api.py:162-213`

- [ ] **Step 1: Rewrite weather API endpoints**

Replace lines 162-213 in `talevision/web/api.py`:

```python
@api_bp.get("/weather/location")
def get_weather_location():
    """GET /api/weather/location — current city + coordinates."""
    weather = _orchestrator()._modes.get("weather")
    if not weather:
        return jsonify({"city": "", "lat": 0, "lon": 0})
    return jsonify({
        "city": weather._city,
        "lat": weather._lat,
        "lon": weather._lon,
    })


@api_bp.post("/weather/location")
def set_weather_location():
    """POST /api/weather/location — {"city": "Milano", "lat": 45.46, "lon": 9.19}"""
    body = request.get_json(silent=True) or {}
    city = body.get("city", "").strip()
    lat = body.get("lat")
    lon = body.get("lon")
    if not city or lat is None or lon is None:
        return jsonify({"error": "Missing city, lat, or lon"}), 400
    try:
        _orchestrator().set_weather_location(city, float(lat), float(lon))
        return jsonify({"ok": True, "city": city})
    except Exception as exc:
        log.error(f"Set weather location error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/weather/search")
def search_weather_location():
    """GET /api/weather/search?q=Milano — city autocomplete via Open-Meteo."""
    q = request.args.get("q", "").strip()
    lang = request.args.get("lang", "en")
    if not q or len(q) < 2:
        return jsonify({"results": []})
    try:
        encoded = urllib.parse.quote(q)
        url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?count=6&language={lang}&format=json&name={encoded}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        for item in data.get("results", []):
            name = item.get("name", "")
            admin1 = item.get("admin1", "")
            country = item.get("country", "")
            display = ", ".join(p for p in [name, admin1, country] if p)
            results.append({
                "name": name,
                "display": display,
                "lat": round(item.get("latitude", 0), 4),
                "lon": round(item.get("longitude", 0), 4),
            })
        return jsonify({"results": results})
    except Exception as exc:
        log.error(f"Weather search error: {exc}")
        return jsonify({"results": []})


@api_bp.get("/weather/units")
def get_weather_units():
    """GET /api/weather/units — current unit system."""
    weather = _orchestrator()._modes.get("weather")
    units = weather._units if weather else "m"
    return jsonify({"units": units})


@api_bp.post("/weather/units")
def set_weather_units():
    """POST /api/weather/units — {"units": "m"|"u"}"""
    body = request.get_json(silent=True) or {}
    units = body.get("units", "")
    if units not in ("m", "u", "M"):
        return jsonify({"error": "Invalid units (m, u, or M)"}), 400
    try:
        weather = _orchestrator()._modes.get("weather")
        if weather and hasattr(weather, "set_units"):
            weather.set_units(units)
        _orchestrator()._action_queue.put(("force_refresh", None))
        _orchestrator()._timer.interrupt()
        return jsonify({"ok": True, "units": units})
    except Exception as exc:
        log.error(f"Set weather units error: {exc}")
        return jsonify({"error": str(exc)}), 500
```

- [ ] **Step 2: Commit**

```bash
git add talevision/web/api.py
git commit -m "feat(weather): update API for lat/lon, Open-Meteo geocoding, units"
```

---

### Task 4: Update Orchestrator

**Files:**
- Modify: `talevision/system/orchestrator.py:132-137,221-224`

- [ ] **Step 1: Update set_weather_location signature**

Replace orchestrator method at line 132-137:

```python
    def set_weather_location(self, city: str, lat: float, lon: float) -> None:
        weather = self._modes.get("weather")
        if weather and hasattr(weather, "set_location"):
            weather.set_location(city, lat, lon)
        self._action_queue.put(("force_refresh", None))
        self._timer.interrupt()
```

- [ ] **Step 2: Update status cache to report city + units**

Replace lines 221-224 in `_update_status_cache`:

```python
        weather_location = None
        weather_units = None
        weather_mode = self._modes.get("weather")
        if weather_mode:
            weather_location = getattr(weather_mode, "_city", None)
            weather_units = getattr(weather_mode, "_units", None)
```

Also add `"weather_units": weather_units,` to the status_cache dict (next to `weather_location` line).

- [ ] **Step 3: Commit**

```bash
git add talevision/system/orchestrator.py
git commit -m "feat(weather): orchestrator accepts city/lat/lon, reports units"
```

---

### Task 5: Update Frontend

**Files:**
- Modify: `frontend/src/types.ts:27`
- Modify: `frontend/src/api.ts:56-69`
- Modify: `frontend/src/App.tsx:870-965`

- [ ] **Step 1: Update types**

In `frontend/src/types.ts`, add after `weather_location`:

```typescript
  weather_location?: string | null
  weather_units?: string | null
```

- [ ] **Step 2: Update API client**

Replace weather functions in `frontend/src/api.ts`:

```typescript
  getWeatherLocation: () =>
    fetch('/api/weather/location').then(r => json<{ city: string; lat: number; lon: number }>(r)),

  setWeatherLocation: (city: string, lat: number, lon: number) =>
    fetch('/api/weather/location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city, lat, lon }),
    }).then(r => json<{ ok: boolean }>(r)),

  searchWeatherLocation: (q: string, lang?: string) =>
    fetch(`/api/weather/search?${new URLSearchParams({ q, lang: lang ?? 'en' })}`).then(
      r => json<{ results: Array<{ name: string; display: string; lat: number; lon: number }> }>(r)
    ),

  getWeatherUnits: () =>
    fetch('/api/weather/units').then(r => json<{ units: string }>(r)),

  setWeatherUnits: (units: string) =>
    fetch('/api/weather/units', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ units }),
    }).then(r => json<{ ok: boolean }>(r)),
```

- [ ] **Step 3: Rewrite WeatherSettings component**

Replace the WeatherSettings function in `frontend/src/App.tsx` (lines 870-965):

```tsx
function WeatherSettings({ currentLocation }: { currentLocation?: string }) {
  const qc = useQueryClient()
  const [input, setInput] = useState(currentLocation ?? '')
  const [suggestions, setSuggestions] = useState<Array<{ name: string; display: string; lat: number; lon: number }>>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedCoords, setSelectedCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [saved, setSaved] = useState(false)
  const [units, setUnits] = useState('m')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (currentLocation && !input) setInput(currentLocation)
  }, [currentLocation])

  useEffect(() => {
    api.getWeatherUnits().then(d => setUnits(d.units)).catch(() => {})
  }, [])

  const searchMut = useMutation({
    mutationFn: (q: string) => api.searchWeatherLocation(q),
    onSuccess: (data) => {
      setSuggestions(data.results)
      setShowSuggestions(data.results.length > 0)
    },
  })

  const saveMut = useMutation({
    mutationFn: () => {
      if (!selectedCoords) return Promise.reject(new Error('No city selected'))
      return api.setWeatherLocation(input, selectedCoords.lat, selectedCoords.lon)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      setSaved(true)
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setSaved(false), 2500)
    },
  })

  const unitsMut = useMutation({
    mutationFn: (u: string) => api.setWeatherUnits(u),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['status'] }),
  })

  const handleInputChange = (val: string) => {
    setInput(val)
    setSelectedCoords(null)
    clearTimeout(debounceRef.current)
    if (val.length >= 2) {
      debounceRef.current = setTimeout(() => searchMut.mutate(val), 400)
    } else {
      setSuggestions([])
      setShowSuggestions(false)
    }
  }

  const selectSuggestion = (s: { name: string; display: string; lat: number; lon: number }) => {
    setInput(s.name)
    setSelectedCoords({ lat: s.lat, lon: s.lon })
    setSuggestions([])
    setShowSuggestions(false)
  }

  const toggleUnits = () => {
    const next = units === 'm' ? 'u' : 'm'
    setUnits(next)
    unitsMut.mutate(next)
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
            className="w-full bg-deep rounded-sm text-primary font-display text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(74,75,89,0.15)' }}
            onFocus={e => { e.target.style.borderColor = '#CA796D' }}
          />
          {showSuggestions && suggestions.length > 0 && (
            <div
              className="absolute top-full left-0 right-0 mt-1 bg-surface rounded-sm z-50 overflow-hidden"
              style={{ border: '1px solid rgba(74,75,89,0.15)' }}
            >
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => selectSuggestion(s)}
                  className="w-full text-left px-3 py-2 font-display text-sm text-secondary hover:bg-surface-hover hover:text-accent transition-colors"
                >
                  <span className="text-primary">{s.name}</span>
                  <span className="text-muted text-xs ml-2">{s.display}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending || !input.trim() || !selectedCoords}
          className="font-display text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-sm bg-accent text-cream hover:bg-accent-hover transition-all duration-200 disabled:opacity-50"
          style={{ boxShadow: '0 0 20px rgba(202,121,109,0.20)' }}
        >
          {saveMut.isPending ? 'Saving…' : 'Set location'}
        </button>
        <button
          onClick={toggleUnits}
          className="font-display text-xs font-bold uppercase tracking-widest px-4 py-2.5 rounded-sm bg-deep text-secondary hover:text-accent transition-all duration-200"
          style={{ border: '1px solid rgba(74,75,89,0.15)' }}
        >
          {units === 'm' ? '°C · km/h' : '°F · mph'}
        </button>
        {saved && <span className="label animate-fade-in" style={{ color: '#8DA495' }}>Saved</span>}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/App.tsx
git commit -m "feat(weather): frontend with lat/lon autocomplete + units toggle"
```

---

### Task 6: Integration Test + Deploy

- [ ] **Step 1: Run all backend tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Merge to main and deploy**

```bash
cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision
git checkout main && git merge claude/practical-borg && git push origin main
```

- [ ] **Step 3: Deploy to Pi**

```bash
sshpass -p 'porcoddio' ssh enuzzo@talevision.local "cd ~/talevision && git pull && sudo systemctl restart talevision"
```

- [ ] **Step 4: Visual check**

Wait ~60s for e-ink refresh, then check display shows ANSI weather output with:
- White background, black text
- Orange temperature values
- Blue wind values
- ASCII art weather icons
- Box-drawing table borders
- Unicode arrows for wind direction
