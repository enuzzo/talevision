# TaleVision — Codex Memory

## Prime Directives
- Never write secrets in plain text anywhere (files, logs, commits, this file)
- Preserve visual output: LitClock typography + SlowMovie QR+overlay are non-negotiable
- Pi Zero lean: no headless browsers, no heavy deps; PIL + Flask + inky only
- archive/ is reference only — never modify, always gitignored

## Technical Stack
- Python 3.11+, Pillow, Flask 3, PyYAML, Babel, rich, inky, ffmpeg-python, qrcode[pil], RPi.GPIO
- Display: 800x480 Inky Impression (7-color e-ink), saturation via inky API
- Entry point: `python main.py`; config: `config.yaml`; secrets: `secrets.yaml` (local only)
- Web dashboard: http://<pi-ip>:5000

## Secrets Rules
- secrets.yaml → GITIGNORED, NEVER COMMITTED
- secrets.yaml.example → committed with placeholder values only
- No passwords, tokens, or credentials anywhere in committed files
- .codex/ files must never contain real credential values

## Key File Paths
- Config: `config.yaml` (committed), `secrets.yaml` (local)
- Fonts: `assets/fonts/`
- Quote data: `assets/lang/quotes-{lang}.csv` + `assets/lang/fallback.csv`
- Movies: `media/` (gitignored)
- Frame cache: `cache/` (gitignored)
- Reference: `archive/` (gitignored)

## Gotchas — Pi Zero W (armv6l)
- [ASSUMPTION] Pillow must be installed from system packages or armv6l wheel (pip wheel may fail)
- [ASSUMPTION] ffmpeg must be apt-installed, not pip; ffmpeg-python is just a wrapper
- [ASSUMPTION] inky library requires SPI enabled (raspi-config)
- [ASSUMPTION] RPi.GPIO requires running as root or gpio group membership

## Key Rendering Invariants

### LitClock (preserve exactly from archive/litclock/lc.py)
- `wrap_text_block()`: wrap at max_width px using textbbox
- `draw_header()`: Babel locale format, separator line draw
- `draw_centered_text_block()`: centered lines with configurable line_spacing
- Vertical centering: `(avail_h - content_h)//2 - vertical_centering_adjustment`
- Details row: em-dash author + " - " separator + title, drawn on one line centered
- Italic switch: if `<em>` tag in raw quote AND use_italic_for_em=true → use quote_italic font

### SlowMovie (preserve exactly from archive/slowmovie/sm.py)
- SHA256 hash of video file for cache key
- PIL chain: Brightness → Gamma (custom LUT) → Contrast → autocontrast? → Color
- Fit modes: cover=ImageOps.fit, contain=thumbnail+paste on black canvas
- Overlay: RGBA layer, rounded_rectangle box (radius=8), alpha_composite at end
- QR: imdb_search URL = f"https://www.imdb.com/find?q={title}"

## Preflight Checklist (pre-push)
- [ ] archive/ is in .gitignore and not tracked
- [ ] secrets.yaml is in .gitignore and not tracked
- [ ] media/ .mp4 files are in .gitignore
- [ ] No hardcoded passwords/tokens in any committed file
- [ ] bandit scan clean (no HIGH findings)
- [ ] pip-audit shows no known CVEs in requirements
- [ ] grep scan for: password=, api_key=, token=, ssid=, Authorization:
