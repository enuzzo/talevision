# TaleVision Project Knowledge

Stable technical context for all assistants.

## Repository Layout

- `talevision/`: main application package (modes, render, system, web, config).
- `assets/`: fonts, quote CSVs, icons — committed and versioned.
- `media/`: user-supplied `.mp4` film files (gitignored, `.gitkeep` committed). Sidecar `.json` files (title/director/year) live here alongside the videos and are committed.
- `cache/`: runtime caches — video info JSON + rendered frames (gitignored).
- `deploy/`: systemd unit file (`talevision.service`) for Pi autostart.
- `scripts/`: Pi install and systemd deploy scripts.
- `archive/`: reference implementations (gitignored — read only, never modify).
- `knowledge/`: shared, sanitized cross-assistant knowledge (public, versioned).

## Core Stack

- Language/runtime: Python 3.11+
- Web: Flask 3.x, served by **waitress 3.0.2** (production WSGI; Flask dev server is the fallback)
- Image: Pillow 10+, ffmpeg (system-installed via apt on Pi)
- Config: PyYAML + dacite dataclasses
- Typography: Babel (locale formatting), Signika + Taviraj + Inconsolata Nerd Font Mono TTF fonts
- Display: Pimoroni Inky Impression 7-colour, 800×480 px, 7-colour e-ink (SPI). Driver: `inky.inky_ac073tc1a.Inky` (NOT `inky.auto` — no EEPROM on this board). Init: `Inky(resolution=(800, 480))`.
- Target platform: Raspberry Pi Zero W (armv6l, 512MB RAM), Raspbian Trixie (Debian 13)
- Dev platform: macOS or Linux (no hardware required for render pipeline)
- Network: LAN + Tailscale; WebUI reachable at LAN IP, `talevision.local`, or Tailscale IP

## Canonical Build / Run Commands

Install (dev, no hardware):

```bash
python3 -m venv venv && source venv/bin/activate
pip install Pillow Flask PyYAML babel rich dacite qrcode[pil] waitress
```

Run (render one frame, exit):

```bash
python main.py --render-only --mode litclock
# Output: talevision_frame.png (800×480)
```

Run (full daemon):

```bash
python main.py
```

Web dashboard: `http://<DEVICE_IP>:<PORT>` (default port 5000)

Pi install:

```bash
bash scripts/install.sh
sudo systemctl start talevision
```

Generate TMDB sidecar JSON files for SlowMovie:

```bash
# Requires tmdb_api_key in secrets.yaml
python generate_sidecars.py
python generate_sidecars.py --dry-run   # preview only
python generate_sidecars.py --verify    # validate all sidecars
```

## Configuration Boundaries

- `config.yaml` — committed, all non-secret options, sane defaults.
- `secrets.yaml` — local only, gitignored, never committed. Contains `tmdb_api_key` (used by `generate_sidecars.py`).
- `secrets.yaml.example` — committed with `<BCRYPT_HASH>` and `<API_KEY>` placeholders only.
- Versioned files must contain zero secrets.

## Key Rendering Invariants

### LitClock

- `wrap_text_block()`: word-wrap at `max_width` px using `draw.textbbox`.
- `draw_header()`: Babel locale format + separator line (configurable thickness/spacing).
- `draw_centered_text_block()`: center each line by `(canvas_w - w) // 2`.
- Vertical centering: `(avail_h - total_content_h) // 2 − vertical_centering_adjustment` (default −40 px).
- Details row: `— Author - Title` on one line, centered, drawn as a unit.
- Italic switch: `<em>` tag in raw quote AND `use_italic_for_em=true` → use Taviraj Italic.
- Fallback quotes: `"fallback"` font key; details format `— {author} ({time})`.
- `litclock.refresh_rate` in config is `300` (5 min) — confirm this is intentional vs. the documented 60 s.

### SlowMovie

