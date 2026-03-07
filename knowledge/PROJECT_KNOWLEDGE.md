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

## Orchestrator Loop Logging

LOOP-step log messages in `orchestrator.py` are at **DEBUG** level (changed from INFO). Normal operation produces no INFO noise from the loop — only meaningful state transitions (mode switch, suspend toggle, errors) remain at INFO.

## Suspend Scheduler

- `SuspendScheduler` handles overnight windows correctly (e.g., 23:00–07:00): if `start > end`, wraps midnight.
- Day-of-week filtering: `days` list (0=Mon, 6=Sun); empty list = all days.
- `next_wake_time()` returns the datetime when suspension ends (used by dashboard).
- Thread-safe `update()` method called from API handler.
- Suspend screen is rendered once on entry and held; `_suspended_displayed` flag prevents re-rendering.

## InterruptibleTimer

- `threading.Event`-based timer in `talevision/system/timer.py`.
- Interrupt signal is **preserved** if `interrupt()` is called before `wait()` — next `wait()` returns immediately.
- `wait()` clears the event after returning, not before — preserves the pre-wait interrupt.

## Current Product Behaviors

- **LitClock mode**: renders a literary quote for the current minute; 6 languages switchable at runtime.
- **SlowMovie mode**: extracts a random film frame every 90 s with PIL enhancement and info overlay.
- **Suspend schedule**: overnight window (e.g. 23:00–07:00), wraps midnight correctly; day-of-week filtering supported.
- **Web dashboard**: Flask 3 + waitress at `http://<DEVICE_IP>:<PORT>`; all controls via JSON API, no page reloads.
- **Physical buttons**: GPIO 5/6/16/24 (A/B/C/D on Inky Impression); remappable in `config.yaml`.
- **Off-Pi fallback**: no Inky → saves `talevision_frame.png`; no GPIO → one warning, silent from then on.

## Recurring Gotchas

- **Pillow on armv6l**: `pip install Pillow` may fail (no wheel); use `sudo apt install python3-pil` on Pi.
- **ffmpeg**: `ffmpeg-python` is a Python wrapper only — the system binary (`/usr/bin/ffmpeg`) must be installed via `apt install ffmpeg`.
- **Inky SPI**: must be enabled via `raspi-config → Interface Options → SPI` before Inky will work; `scripts/install.sh` handles this.
- **GPIO group**: run as `pi` user or add to `gpio` group (`sudo usermod -aG gpio pi`); otherwise button polling silently no-ops.
- **Panel refresh**: e-ink takes ~30 s to update; software intervals (60 s / 90 s) are longer by design — this is not a bug.
- **SPI chip select conflict (CRITICAL)**: on Trixie, Inky SPI fails with default `dtparam=spi=on`. Add `dtoverlay=spi0-0cs` on the line after `dtparam=spi=on` in `/boot/firmware/config.txt`, then reboot. Without this, display never initializes.
- **IP detection on Pi Zero W**: `socket.getaddrinfo()` does not return LAN/Tailscale IPs; `main.py` uses `subprocess.check_output(["hostname", "-I"])` instead.
- **Orchestrator status cache**: `get_status()` reads from `_status_cache` dict protected by a separate `_status_lock`, never the render lock — prevents Flask threads from blocking during long SPI writes (~56 s).
- **waitress required**: without waitress, Flask dev server runs instead — acceptable on Pi but not ideal.
- **`archive/`**: reference implementations, gitignored, read-only — never modify, never commit.
- **`litclock.refresh_rate`**: currently set to `300` in config.yaml (5 min), not 60 s as documented in README/DECISIONS. Verify intent before changing.

## Systemd Service

The canonical service file is `deploy/talevision.service`. On Pi:

```bash
sudo cp deploy/talevision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable talevision
sudo systemctl start talevision
```

Assumes venv at `/home/pi/talevision/venv` and repo at `/home/pi/talevision`.

## Pre-Push Checklist

1. No secrets in committed files: `grep -rn "tmdb_api_key\|password=\|api_key=\|token=" talevision/ config.yaml`
2. `secrets.yaml` not staged: `git status | grep secrets.yaml`
3. No `media/*.mp4` staged: `git status | grep media/`
4. Static analysis: `bandit -r talevision/ -ll`
5. Dependency CVEs: `pip-audit -r requirements.txt`
6. Render smoke test: `python main.py --render-only --mode litclock && python main.py --render-only --mode slowmovie`

## Known Open TODOs

- WebUI mode cards don't reflect active state on page load — needs `/api/status` poll to set initial active card.
- WebUI preview shows "No frame yet" on first load — JS only loads frame after status poll.
- `generate_sidecars.py` lives in repo root; should move to `scripts/`.
- SlowMovie picks the same video until removed — no rotation between multiple films yet.

## Open Questions

- Should the web dashboard have optional HTTP basic auth?
- `litclock.refresh_rate` is 300 s in config.yaml but README/DECISIONS document 60 s — which is correct?

## Public Logging Rule

When adding notes to versioned docs:

- keep only generalized lessons
- avoid local identifiers (paths, IPs, hostnames, serial IDs)
- do not paste raw logs with personal or network metadata
