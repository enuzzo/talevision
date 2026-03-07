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
- Typography: Babel (locale formatting), Signika + Taviraj TTF fonts
- Display: Pimoroni Inky Impression 7-colour, 800×480 px, 7-colour e-ink (SPI)
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
- Current video is remembered in-memory across render cycles (`_current_video`); only re-selected if removed from `media/`.
- Frame skip: `skip_start_seconds=120`, `skip_end_seconds=240` (avoids cold-open slates and end credits).
- Cached frames: `cache/current_frame.jpg` (raw extract) and `cache/slowmovie_frame.jpg` (final processed).

## Sidecar Metadata Files

`generate_sidecars.py` is a dev-side utility (not run on the Pi):

- Scans `media/` for video files lacking a `.json` sidecar.
- Parses title and year from common filename patterns (`Title - YEAR__suffix.mp4`, `Title (YEAR).mp4`).
- Queries TMDB API (`/search/movie` + `/movie/{id}/credits`) for canonical title, year, director.
- Writes `{videoname}.json` with `title`, `year`, `director`, `tmdb_id`, `imdb_url`.
- Requires `tmdb_api_key` in `secrets.yaml`; supports `--dry-run`.
- Example sidecar: `media/Koyaanisqatsi - 1982__slowmovie.json` → title "Koyaanisqatsi", year "1983", director "Godfrey Reggio".

**Auto-generation on SlowMovie activation:** `talevision/media/sidecars.py` (no `rich` dependency) is called from `SlowMovie.on_activate()` in a daemon thread. Scans `media/` for videos without `.json`, calls TMDB silently. Module-level lock prevents concurrent runs. Silent no-op if no API key.

## Web Frontend (React SPA)

