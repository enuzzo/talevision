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

Both modes share one 800×480 seven-colour e-ink panel, one Pi Zero W, one Flask dashboard, and one quiet conviction: the best thing a screen can do is earn its update.

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

Every 60 seconds: check the time, look up which literary quotes mention that exact minute, pick one at random, render it on screen.

The quote fills the panel in a centred text block, word-wrapped at 700px, in Taviraj Regular at 28pt. If the raw quote contains an `<em>` tag — the database uses these to mark the time string in the original sentence — and `use_italic_for_em` is enabled, the whole quote switches to Taviraj Italic. Below the quote: an em-dash, the author, a separator, the book title — all on one line, typeset as a unit so the spacing lands correctly. At the top: time and full date, Babel-formatted in the configured locale, separated from the quote by a thin ruled line.

The vertical position is not simply centred. It uses mathematical centre minus a configurable `vertical_centering_adjustment` offset (default: 40px upward) because centred text on a wide panel reads as sitting low. This is not a bug. It took an afternoon to figure out the right number.

If no quote exists for the current minute — coverage is good but not complete — a fallback pool is used instead. The display doesn't panic. It finds something worth saying.

**Languages:** `it` · `en` · `de` · `es` · `fr` · `pt` — switchable from the dashboard without restart.

---

## SlowMovie

Every 90 seconds: select a film from `media/`, pick a random frame somewhere in the middle (skipping the first 2 minutes and the last 4 — credits and cold-open black slates are not cinema), extract it with ffmpeg, run it through the PIL pipeline, fit it to the panel, composite the overlay.

**PIL pipeline, in order:** Brightness → Gamma (custom LUT via `point()`, not an ImageEnhance filter) → Contrast → Color saturation → cover or contain fit.

**Cover fit:** `ImageOps.fit()` — crops to fill the panel while preserving aspect ratio. Films wider than 800×480 lose the bars. This is correct.

**Contain fit:** thumbnail + paste on black canvas — letterboxed. Films keep their bars. This is also correct. Choose based on the film.

**Overlay:** an RGBA composite layer, `alpha_composite()` at the end. A rounded rectangle (`radius=8`, `fill=(0,0,0,190)`) sits in the bottom-left with the film title (bold), year (light), director, and timecode. A QR code in a white-on-black rounded box in the bottom-right links to TMDB search for that title. If a `.json` sidecar file exists next to the `.mp4` with `title`, `director`, and `year` keys, those populate the overlay. Without one, the filename stem is used. Both outcomes are dignified.

**Auto-generated sidecars:** on first activation of SlowMovie, the system scans `media/` for videos without a `.json` sidecar and generates them automatically via TMDB (requires `tmdb_api_key` in `secrets.yaml`). No manual step needed. `generate_sidecars.py` in the project root is still available for bulk pre-generation or dry-runs.

---

## Playlist & Rotation

TaleVision doesn't make you choose. Enable both modes — or eventually all four — and the Orchestrator cycles through them in order. A unified rotation interval (default: 5 minutes, configurable 30s–60min) replaces per-mode intervals during rotation. After each render, it waits, then advances to the next mode in the playlist.

Single mode? Per-mode interval applies as before. Two or more? Rotation takes over. The playlist is reorderable from the dashboard with up/down arrows. Persisted to `user_prefs.json`. Survives reboots.

**API:** `POST /api/playlist` with `{"modes": ["litclock", "slowmovie"], "rotation_interval": 300}`.

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
                        ┌─────────────────────────────────────┐
                        │           Orchestrator              │
                        │         (main thread)               │
                        │                                     │
         button press   │  _action_queue ◄── Flask API thread │
         ─────────────► │                                     │
                        │  ┌─────────┐       ┌─────────────┐  │
                        │  │LitClock │  or   │  SlowMovie  │  │
                        │  │  Mode   │       │    Mode     │  │
                        │  └────┬────┘       └──────┬──────┘  │
                        │       │ render()          │         │
                        │       └────────┬──────────┘         │
                        │                ▼                    │
                        │          InkyCanvas                 │
                        │     (hardware or PNG sim)           │
                        └─────────────┬───────────────────────┘
                                      │
                          ┌───────────┴───────────┐
                          │                       │
                    Inky display           cache/frame.png
                    (Pi only)            (served at /api/frame)
```

The Orchestrator runs in the main thread. Flask runs in a daemon thread. They communicate through a `queue.Queue` and a `threading.Lock`. Button presses from GPIO polling go through the same queue. Nobody touches the render pipeline from outside the main thread.

---

## Boot Sequence

On power-up, TaleVision renders a **welcome screen** to the e-ink display before anything else — a BBS/NFO-style boot splash on a white background with a colourful ASCII art logo, hostname, LAN IP, dashboard URL, active mode, and current playlist. The seven native Inky colours (red, orange, blue, black) are used at full saturation — no dithering, no apologies.

The welcome screen holds for 15 seconds. Long enough to confirm the device is alive and read the IP address. Then the Orchestrator takes over and renders the first real frame.

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
| `slowmovie.refresh_interval` | `90` | Seconds between SlowMovie frames |
| `slowmovie.video_file` | `random` | Specific filename or `random` |
| `slowmovie.image.fit_mode` | `cover` | `cover` (crop to fill) or `contain` (letterbox) |
| `slowmovie.overlay.qr_enabled` | `true` | TMDB QR code in frame corner |
| `slowmovie.overlay.qr_content` | `tmdb_search` | QR link pattern (`tmdb_search` or `imdb_search`) |
| `display.saturation` | `0.6` | Inky colour saturation (0.0 – 1.0) |
| `suspend.start` / `.end` | `23:00` / `07:00` | Sleep window — overnight ranges handled correctly |
| `suspend.days` | `[0..6]` | Which weekdays to suspend (0=Mon, 6=Sun; all = every day) |
| `buttons.actions` | see below | Remap GPIO buttons to any action |

---

## Web Dashboard

`http://<pi-ip>:5000` — built in React (Vite + Tailwind CSS + Radix UI), themed with the ScryBar Design System (deep navy #070D2D, violet accent #7551FF, cyan secondary #39B8FF, Montserrat + Space Mono). No page reloads. Animated particle background. Netmilk Studio logo in the footer.

