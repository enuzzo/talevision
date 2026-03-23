# Museo Mode

## Summary

Full-bleed artwork display from 3 museum open-access APIs (Met, AIC, Cleveland Museum of Art). Each render shows a random public-domain artwork that fills the entire 800x480 e-ink display, with a compact overlay (title, artist, date, museum, department, QR) matching SlowMovie's visual pattern.

## Provider Round-Robin

Three providers cycle deterministically: **Met -> AIC -> Cleveland -> Met -> ...**

- State is an in-memory index (`_provider_index: int`), starts at 0 (Met) on boot
- No persistence — reboot resets to Met
- Index advances by 1 each time Museo renders, regardless of other modes in between
- Example with playlist `[museo, litclock]`: Met, litclock, AIC, litclock, Cleveland, litclock, Met, ...

## Data Sources

All free, no authentication required. All requests use `User-Agent: TaleVision/1.0`.

### The Metropolitan Museum of Art (New York)

- API: `https://collectionapi.metmuseum.org/public/collection/v1/`
- Catalogue: `GET /search?hasImages=true&isPublicDomain=true&q=*` returns `{"total": N, "objectIDs": [...]}`
- Object: `GET /objects/{objectID}`
- Image: `primaryImageSmall` field (~600px wide JPEG). Can be empty even for public domain objects — handle as missing.
- Metadata: `title`, `artistDisplayName`, `objectDate`, `department`, `objectURL`
- Cache: full ID list in `cache/museo_met_ids.json` (~2-5MB on disk, **~15MB in RAM** as Python list of ints). Refresh every 24h. Acceptable on 512MB Pi Zero W but worth noting.

### Art Institute of Chicago

- API: `https://api.artic.edu/api/v1/`
- **Cache strategy**: AIC Elasticsearch enforces a hard cap of `offset <= 10,000` (page * limit), so random pagination cannot reach the full ~50k collection. Instead, cache a **batch of IDs** by paginating `limit=100` across 100 pages (10,000 IDs):
  - `GET /artworks/search?query[term][is_public_domain]=true&limit=100&page={1..100}&fields=id,title,artist_display,date_display,image_id,department_title`
  - Store all collected IDs in `cache/museo_aic_ids.json`. Refresh every 24h.
  - At render time: `random.choice(cached_ids)` then fetch full object.
- Object details (if needed beyond cached fields): `GET /artworks/{id}?fields=id,title,artist_display,date_display,image_id,department_title`
- Image: IIIF `https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg`
- Metadata: `title`, `artist_display` (**note**: contains newlines with biography — use only first line before `\n`), `date_display`, `department_title`
- Object URL: `https://www.artic.edu/artworks/{id}`

### Cleveland Museum of Art

- API: `https://openaccess-api.clevelandart.org/api/artworks/`
- **Note**: `limit=0` returns 1000 full records (~12MB), not just metadata. Use `limit=1` to get the total count with minimal payload.
- Catalogue: `GET /?has_image=1&cc0=1&limit=1` returns `{"info": {"total": N}, "data": [...]}`
- Random artwork: `GET /?has_image=1&cc0=1&limit=1&skip={random_0_to_total}`
- Image: `images.web.url` nested field
- Metadata: `title`, `creators[0].description`, `creation_date`, `collection`
- Object URL: `url` field
- Cache: total count in `cache/museo_cleveland_total.json`, refresh every 24h

## Cache System

File: `talevision/modes/museo_cache.py`

- Met: caches full objectID list (~2-5MB on disk, ~15MB RAM). Heavy but one-time per day.
- AIC: caches batch of ~10,000 IDs (paginated fetch, ~100 requests on refresh). Runs once per day.
- Cleveland: caches only total count (tiny JSON, single request).
- Refresh trigger: `time.time() - os.path.getmtime(cache_file) > 86400`
- On refresh failure: use stale cache silently, log warning
- On no cache at all (first boot, no network): raise, trigger fallback frame
- Rate impact: ~96 API calls per provider per day in normal rotation (one Museo render every 15 min with 3 providers). Well within museum API limits.