- Video cache key: SHA256 of the video file path (via `frame_cache.py`).
- PIL enhancement chain: Brightness → Gamma (custom LUT via `point()`) → Contrast → Color.
- Fit modes: `cover` = `ImageOps.fit` (crop to fill); `contain` = thumbnail + paste on black canvas.
- Overlay: RGBA layer, `rounded_rectangle(radius=8, fill=(0,0,0,190))`, `alpha_composite` at the end.
- QR URL patterns: `imdb_search` → `https://www.imdb.com/find?q={title}`; `tmdb_search` → `https://www.themoviedb.org/search?query={title}`.
- Metadata source: `{video}.json` sidecar file with `title`, `director`, `year` keys; fallback to filename stem.
- Video selection: when `video_file=random` (default), a new random video is picked on **every render cycle** — each frame shows a different film. When a specific filename is configured, the selection is sticky (re-selected only if removed from `media/`). This changed from the previous behaviour where random selection was sticky within one activation.
- Frame skip: `skip_start_seconds=30`, `skip_end_seconds=120` (avoids cold-open slates and end credits; reduced from 120/240 to support short films).
- Cached frames: `cache/current_frame.jpg` (raw extract) and `cache/slowmovie_frame.jpg` (final processed).

## Sidecar Metadata Files

`generate_sidecars.py` is a dev-side utility (not run on the Pi):

- Scans `media/` for video files lacking a `.json` sidecar.
- Parses title and year from common filename patterns (`Title - YEAR__suffix.mp4`, `Title (YEAR).mp4`).
- Queries TMDB API (`/search/movie` + `/movie/{id}/credits`) for canonical title, year, director.
- Writes `{videoname}.json` with `title`, `year`, `director`, `tmdb_id`, `imdb_url`.
- Requires `tmdb_api_key` in `secrets.yaml`; supports `--dry-run` and `--verify` (validates all sidecars have required fields).
- Example sidecar: `media/Koyaanisqatsi - 1982__slowmovie.json` → title "Koyaanisqatsi", year "1983", director "Godfrey Reggio".

**Auto-generation on SlowMovie activation:** `talevision/media/sidecars.py` (no `rich` dependency) is called from `SlowMovie.on_activate()` in a daemon thread. Scans `media/` for videos without `.json`, calls TMDB silently. Module-level lock prevents concurrent runs. Silent no-op if no API key.

## Web Frontend (React SPA)

- Built with **Vite + React 18 + TypeScript + Tailwind CSS 3 + Radix UI primitives**.
- Source: `frontend/src/`. Build output: `talevision/web/static/dist/` (committed to repo).
- Build on Mac: `cd frontend && npm run build` → output goes directly to `talevision/web/static/dist/`.
- Served by Flask: `views.py` uses `send_file(dist/index.html)` if built; falls back to Jinja template.
- Data: TanStack React Query v5, polls `/api/status` every 12s (2s when waiting for frame render).
- Frame waiting state: when mode switch or force-refresh is triggered, shows `RenderingOverlay` until `status.last_update` advances past the trigger timestamp. 120s safety timeout.
- Fonts: self-hosted woff2 — Lobster (title), Chakra Petch 400/600/700 (display/body), Space Mono 400/700 (mono). No Google Fonts dependency.
- **Design system**: Solar Dust theme (from Vibemilk design system) — dark brown-black `bg: #1A1410`, gold accent `#E8A838`, terracotta `#D06B50`, cream text `#F0E6D6`. Lobster for logotype/headings, Chakra Petch for interface text. Rounded corners (4/6/8/10/12px). Borders use gold-alpha (`rgba(232,168,56,0.18)`).
- **Mode accent colours**: LitClock `#6A9FBF`, SlowMovie `#E8A838`, Wikipedia `#D06B50`, Weather `#7FA87F`, Museo `#B8860B`.
- **RenderingOverlay** (CRT vintage): dark `#1A1410` background, `NoiseCanvas` (100×62px canvas scaled to fill, ~13fps TV grain), CSS scanlines, gold sweep band, RadioWaves animation, mode name in Lobster + `animate-flicker`, "Tuning" label.
- **`pendingMode` state**: set in `playlistMut.onMutate` to `modes[0]`, cleared when `waiting` goes false. Prevents overlay from briefly showing the old mode name. Pass `pendingMode ?? currentMode` to `FramePreview`.
- **`lastSyncedRef` playlist sync**: tracks `playlist.join(',') + ':' + rotationInterval`. Prevents premature sync on preliminary `['litclock']` before server data arrives.
- **Language selector**: always visible at top (affects LitClock + Wikipedia). Shows full language names (`Italiano`, `Español`, etc.) via `LANG_NAMES` dict. `localLang` state for instant update.
- **Stats card**: shows Uptime (via `formatUptime(status?.uptime_seconds)`), Last render, Mode, Status. `uptime_seconds` field in `/api/status`.
- **Taglines**: 20 rotating sardonic taglines, one chosen per page load (`Math.random()`), displayed in Lobster italic at 12px below the "TaleVision" title.
- **Footer**: Netmilk SVG logo (full opacity, `hover:animate-shake`), GitHub repo link, MIT credit.
- **Do not gitignore `talevision/web/static/dist/`** — exception is set in `.gitignore`. The built bundle must be in the repo so the Pi can serve it after `git pull`.

