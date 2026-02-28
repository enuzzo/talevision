# TaleVision Project Knowledge

Stable technical context for all assistants.

## Repository Layout

- `talevision/`: main application package (modes, render, system, web, config).
- `assets/`: fonts, quote CSVs, icons — committed and versioned.
- `media/`: user-supplied `.mp4` film files (gitignored, `.gitkeep` committed).
- `cache/`: runtime caches — video info JSON + rendered frames (gitignored).
- `scripts/`: Pi install and systemd deploy scripts.
- `archive/`: reference implementations (gitignored — read only, never modify).
- `knowledge/`: shared, sanitized cross-assistant knowledge (public, versioned).

## Core Stack

- Language/runtime: Python 3.11+
- Web: Flask 3.x
- Image: Pillow 10+, ffmpeg (system-installed via apt on Pi)
- Config: PyYAML + dacite dataclasses
- Typography: Babel (locale formatting), Signika + Taviraj TTF fonts
- Display: Pimoroni Inky Impression 7-colour, 800×480 px, 7-colour e-ink (SPI)
- Target platform: Raspberry Pi Zero W (armv6l, 512MB RAM)
- Dev platform: macOS or Linux (no hardware required for render pipeline)

## Canonical Build / Run Commands

Install (dev, no hardware):

```bash
python3 -m venv venv && source venv/bin/activate
pip install Pillow Flask PyYAML babel rich dacite qrcode[pil]
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

## Configuration Boundaries

- `config.yaml` — committed, all non-secret options, sane defaults.
- `secrets.yaml` — local only, gitignored, never committed.
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

### SlowMovie

- Video cache key: SHA256 of the video file path (via `frame_cache.py`).
- PIL enhancement chain: Brightness → Gamma (custom LUT via `point()`) → Contrast → Color.
- Fit modes: `cover` = `ImageOps.fit` (crop to fill); `contain` = thumbnail + paste on black canvas.
- Overlay: RGBA layer, `rounded_rectangle(radius=8, fill=(0,0,0,190))`, `alpha_composite` at the end.
- QR URL pattern: `https://www.imdb.com/find?q={title}` (IMDb search link).
- Metadata source: `{video}.json` sidecar file with `title`, `director`, `year` keys; fallback to filename stem.

## Current Product Behaviors

- **LitClock mode**: renders a literary quote for the current minute every 60 seconds; 6 languages switchable at runtime.
- **SlowMovie mode**: extracts and renders a random film frame every 90 seconds with PIL enhancement and info overlay.
- **Suspend schedule**: overnight window (e.g. 23:00–07:00), wraps midnight correctly; day-of-week filtering supported.
- **Web dashboard**: Flask 3 at `http://<DEVICE_IP>:<PORT>`; all controls via JSON API, no page reloads.
- **Physical buttons**: GPIO 5/6/16/24 (A/B/C/D on Inky Impression); remappable in `config.yaml`.
- **Off-Pi fallback**: no Inky → saves `talevision_frame.png`; no GPIO → one warning, silent from then on.

## Recurring Gotchas

- **Pillow on armv6l**: `pip install Pillow` may fail (no wheel); use `sudo apt install python3-pil` on Pi.
- **ffmpeg**: `ffmpeg-python` is a Python wrapper only — the system binary (`/usr/bin/ffmpeg`) must be installed via `apt install ffmpeg`.
- **Inky SPI**: must be enabled via `raspi-config → Interface Options → SPI` before Inky will work; `scripts/install.sh` handles this.
- **GPIO group**: run as `pi` user or add to `gpio` group (`sudo usermod -aG gpio pi`); otherwise button polling silently no-ops.
- **Panel refresh**: e-ink takes ~30 s to update; software intervals (60 s / 90 s) are longer by design — this is not a bug.
- **`archive/`**: reference implementations, gitignored, read-only — never modify, never commit.

## Open Questions

- Should the web dashboard have optional HTTP basic auth?
- Should LitClock and SlowMovie share a single quotes/fallback CSV pool, or keep separate per-mode pools?

## Public Logging Rule

When adding notes to versioned docs:

- keep only generalized lessons
- avoid local identifiers (paths, IPs, hostnames, serial IDs)
- do not paste raw logs with personal or network metadata