## Deduplication

Ring buffer of last 50 artwork IDs (across all providers) in `_recent_ids: collections.deque(maxlen=50)`.
- Before fetching object details, check if ID is in buffer; if so, re-pick
- Max 5 re-pick attempts before accepting a duplicate (safety valve)
- In-memory only, not persisted

## Render Pipeline

```
1. provider = PROVIDERS[self._provider_index % 3]
2. self._provider_index += 1
3. Check cache age, refresh if > 24h (background-tolerant: stale OK)
4. Pick random artwork ID (not in recent_ids ring buffer)
5. Fetch object metadata from provider API (timeout=10s)
6. Validate image URL exists; if missing, re-pick a different artwork (up to 5 re-picks)
7. Fetch image (urllib, timeout=60s for Pi Zero W). If download fails, re-pick (do NOT retry same URL)
8. PIL enhancement: Brightness(1.1) -> Contrast(1.2) -> Color(1.3)
9. ImageOps.fit(img, (800, 480), Image.LANCZOS) — cover crop
10. Draw overlay (RGBA layer, alpha_composite)
11. Save last rendered frame to cache/museo_last_frame.png (warm fallback)
12. Write ISO 8601 timestamp to cache/museo_last_success.txt
13. Return RGB 800x480
```

Steps 6-7 clarification: the 5 retry loop is for **re-picking different artworks** (fast: random ID + metadata check), NOT for retrying the same failed download. This prevents a worst-case 5 * 60s = 5min block.

## Image Enhancement

Same chain as SlowMovie, tuned for artwork:

```python
from PIL import ImageEnhance
img = ImageEnhance.Brightness(img).enhance(1.1)
img = ImageEnhance.Contrast(img).enhance(1.2)
img = ImageEnhance.Color(img).enhance(1.3)
```

No gamma LUT needed (artworks are already well-exposed, unlike dark film frames).

## Overlay

Identical pattern to SlowMovie: RGBA layer with `rounded_rectangle` + `alpha_composite`.

```
┌──────────────────────────────────────────────────┐
│                                                  │
│          ARTWORK IMAGE (full bleed 800x480)       │
│          cover-cropped, PIL-enhanced              │
│                                                  │
│                                                  │
│  ┌────────────────────────────────────┬────────┐ │
│  │ The Starry Night · 1889            │        │ │
│  │ Vincent van Gogh                   │   QR   │ │
│  │ The Met · European Paintings       │        │ │
│  └────────────────────────────────────┴────────┘ │
└──────────────────────────────────────────────────┘
```

### Info box (bottom-left)

- Line 1: **Title** + ` · ` + **Date** — Signika-Bold, font_size from config (default 22pt), white
- Line 2: **Artist** — Signika-Light, same size, white
- Line 3: **Museum** + ` · ` + **Department** — InconsolataNerdFontMono-Regular.ttf, 12pt, light grey (200,200,200,255)
- Box: `rounded_rectangle(radius=8, fill=(0,0,0,190))`, padding 10px
- Position: bottom-left, margin_l=20, bottom_margin from config (default 35px)

### QR box (bottom-right)

- Links to the artwork's page on the museum website (`object_url` from provider — custom handling, not SlowMovie's imdb/tmdb dispatch)
- Same style as SlowMovie: white-on-transparent QR inside dark rounded box
- Size: 70px (configurable), margin=20px from right edge

### Title truncation

Artwork titles can be long. Truncate to fit overlay width:
- Max title width = 800 - margin_l(20) - padding(10) - qr_box_width(~110) - gap(20) = ~640px
- If title exceeds, truncate with ` ...`

## Provider ABC

File: `talevision/modes/museo_providers/base.py`

