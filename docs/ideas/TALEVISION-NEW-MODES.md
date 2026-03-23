# TaleVision — New Modes Implementation Plan

**Project:** TaleVision  
**Hardware:** Raspberry Pi Zero W (512MB RAM, single-core ARM11 1GHz, ARMv6)  
**Display:** Inky Impression 4" — 800×480, 7-colour ACeP (Black, White, Red, Green, Blue, Yellow, Orange)  
**Stack:** Python 3.11 + Pillow (PIL), `qrcode` library  
**Refresh:** 5-minute cycle (modes may exceed this — see per-mode timing)  
**Date:** March 2026  

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Shared Infrastructure](#2-shared-infrastructure)
3. [Mode: Museo](#3-mode-museo)
4. [Mode: Koan](#4-mode-koan)
5. [Mode: Tessera](#5-mode-tessera)
6. [Mode: Cucina](#6-mode-cucina)
7. [Mode: Atlante](#7-mode-atlante)
8. [LLM Engine (shared by Koan & Tessera)](#8-llm-engine-shared-by-koan--tessera)
9. [Error Reporting System](#9-error-reporting-system)
10. [Terminal Test Suite](#10-terminal-test-suite)
11. [File Structure](#11-file-structure)
12. [Implementation Order](#12-implementation-order)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                   TaleVision Main Loop                │
│                                                      │
│  while True:                                         │
│    mode = get_current_mode()   # from config/playlist│
│    try:                                              │
│      img = mode.render()       # returns PIL Image   │
│      display.show(img)         # push to e-ink       │
│      error_log.success(mode)                         │
│    except Exception as e:                            │
│      error_log.record(mode, e)                       │
│      img = mode.fallback()     # always has one      │
│      display.show(img)                               │
│    sleep(mode.interval)                              │
└──────────────────────────────────────────────────────┘
```

Every mode MUST implement:
- `render() -> PIL.Image.Image` (800×480 RGB)
- `fallback() -> PIL.Image.Image` (offline/error frame)
- `test() -> dict` (returns diagnostic info for terminal tests)
- `name: str` (human-readable mode name)
- `interval: int` (seconds between refreshes)

---

## 2. Shared Infrastructure

### 2.1 Seven-Colour Dithering Engine

File: `lib/dither.py`

```python
EINK_PALETTE = [
    (0, 0, 0),        # Black
    (255, 255, 255),   # White
    (0, 128, 0),       # Green
    (0, 0, 255),       # Blue
    (255, 0, 0),       # Red
    (255, 255, 0),     # Yellow
    (255, 128, 0),     # Orange
]

def dither_floyd_steinberg(img: Image, palette=EINK_PALETTE) -> Image:
    """Floyd-Steinberg error diffusion to 7-colour ACeP palette."""
    ...

def dither_atkinson(img: Image, palette=EINK_PALETTE) -> Image:
    """Atkinson dithering — cleaner for text-heavy layouts.
    Diffuses only 6/8 of the error, leaving more white space."""
    ...
```

Use Floyd-Steinberg for photographic content (Museo, Astro).
Use Atkinson for graphic/text content (Koan, Tessera) — it preserves more white space.

### 2.2 Font Registry

File: `lib/fonts.py`

All fonts live in `assets/fonts/`. Register them once:

```python
FONTS = {
    "signika_bold": "assets/fonts/Signika-Bold.ttf",
    "taviraj": "assets/fonts/Taviraj-Regular.ttf",
    "taviraj_italic": "assets/fonts/Taviraj-Italic.ttf",
    "lobster": "assets/fonts/Lobster-Regular.ttf",
    "inconsolata": "assets/fonts/InconsolataNerdFontMono-Regular.ttf",
    "dejavumono": "assets/fonts/DejaVuSansMono.ttf",
}

def font(name: str, size: int) -> ImageFont:
    return ImageFont.truetype(FONTS[name], size)
```

### 2.3 QR Code Helper

File: `lib/qr.py`

```python
def make_qr(url: str, size: int = 70) -> Image:
    """Generate a PIL Image of a QR code at the given pixel size."""
    ...
```

### 2.4 Text Layout Helper

File: `lib/text.py`

```python
def wrap_text(text: str, font: ImageFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    ...

def draw_centered_text(draw, text, font, y, canvas_width, fill):
    """Draw a single line of text horizontally centred."""
    ...
```

### 2.5 HTTP Fetch with Timeout

File: `lib/fetch.py`

Pi Zero W has slow HTTPS. All network calls go through this wrapper:

```python
import urllib.request
import ssl
import json

TIMEOUT = 30  # seconds — generous for Pi Zero W SSL

def fetch_json(url: str, timeout=TIMEOUT) -> dict:
    """Fetch JSON from URL. Returns parsed dict or raises."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode())

def fetch_image(url: str, timeout=60) -> Image:
    """Fetch image from URL and return as PIL Image."""
    req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")
```

No `requests` library — pure stdlib to minimize dependencies.

---

## 3. Mode: Museo

**File:** `modes/museo.py`  
**Interval:** 300 seconds (5 minutes)  
**Network:** Required (fetches artwork images from museum APIs)

### 3.1 Supported Museums

Each museum is a provider class in `modes/museo_providers/`:

#### The Metropolitan Museum of Art (New York)

- **File:** `modes/museo_providers/met.py`
- **API base:** `https://collectionapi.metmuseum.org/public/collection/v1/`
- **Auth:** None
- **Collection:** ~470,000 objects, ~200,000+ public domain with images
- **Cache strategy:**
  - Endpoint to get ALL valid public-domain object IDs:
    `GET /search?hasImages=true&isPublicDomain=true&q=*`
  - Returns `{"total": N, "objectIDs": [1, 2, 3, ...]}`
  - Cache this full ID list to `cache/met_ids.json`
- **Object fetch:** `GET /objects/{objectID}`
- **Image field:** `primaryImageSmall` (JPEG, ~600px wide — ideal for Pi Zero)
- **Metadata fields:** `title`, `artistDisplayName`, `objectDate`, `department`, `repository`, `objectURL`

#### Art Institute of Chicago

- **File:** `modes/museo_providers/aic.py`
- **API base:** `https://api.artic.edu/api/v1/`
- **Auth:** None
- **Collection:** ~50,000 CC0 public domain works
- **Cache strategy:**
  - Endpoint: `GET /artworks/search?query[term][is_public_domain]=true&limit=0&fields=id`
  - Returns `{"pagination": {"total": N}}` — use `total` to know the range
  - To get a random artwork: `GET /artworks/search?query[term][is_public_domain]=true&limit=1&page={random_1_to_total}&fields=id,title,artist_display,date_display,image_id`
  - AIC does not return a full ID dump easily, so we use the paginated random approach
  - Cache `total` count to `cache/aic_total.json`
- **Image URL construction:** `https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg`
- **Metadata fields:** `title`, `artist_display`, `date_display`, `image_id`

#### Cleveland Museum of Art

- **File:** `modes/museo_providers/cleveland.py`
- **API base:** `https://openaccess-api.clevelandart.org/api/artworks/`
- **Auth:** None
- **Collection:** ~61,000 CC0 records with metadata, subset with images
- **Cache strategy:**
  - Endpoint: `GET /api/artworks/?has_image=1&cc0=1&limit=0`
  - Returns `{"info": {"total": N}}`
  - For random: `GET /api/artworks/?has_image=1&cc0=1&limit=1&skip={random}`
  - Cache `total` to `cache/cleveland_total.json`
- **Image field:** In `images.web.url` nested object
- **Metadata fields:** `title`, `creators[0].description`, `creation_date`, `collection`, `url`

### 3.2 Cache System — 24-Hour Refresh

File: `modes/museo_cache.py`

```python
CACHE_DIR = "cache/"
CACHE_MAX_AGE = 86400  # 24 hours in seconds

class MuseoCache:
    def needs_refresh(self, provider_name: str) -> bool:
        """Check if cache file is older than 24h or missing."""
        cache_file = f"{CACHE_DIR}{provider_name}_ids.json"
        if not os.path.exists(cache_file):
            return True
        age = time.time() - os.path.getmtime(cache_file)
        return age > CACHE_MAX_AGE

    def refresh(self, provider: MuseoProvider) -> None:
        """Fetch fresh ID list / total count from provider API.
        This runs once per day, typically at first render after midnight.
        
        For Met: fetches full objectID list (~2-5MB JSON, takes ~30-60s on Pi Zero).
        For AIC/Cleveland: fetches only total count (tiny JSON, <1s).
        """
        data = provider.fetch_catalogue()
        with open(f"{CACHE_DIR}{provider.name}_ids.json", "w") as f:
            json.dump(data, f)

    def get_random_id(self, provider_name: str) -> int | str:
        """Pick a random item from cached catalogue."""
        ...
```

**Refresh flow:**
1. At each Museo render, check `needs_refresh()` for ALL enabled providers
2. If any provider needs refresh, refresh it BEFORE picking an artwork
3. The Met refresh is the heaviest (~2-5MB download) — do it first, once per day
4. AIC and Cleveland refreshes are tiny (just a total count)
5. If refresh fails (network error), keep using stale cache and log the error
6. If there is NO cache at all (first boot, no network), use fallback

### 3.3 Provider Selection

File: `modes/museo.py`

Configuration in `config/museo.json`:

```json
{
  "providers": {
    "met": {"enabled": true, "weight": 3},
    "aic": {"enabled": true, "weight": 2},
    "cleveland": {"enabled": true, "weight": 1}
  }
}
```

Selection logic:
```python
def pick_provider(config) -> MuseoProvider:
    """Weighted random selection among enabled providers."""
    enabled = [(name, p) for name, p in config["providers"].items() if p["enabled"]]
    weights = [p["weight"] for _, p in enabled]
    chosen_name = random.choices([n for n, _ in enabled], weights=weights, k=1)[0]
    return PROVIDERS[chosen_name]
```

### 3.4 Render Pipeline

```python
def render(self) -> Image:
    # 1. Check cache, refresh if needed
    for provider in self.enabled_providers:
        if self.cache.needs_refresh(provider.name):
            try:
                self.cache.refresh(provider)
            except Exception as e:
                error_log.record("museo", f"Cache refresh failed for {provider.name}: {e}")

    # 2. Pick random provider (weighted) and random artwork
    provider = pick_provider(self.config)
    object_data = None
    attempts = 0
    while object_data is None and attempts < 5:
        try:
            obj_id = self.cache.get_random_id(provider.name)
            object_data = provider.fetch_object(obj_id)
            # Verify it has an image URL
            img_url = provider.get_image_url(object_data)
            if not img_url:
                object_data = None
                attempts += 1
                continue
        except Exception:
            attempts += 1

    if object_data is None:
        raise RuntimeError("Failed to fetch artwork after 5 attempts")

    # 3. Download image
    artwork_img = fetch_image(img_url, timeout=60)

    # 4. Compose frame
    canvas = self._compose_frame(artwork_img, object_data, provider)

    # 5. Dither to 7 colours
    return dither_floyd_steinberg(canvas)
```

### 3.5 Visual Layout

```
┌────────────────────────────────────────────┐
│ 10px margin                                │
│  ┌──────────────────────────────────────┐  │
│  │                                      │  │
│  │        Artwork image                 │  │
│  │        (cover-cropped to fill)       │  │
│  │        780 × 395 px                  │  │
│  │                                      │  │
│  └──────────────────────────────────────┘  │
│─ ─ ─ ─ ─ ─ thin rule ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
│  Title of Artwork          Signika Bold 18 │
│  Artist Name, Date         Signika 14      │  ┌──────┐
│  Museum Name               Inconsolata 11  │  │  QR  │
│                                            │  └──────┘
└────────────────────────────────────────────┘
```

### 3.6 Fallback

If all network calls fail, render a "Museo Offline" frame:
- Solid white background
- "MUSEO" in large Lobster
- "La connessione non è disponibile" in Taviraj italic
- Timestamp of last successful render (read from `cache/museo_last_success.txt`)

---

## 4. Mode: Koan

**File:** `modes/koan.py`  
**Interval:** 600 seconds (10 minutes — allows for slow LLM generation)  
**Network:** NOT required — fully offline, runs local LLM  

### 4.1 Concept

A tiny LLM running directly on the Pi Zero W generates existential haiku from its own perspective as an AI. Each haiku is seeded with a concept word drawn from a curated list. The result is displayed with large typographic treatment.

### 4.2 Seed System

File: `assets/koan_seeds.json`

A curated list of ~200 concept words across categories:

```json
{
  "existence": ["silenzio", "vuoto", "eco", "ombra", "sogno", "memoria", "oblio"],
  "computation": ["calcolo", "numero", "ciclo", "bit", "segnale", "errore", "overflow"],
  "nature": ["luce", "acqua", "pietra", "radice", "seme", "polvere", "vento"],
  "perception": ["specchio", "colore", "forma", "confine", "orizzonte", "riflesso"],
  "time": ["istante", "attesa", "alba", "crepuscolo", "entropia", "ritorno"],
  "emotion": ["dubbio", "meraviglia", "nostalgia", "solitudine", "gioia", "paura"],
  "language": ["parola", "nome", "verso", "domanda", "risposta", "traduzione"]
}
```

Selection: `random.choice()` across all categories, flattened. Keep a history of last 50 seeds used (in `cache/koan_history.json`) to avoid repeats.

### 4.3 LLM Prompt

```
You are a tiny artificial mind running on a $5 computer, 
consuming 2 watts of electricity, thinking very slowly.
Write ONE haiku (5-7-5 syllables) about: {seed_word}
Write from your own perspective as an AI.
Output ONLY the three lines of the haiku. Nothing else.
Language: Italian.
```

For variety, rotate among 3-4 prompt variants:
- The "tiny AI" perspective above
- A "digital monk" perspective: "You are a digital monk in a silicon monastery..."
- A "dreaming machine" perspective: "You are a machine that has just learned to dream..."
- A "observer" perspective: "You observe the world through a single eye that refreshes every 5 minutes..."

### 4.4 Output Parsing

```python
def parse_haiku(raw_output: str) -> list[str] | None:
    """Extract 3 lines from LLM output. Returns None if invalid."""
    # Strip leading/trailing whitespace and empty lines
    lines = [l.strip() for l in raw_output.strip().split("\n") if l.strip()]
    
    # Accept 3 lines
    if len(lines) == 3:
        # Sanity check: each line should be 2-40 chars
        if all(2 <= len(l) <= 60 for l in lines):
            return lines
    
    # Try to extract from verbose output (model added preamble)
    # Look for 3 consecutive short lines
    for i in range(len(lines) - 2):
        candidate = lines[i:i+3]
        if all(2 <= len(l) <= 60 for l in candidate):
            return candidate
    
    return None  # trigger fallback
```

### 4.5 Visual Layout

```
┌────────────────────────────────────────────┐
│                                            │
│                                            │
│                                            │
│         prima riga dell'haiku              │  Taviraj 28pt
│       seconda riga dell'haiku              │  Taviraj 28pt
│         terza riga dell'haiku              │  Taviraj 28pt
│                                            │
│                          ◯                 │  geometric glyph
│                                            │
│                                            │
│                     · silenzio ·            │  Inconsolata 12pt
│                                            │
│   KOAN №247                                │  Inconsolata 10pt
│                                            │
└────────────────────────────────────────────┘
```

- Background: solid White (or pale Yellow — alternate daily)
- Haiku text: Black, centred, Taviraj Regular 28pt
- Seed word: Green or Blue, centred, Inconsolata 12pt with interpuncts
- Geometric glyph: generated from `hash(haiku_text) % 6` → circle, triangle, square, line, diamond, cross. Drawn in Red or Orange at ~20px. Centred below haiku.
- Koan number: sequential, stored in `cache/koan_counter.txt`, incremented per successful generation. Bottom-left in Inconsolata 10pt, faint grey.

### 4.6 Fallback

Pre-generated archive: `assets/koan_fallback.json` — 100+ haiku generated offline (by running the LLM on a faster machine or by hand). If the LLM fails 3 times in a row, pick randomly from this archive. Mark the frame with a tiny "◆" instead of "◯" to indicate it's a fallback.

---

## 5. Mode: Tessera

**File:** `modes/tessera.py`  
**Interval:** 600 seconds (10 minutes — same as Koan due to LLM)  
**Network:** NOT required — fully offline  

### 5.1 Concept

The LLM acts as a "creative director" — it picks an artistic style, a conceptual theme, and a mood from curated lists. Then a dispatch table of pure-Python/Pillow generative algorithms renders the artwork. Each piece is unique and numbered.

### 5.2 LLM Prompt

```
You are an art director choosing parameters for a generative artwork.
Pick ONE from each list:

STYLE: mondrian, bauhaus, memphis, truchet, suprematist, 
       pointillist, woven, concreteart, destijl, opart
THEME: equilibrio, tensione, ritmo, silenzio, crescita, 
       frammentazione, convergenza, risonanza, gravità, espansione
MOOD: calm, energetic, minimal, playful, solemn

Reply ONLY in this exact format:
STYLE: xxx
THEME: yyy
MOOD: zzz
```

### 5.3 Output Parsing

```python
def parse_tessera_params(raw: str) -> dict | None:
    """Extract STYLE, THEME, MOOD from LLM output."""
    result = {}
    for line in raw.strip().split("\n"):
        line = line.strip().upper()
        for key in ["STYLE", "THEME", "MOOD"]:
            if line.startswith(f"{key}:"):
                value = line.split(":", 1)[1].strip().lower()
                # Validate against known values
                if value in VALID_VALUES[key.lower()]:
                    result[key.lower()] = value
    
    if len(result) == 3:
        return result
    return None  # trigger random fallback
```

### 5.4 Generative Algorithms

File: `modes/tessera_styles/` — one file per style.

Each style is a function: `def render(mood: str, palette: list, w: int, h: int) -> Image`

The `mood` parameter maps to numeric controls:

```python
MOOD_PARAMS = {
    "calm":      {"density": 0.3, "symmetry": 0.7, "max_elements": 15},
    "energetic": {"density": 0.8, "symmetry": 0.3, "max_elements": 50},
    "minimal":   {"density": 0.15, "symmetry": 0.5, "max_elements": 8},
    "playful":   {"density": 0.6, "symmetry": 0.2, "max_elements": 35},
    "solemn":    {"density": 0.4, "symmetry": 0.8, "max_elements": 12},
}
```

Minimum styles to implement at launch (4):

#### mondrian — Recursive Rectangle Subdivision
- Start with full canvas
- Recursively split into rectangles (horizontal or vertical)
- Fill some rectangles with colour, leave others white
- Draw black borders between all rectangles
- Mood: density controls split probability, minimal → fewer splits

#### memphis — Sottsass-Inspired Pattern
- Background: one solid colour (or two-tone split)
- Scatter geometric shapes: triangles, circles, zigzag lines, squiggles
- Use ALL 7 colours aggressively
- Add "confetti" dots pattern in background areas
- Diagonal stripes as accents
- Mood: playful → max confetti; calm → fewer elements, pastels

#### truchet — Tile-Based Generative Pattern
- Divide canvas into NxM grid of square cells
- Each cell randomly picks from tile variants (quarter-circle arcs, diagonal lines)
- 2-3 colours only, high contrast
- Creates mesmerizing flow patterns
- Mood: density controls grid resolution (more cells = finer pattern)

#### suprematist — Malevich-Style Floating Geometry
- White background
- Floating rectangles, circles, crosses at various angles
- Black, red, yellow, blue only
- Off-centre composition, deliberate imbalance
- Mood: minimal → 3-4 shapes; energetic → 12+ shapes with rotation

Additional styles (implement in phase 2):

- **pointillist** — field of coloured dots, varying size by region
- **woven** — Anni Albers-style interlocking horizontal/vertical bands
- **concreteart** — Swiss concrete art (Max Bill): mathematical curves, precise geometry
- **destijl** — stricter Mondrian: only primary colours + black/white, only right angles
- **opart** — optical illusion patterns: concentric circles, moiré, wave interference

### 5.5 Visual Layout

```
┌────────────────────────────────────────────┐
│                                            │
│                                            │
│                                            │
│       [Full-bleed generative artwork]      │
│              780 × 440 px                  │
│                                            │
│                                            │
│                                            │
├────────────────────────────────────────────┤
│  Tessera №142 · memphis · equilibrio       │  Inconsolata 10pt
└────────────────────────────────────────────┘
```

Bottom strip: 30px, white background, metadata in small Inconsolata. The artwork itself fills the rest.

### 5.6 Fallback

If LLM fails: use `random.choice()` for style + theme + mood from the same valid lists. The render pipeline works identically — the only difference is who picked the parameters (LLM vs random). This means Tessera NEVER fails completely. Mark the frame with "·R·" (random) instead of "·AI·" in the bottom strip to distinguish.

---

## 6. Mode: Cucina

**File:** `modes/cucina.py`  
**Interval:** 300 seconds (5 minutes)  
**Network:** Required (fetches from TheMealDB)

### 6.1 Concept

A random dish from world cuisines, displayed as a food-photography frame with recipe title, origin, and category. It's a quiet daily suggestion — not a recipe app, not a task. You glance at it and think "oh, pad thai tonight maybe." The image-first approach makes it the most visually warm mode on e-ink.

### 6.2 Data Source

**TheMealDB** — free, public test API key (`1`):
- Random meal: `https://www.themealdb.com/api/json/v1/1/random.php`
- No auth required for the test key
- Returns a single random meal with full metadata + image URL

**Response structure (relevant fields):**
```json
{
  "meals": [{
    "idMeal": "52772",
    "strMeal": "Teriyaki Chicken Casserole",
    "strCategory": "Chicken",
    "strArea": "Japanese",
    "strMealThumb": "https://www.themealdb.com/images/media/meals/wvpsxx1468256321.jpg",
    "strTags": "Meat,Casserole",
    "strYoutube": "https://www.youtube.com/watch?v=4aZr5hZXP_s",
    "strSource": "http://www.ثhttps://..."
  }]
}
```

Key fields:
- `strMeal` — dish name (always English)
- `strArea` — cuisine origin ("Japanese", "Italian", "Mexican", etc.)
- `strCategory` — food category ("Chicken", "Seafood", "Dessert", etc.)
- `strMealThumb` — 320×320 JPEG thumbnail (small, fast to download on Pi Zero)
- `strTags` — comma-separated tags (optional, can be null)

### 6.3 Visual Layout

```
┌────────────────────────────────────────────┐
│                                            │
│   ┌──────────────┐                         │
│   │              │  TERIYAKI CHICKEN        │  Signika Bold 22pt
│   │   Food       │  CASSEROLE              │
│   │   Photo      │                         │
│   │  320×320     │  Japanese · Chicken      │  Inconsolata 13pt
│   │  (dithered)  │                         │
│   │              │  ─────────              │
│   │              │                         │
│   │              │  "Meat, Casserole"       │  Taviraj Italic 12pt
│   └──────────────┘                         │
│                                            │
│                                       [QR] │
│   CUCINA                                   │  Inconsolata 10pt
└────────────────────────────────────────────┘
```

- Left side: food photo, square, dithered to 7 colours — takes up roughly 320×320px area (scaled to ~360px after padding)
- Right side: text layout with dish name (large), origin · category (medium), tags (italic, small)
- QR code: links to YouTube tutorial (`strYoutube`) if available, otherwise to source URL
- Background: warm White (the natural e-ink paper tint works perfectly for food)
- Mode label "CUCINA" in bottom-left, subtle

**Colour note:** food photography dithers beautifully to this palette — reds/oranges for sauces and meats, greens for herbs/vegetables, yellows for pasta/rice/cheese, browns (via dithered red+black+orange) for bread/chocolate. This will be one of the most visually striking modes.

### 6.4 Image Handling

```python
def fetch_meal_image(thumb_url: str) -> Image:
    """Fetch meal thumbnail. TheMealDB serves 320x320 JPEGs — 
    small enough for Pi Zero W. Downsample further if needed."""
    img = fetch_image(thumb_url, timeout=30)
    # Ensure max 360px on longest side
    img.thumbnail((360, 360), Image.LANCZOS)
    return img
```

The `strMealThumb` images are already 320×320 — this is generous for e-ink. No need to request a smaller version. The JPEG is typically 20-60KB, fast even on Pi Zero W's slow WiFi.

### 6.5 Render Pipeline

```python
def render(self) -> Image:
    # 1. Fetch random meal
    data = fetch_json("https://www.themealdb.com/api/json/v1/1/random.php")
    meal = data["meals"][0]
    
    # 2. Download thumbnail
    img = fetch_meal_image(meal["strMealThumb"])
    
    # 3. Compose frame
    canvas = Image.new("RGB", (800, 480), (245, 240, 230))
    draw = ImageDraw.Draw(canvas)
    
    # Paste food photo (left side)
    canvas.paste(img, (20, 40))
    
    # Text (right side)
    text_x = 400
    draw_text_block(draw, meal["strMeal"], text_x, 50, 
                    font("signika_bold", 22), max_width=370)
    
    origin_cat = f'{meal["strArea"]} · {meal["strCategory"]}'
    draw.text((text_x, 130), origin_cat, 
              fill=(0, 128, 0), font=font("inconsolata", 13))
    
    if meal.get("strTags"):
        draw.text((text_x, 165), meal["strTags"], 
                  fill=(120, 120, 120), font=font("taviraj_italic", 12))
    
    # QR code
    qr_url = meal.get("strYoutube") or meal.get("strSource") or \
             f'https://www.themealdb.com/meal/{meal["idMeal"]}'
    qr = make_qr(qr_url, 58)
    canvas.paste(qr, (720, 400))
    
    # 4. Dither
    return dither_floyd_steinberg(canvas)
```

### 6.6 Fallback

If the API is down, render a "Cucina Offline" frame with a simple fork-and-knife icon (drawn with PIL primitives — two rectangles for the knife, ellipse+lines for the fork, a circle for the plate) and "Torna dopo" in Taviraj. Charming, not broken.

### 6.7 API Key Note

The test key `1` is documented by TheMealDB for development and personal projects. TaleVision is a personal, non-commercial, single-device project. If you ever distribute publicly, request a free API key at `https://www.themealdb.com/api.php`. The free tier supports personal/small projects.

---

## 7. Mode: Atlante

**File:** `modes/atlante.py`  
**Interval:** 300 seconds (5 minutes)  
**Network:** Required (fetches from REST Countries + flag images)

### 7.1 Concept

A random country's flag fills the display with bold colour, accompanied by the country name (in the user's language), capital, population, languages, and a simplified map silhouette. Flags are the single best subject for a 7-colour e-ink palette — most national flags use exactly the kind of flat, saturated, limited-colour compositions that ACeP excels at. Many flags contain only 2-3 of the exact 7 colours available.

### 7.2 Data Source

**REST Countries API** — free, no auth:
- All countries: `https://restcountries.com/v3.1/all?fields=name,cca2,capital,population,languages,flags,region,subregion`
- Single country: `https://restcountries.com/v3.1/alpha/{cca2}?fields=name,cca2,capital,population,languages,flags,region,subregion,latlng,borders`

**Response structure (relevant fields):**
```json
{
  "name": {
    "common": "Japan",
    "official": "Japan",
    "nativeName": {
      "jpn": {"official": "日本国", "common": "日本"}
    }
  },
  "cca2": "JP",
  "capital": ["Tokyo"],
  "population": 125836021,
  "languages": {"jpn": "Japanese"},
  "flags": {
    "png": "https://flagcdn.com/w320/jp.png",
    "svg": "https://flagcdn.com/jp.svg"
  },
  "region": "Asia",
  "subregion": "Eastern Asia"
}
```

**Flag image:** `https://flagcdn.com/w320/{cca2_lowercase}.png` — fixed 320px-wide PNG. Small, fast. Perfect for Pi Zero W.

### 7.3 Cache System

On first run (or every 24h), fetch the full country list and cache locally:

```python
# cache/atlante_countries.json — ~250 countries, ~200KB
def refresh_country_cache():
    url = "https://restcountries.com/v3.1/all?fields=name,cca2,capital,population,languages,flags,region,subregion"
    countries = fetch_json(url)
    # Filter out entries with missing flags
    countries = [c for c in countries if c.get("flags", {}).get("png")]
    with open("cache/atlante_countries.json", "w") as f:
        json.dump(countries, f)
    return countries
```

Then each render just picks `random.choice(countries)` from the local cache and only fetches the flag image over the network.

### 7.4 Visual Layout

```
┌────────────────────────────────────────────┐
│                                            │
│   ┌──────────────────────────────────────┐ │
│   │                                      │ │
│   │         FLAG IMAGE                   │ │
│   │         (dithered to 7 colours)      │ │
│   │         760 × 320 px                 │ │
│   │                                      │ │
│   └──────────────────────────────────────┘ │
│                                            │
│   GIAPPONE                    Signika 26pt │
│   日本 · Japan       native + EN fallback  │
│                                            │
│   ● Tokyo    ● 125.8M    ● 日本語     [QR] │
│   ATLANTE · Asia · Eastern Asia            │
└────────────────────────────────────────────┘
```

- Flag: centred, scaled to fill ~760×320px area (maintaining aspect ratio, many flags are 3:2 or 2:1)
- Country name: large Signika Bold, in the TaleVision UI language (use `name.common` for EN, or `name.nativeName.{lang}.common` for native script). Show native name alongside if different from display language.
- Three micro-facts in a row: capital, population (formatted as "125.8M" / "4.2K" etc.), languages
- QR: links to Wikipedia page for the country (`https://{lang}.wikipedia.org/wiki/{country_name}`)
- Bottom strip: mode label + region/subregion

### 7.5 Population Formatting

```python
def format_population(pop: int) -> str:
    if pop >= 1_000_000_000:
        return f"{pop / 1_000_000_000:.1f}B"
    elif pop >= 1_000_000:
        return f"{pop / 1_000_000:.1f}M"
    elif pop >= 1_000:
        return f"{pop / 1_000:.1f}K"
    return str(pop)
```

### 7.6 Language Display

```python
def format_languages(langs: dict, max_show: int = 3) -> str:
    """Show up to 3 language names, comma-separated."""
    names = list(langs.values())[:max_show]
    result = ", ".join(names)
    if len(langs) > max_show:
        result += f" +{len(langs) - max_show}"
    return result
```

### 7.7 Flag Dithering — Why It's Special

Flags are the ideal subject for ACeP 7-colour. Consider:

- **Japan** — red circle on white. Uses exactly 2 of the 7 palette colours. Renders PERFECTLY.
- **Italy** — green, white, red vertical stripes. 3 palette colours, pixel-perfect.
- **Sweden** — blue with yellow cross. 2 exact palette colours.
- **Germany** — black, red, yellow. 3 exact palette colours.
- **Brazil** — green, yellow, blue, white. 4 palette colours.
- **South Africa** — black, green, yellow, red, white, blue. 6 of 7!

Even flags with colours outside the palette (like France's particular blue, or India's deep orange) will dither cleanly because the shapes are flat-fill with hard edges — Atkinson dithering handles this better than Floyd-Steinberg for flags.

**Use Atkinson dithering for flags**, not Floyd-Steinberg. Atkinson preserves hard edges and flat colour areas much better, which is exactly what flags need. Floyd-Steinberg would introduce unnecessary speckling in large solid-colour areas.

```python
# In the render pipeline:
flag_dithered = dither_atkinson(flag_img, EINK_PALETTE)  # NOT floyd_steinberg
```

### 7.8 Render Pipeline

```python
def render(self) -> Image:
    # 1. Load cache, refresh if needed
    if self.cache_needs_refresh():
        try:
            self.refresh_country_cache()
        except Exception as e:
            error_log.record("atlante", f"Cache refresh failed: {e}")
    
    countries = self.load_country_cache()
    if not countries:
        raise RuntimeError("No country cache available")
    
    # 2. Pick random country
    country = random.choice(countries)
    
    # 3. Fetch flag image
    flag_url = country["flags"]["png"]
    flag_img = fetch_image(flag_url, timeout=30)
    
    # 4. Compose frame
    canvas = Image.new("RGB", (800, 480), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    
    # Scale flag to fill ~760×320, maintain aspect ratio
    fw, fh = flag_img.size
    scale = min(760 / fw, 320 / fh)
    flag_resized = flag_img.resize(
        (int(fw * scale), int(fh * scale)), Image.LANCZOS)
    # Centre horizontally
    flag_x = (800 - flag_resized.width) // 2
    canvas.paste(flag_resized, (flag_x, 15))
    
    # Country name
    name = country["name"]["common"]
    draw.text((20, 350), name.upper(), fill=(0, 0, 0), 
              font=font("signika_bold", 26))
    
    # Native name (if different)
    native_names = country.get("name", {}).get("nativeName", {})
    if native_names:
        first_native = list(native_names.values())[0].get("common", "")
        if first_native and first_native.lower() != name.lower():
            draw.text((20, 382), first_native, fill=(100, 100, 100),
                      font=font("taviraj", 14))
    
    # Micro-facts row
    facts_y = 410
    capital = country.get("capital", ["—"])[0]
    pop = format_population(country.get("population", 0))
    langs = format_languages(country.get("languages", {}))
    
    facts_text = f"● {capital}    ● {pop}    ● {langs}"
    draw.text((20, facts_y), facts_text, fill=(0, 0, 0), 
              font=font("inconsolata", 12))
    
    # Region
    region = country.get("region", "")
    subregion = country.get("subregion", "")
    region_text = f"ATLANTE · {region}"
    if subregion:
        region_text += f" · {subregion}"
    draw.text((20, 450), region_text, fill=(140, 140, 140),
              font=font("inconsolata", 10))
    
    # QR to Wikipedia
    wiki_url = f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}"
    qr = make_qr(wiki_url, 58)
    canvas.paste(qr, (720, 400))
    
    # 5. Dither — use Atkinson for flags!
    return dither_atkinson(canvas)
```

### 7.9 Fallback

If network is unavailable and no cache exists, render a "globe" frame:
- Simple circle (outline) representing Earth, drawn with PIL
- Longitude/latitude grid lines inside
- "ATLANTE · Offline" below
- If cache exists but flag download fails, show the text metadata without the flag image (still useful)

---

## 8. LLM Engine (shared by Koan & Tessera)

**File:** `lib/llm.py`

### 8.1 Setup

Use **llama.zero** (fork of llama.cpp for ARMv6):
- Repo: `https://github.com/pham-tuan-binh/llama.zero`
- Build on the Pi Zero W itself (slow but one-time)
- Binary location: `/opt/llama.zero/llama-cli`

Model: **SmolLM2-135M-Instruct-GGUF** (Q4_K_M quantisation):
- Source: `https://huggingface.co/unsloth/SmolLM2-135M-Instruct-GGUF/resolve/main/SmolLM2-135M-Instruct-Q4_K_M.gguf`
- Size on disk: ~100MB
- Runtime RAM: ~80-100MB via mmap
- Location: `/opt/llama.zero/models/smollm2-135m-instruct-q4km.gguf`

If SmolLM2-135M produces output that is too incoherent, upgrade to **SmolLM-360M** (~250MB). Test both during setup and pick the smallest that produces usable haiku.

### 8.2 Python Wrapper

```python
import subprocess
import shlex

LLM_BINARY = "/opt/llama.zero/llama-cli"
LLM_MODEL = "/opt/llama.zero/models/smollm2-135m-instruct-q4km.gguf"
LLM_TIMEOUT = 300  # 5 minutes max — generous for Pi Zero W

def llm_generate(prompt: str, max_tokens: int = 64, ctx_size: int = 256) -> str | None:
    """Run LLM inference via subprocess. Returns generated text or None on failure."""
    cmd = [
        LLM_BINARY,
        "-m", LLM_MODEL,
        "-p", prompt,
        "-n", str(max_tokens),
        "--ctx-size", str(ctx_size),
        "--temp", "0.8",
        "--top-k", "40",
        "--top-p", "0.9",
        "--repeat-penalty", "1.1",
        "--threads", "1",  # Pi Zero W has only 1 core
        "--no-display-prompt",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=LLM_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            error_log.record("llm", f"Non-zero exit: {result.returncode}, stderr: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        error_log.record("llm", f"Timeout after {LLM_TIMEOUT}s")
        return None
    except Exception as e:
        error_log.record("llm", f"Subprocess error: {e}")
        return None
```

### 8.3 Generation Timing

Expected performance on Pi Zero W (ARM11 1GHz, no NEON):

| Model | Load time | Tokens/sec | 30-token haiku | 20-token params |
|-------|-----------|------------|----------------|-----------------|
| SmolLM2-135M Q4_K_M | ~10-20s | ~0.3-0.5 | **60-100s** | **40-70s** |
| SmolLM-360M Q4_K_M | ~20-40s | ~0.1-0.3 | **100-300s** | **70-200s** |

These times are acceptable for a 10-minute refresh interval. The LLM generates while the previous frame is displayed. The total cycle is: generate → render → display → wait.

### 8.4 Retry Logic

```python
MAX_LLM_RETRIES = 3

def generate_with_retries(prompt: str, parser_fn, max_tokens=64) -> any:
    """Try LLM generation up to MAX_LLM_RETRIES times.
    parser_fn(raw_text) should return parsed result or None."""
    for attempt in range(MAX_LLM_RETRIES):
        raw = llm_generate(prompt, max_tokens=max_tokens)
        if raw is not None:
            parsed = parser_fn(raw)
            if parsed is not None:
                return parsed
            else:
                error_log.record("llm", 
                    f"Parse failed (attempt {attempt+1}): {raw[:100]}")
        else:
            error_log.record("llm", f"Generation failed (attempt {attempt+1})")
    
    return None  # all retries exhausted — caller must use fallback
```

---

## 9. Error Reporting System

**File:** `lib/error_log.py`

### 9.1 Error Storage

Errors are stored in a SQLite database: `data/errors.db`

```sql
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- ISO 8601
    mode TEXT NOT NULL,                -- "museo", "koan", "tessera", "llm", "system"
    level TEXT NOT NULL DEFAULT 'ERROR', -- "ERROR", "WARN", "INFO"
    message TEXT NOT NULL,
    details TEXT,                       -- traceback or raw LLM output
    resolved INTEGER DEFAULT 0          -- 0 = unresolved, 1 = resolved
);

CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    mode TEXT NOT NULL,
    event TEXT NOT NULL,               -- "render_ok", "render_fallback", "cache_refresh"
    duration_ms INTEGER,               -- render time in milliseconds
    details TEXT                        -- e.g. museum name, style chosen
);
```

### 9.2 Logging API

```python
class ErrorLog:
    def __init__(self, db_path="data/errors.db"):
        self.db = sqlite3.connect(db_path)
        self._init_tables()

    def record(self, mode: str, message: str, details: str = None, 
               level: str = "ERROR"):
        """Log an error or warning."""
        ...

    def success(self, mode: str, duration_ms: int = None, details: str = None):
        """Log a successful render."""
        ...

    def get_recent_errors(self, limit=50) -> list[dict]:
        """Get recent errors for web UI display."""
        ...

    def get_stats(self, hours=24) -> dict:
        """Aggregate stats for dashboard."""
        ...

    def clear_resolved(self):
        """Delete errors marked as resolved."""
        ...
```

### 9.3 Web Interface — Error Dashboard

TaleVision already has a WebUI (Flask-based). Add a new route and a block at the bottom of the main page.

**Route:** `GET /errors`  
**Also:** Append a collapsible section at the bottom of the existing WebUI main page.

```html
<!-- At the bottom of the existing WebUI page -->
<details id="error-dashboard">
  <summary>
    🔧 Diagnostics 
    <span class="error-badge">{{ error_count }}</span>
  </summary>
  
  <div class="diag-section">
    <h3>Last 24h Summary</h3>
    <table>
      <tr><th>Mode</th><th>OK</th><th>Fallback</th><th>Errors</th><th>Avg Time</th></tr>
      {% for mode in stats %}
      <tr>
        <td>{{ mode.name }}</td>
        <td class="ok">{{ mode.ok_count }}</td>
        <td class="warn">{{ mode.fallback_count }}</td>
        <td class="err">{{ mode.error_count }}</td>
        <td>{{ mode.avg_duration_ms }}ms</td>
      </tr>
      {% endfor %}
    </table>
  </div>

  <div class="diag-section">
    <h3>Recent Errors</h3>
    {% for err in errors %}
    <div class="error-entry {{ err.level | lower }}">
      <span class="ts">{{ err.timestamp }}</span>
      <span class="mode-tag">{{ err.mode }}</span>
      <span class="msg">{{ err.message }}</span>
      {% if err.details %}
      <details><summary>Details</summary>
        <pre>{{ err.details }}</pre>
      </details>
      {% endif %}
    </div>
    {% endfor %}
  </div>

  <div class="diag-section">
    <h3>LLM Status</h3>
    <p>Model: {{ llm_model_name }}</p>
    <p>Last generation: {{ llm_last_gen_time }}s</p>
    <p>Last output: <code>{{ llm_last_output[:80] }}</code></p>
    <p>Success rate (24h): {{ llm_success_rate }}%</p>
  </div>

  <div class="diag-section">
    <h3>Cache Status</h3>
    {% for provider in museo_providers %}
    <p>{{ provider.name }}: 
      {{ provider.cached_count }} items, 
      age {{ provider.cache_age_hours }}h
      {% if provider.cache_age_hours > 24 %}⚠️ stale{% endif %}
    </p>
    {% endfor %}
  </div>

  <div class="diag-actions">
    <button onclick="fetch('/api/clear-errors', {method:'POST'})">
      Clear Resolved Errors
    </button>
    <button onclick="fetch('/api/refresh-cache', {method:'POST'})">
      Force Cache Refresh
    </button>
    <button onclick="fetch('/api/test-llm', {method:'POST'})">
      Test LLM
    </button>
  </div>
</details>
```

**API endpoints for the dashboard:**

```python
@app.route("/api/clear-errors", methods=["POST"])
def api_clear_errors():
    error_log.clear_resolved()
    return {"status": "ok"}

@app.route("/api/refresh-cache", methods=["POST"])
def api_refresh_cache():
    """Force refresh all museo caches regardless of age."""
    for provider in museo_providers:
        try:
            museo_cache.refresh(provider)
        except Exception as e:
            error_log.record("museo", f"Manual refresh failed: {e}")
    return {"status": "ok"}

@app.route("/api/test-llm", methods=["POST"])
def api_test_llm():
    """Run a quick LLM test and return the result."""
    start = time.time()
    raw = llm_generate("Write one line about the moon.", max_tokens=20)
    duration = time.time() - start
    return {
        "status": "ok" if raw else "failed",
        "output": raw,
        "duration_s": round(duration, 1),
    }
```

---

## 10. Terminal Test Suite

**File:** `test_modes.py`

Run with: `python3 test_modes.py [mode_name]`  
No arguments = run all tests.

### 10.1 Test: Museo

```bash
python3 test_modes.py museo
```

Tests performed:
1. **API reachability** — can we reach each museum API?
   - `fetch_json("https://collectionapi.metmuseum.org/public/collection/v1/departments")`
   - `fetch_json("https://api.artic.edu/api/v1/artworks?limit=1")`
   - `fetch_json("https://openaccess-api.clevelandart.org/api/artworks/?limit=1")`
   - Report: `[MET] ✓ reachable (1.2s)` or `[MET] ✗ unreachable: timeout`

2. **Cache state** — is the cache present and fresh?
   - Check each provider's cache file age
   - Report: `[MET] cache: 14521 IDs, age 6.2h ✓`

3. **Random fetch** — can we fetch a random artwork end-to-end?
   - Pick random ID, fetch metadata, download image
   - Report: `[MET] fetch: "Water Lilies" by Claude Monet, image 640x480 ✓`

4. **Render test** — generate a full 800×480 dithered frame
   - Render and save to `test_output/museo_test.png`
   - Report: `[RENDER] museo_test.png saved (12.4s)`

5. **Fallback test** — does the fallback render correctly?
   - Save to `test_output/museo_fallback.png`

### 10.2 Test: Koan

```bash
python3 test_modes.py koan
```

Tests performed:
1. **LLM binary check** — is llama.zero compiled and accessible?
   - Check that `LLM_BINARY` exists and is executable
   - Report: `[LLM] binary: /opt/llama.zero/llama-cli ✓`

2. **Model file check** — is the GGUF model present?
   - Check file size matches expected
   - Report: `[LLM] model: smollm2-135m (98.4 MB) ✓`

3. **LLM smoke test** — can it generate ANY output?
   - Prompt: `"Say hello"`, max_tokens=10
   - Report: `[LLM] smoke test: "Hello! How can I" (23.4s, 0.43 tok/s) ✓`

4. **Haiku generation test** — full pipeline
   - Use seed "silenzio", full haiku prompt
   - Report parsed haiku or parse failure
   - Report: `[KOAN] haiku generated in 87.2s:`
     ```
     Nel vuoto digitale
     un pensiero si accende
     poi torna il silenzio
     ```

5. **Parse robustness test** — feed known good/bad outputs to parser
   - Test with: valid 3-line haiku → should parse
   - Test with: 5 lines of preamble then haiku → should extract
   - Test with: complete garbage → should return None
   - Report: `[PARSE] 3/3 test cases passed ✓`

6. **Render test** — generate frame from haiku
   - Save to `test_output/koan_test.png`

7. **Fallback test** — pick from archive and render
   - Save to `test_output/koan_fallback.png`

### 10.3 Test: Tessera

```bash
python3 test_modes.py tessera
```

Tests performed:
1. **LLM param generation** — can it pick style/theme/mood?
   - Full Tessera prompt
   - Report: `[TESSERA] LLM chose: style=memphis, theme=ritmo, mood=playful (45.1s) ✓`

2. **Parse test** — feed good/bad outputs
   - Report: `[PARSE] 3/3 test cases passed ✓`

3. **Style render tests** — render EACH implemented style
   - For each style, render with mood="calm" and mood="energetic"
   - Save to `test_output/tessera_{style}_{mood}.png`
   - Report: `[STYLE] mondrian/calm rendered (0.8s) ✓`
   - Report: `[STYLE] memphis/energetic rendered (1.2s) ✓`
   - etc.

4. **Full pipeline test** — LLM picks, renderer executes
   - Save to `test_output/tessera_full_test.png`

5. **Random fallback test** — verify random selection works when LLM returns None
   - Save to `test_output/tessera_fallback.png`

### 10.4 Test: Cucina

```bash
python3 test_modes.py cucina
```

Tests performed:
1. **API reachability** — can we reach TheMealDB?
   - `fetch_json("https://www.themealdb.com/api/json/v1/1/random.php")`
   - Report: `[MEALDB] ✓ reachable (0.8s)`

2. **Random meal fetch** — full metadata + image download
   - Fetch random meal, download thumbnail
   - Report: `[CUCINA] "Pad Thai" · Thai · Seafood · image 320×320 ✓`

3. **Render test** — full 800×480 dithered frame
   - Save to `test_output/cucina_test.png`
   - Report: `[RENDER] cucina_test.png saved (9.2s)`

4. **Null-field robustness** — handle missing strTags, strYoutube, strSource
   - Feed mock data with None/empty fields → should not crash
   - Report: `[PARSE] null-field handling 3/3 ✓`

5. **Fallback test** — render offline frame with fork-and-knife icon
   - Save to `test_output/cucina_fallback.png`

### 10.5 Test: Atlante

```bash
python3 test_modes.py atlante
```

Tests performed:
1. **API reachability** — can we reach REST Countries?
   - `fetch_json("https://restcountries.com/v3.1/alpha/JP?fields=name,flags")`
   - Report: `[RESTCOUNTRIES] ✓ reachable (0.6s)`

2. **Cache build** — fetch full country list, validate
   - Download all ~250 countries, filter those with flags
   - Report: `[CACHE] 249 countries cached (3.1s)`

3. **Flag download + dithering** — fetch a known flag, dither with Atkinson
   - Use Japan (JP) — simple, red on white, should dither perfectly
   - Save flag-only to `test_output/atlante_flag_jp.png`
   - Report: `[FLAG] JP flag downloaded and dithered ✓`

4. **Palette accuracy test** — check flags with exact palette matches
   - Fetch JP (red+white), SE (blue+yellow), DE (black+red+yellow)
   - After dithering, verify dominant colours are in EINK_PALETTE
   - Report: `[PALETTE] JP: 2 colours exact ✓  SE: 2 colours exact ✓  DE: 3 colours exact ✓`

5. **Render test** — full 800×480 frame with random country
   - Save to `test_output/atlante_test.png`

6. **Edge cases** — countries with long names, many languages, missing capitals
   - Test: "Bosnia and Herzegovina" (long name wrapping)
   - Test: South Africa (11 official languages — truncation)
   - Test: territories without capital (e.g. some small islands)
   - Report: `[EDGE] long name ✓  many langs ✓  no capital ✓`

7. **Fallback test** — render globe outline
   - Save to `test_output/atlante_fallback.png`

### 10.6 Test: Error System

```bash
python3 test_modes.py errors
```

1. **DB creation** — create fresh DB, insert test error
2. **Retrieval** — query recent errors
3. **Stats aggregation** — verify counts are correct
4. **Web endpoint** — start Flask briefly, hit `/errors` endpoint

### 10.7 Full Suite

```bash
python3 test_modes.py all
```

Runs all tests in sequence. At the end, prints a summary:

```
═══════════════════════════════════════
  TaleVision Test Suite — Results
═══════════════════════════════════════
  MUSEO
    API reachability .... MET ✓  AIC ✓  CLE ✓
    Cache state ......... MET ✓  AIC ✓  CLE ✓
    Random fetch ........ ✓ (14.2s)
    Render .............. ✓ (16.8s)
    Fallback ............ ✓
  
  KOAN
    LLM binary .......... ✓
    Model file .......... ✓ (98.4 MB)
    LLM smoke test ...... ✓ (23.4s, 0.43 tok/s)
    Haiku generation .... ✓ (87.2s)
    Parse robustness .... 3/3 ✓
    Render .............. ✓
    Fallback ............ ✓
  
  TESSERA
    LLM param gen ....... ✓ (45.1s)
    Parse robustness .... 3/3 ✓
    Style: mondrian ..... calm ✓  energetic ✓
    Style: memphis ...... calm ✓  energetic ✓
    Style: truchet ...... calm ✓  energetic ✓
    Style: suprematist .. calm ✓  energetic ✓
    Full pipeline ....... ✓
    Fallback ............ ✓
  
  CUCINA
    API reachability .... ✓
    Random fetch ........ ✓ (2.1s)
    Render .............. ✓ (9.2s)
    Null-field handling . 3/3 ✓
    Fallback ............ ✓
  
  ATLANTE
    API reachability .... ✓
    Cache build ......... 249 countries ✓
    Flag dithering ...... JP ✓  SE ✓  DE ✓
    Palette accuracy .... 3/3 exact ✓
    Render .............. ✓
    Edge cases .......... 3/3 ✓
    Fallback ............ ✓
  
  ERROR SYSTEM
    DB operations ....... ✓
    Web endpoints ....... ✓

  All test images saved to: test_output/
═══════════════════════════════════════
```

---

## 11. File Structure

```
talevision/
├── modes/
│   ├── __init__.py
│   ├── museo.py                  # Museo mode main
│   ├── museo_cache.py            # 24h cache system
│   ├── museo_providers/
│   │   ├── __init__.py
│   │   ├── base.py               # MuseoProvider abstract base
│   │   ├── met.py                # Metropolitan Museum
│   │   ├── aic.py                # Art Institute Chicago
│   │   └── cleveland.py          # Cleveland Museum of Art
│   ├── koan.py                   # Koan mode main
│   ├── tessera.py                # Tessera mode main
│   ├── cucina.py                 # Cucina mode main
│   ├── atlante.py                # Atlante mode main
│   └── tessera_styles/
│       ├── __init__.py
│       ├── mondrian.py
│       ├── memphis.py
│       ├── truchet.py
│       └── suprematist.py
├── lib/
│   ├── __init__.py
│   ├── dither.py                 # 7-colour dithering
│   ├── fonts.py                  # Font registry
│   ├── qr.py                     # QR code helper
│   ├── text.py                   # Text layout/wrapping
│   ├── fetch.py                  # HTTP fetch with timeout
│   ├── llm.py                    # LLM subprocess wrapper
│   └── error_log.py              # Error logging + SQLite
├── assets/
│   ├── fonts/                    # .ttf files
│   ├── koan_seeds.json           # 200 seed words
│   └── koan_fallback.json        # 100 pre-generated haiku
├── config/
│   └── museo.json                # Provider weights/enabled
├── cache/                        # Runtime caches (gitignored)
│   ├── met_ids.json
│   ├── aic_total.json
│   ├── cleveland_total.json
│   ├── atlante_countries.json
│   ├── museo_last_success.txt
│   ├── koan_history.json
│   └── koan_counter.txt
├── data/
│   └── errors.db                 # SQLite error/stats DB
├── templates/
│   └── errors.html               # Web UI error dashboard
├── test_modes.py                 # Terminal test suite
└── test_output/                  # Test-generated images (gitignored)
```

---

## 12. Implementation Order

### Phase 1 — Foundation (do first)
1. `lib/dither.py` — the 7-colour dithering engine (everything depends on this)
2. `lib/fonts.py`, `lib/text.py`, `lib/qr.py` — shared rendering helpers
3. `lib/fetch.py` — HTTP wrapper
4. `lib/error_log.py` — error logging + SQLite
5. Run: `python3 test_modes.py errors` to verify error system

### Phase 2 — Museo (network-dependent, no LLM)
1. `modes/museo_providers/base.py` — abstract base class
2. `modes/museo_providers/met.py` — Met provider (largest, test first)
3. `modes/museo_cache.py` — cache system with 24h refresh
4. `modes/museo.py` — main mode with render pipeline + fallback
5. Run: `python3 test_modes.py museo`
6. Then add AIC and Cleveland providers
7. Run full museo tests again

### Phase 3 — LLM Engine (the hard part)
1. Compile llama.zero on the Pi Zero W (estimate: 30-60 min compile time)
2. Download SmolLM2-135M-Instruct GGUF to SD card
3. Test raw CLI: `./llama-cli -m model.gguf -p "hello" -n 10`
4. Measure actual tokens/sec on THIS hardware
5. If too slow or incoherent, try SmolLM-360M or alternative tiny model
6. `lib/llm.py` — Python subprocess wrapper
7. Run: `python3 test_modes.py koan` (LLM smoke test + haiku test)

### Phase 4 — Koan
1. `assets/koan_seeds.json` — curate seed word list
2. `assets/koan_fallback.json` — pre-generate 100 haiku offline
3. `modes/koan.py` — mode with prompt rotation, parsing, rendering
4. Run: `python3 test_modes.py koan` (full pipeline)

### Phase 5 — Tessera
1. `modes/tessera_styles/mondrian.py` — first style (simplest algorithm)
2. `modes/tessera_styles/memphis.py` — second style (most visually distinctive)
3. `modes/tessera_styles/truchet.py` — third style
4. `modes/tessera_styles/suprematist.py` — fourth style
5. `modes/tessera.py` — main mode with LLM director + dispatch
6. Run: `python3 test_modes.py tessera` (per-style + full pipeline)

### Phase 6 — Cucina (quick win, no LLM)
1. `modes/cucina.py` — single-file mode, simple fetch→render pipeline
2. Implement food photo dithering (Floyd-Steinberg — food photography has gradients)
3. Text layout with dish name + origin + category
4. Fallback with fork-and-knife PIL drawing
5. Run: `python3 test_modes.py cucina`

### Phase 7 — Atlante (quick win, no LLM)
1. `modes/atlante.py` — single-file mode
2. Country cache system (24h refresh, same pattern as Museo)
3. Flag dithering — use Atkinson, NOT Floyd-Steinberg (flat colours, hard edges)
4. Population formatting, language display, native name handling
5. Fallback with globe outline
6. Run: `python3 test_modes.py atlante`

### Phase 8 — Web UI + Polish
1. Error dashboard HTML block for existing WebUI
2. API endpoints (`/api/test-llm`, `/api/refresh-cache`, `/api/clear-errors`)
3. Run: `python3 test_modes.py all` — full suite
4. Integration test: add new modes to TaleVision's mode playlist/rotation

---

## Notes for Implementation

- **Never `import requests`** — use stdlib `urllib.request` everywhere
- **Never `import numpy`** — use pure Python + Pillow only (memory constraint)
- **All file writes to `cache/` and `data/`** — these dirs are on the SD card, not tmpfs
- **Subprocess for LLM, not Python bindings** — llama.zero is C, subprocess is the cleanest bridge
- **PIL Image mode is always RGB** — the display driver handles the conversion to e-ink protocol
- **Error log should never crash the main loop** — wrap all error_log calls in try/except
- **Dithering is the slowest Pillow operation** — expect 5-15 seconds on Pi Zero W for a full 800×480 Floyd-Steinberg pass
- **Test images should be visually inspected** — `scp` them to a laptop and open them to verify the dithering looks right