## Web Server

`main.py` prefers **waitress** over Flask dev server:

```python
try:
    from waitress import serve
    serve(flask_app, host="0.0.0.0", port=port, threads=4,
          connection_limit=20, cleanup_interval=10)
except ImportError:
    flask_app.run(host="0.0.0.0", port=port, debug=False,
                 use_reloader=False, threaded=True)
```

waitress is included in `requirements.txt` (`waitress==3.0.2`). Always install it on Pi.

## Playlist / Rotation System

- `Orchestrator` supports a **playlist**: an ordered list of enabled modes that cycle automatically.
- `set_playlist(modes, rotation_interval)`: set which modes to cycle and at what interval.
- **Single mode** (playlist length 1): uses per-mode interval as before. Per-mode interval controls visible in dashboard.
- **Rotation** (playlist length 2+): after each render, waits `rotation_interval` seconds, then advances to next mode in playlist order. Per-mode interval controls hidden in dashboard (rotation interval takes over).
- `rotation_interval` default: 300s (5 min). Range: 30–3600s.
- Persisted to `user_prefs.json` alongside interval overrides: `{intervals: {...}, playlist: [...], rotation_interval: N}`.
- API: `POST /api/playlist` with `{modes: ["litclock", "slowmovie"], rotation_interval: 300}`.
- `GET /api/status` returns `playlist`, `playlist_index`, `rotation_interval` fields.
- Dashboard `PlaylistEditor`: checkboxes to enable/disable modes, up/down arrows to reorder, rotation interval input when 2+ modes enabled.
- 5 modes in registry: `litclock` (active), `slowmovie` (active), `wikipedia` (active), `weather` (active), `museo` (active). ANSi and Teletext removed.

## Per-mode Interval Overrides

- `Orchestrator.set_mode_interval(mode, seconds)` / `reset_mode_interval(mode)`: override/restore per-mode refresh intervals at runtime.
- Overrides persisted to `user_prefs.json` in the project root (gitignored).
- API: `GET /api/interval`, `POST /api/interval` `{mode, seconds}`, `DELETE /api/interval/<mode>`.
- `get_status()` response includes `intervals` dict with `effective`, `default`, `overridden` per mode.
- Dashboard shows per-mode minute input with "Set" / "reset" buttons (only visible in single-mode, hidden during rotation).

## Orchestrator Loop Logging

LOOP-step log messages in `orchestrator.py` are at **DEBUG** level (changed from INFO). Normal operation produces no INFO noise from the loop — only meaningful state transitions (mode switch, suspend toggle, errors) remain at INFO.

## Suspend Scheduler

- `SuspendScheduler` handles overnight windows correctly (e.g., 23:00–07:00): if `start > end`, wraps midnight.
- **Day semantics**: `days` list = days the device is fully OFF (suspend days). Days NOT in the list are "active days" — suspend applies only during the time window on those days. Empty list = time window applies to all days (no full-suspend days).
- **Full-suspend days**: if today's weekday is in `days`, device is suspended ALL 24 hours — no time check.
- **Active days**: if today's weekday is NOT in `days`, device follows the time window (suspended during window, active outside).
- **Example**: active 09–18 Mon-Fri, Sat+Sun off → device OFF from Fri 18:00 to Mon 09:00 continuously.
- `next_wake_time()` returns the datetime when suspension ends. Skips forward past full-suspend days to find the first active day where the wake time (end) applies. Returns `None` if all 7 days are in `days` (device configured to never wake).
- Thread-safe `update()` method called from API handler.
- Suspend screen is rendered once on entry and held; `_suspended_displayed` flag prevents re-rendering.
- **BBS/NFO suspend screen** (`talevision/render/suspend_screen.py`): renders to the e-ink display when suspended. White background, DejaVuSansMono Bold font (24/19/16 pt), box-drawing chars (`╔═╗║╚╝╠╣`), orange header "T · A · L · E · V · I · S · I · O · N", active hours/days row (`[MON] [TUE]...`), resume time, rainbow border bars top/bottom (same as welcome screen). `inner_w=60` to fit all 7 days with single-space separators. The orchestrator intercepts the loop before `active.render()` and calls this instead. Rendered once on suspend entry and held until resume.
- **Dashboard UX inversion (double)**: UI shows "active hours" and "active days" — both inverted at the API boundary. Hours: `UI activeFrom → API end`, `UI activeTo → API start`. Days: UI sends active days, frontend inverts to suspend days before POST (`[0,1,2,3,4,5,6].filter(d => !activeDays.includes(d))`). On load, suspend days from API are inverted back to active days for display.