```python
class MuseoProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def museum_display_name(self) -> str:
        """Human-readable museum name for overlay, e.g. 'The Met'."""

    @abc.abstractmethod
    def fetch_catalogue_meta(self) -> dict:
        """Fetch catalogue metadata for caching (ID list or total count)."""

    @abc.abstractmethod
    def pick_random_id(self, cache_data: dict) -> str | int:
        """Pick a random artwork ID from cached catalogue data."""

    @abc.abstractmethod
    def fetch_artwork(self, artwork_id) -> dict:
        """Fetch full artwork metadata. Returns normalised dict."""

    @abc.abstractmethod
    def get_image_url(self, artwork: dict) -> str | None:
        """Extract image URL from artwork metadata."""

    @abc.abstractmethod
    def get_object_url(self, artwork: dict) -> str:
        """URL to artwork page on museum website (for QR)."""
```

Each provider normalises its response to a common dict:

```python
{
    "title": str,
    "artist": str,         # cleaned: first line only (AIC sends multi-line)
    "date": str,
    "department": str,
    "museum": str,           # human-readable museum name
    "image_url": str,
    "object_url": str,       # for QR
    "provider": str,         # "met" | "aic" | "cleveland"
    "artwork_id": str | int,
}
```

## Lifecycle Hooks

- `on_activate()`: trigger cache refresh for current provider if stale (non-blocking, best-effort). Log activation.
- `on_deactivate()`: no-op.

## Configuration

Add to `schema.py`:

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
    timeout: int = 60           # generous for Pi Zero W image downloads
    cache_max_age: int = 86400  # 24h in seconds
    brightness: float = 1.1
    contrast: float = 1.2
    color: float = 1.3
    overlay: OverlayConfig = field(default_factory=lambda: OverlayConfig(
        qr_content="museo_page",
    ))
    fonts: MuseoFontsConfig = field(default_factory=MuseoFontsConfig)
```

Add `museo: MuseoConfig` to `AppConfig`.

Overlay can be disabled via config: `museo.overlay.show_info: false` or `museo.overlay.qr_enabled: false`.

## config.yaml

```yaml
museo:
  refresh_interval: 300
  timeout: 60
```

## Registration

In `main.py`:

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

## Fallback

Layered fallback strategy:

1. **Warm fallback** (preferred): if `cache/museo_last_frame.png` exists, display it. Shows the last successful artwork rather than an error screen.
2. **Cold fallback** (no cached frame): white background, "MUSEO" in Lobster ~50pt centred black, "La connessione non è disponibile" in Taviraj-Italic 18pt centred grey. If `cache/museo_last_success.txt` exists, show "Ultimo aggiornamento: {ISO 8601 timestamp}" below.

## get_state()

```python
ModeState(
    mode="museo",
    extra={
        "title": artwork_title,
        "artist": artist_name,
        "museum": museum_name,
        "provider": provider_name,
        "object_url": object_url,
    }
)
```

## File Structure

```
talevision/modes/
    museo.py                    # MuseoMode class, render pipeline, round-robin
    museo_cache.py              # Cache refresh logic, file I/O
    museo_providers/
        __init__.py
        base.py                 # MuseoProvider ABC
        met.py                  # Metropolitan Museum provider
        aic.py                  # Art Institute of Chicago provider
        cleveland.py            # Cleveland Museum of Art provider
cache/
    museo_met_ids.json          # Met full ID list (runtime, gitignored)
    museo_aic_ids.json          # AIC batch of ~10k IDs (runtime, gitignored)
    museo_cleveland_total.json  # Cleveland total count (runtime, gitignored)
    museo_last_success.txt      # ISO 8601 timestamp of last successful render
    museo_last_frame.png        # Last rendered frame for warm fallback
```

## Error Handling

- Network timeout on metadata fetch (10s): re-pick different artwork (up to 5 attempts)
- Network timeout on image fetch (60s): re-pick different artwork (do NOT retry same URL)
- Provider API returns no image URL: skip, re-pick
- Cache refresh fails: use stale cache, log warning, continue
- All 5 attempts fail: raise RuntimeError, orchestrator shows fallback (warm then cold)
- PIL enhancement or overlay errors: log, return un-enhanced/un-overlaid image rather than crash

## Testing

`python main.py --render-only --mode museo` produces `talevision_frame.png`.

Note: requires `museo` to be registered in the `modes` dict in `main.py` first.