**Frame preview** — when you switch mode or force-refresh, the preview immediately shows a cinematic "Rendering" overlay (sweeping scan line, pulsing rings, corner brackets) and polls status every 2 s. As soon as the Pi finishes rendering, the overlay clears and the new frame fades in automatically. No manual reload needed.

**Layout:**

```
┌─────────────────────────────────────────────────┐
│  ● TaleVision              22:17  🕐 litclock   │  ← sticky topbar
├─────────────────────────────────────────────────┤
│  [ last rendered frame, 800×480 ]               │  ← auto-updates on render complete
│  🕐 LitClock  🎬 SlowMovie       [ ⟳ Refresh ] │  ← mode switch + force refresh
├─────────────────────────────────────────────────┤
│  Status              │  Active schedule         │
│  Mode / Suspended    │  ▶ On from  ⏹ Off at    │
│  Last render / Film  │  Active days  [Save]     │
├─────────────────────────────────────────────────┤
│  Refresh intervals: 🕐 litclock [___] min [Set] │
│                     🎬 slowmovie [___] min [Set]│
├─────────────────────────────────────────────────┤
│  Language  [ it ▾ ]   ← LitClock only           │
└─────────────────────────────────────────────────┘
```

| Endpoint | Method | Body | Does |
|---|---|---|---|
| `/api/status` | GET | — | Mode, suspension state, intervals, last frame timestamp |
| `/api/mode` | POST | `{"mode": "litclock"}` | Switch mode |
| `/api/refresh` | POST | — | Force immediate render cycle |
| `/api/language` | POST | `{"lang": "en"}` | Change LitClock language |
| `/api/languages` | GET | — | List detected language files |
| `/api/suspend` | POST | `{"enabled": bool, "start": "HH:MM", "end": "HH:MM", "days": [...]}` | Update schedule |
| `/api/frame` | GET | — | Last rendered frame (PNG or JPG) |
| `/api/frame/<mode>` | GET | — | Frame for a specific mode |
| `/api/interval` | GET | — | Per-mode interval overrides |
| `/api/interval` | POST | `{"mode": "litclock", "seconds": 300}` | Set interval override |
| `/api/interval/<mode>` | DELETE | — | Reset to config default |
| `/api/playlist` | POST | `{"modes": [...], "rotation_interval": N}` | Set playlist and rotation interval |

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

On entering suspension, it renders a **BBS/NFO style screen** — black background, box-drawing characters, amber header, active hours, day-of-week markers (`[MON]` for active, ` MON ` for inactive), and the next wake time. Minimal, typeset, readable in the dark.

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
│   │   └── slowmovie.py         SlowMovie — PIL chain + RGBA overlay + TMDB QR
│   ├── render/
│   │   ├── typography.py        FontManager, wrap_text_block, get_text_dimensions
│   │   ├── layout.py            draw_header, draw_centered_text_block
│   │   ├── suspend_screen.py    BBS/NFO style e-ink suspend screen (DejaVuSansMono Bold)
│   │   ├── welcome_screen.py    Boot splash — ASCII art logo, system info, 7-colour
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
│   ├── package.json             Vite + React + Tailwind + Radix UI + TanStack Query
│   └── vite.config.ts           Outputs to talevision/web/static/dist/
├── assets/
│   ├── fonts/                   Signika + Taviraj (22 weights) + DejaVuSansMono + Bold
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

## Upcoming Modes

TaleVision is designed as a multi-mode playlist system. Modes can run alone or cycle in rotation with a unified interval. These are next:

**Teletext** — Ceefax/Oracle/Viewdata-style retro teletext pages. Mode 7 font, block graphics, 40×25 character grid. Archives of real teletext pages from the '70s–'80s rendered to the e-ink display. Coming soon.

**ANSi Art** — ANSI art from the BBS artscene, displayed as a slow gallery. The art shown in this mode comes from the incredible archives at **[Sixteen Colors](https://16colo.rs/)** — the definitive collection of ANSI, ASCII, and artscene work spanning decades of digital art history. All artwork is the creation of the original artists and artgroups credited in each file. TaleVision displays these works with deep respect and admiration for the scene that produced them. If you enjoy what you see on the display, visit [16colo.rs](https://16colo.rs/) and explore — the talent, craft, and community behind this art form is extraordinary.

---

## License

[MIT](./LICENSE) — Netmilk Studio sagl.

Use it, fork it, replace the quote database with your own obsessions, point SlowMovie at a different genre of cinema, run it in a gallery and tell people it's art (it is).

---

<div align="center">

*A library of literary time. One frame of film every 90 seconds.*
*One Pi Zero W. One wall. One question answered.*

</div>