- Built with **Vite + React 18 + TypeScript + Tailwind CSS 3 + Radix UI primitives**.
- Source: `frontend/src/`. Build output: `talevision/web/static/dist/` (committed to repo).
- Build on Mac: `cd frontend && npm run build` → output goes directly to `talevision/web/static/dist/`.
- Served by Flask: `views.py` uses `send_file(dist/index.html)` if built; falls back to Jinja template.
- Data: TanStack React Query v5, polls `/api/status` every 12s (2s when waiting for frame render).
- `ParticleBackground.tsx`: canvas RAF loop, 80 violet/cyan particles, mouse repulsion within 110px.
- Frame waiting state: when mode switch or force-refresh is triggered, shows `RenderingOverlay` (scan line + rings + brackets) until `status.last_update` advances past the trigger timestamp. 120s safety timeout.
- Fonts loaded from Google Fonts (Montserrat + Space Mono). No local font files needed for the web UI.
- **Design system**: ScryBar Design System v1.4 (default theme). Deep navy backgrounds (#070D2D/#0B1437/#111C44), violet accent (#7551FF), cyan secondary (#39B8FF). Montserrat for display headings, Space Mono for monospace. Rounded corners (8px/12px/16px). Reference: `assets/netmilk_design_system/`.
- **Footer**: Netmilk Studio SVG logo centered, loaded from `https://netmi.lk/wp-content/uploads/2024/10/netmilk.svg`.
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
- 4 modes in registry: `litclock` (active), `slowmovie` (active), `teletext` (coming soon), `ansi` (coming soon). Coming-soon modes shown in UI but disabled.

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
- `next_wake_time()` returns the datetime when suspension ends. Skips forward past full-suspend days to find the first active day where the wake time (end) applies.
- Thread-safe `update()` method called from API handler.
- Suspend screen is rendered once on entry and held; `_suspended_displayed` flag prevents re-rendering.
- **BBS/NFO suspend screen** (`talevision/render/suspend_screen.py`): renders to the e-ink display when suspended. Black background, DejaVuSansMono font, box-drawing chars (`╔═╗║╚╝╠╣`), amber header "T · A · L · E · V · I · S · I · O · N", suspend hours/days row (`[MON] [TUE]...`), resume time. `inner_w=60` to fit all 7 days with single-space separators. Labels read "SUSPEND HOURS" and "SUSPEND DAYS" (values are the raw config suspend window). The orchestrator intercepts the loop before `active.render()` and calls this instead.
- **Dashboard UX inversion (double)**: UI shows "active hours" and "active days" — both inverted at the API boundary. Hours: `UI activeFrom → API end`, `UI activeTo → API start`. Days: UI sends active days, frontend inverts to suspend days before POST (`[0,1,2,3,4,5,6].filter(d => !activeDays.includes(d))`). On load, suspend days from API are inverted back to active days for display.

## InterruptibleTimer

- `threading.Event`-based timer in `talevision/system/timer.py`.
- Interrupt signal is **preserved** if `interrupt()` is called before `wait()` — next `wait()` returns immediately.
- `wait()` clears the event after returning, not before — preserves the pre-wait interrupt.

## Current Product Behaviors

- **LitClock mode**: renders a literary quote for the current minute; 6 languages switchable at runtime. Refresh: 300 s (5 min).
- **SlowMovie mode**: extracts a random film frame every 90 s with PIL enhancement and info overlay. TMDB QR (white-on-black rounded box, bottom-right). Auto-generates sidecar `.json` on first activation.
- **Suspend schedule**: overnight window (e.g. 23:00–07:00), wraps midnight; day-of-week filtering; BBS/NFO style screen on e-ink.
- **Playlist rotation**: orchestrator cycles through enabled modes in order with a unified rotation interval (default 5 min). Single-mode uses per-mode interval. Configurable from dashboard.
- **Web dashboard**: React SPA (Vite + Tailwind) at `http://<DEVICE_IP>:<PORT>`; ScryBar Design System (deep navy + violet accent); PlaylistEditor with reorder; rendering overlay on mode switch; polling accelerates to 2s while waiting for new frame. Netmilk logo in footer.
- **Per-mode refresh intervals**: overridable from dashboard, persisted to `user_prefs.json` (visible in single-mode only).
- **Physical buttons**: GPIO 5/6/16/24 (A/B/C/D on Inky Impression); remappable in `config.yaml`.
- **Off-Pi fallback**: no Inky → saves `talevision_frame.png`; no GPIO → one warning, silent from then on.

## Recurring Gotchas

- **Pillow on armv6l**: `pip install Pillow` may fail (no wheel); use `sudo apt install python3-pil` on Pi.
- **ffmpeg**: `ffmpeg-python` is a Python wrapper only — the system binary (`/usr/bin/ffmpeg`) must be installed via `apt install ffmpeg`.
- **Inky SPI**: must be enabled via `raspi-config → Interface Options → SPI` before Inky will work; `scripts/install.sh` handles this.
- **GPIO group**: run as the deploy user or add to `gpio` group; otherwise button polling silently no-ops.
- **Panel refresh**: e-ink takes ~30 s to update; software intervals (300 s / 90 s) are longer by design — this is not a bug.
- **SPI chip select conflict (CRITICAL)**: on Trixie, Inky SPI fails with default `dtparam=spi=on`. Add `dtoverlay=spi0-0cs` on the line after `dtparam=spi=on` in `/boot/firmware/config.txt`, then reboot. Without this, display never initializes.
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
6. Render smoke test: `python main.py --render-only --mode litclock && python main.py --render-only --mode slowmovie`

## Known Open TODOs

- `generate_sidecars.py` lives in repo root; should move to `scripts/`.
- SlowMovie picks the same video until removed — no rotation between multiple films yet.
- Web dashboard has no HTTP basic auth — LAN-only deployment assumed.

## Open Questions

- Should the web dashboard have optional HTTP basic auth?

## Public Logging Rule

When adding notes to versioned docs:

- keep only generalized lessons
- avoid local identifiers (paths, IPs, hostnames, serial IDs)
- do not paste raw logs with personal or network metadata