## InterruptibleTimer

- `threading.Event`-based timer in `talevision/system/timer.py`.
- Interrupt signal is **preserved** if `interrupt()` is called before `wait()` — next `wait()` returns immediately.
- `wait()` clears the event after returning, not before — preserves the pre-wait interrupt.

## Current Product Behaviors

- **LitClock mode**: renders a literary quote for the current minute; 6 languages (it/es/pt/en/fr/de) switchable at runtime. Refresh: 300 s.
- **SlowMovie mode**: picks a random film and extracts a random frame every 5 min with PIL enhancement and info overlay. Each render picks a new random film (not sticky). TMDB QR bottom-right. Auto-generates sidecar `.json` on first activation.
- **Wikipedia mode**: fetches a random article via Wikipedia REST API (summary) + MediaWiki action API (full extract up to 3000 chars). Renders title + body + thumbnail (proportional width, no forced crop) + QR. Text wraps in three zones: beside thumbnail (narrow), below thumbnail (full width), in QR zone (qr_safe_w). Last line gets ` …` ellipsis if clipped. Babel-formatted date header. 6 languages. Refresh: 300 s.
- **Weather mode**: fetches wttr.in native ANSI terminal output (flag `AQF`), parses SGR escape codes char-by-char, and renders on PIL with Inconsolata Nerd Font Mono. Two-zone layout: custom header (`City · HH:MM` in Signika-Bold 16pt) + current conditions at 14pt (ASCII art cloud/sun + weather data) + forecast tables at 12pt. ANSI colours mapped to e-ink 7-colour palette. Location configurable with lat/lon coordinates (Open-Meteo geocoding). Metric/Imperial toggle. Refresh: 300 s.
- **Suspend schedule**: overnight window (e.g. 17:00–08:00), wraps midnight; day-of-week filtering; BBS/NFO style screen on e-ink.
- **Playlist rotation**: orchestrator cycles through enabled modes in order with a unified rotation interval (default 5 min). Single-mode uses per-mode interval. Configurable from dashboard.
- **Web dashboard**: React SPA (Vite + Tailwind) at `http://<DEVICE_IP>:<PORT>`; warm vintage cream palette (bg #F1EBD9, accent #CA796D); Lobster logotype; CRT vintage RenderingOverlay (NoiseCanvas + TuningGauge SVG + scanlines); Stats card; PlaylistEditor with DnD reorder; Language selector (full names, always visible); rotating taglines. Netmilk logo in footer.
- **`/api/status` uptime**: `uptime_seconds` field added — seconds since orchestrator started. Used in Stats card.
- **Per-mode refresh intervals**: overridable from dashboard, persisted to `user_prefs.json` (visible in single-mode only).
- **Museo mode**: fetches random public-domain artworks from 3 museum APIs (Met, AIC, Cleveland) in round-robin rotation. PIL enhancement (brightness/contrast/colour). Overlay: title·date (Signika-Bold 20pt), artist (Signika-Light 20pt), museum·department (Inconsolata 16pt) in rounded-rect box bottom-left; QR to museum object page bottom-right. 50-ID recent buffer prevents repeats. 24h catalogue cache. Fallback: last cached frame or "MUSEO" splash. Refresh: 300 s.
- **Physical buttons**: GPIO 5/6/16/24 (A/B/C/D on Inky Impression); remappable in `config.yaml`.
- **Off-Pi fallback**: no Inky → saves `talevision_frame.png`; no GPIO → one warning, silent from then on.

## Recurring Gotchas

- **Pillow on armv6l**: `pip install Pillow` may fail (no wheel); use `sudo apt install python3-pil` on Pi.
- **ffmpeg**: `ffmpeg-python` is a Python wrapper only — the system binary (`/usr/bin/ffmpeg`) must be installed via `apt install ffmpeg`.
- **Inky SPI**: must be enabled via `raspi-config → Interface Options → SPI` before Inky will work; `scripts/install.sh` handles this.
- **GPIO group**: run as the deploy user or add to `gpio` group; otherwise button polling silently no-ops.
- **Panel refresh**: e-ink takes ~30 s to update; software intervals (300 s / 90 s) are longer by design — this is not a bug.
- **SPI chip select conflict (CRITICAL)**: on Trixie, Inky SPI fails with default `dtparam=spi=on`. Add `dtoverlay=spi0-0cs` on the line after `dtparam=spi=on` in `/boot/firmware/config.txt`, then reboot. Without this, display never initializes.
- **Inky Impression 7" has NO EEPROM**: `inky.auto.auto()` always fails with "No EEPROM detected!". Must use `from inky.inky_ac073tc1a import Inky` with explicit `resolution=(800, 480)`. The older `inky.inky_uc8159` does NOT support 800×480. Library version: inky 2.3.0.
- **Inky 7-colour native palette**: Black (0,0,0), White (255,255,255), Red (255,0,0), Green (0,255,0), Blue (0,0,255), Yellow (255,255,0), Orange (255,128,0). Pure colours render crisp; intermediate colours get dithered.
- **Inky "Busy Wait" warnings**: `Busy Wait: Timed out after N.NNs` warnings from the ac073tc1a driver are normal during e-ink refresh. The display takes ~30–60 s to fully update. These are not errors.
- **E-ink colour contrast**: Green text on white e-ink background is too faint to read. For white backgrounds, use Black for body text. Red, Blue, Orange work well for accents/headers. Yellow is faint on white — use only on dark backgrounds.
- **Welcome screen**: TV frame graphic (`assets/img/talevision-frame.png`, RGBA composited on white) boot splash, shown for **30 s**. Lobster 75pt BLACK title, random tagline (20 options), `— STARTING IN 30 SECONDS —` in red, compact BBS info box (HOSTNAME.local/IP/DASHBOARD only, `inner_w=64`), `TaleVision v1.5 · Netmilk Studio` footer in blue. Saved to `cache/welcome_frame.png` on every boot. Rendered by `talevision/render/welcome_screen.py`, triggered from `orchestrator.run()`.
- **Suspend screen**: TV frame graphic (same as welcome screen) composited on white. Lobster 65pt BLACK title, `· DISPLAY SUSPENDED ·` in ORANGE, random literary quote in Taviraj Italic, BBS info box (active hours/days/resume time) in DejaVuSansMono Bold 19/16pt, timestamp in grey. Rendered once on suspend entry and held — no periodic refresh.
- **Suspend timer sleep**: when suspended, the orchestrator sleeps until `next_wake_time()` (the actual resume time), not for `effective_interval`. This prevents unnecessary loop cycles and display refreshes during the suspend window.
- **`set_suspend_schedule()` must interrupt the timer**: if the schedule changes via API while suspended, the loop is sleeping until the old `next_wake_time`. Without `timer.interrupt()` + `_suspended_displayed = False` in `set_suspend_schedule()`, the new schedule takes effect only when the old sleep expires — which can be hours away.
- **`set_playlist()` and `get_status()` use `_lock`**: `_playlist`, `_playlist_index`, `_rotation_interval`, `_interval_overrides` are shared between the Flask thread and the main loop. All reads/writes to these fields go under `_lock`. `set_playlist()` derives `switch_needed` inside the lock before releasing, then enqueues the action outside.
- **`render()` has no `is_suspended` parameter**: the orchestrator intercepts suspend before calling `render()`, so modes never receive a suspended state. `DisplayMode.render()` signature is `render(self) -> Image.Image` — no flag.
- **IP detection on Pi Zero W**: `socket.getaddrinfo()` does not return LAN/Tailscale IPs; `main.py` uses `subprocess.check_output(["hostname", "-I"])` instead.
- **Orchestrator status cache**: `get_status()` reads from `_status_cache` dict protected by a separate `_status_lock`, never the render lock — prevents Flask threads from blocking during long SPI writes (~56 s).
- **waitress required**: without waitress, Flask dev server runs instead — acceptable on Pi but not ideal.
- **`archive/`**: reference implementations, gitignored, read-only — never modify, never commit.
- **`litclock.refresh_rate`**: set to `300` in config.yaml (5 min) — intentional, not 60 s.
- **LitClock detail baseline**: author (italic) / separator / title (regular) must all use `anchor="ls"` (stroke/baseline) with the same `baseline_y`. Using `anchor="lb"` (bottom of bounding box) causes misalignment when italic and regular bounding-box heights differ.
- **`last_update` timestamp**: `status.last_update` is a Unix float (seconds). In JS: multiply by 1000 before `new Date()`. `Date.now()` (ms) comparison for frame-ready detection works correctly after this conversion.
- **DejaVuSansMono.ttf**: required by `suspend_screen.py` for box-drawing characters. Must be present in `assets/fonts/` — copy from Pi (`/usr/share/fonts/truetype/dejavu/`) or install on Pi via `apt install fonts-dejavu`.
- **`dist/` in gitignore**: `.gitignore` has `dist/` globally but `!talevision/web/static/dist/` exception. Without the exception the built React bundle is gitignored and the Pi can't serve it after `git pull`.

## Systemd Service

The canonical service file is `deploy/talevision.service`. On Pi:

```bash
sudo cp deploy/talevision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable talevision
sudo systemctl start talevision
```

`User=`, `WorkingDirectory=`, and `ExecStart=` in the service file must match the actual deploy user and venv path. The file currently uses the deploying user's home directory — update if deploying as a different user.

## Pre-Push Checklist

1. No secrets in committed files: `grep -rn "tmdb_api_key\|password=\|api_key=\|token=" talevision/ config.yaml`
2. `secrets.yaml` not staged: `git status | grep secrets.yaml`
3. No `media/*.mp4` staged: `git status | grep media/`
4. Static analysis: `bandit -r talevision/ -ll`
5. Dependency CVEs: `pip-audit -r requirements.txt`
6. Render smoke test: `python main.py --render-only --mode litclock && python main.py --render-only --mode slowmovie && python main.py --render-only --mode wikipedia && python main.py --render-only --mode weather && python main.py --render-only --mode museo`

## Wikipedia Mode

- `talevision/modes/wikipedia.py` — `WikipediaMode` class.
- Fetch: `GET https://{lang}.wikipedia.org/api/rest_v1/page/random/summary` — random article per render call.
- Languages: `it`, `es`, `pt`, `en`, `fr`, `de` (in that order). Switchable via `POST /api/language`.
- Render (800×480, white bg): time+date header → accent separator → article title → extract body → thumbnail 180×135px top-right → QR 80×80px bottom-right.
- **Header**: single line `{HH:MM} · {d MMMM} {'YY}` in Taviraj-SemiBold 32pt, black. `"Wikipedia · IT"` right-aligned in Taviraj-Regular 24pt. Date is babel-formatted (`format_date(now, "d MMMM", locale=LANG_TO_BABEL[lang])`).
- **Text clipping**: when body is clipped, last visible line gets ` …` ellipsis. QR code is self-explanatory — no additional hint text.
- Article title: Signika-Bold 26pt, max 2 lines. Extract: Taviraj-Regular 22pt, word-wrapped to available width.
- QR: `qrcode[pil]`. Thumbnail: `urllib.request`, graceful skip on timeout/error. Cropped 4:3 then resized LANCZOS.
- Config: `wikipedia.refresh_interval` (default 300s), `wikipedia.language`, `wikipedia.timeout`.
- `get_state()` exposes `title`, `language`, `url` in status extra.

## Weather Mode (wttr.in ANSI)

- `talevision/modes/weather.py` — `WeatherMode` class.
- Fetch: `GET http://wttr.in/{lat},{lon}?AQF&lang={lang}&{units}` — raw ANSI terminal output, no API key. Flags: `A` (force ANSI), `Q` (superquiet — removes coordinate header), `F` (no follow). **HTTP not HTTPS** — HTTPS handshake times out on Pi Zero W (armv6l).
- ANSI parsing: `_parse_ansi()` extracts characters with SGR colour codes and bold flags. `ANSI_COLOR_MAP` maps 16 ANSI colours to 7 e-ink native colours (green→blue, yellow→orange, white→black for inverted bg).
- Font: Inconsolata Nerd Font Mono (Bold variant). 125/125 Unicode glyph coverage (arrows ↑↓←→↗↘, degree °, box-drawing ┌─┐│└┘, etc.). 6 font files in `assets/fonts/`.
- Two-zone rendering:
  - **Header**: `"{city} · {HH:MM}"` in Signika-Bold 16pt, centred.
  - **Current conditions** (above `┌`): ASCII art weather icon + temperature/wind/humidity at 14pt. Split detected via `_find_forecast_start()` (first line with `┌` box-drawing char).
  - **Forecast tables** (from `┌` onwards): 3-day forecast at 12pt. `LINE_GAP=0` to fit all 37 lines.
- Location: configurable from dashboard with autocomplete. Stored as `city` + `lat` + `lon`. Set via `POST /api/weather/location` with `{city, lat, lon}`.
- Autocomplete: `GET /api/weather/search?q=&lang=` → Open-Meteo free geocoding API (no key), returns `[{name, display, lat, lon}]`.
- Units: `m` (metric), `u` (imperial), `M` (metric + m/s wind). Toggle via `POST /api/weather/units`.
- Config: `weather.refresh_interval` (default 300s), `weather.city`, `weather.lat`, `weather.lon`, `weather.units`, `weather.language`, `weather.timeout`.
- `/api/status` includes `weather_units` field.
- Graceful fallback: if fetch fails, shows last cached ANSI data or "Weather unavailable" message.

## Museo Mode

- `talevision/modes/museo.py` — `MuseoMode` class. Providers in `talevision/modes/museo_providers/`.
- **Up to 4 providers** (round-robin rotation): Met (NYC, ~200k, no key), Cleveland (~41k, no key), V&A (London, ~732k, no key), Smithsonian (~87k across SAAM/NPG/Cooper Hewitt/Freer, free API key). Smithsonian requires API key via `museo.smithsonian_api_key` or env var `SMITHSONIAN_API_KEY`. Without key, gracefully degrades to Met + Cleveland + V&A (~973k total).
- Provider rotation: deterministic round-robin. Index advances by 1 each time Museo renders, regardless of what other modes run between calls. Index persists in-memory only (resets on restart).
- **Catalogue cache**: `museo_cache.py`, file-based JSON in `cache/`, 24h TTL (`cache_max_age=86400`). Refreshed on `on_activate()` and on render if stale.
- **Artwork selection**: `pick_random_id()` per provider, up to 5 retries. 50-ID deque (`_recent_ids`) prevents repeats across renders.
- **Image fetch**: `urllib.request` with `User-Agent: TaleVision/1.0`, configurable timeout (default 60s).
- **PIL enhancement**: Brightness 1.1 → Contrast 1.2 → Color 1.3 (no gamma). `ImageOps.fit()` cover mode.
- **Overlay** (same pattern as SlowMovie): RGBA layer, `rounded_rectangle(radius=8, fill=(0,0,0,190))`, `alpha_composite`. Three text lines: title·date (Signika-Bold 20pt, white), artist (Signika-Light 20pt, white), museum·department (Inconsolata Bold 18pt, light grey). QR code bottom-right links to museum object page.
- **Fallback**: warm fallback from `cache/museo_last_frame.png`; cold fallback = white bg + "MUSEO" in Lobster 50pt + "Connection unavailable" in Taviraj 18pt.
- Config: `museo.refresh_interval` (300s), `museo.timeout` (60s), `museo.cache_max_age` (86400s), `museo.brightness/contrast/color`, `museo.smithsonian_api_key`, overlay sub-config, fonts sub-config.
- `get_state()` exposes `title`, `artist`, `museum`, `provider`, `object_url` in status extra.

## Known Open TODOs

- `generate_sidecars.py` lives in repo root; should move to `scripts/`.
- Web dashboard has no HTTP basic auth — LAN-only deployment assumed.

## Open Questions

- Should the web dashboard have optional HTTP basic auth?

## Public Logging Rule

When adding notes to versioned docs:

- keep only generalized lessons
- avoid local identifiers (paths, IPs, hostnames, serial IDs)
- do not paste raw logs with personal or network metadata
