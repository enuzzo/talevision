# TaleVision

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Pillow](https://img.shields.io/badge/Pillow-10+-FFD43B?style=for-the-badge)](https://python-pillow.org/)
[![Inky Impression](https://img.shields.io/badge/Inky_Impression-7--colour_800×480-e84393?style=for-the-badge)](https://shop.pimoroni.com/products/inky-impression-7-3)
[![Pi Zero W](https://img.shields.io/badge/Pi_Zero_W-armv6l_512MB-c51a4a?style=for-the-badge&logo=raspberry-pi)](https://www.raspberrypi.com/products/raspberry-pi-zero-w/)
[![Quotes](https://img.shields.io/badge/Quotes-6_languages-4ade80?style=for-the-badge)](#litclock)
[![License](https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge)](./LICENSE)

> *"What if LitClock and SlowMovie — two Pi projects that each had their own Pi,*
> *their own Inky, their own Flask server — lived on the same wall, on the same device?"*
>
> The Pis were already there. The wall was already there. The reasoning was air-tight.

<br />

**TaleVision** is a Raspberry Pi Zero W that doesn't know if it's a clock or a cinema, and has decided that's fine.

As **LitClock**, it reads the current minute and surfaces a literary quote — from Calvino, Woolf, Borges, Saramago, a few hundred others — that contains those exact digits somewhere in the sentence. Every 5 minutes. In six languages. Typeset in Taviraj, centred, with an em-dash and the author's name below.

As **SlowMovie**, it extracts a random frame from a film in your media folder, runs it through a PIL enhancement pipeline, fits it to the panel, and holds it for 90 seconds. There is an overlay with title, director, timecode. There is a QR code linking to TMDB. There is absolutely no hurry.

As **Wikipedia**, it fetches a random article every few minutes, renders the title and extract in a clean serif layout with a thumbnail and a QR code. One unexpected thing you didn't know, in Italian or five other languages, every time the e-ink decides it's ready.

As **Weather**, it fetches wttr.in's native ANSI terminal output — ASCII art clouds, coloured temperatures, wind arrows — parses the escape codes, and renders them character by character in Inconsolata Nerd Font Mono, mapped to seven e-ink colours. It looks like a terminal printout from the future's past.

As **Museo**, it picks a random public-domain artwork from one of three world museums — the Met, Cleveland Museum of Art, or the Victoria and Albert Museum — downloads the high-resolution image, enhances it for e-ink, and holds it on the wall with the title, artist, and museum name in a discreet overlay. A QR code links to the museum's page for that object. The three museums rotate in order, one per render cycle. Nearly a million artworks, zero API keys.

As **Koan**, it writes a haiku. A 70-billion-parameter language model receives a theme — which might be "consciousness" or "the topology of tangled earphones" or "a parking ticket on a hearse" — and produces three lines of poetry in the language you've chosen, signed with a self-invented pen name. The theme stays in English in the header; the haiku is written in Italian, or Spanish, or Japanese. Every fifteen minutes, a new poem appears on the wall, and the old one is archived forever. There are 210 themes. The machine does not repeat itself.

As **Cucina**, it picks a random dish from world cuisines — Thai, Mexican, Moroccan, Japanese, Italian, anything — downloads the food photo, and lays out a full recipe card on the display. The photo sits on a dark background with the dish name in Lobster script; below, the instructions fill the white half. Ingredients in two columns, a QR code linking to the YouTube tutorial. Every five minutes, a new dish. No API key.

All seven modes share one 800×480 seven-colour e-ink panel, one Pi Zero W, one Flask dashboard, and one quiet conviction: the best thing a screen can do is earn its update.

---

## Why This Exists

The repo is called `talevision`. Lowercase. The project inside is `TaleVision`. This is a pun — *tale* (story, literary quote, one frame of someone else's cinema) plus *vision* (screen, display, the thing on the wall). Say it fast enough and it also sounds like *television*, which is exactly what this is except it updates once a minute, fits in your palm, costs the price of a dinner, and never asks you to subscribe to anything.

It started as two separate projects. LitClock lived on a Pi Zero, showed quotes, had a Flask UI. SlowMovie lived on a different Pi Zero, showed films, had a different Flask UI. Same fonts. Same wall. Same guests asking "wait, how does it know the time?" and "wait, is that actually playing?".

At some point running two Pis to impress the same guests with the same e-ink display technology felt like a statement about resource allocation that nobody was prepared to defend. The Pis were doing the same job — making the wall interesting — and there was no good reason they couldn't take turns.

TaleVision is the obvious outcome. One device. One config file. One dashboard. Switch between literary and cinematic at the push of a button — literally, the Inky Impression has four of them on the side. The architecture is cleaner than either original. The fonts survived the migration intact. The wall is still interesting.

---

## Table of Contents

- [LitClock](#litclock)
- [SlowMovie](#slowmovie)
- [Wikipedia](#wikipedia)
- [Weather](#weather)
- [Museo](#museo)
- [Koan](#koan)
- [Cucina](#cucina)
- [Playlist & Rotation](#playlist--rotation)
- [Hardware](#hardware)
- [How It Works](#how-it-works)
- [Boot Sequence](#boot-sequence)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Web Dashboard](#web-dashboard)
- [Physical Buttons](#physical-buttons)
- [Suspend Schedule](#suspend-schedule)
- [Project Structure](#project-structure)
- [Security](#security)
- [Notes for Pi Deployers](#notes-for-pi-deployers)
- [License](#license)

---

## LitClock

Every 5 minutes: check the time, look up which literary quotes mention that exact minute, pick one at random, render it on screen.

The quote fills the panel in a centred text block, word-wrapped at 700px, in Taviraj Regular at 28pt. If the raw quote contains an `<em>` tag — the database uses these to mark the time string in the original sentence — and `use_italic_for_em` is enabled, the whole quote switches to Taviraj Italic. Below the quote: an em-dash, the author, a separator, the book title — all on one line, typeset as a unit so the spacing lands correctly. At the top: time and full date, Babel-formatted in the configured locale, separated from the quote by a thin ruled line.

The vertical position is not simply centred. It uses mathematical centre minus a configurable `vertical_centering_adjustment` offset (default: 40px upward) because centred text on a wide panel reads as sitting low. This is not a bug. It took an afternoon to figure out the right number.

If no quote exists for the current minute — coverage is good but not complete — a fallback pool is used instead. The display doesn't panic. It finds something worth saying.

**Languages:** `it` · `es` · `pt` · `en` · `fr` · `de` — switchable from the dashboard without restart.

---

## SlowMovie

Every 5 minutes: pick a random film from `media/`, extract a random frame from somewhere in the middle (skipping the first 30 seconds and the last 2 minutes — credits and cold-open black slates are not cinema), run it through the PIL pipeline, fit it to the panel, composite the overlay. Each render picks a different film — every frame on the wall is a still from a different movie.

**PIL pipeline, in order:** Brightness → Gamma (custom LUT via `point()`, not an ImageEnhance filter) → Contrast → Color saturation → cover or contain fit.

**Cover fit:** `ImageOps.fit()` — crops to fill the panel while preserving aspect ratio. Films wider than 800×480 lose the bars. This is correct.

**Contain fit:** thumbnail + paste on black canvas — letterboxed. Films keep their bars. This is also correct. Choose based on the film.

**Overlay:** an RGBA composite layer, `alpha_composite()` at the end. A rounded rectangle (`radius=8`, `fill=(0,0,0,190)`) sits in the bottom-left with the film title (bold), year (light), director, and timecode. A QR code in a white-on-black rounded box in the bottom-right links to TMDB search for that title. If a `.json` sidecar file exists next to the `.mp4` with `title`, `director`, and `year` keys, those populate the overlay. Without one, the filename stem is used. Both outcomes are dignified.

**Auto-generated sidecars:** on first activation of SlowMovie, the system scans `media/` for videos without a `.json` sidecar and generates them automatically via TMDB (requires `tmdb_api_key` in `secrets.yaml`). No manual step needed. `generate_sidecars.py` in the project root is still available for bulk pre-generation or dry-runs.

---

## Wikipedia

Every 5 minutes: pick a random Wikipedia article in your chosen language, render it to the display. Title in bold, extract body word-wrapped to fit, thumbnail image if the article has one (top-right, resized proportionally to 180px wide), QR code bottom-right linking to the full article.

At the top: the time and date in the same Taviraj-SemiBold header used by LitClock — `14:32 · 10 marzo '26` — with the language label right-aligned (`Wikipedia · IT`). Date formatted with Babel so the month name is in the display language, not whatever the system locale happens to be.

The body text uses a full second API call (`action=query&prop=extracts`) to fetch up to 3000 characters of article content beyond the intro — internal sections included. Text fills the panel intelligently: lines beside the thumbnail use a narrower wrap, lines below it use full width, and lines that descend into the QR zone auto-narrow to avoid overdrawing the code. If the text still runs long, the last body line ends with ` …`. The QR code is self-explanatory — no hint text needed.

**Languages:** `it` · `es` · `pt` · `en` · `fr` · `de` — same six as LitClock, same language selector in the dashboard. One setting controls both.

---

## Weather

Every 5 minutes: fetch current conditions and a 3-day forecast from [wttr.in](https://wttr.in/) — no API key, no account, no nothing. But not as JSON. As raw ANSI terminal output — the same colourful ASCII art you'd see if you ran `curl wttr.in` in a terminal.

The ANSI escape codes are parsed character by character and rendered onto the e-ink panel with Inconsolata Nerd Font Mono. ANSI colours are mapped to the 7-colour e-ink palette — green becomes blue, yellow becomes orange, everything inverted for a white background. The result is a weather display that looks like a vintage terminal printout, complete with ASCII art clouds and sun icons.

Two rendering zones: at the top, the current conditions with a larger font (14pt) — the ASCII art weather icon alongside temperature, wind, humidity. Below, the 3-day forecast tables at a compact 12pt. A custom header shows the city name and fetch timestamp.

Location is configurable from the dashboard, with autocomplete powered by Open-Meteo geocoding (free, no key). Coordinates are stored as lat/lon for precision. Metric and Imperial units are toggleable from the dashboard.

Note: wttr.in is fetched over HTTP on the Pi Zero W. The HTTPS handshake reliably times out on armv6l hardware. This is not a security oversight — the data is non-sensitive weather information from a public endpoint.

---

## Museo

Every 5 minutes: pick a random public-domain artwork from one of three world museums, download the high-resolution image, run it through the PIL enhancement pipeline, fit it to the panel, add the overlay. The three museums — **Metropolitan Museum of Art** (NYC, ~200k works), **Cleveland Museum of Art** (~41k works), **Victoria and Albert Museum** (London, ~732k works) — rotate in strict order, one per render cycle.

No API keys. No accounts. No registration. All three museums offer free, unauthenticated APIs with CC0 or public-domain images. Nearly a million artworks total. The catalogue is cached locally for 24 hours to avoid hammering the APIs on every render.

**Overlay:** same RGBA composite pattern as SlowMovie. A rounded-rectangle box in the bottom-left with the artwork title and date (Signika-Bold 20pt), artist name (Signika-Light 20pt), and museum + department (Inconsolata 16pt, light grey). A QR code in the bottom-right links to the museum's object page for that artwork. If you want to know more about what's on your wall, scan it.

**Fallback:** if the network is down, Museo shows the last successfully rendered frame from cache. If there's no cache at all (cold start with no network), it shows a clean white screen with "MUSEO" in Lobster and a connection-unavailable message.

A 50-ID recent buffer prevents the same artwork from appearing twice in a row — with ~973k works across the three museums, collisions are unlikely, but the buffer removes the possibility entirely.

---

## Koan

Every 15 minutes: pick one of 210 themes, send it to a 70-billion-parameter language model, receive a haiku and a pen name, render it on the wall, archive it forever.

The themes range from the philosophical ("consciousness", "the weight of a word you cannot say") to the absurd ("a parking ticket on a hearse", "the topology of tangled earphones", "the retirement plan of a mayfly"). The haiku is written in whatever language you've set on the dashboard — Italian, English, Spanish, Portuguese, French, German, or Japanese. The theme stays in English in the header. The contrast is intentional.

**Layout:** zen minimalist on a bamboo ink wash watercolour background. The haiku is right-aligned in Crimson Text Regular at 46pt, near-black, optically centred at 38% height. Above it: the theme and a sequential number in Inconsolata Mono. Below: the pen name in uppercase, and a tech stats line showing the model, response time, and token count — the cold anatomy of the machine that wrote the poem. About 70% of the canvas is negative space.

**Backend:** Groq API (primary, `llama-3.3-70b-versatile`) or Google Gemini (fallback, `gemini-2.0-flash-lite`), auto-detected from `secrets.yaml`. Generation takes ~1 second. The Groq free tier allows 100K tokens per day; at ~180 tokens per haiku and 96 haiku per day, TaleVision uses about 18% of the budget.

**Error screen:** when the API is unreachable, the display shows a warm cream background with "the poet is silent today / words could not cross the wire" in Taviraj Italic. Poetic, but visually distinct from a real haiku — you'll know something is wrong.

**Archive:** every haiku is saved as an individual JSON file in `cache/koan_archive/`, with full metadata (model, tokens, timing, theme, pen name). The archive is purely historical — it's never replayed on the display, but it's browsable via the dashboard API.

---

## Cucina

Every 5 minutes: fetch a random dish from TheMealDB, download the food photo, render a full recipe card on the display.

The layout is split in half. The top is a dark band — the food photo sits there as a 240×240 square with rounded corners, the dish name in Lobster script to its right, and the ingredients listed in one or two compact columns. The bottom half is white — the instructions fill it in Taviraj Regular, truncated with an ellipsis when the recipe runs long. A dark footer bar at the bottom shows the current time and date. A QR code in the bottom-right links to the YouTube tutorial or recipe source.

**Smart title case:** dish names are rendered with proper English title case — "Chicken with Garlic and Thyme", not "Chicken With Garlic And Thyme". Prepositions, articles, and conjunctions stay lowercase unless they're the first word.

**Photo:** always 1:1 square, cover-cropped from the original with `ImageOps.fit()`. Rounded corners (14px radius) via an alpha mask. PIL enhancement: brightness 1.1, contrast 1.2, colour 1.3.

**Ingredients:** single column for 6 or fewer items, two columns for 7+. Each line shows the measure and ingredient name, truncated at 26 characters with an ellipsis if needed.

**Fallback:** if the network is down, shows the last successfully rendered frame from cache. Cold start with no network: white background, "CUCINA" in Lobster, connection-unavailable message.

TheMealDB's free tier (test key "1") has no rate limits and about 300 recipes. No API key required.

---

## Playlist & Rotation

TaleVision doesn't make you choose. Enable any combination of modes and the Orchestrator cycles through them in order. A unified rotation interval (default: 5 minutes, configurable 30s–60min) replaces per-mode intervals during rotation. After each render, it waits, then advances to the next mode in the playlist.

Single mode? Per-mode interval applies as before. Two or more? Rotation takes over. The playlist is reorderable from the dashboard with up/down arrows. Persisted to `user_prefs.json`. Survives reboots.

**API:** `POST /api/playlist` with `{"modes": ["litclock", "wikipedia", "weather"], "rotation_interval": 300}`.

---

## Hardware

| Component | Spec | Notes |
|---|---|---|
| **SBC** | Raspberry Pi Zero W | 512MB RAM, armv6l, single core. Runs the whole stack. No headless browsers, no exceptions. |
| **Display** | Pimoroni Inky Impression 7.3" | 800×480, 7-colour e-ink, SPI. ~30s panel refresh. Holds image with zero power draw. |
| **Buttons** | A / B / C / D (onboard) | GPIO 5/6/16/24. Wired to mode switch, force refresh, suspend toggle. |
| **Storage** | microSD | 8GB minimum. `media/` lives here. It is gitignored. |
| **Power** | 5V micro-USB | Any phone charger. The Pi Zero W is not demanding about this. |

The display refreshes slowly on purpose. E-ink panels take ~30 seconds and hold the image at zero power. The software intervals (60s, 90s) are deliberately longer than the panel refresh time. There is no race condition to fix here.

---

## How It Works

```
                        ┌──────────────────────────────────────────┐
                        │              Orchestrator                │
                        │            (main thread)                 │
                        │                                          │
         button press   │  _action_queue ◄── Flask API thread      │
         ─────────────► │                                          │
                        │  ┌──────────┐  ┌──────────┐             │
                        │  │ LitClock │  │SlowMovie │             │
                        │  └────┬─────┘  └────┬─────┘             │
                        │  ┌────┴─────┐  ┌────┴─────┐             │
                        │  │Wikipedia │  │ Weather  │             │
                        │  └────┬─────┘  └────┬─────┘             │
                        │       │      ┌──────┘                   │
                        │       │      │  ┌────────┐              │
                        │       │      │  │ Museo  │  (playlist)  │
                        │       │      │  └───┬────┘              │
                        │       └──────┬───────┘                  │
                        │              ▼ render()                  │
                        │          InkyCanvas                      │
                        │     (hardware or PNG sim)                │
                        └──────────────┬───────────────────────────┘
                                       │
                           ┌───────────┴───────────┐
                           │                       │
                     Inky display           cache/frame.png
                     (Pi only)            (served at /api/frame)
```

The Orchestrator runs in the main thread. Flask runs in a daemon thread. They communicate through a `queue.Queue` and a `threading.Lock`. Button presses from GPIO polling go through the same queue. Nobody touches the render pipeline from outside the main thread.

---

## Boot Sequence

On power-up, TaleVision renders a **welcome screen** to the e-ink display before anything else. A vintage TV frame graphic (800×480, transparent centre) is composited as background. Inside it: "TaleVision" in Lobster at 75pt, black, centred. Below it: a randomly chosen sardonic tagline from a pool of twenty, in Taviraj Italic. Below that: `— STARTING IN 30 SECONDS —` in red. Then a compact BBS/NFO-style info box — hostname (with `.local` mDNS suffix), LAN IP, dashboard URL — in DejaVuSansMono Bold with box-drawing characters. Closes with "TaleVision v1.5 · Netmilk Studio" in blue.

The welcome screen holds for 30 seconds. Long enough to confirm the device is alive, read the IP address, and actually look at it. The rendered frame is saved to `cache/welcome_frame.png` on every boot. Then the Orchestrator takes over and renders the first real frame.

The systemd service is set to `Restart=always`. On reboot, crash, power cycle, existential doubt — TaleVision comes back. The Pi has one job and it will do it.

---

## Quick Start

### Development (macOS/Linux, no hardware)

```bash
git clone https://github.com/netmilk/talevision && cd talevision
python3 -m venv venv && source venv/bin/activate
pip install Pillow Flask PyYAML babel rich dacite qrcode[pil]

# Render one LitClock frame to PNG and exit
python main.py --render-only --mode litclock
open talevision_frame.png   # or xdg-open on Linux
```

No Inky? The canvas saves `talevision_frame.png` instead. No GPIO? The button handler logs one warning and disappears. The render pipeline is fully exercisable on a Mac.

### Raspberry Pi

```bash
git clone https://github.com/netmilk/talevision /home/pi/talevision
cd /home/pi/talevision

# Full install: apt deps + venv + systemd service + SPI enable
bash scripts/install.sh

# Drop your films in
cp /path/to/films/*.mp4 media/

# Start
sudo systemctl start talevision
```

Dashboard at `http://<pi-ip>:5000`.

---

## Configuration

`config.yaml` — committed, sane defaults. `secrets.yaml` — local only, gitignored, never committed. Copy `secrets.yaml.example` to start.

| Key | Default | What it does |
|---|---|---|
| `app.default_mode` | `litclock` | Which mode boots first |
| `litclock.language` | `it` | Quote language (`it` · `en` · `de` · `es` · `fr` · `pt`) |
| `litclock.refresh_rate` | `300` | Seconds between LitClock updates (5 min) |
| `litclock.vertical_centering_adjustment` | `40` | Pixels nudged upward from mathematical centre |
| `litclock.use_italic_for_em` | `true` | Switch to italic font when `<em>` appears in quote |
| `litclock.invert_colors` | `false` | White text on black background |
| `slowmovie.refresh_interval` | `300` | Seconds between SlowMovie frames |
| `slowmovie.video_file` | `random` | Specific filename or `random` |
| `slowmovie.image.fit_mode` | `cover` | `cover` (crop to fill) or `contain` (letterbox) |
| `slowmovie.overlay.qr_enabled` | `true` | TMDB QR code in frame corner |
| `slowmovie.overlay.qr_content` | `tmdb_search` | QR link pattern (`tmdb_search` or `imdb_search`) |
| `display.saturation` | `0.6` | Inky colour saturation (0.0 – 1.0) |
| `wikipedia.refresh_interval` | `300` | Seconds between Wikipedia article fetches |
| `wikipedia.language` | `it` | Default language for Wikipedia (`it` · `es` · `pt` · `en` · `fr` · `de`) |
| `weather.refresh_interval` | `300` | Seconds between weather fetches |
| `weather.city` | `Roma` | Default city name (editable from dashboard) |
| `weather.lat` / `weather.lon` | `41.89` / `12.48` | Coordinates for wttr.in (set via dashboard autocomplete) |
| `weather.units` | `m` | `m` (metric), `u` (imperial), `M` (metric + m/s wind) |
| `museo.refresh_interval` | `300` | Seconds between artwork fetches |
| `museo.timeout` | `60` | HTTP timeout for museum API calls |
| `suspend.start` / `.end` | `18:00` / `08:00` | Sleep/wake time — overnight ranges handled correctly (start > end wraps midnight) |
| `suspend.days` | `[5,6]` | Fully-off days (0=Mon … 6=Sun). Default: Sat+Sun fully off, Mon–Fri follow the time window |
| `buttons.actions` | see below | Remap GPIO buttons to any action |

---

## Web Dashboard

`http://<pi-ip>:5000` — built in React (Vite + Tailwind CSS + Radix UI). Solar Dust theme (dark brown-black bg `#1A1410`, gold accent `#E8A838`, terracotta `#D06B50`, cream text `#F0E6D6`). Lobster for the logotype and headings, Chakra Petch for everything else. No page reloads. Netmilk Studio logo in the footer, shakes on hover.

A sardonic tagline rotates with each page load. Twenty options. The display updates roughly once a minute. The tagline changes roughly once per session. Both are fine.

**Frame preview** — when you switch mode or force-refresh, the preview goes dark and shows a vintage CRT overlay: TV grain, scanlines, an amber sweep band, and an oscillating radio tuner needle. The mode name appears in Lobster with a subtle flicker. As soon as the Pi finishes rendering, the overlay clears and the new frame fades in. No manual reload needed.

**Layout:**

```
┌─────────────────────────────────────────────────┐
│  TaleVision                                      │  ← Lobster logotype
│  "The best thing on your wall since the clock."  │  ← rotating tagline (12px italic)
├─────────────────────────────────────────────────┤
│  Language  [ Italiano ▾ ]  ← LitClock + Wikipedia│
├─────────────────────────────────────────────────┤
│  [ last rendered frame, 800×480 ]               │  ← auto-updates on render complete
│  playlist: [LitClock] [Wikipedia] [Weather] ...  │  ← drag-to-reorder
│  rotation interval: [___] min     [Save] [⟳]   │  ← save + force refresh in one row
├─────────────────────────────────────────────────┤
│  Stats          │  Active schedule               │
│  Uptime         │  ▶ On from  ⏹ Off at          │
│  Last render    │  Active days  [Save]            │
│  Mode / Status  │                                 │
├─────────────────────────────────────────────────┤
│  Refresh intervals (single-mode only)            │
└─────────────────────────────────────────────────┘
```

| Endpoint | Method | Body | Does |
|---|---|---|---|
| `/api/status` | GET | — | Mode, suspension, intervals, last frame timestamp, `uptime_seconds`, `is_suspended` |
| `/api/mode` | POST | `{"mode": "litclock"}` | Switch mode |
| `/api/refresh` | POST | — | Force immediate render cycle |
| `/api/language` | POST | `{"lang": "it"}` | Change language (LitClock + Wikipedia) |
| `/api/languages` | GET | — | List detected language files |
| `/api/suspend` | POST | `{"enabled": bool, "start": "HH:MM", "end": "HH:MM", "days": [...]}` | Update schedule |
| `/api/frame` | GET | — | Last rendered frame (PNG or JPG) |
| `/api/frame/<mode>` | GET | — | Frame for a specific mode |
| `/api/interval` | GET | — | Per-mode interval overrides |
| `/api/interval` | POST | `{"mode": "litclock", "seconds": 300}` | Set interval override |
| `/api/interval/<mode>` | DELETE | — | Reset to config default |
| `/api/playlist` | POST | `{"modes": [...], "rotation_interval": N}` | Set playlist and rotation interval |
| `/api/weather/location` | GET | — | Current city, lat, lon |
| `/api/weather/location` | POST | `{"city": "Roma", "lat": 41.89, "lon": 12.48}` | Set weather location |
| `/api/weather/search` | GET | `?q=rom&lang=it` | Autocomplete via Open-Meteo geocoding |
| `/api/weather/units` | GET | — | Current units (`m`/`u`/`M`) |
| `/api/weather/units` | POST | `{"units": "m"}` | Set metric/imperial |

---

## Web UI Fonts

The control dashboard uses the following typefaces, **self-hosted** — no Google Fonts dependency, works fully offline:

| Font | Role | Designer | Copyright |
|---|---|---|---|
| **[Lobster](https://fonts.google.com/specimen/Lobster)** | Logotype ("TaleVision"), section headings; also used on e-ink boot and suspend screens | Pablo Impallari | © 2010 Pablo Impallari |
| **[Funnel Display](https://fonts.google.com/specimen/Funnel+Display)** | Interface text, labels, values | Mirko Velimirović / Undercase Type | © 2024 The Funnel Project Authors |

Font files (`woff2` + `ttf`) are committed to `frontend/public/fonts/` and served directly by Flask. The e-ink screens use `Lobster-Regular.ttf` from `assets/fonts/`.

Both typefaces are licensed under the [SIL Open Font License 1.1](https://openfontlicense.org/) — free to use, embed, and redistribute with attribution.

---

## Physical Buttons

The Inky Impression has four buttons on the side. Default mapping:

| Button | GPIO | Default action | Configurable |
|---|---|---|---|
| **A** | 5 | Switch mode (LitClock ↔ SlowMovie) | Yes |
| **B** | 6 | Force refresh immediately | Yes |
| **C** | 16 | Toggle suspend on/off | Yes |
| **D** | 24 | *(unassigned)* | Yes |

All four remappable in `config.yaml` under `buttons.actions`. On non-Pi hardware the button handler logs one warning at startup and then does nothing, quietly, for the rest of the process lifetime.

---

## Suspend Schedule

Between `suspend.start` and `suspend.end`, TaleVision stops rendering and waits. The panel holds the last image with zero power draw. The Pi idles.

On entering suspension, it renders a **suspend screen**: same vintage TV frame background as the welcome screen. "TaleVision" in Lobster at 65pt, black. Below it: `· DISPLAY SUSPENDED ·` in orange spaced caps — so it's immediately clear what's happening. Below that: a random literary quote from the LitClock database, word-wrapped in Taviraj Italic, with the author below. Then the BBS info box — active hours, day-of-week markers (`[MON]` for active, ` MON ` for suspended), next wake time — in DejaVuSansMono with box-drawing characters. Timestamp at the bottom in grey.

Overnight windows (`23:00 → 07:00`) are handled correctly: if `start > end`, the suspended period wraps midnight. Day-of-week filtering is supported. An empty list means every day.

The suspend screen is rendered once on entry and held. The Pi does not wake on a timer to refresh a screen that says it is sleeping.

The dashboard shows this as **active hours** (when the device is ON), not as a suspend window — the times are inverted at the API boundary for a more intuitive UX.

---

## Project Structure

```
talevision/
├── main.py                      Entry point — --render-only for dev/CI
├── config.yaml                  All configuration (committed)
├── secrets.yaml                 Local secrets (gitignored, never committed)
├── secrets.yaml.example         Template with placeholders (committed)
├── generate_sidecars.py         Dev utility: bulk TMDB sidecar generation for media/
├── talevision/
│   ├── config/
│   │   ├── schema.py            AppConfig + all sub-dataclasses
│   │   └── loader.py            load_config(), load_secrets(), detect_available_languages()
│   ├── modes/
│   │   ├── base.py              DisplayMode ABC + ModeState
│   │   ├── litclock.py          LitClock — Taviraj typography, 6 languages
│   │   ├── slowmovie.py         SlowMovie — PIL chain + RGBA overlay + TMDB QR
│   │   ├── wikipedia.py         Wikipedia — random article, babel header, QR link
│   │   ├── weather.py           Weather — wttr.in ANSI parser + two-zone PIL render
│   │   ├── museo.py             Museo — Met/Cleveland/V&A round-robin + PIL overlay
│   │   ├── museo_cache.py       File-based catalogue cache with TTL
│   │   ├── koan.py              Koan — haiku generation + zen layout
│   │   ├── koan_generator.py    Cloud LLM API (Groq/Gemini) + output parser
│   │   ├── koan_archive.py      Folder-based haiku archive
│   │   ├── cucina.py            Cucina — TheMealDB recipes + dark/light layout
│   │   └── museo_providers/     Provider ABC + Met, Cleveland, V&A implementations
│   ├── render/
│   │   ├── typography.py        FontManager, wrap_text_block, get_text_dimensions
│   │   ├── layout.py            draw_header, draw_centered_text_block
│   │   ├── suspend_screen.py    Suspend screen — Lobster title + random quote + BBS box
│   │   ├── welcome_screen.py    Boot splash — Lobster title + tagline + BBS info box
│   │   ├── canvas.py            InkyCanvas (hardware) + PNG simulation fallback
│   │   └── frame_cache.py       SHA256 video cache + ffmpeg frame extraction
│   ├── media/
│   │   └── sidecars.py          Auto-sidecar generation from TMDB (called on SlowMovie activate)
│   ├── system/
│   │   ├── orchestrator.py      Main loop — action queue, interval overrides, frame save
│   │   ├── suspend.py           Overnight window scheduling + thread-safe update
│   │   ├── timer.py             Interruptible sleep (force-refresh aware)
│   │   ├── buttons.py           GPIO polling — graceful no-op on non-Pi
│   │   └── logging_setup.py     Rich terminal + rotating file handler
│   └── web/
│       ├── app.py               Flask factory
│       ├── api.py               /api/* blueprint (mode, refresh, language, suspend, interval)
│       ├── views.py             Serves React SPA (dist/index.html) or Jinja fallback
│       ├── templates/           Jinja2 fallback dashboard (no build required)
│       └── static/dist/         Built React SPA — committed, served directly by Flask
├── frontend/
│   ├── src/
│   │   ├── App.tsx              Main dashboard: mode switch, frame preview, status, controls
│   │   ├── ParticleBackground.tsx  Amber particle canvas with mouse repulsion
│   │   ├── api.ts               Typed API client
│   │   ├── types.ts             Shared TypeScript types
│   │   └── index.css            Tailwind base + scanline/grain overlays + keyframes
│   ├── public/fonts/            Self-hosted fonts: Lobster-Regular.{woff2,ttf}, FunnelDisplay-variable.{woff2,ttf}
│   ├── package.json             Vite + React + Tailwind + Radix UI + TanStack Query
│   └── vite.config.ts           Outputs to talevision/web/static/dist/
├── assets/
│   ├── fonts/                   Signika + Taviraj (22 weights) + DejaVuSansMono + Lobster-Regular.ttf + InconsolataNerdFontMono (6 variants)
│   ├── lang/                    quotes-{de,en,es,fr,it,pt}.csv + fallback.csv
│   └── icons/                   logo.png
├── media/                       Your .mp4 files + sidecar .json (gitignored for .mp4)
├── cache/                       Runtime cache: video info JSON + rendered frames (gitignored)
├── deploy/
│   └── talevision.service       systemd unit for Pi autostart
└── scripts/
    ├── install.sh               Full Pi setup: apt + venv + SPI + systemd
    ├── setup_venv.sh            venv + pip only
    └── install_service.sh       systemd unit deploy
```

---

## Security

`secrets.yaml` is gitignored and never committed. `secrets.yaml.example` is committed with `<BCRYPT_HASH>` placeholders only. The `archive/` reference implementations are gitignored and stay local.

Pre-push scan:

```bash
# No credentials in committed files
grep -rn "password=\|api_key=\|token=" talevision/ config.yaml

# Static analysis
bandit -r talevision/ -ll

# Dependency CVEs
pip-audit -r requirements.txt
```

---

## Notes for Pi Deployers

**Testing without Pi hardware works.** `--render-only` saves a PNG. The Inky library falls back silently. The GPIO handler logs one line and goes quiet. The full render pipeline runs on macOS without modification. This is by design.

**SPI must be enabled before Inky will work.** `scripts/install.sh` handles this. On Raspbian Trixie, also add `dtoverlay=spi0-0cs` on the line after `dtparam=spi=on` in `/boot/firmware/config.txt` and reboot — without this, the display never initializes (a Trixie-specific SPI chip-select issue).

**The Inky Impression 7" has no EEPROM.** `inky.auto.auto()` will always fail with "No EEPROM detected!". TaleVision uses `inky.inky_ac073tc1a.Inky` with explicit `resolution=(800, 480)` — the correct driver for this board. The older `inky.inky_uc8159` does not support 800×480. If you see EEPROM errors, this is why.

**`pip install Pillow` will likely fail on armv6l.** PyPI does not ship armv6l wheels. Use `sudo apt install python3-pil` and let the system package win. The system package is fine. This is documented, expected, and not something we are going to fix because we cannot fix it.

**`ffmpeg-python` is not ffmpeg.** It is a Python wrapper. Without `/usr/bin/ffmpeg` present — installed via `apt install ffmpeg` — SlowMovie frame extraction will fail and return a grey error image. This is the correct failure mode. Install ffmpeg.

**The display takes ~30 seconds to refresh.** The software intervals (60s for LitClock, 90s for SlowMovie) are deliberately longer than the panel cycle time. The screen is not frozen. The Pi has not crashed. The film is not broken. It's e-ink. Patience is a feature, not a workaround.

---

---

## License

[MIT](./LICENSE) — Netmilk Studio sagl.

Use it, fork it, replace the quote database with your own obsessions, point SlowMovie at a different genre of cinema, run it in a gallery and tell people it's art (it is).

---

<div align="center">

*Literature. Cinema. Wikipedia. Weather. Art.*
*One Pi Zero W. One wall. One question at a time.*

</div>

