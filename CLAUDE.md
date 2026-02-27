# TaleVision — Claude Code Reference

## Repo Map

| Path | Purpose |
|------|---------|
| `main.py` | Entry point: parses args, builds Orchestrator, starts Flask thread, runs loop |
| `config.yaml` | Main configuration (committed) |
| `secrets.yaml` | Local secrets (GITIGNORED — never commit) |
| `talevision/config/` | Config loading and dataclass schema |
| `talevision/modes/` | DisplayMode ABC + LitClockMode + SlowMovieMode |
| `talevision/render/` | Typography, layout, canvas wrapper, frame cache |
| `talevision/system/` | Orchestrator, suspend scheduler, timer, buttons, logging |
| `talevision/web/` | Flask factory, API blueprint, dashboard template |
| `assets/fonts/` | Signika + Taviraj .ttf files |
| `assets/lang/` | quotes-{it,en,de,es,fr,pt}.csv + fallback.csv |
| `assets/icons/` | logo.png, favicon.ico |
| `media/` | MP4 files (gitignored, .gitkeep committed) |
| `cache/` | Runtime caches (gitignored, .gitkeep committed) |
| `archive/` | Reference implementations (GITIGNORED — read only) |

## How to Run Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
# or: python main.py --render-only --mode litclock
```

Web dashboard: http://localhost:5000

## How to Deploy on Pi

```bash
git clone <repo> /home/pi/talevision
cd /home/pi/talevision
bash scripts/install.sh
# Edit config.yaml as needed
sudo systemctl start talevision
sudo systemctl enable talevision
```

## Rendering Pipeline — LitClock

```
_choose_quote()        → quote_data dict (quote, autore, titolo)
process_html_tags()    → strips <em>, <br> tags
wrap_text_block()      → word-wrap at max_width px
draw_header()          → Babel locale format, separator line
draw_centered_text_block() → centered lines with line_spacing
vertical centering     → (avail_h - content_h)//2 - adjustment
draw details row       → em-dash author + separator + title, one line
```

## Rendering Pipeline — SlowMovie

```
_select_video()        → Path to .mp4/.mkv
_get_video_info()      → SHA256 cache + ffprobe → duration/fps/frames
random frame selection → skip_start_seconds..skip_end_seconds range
_generate_frame()      → ffmpeg extract at {ms}ms timecode
_process_image()       → Brightness→Gamma→Contrast→Color→fit (cover/contain)
_draw_overlay()        → RGBA layer: rounded-rect box + title/year/director + QR
_display_image()       → inky.set_image(rgb, saturation=sat); inky.show()
```

## Known Pi Zero W Pitfalls

- **Pillow armv6l**: system packages (`sudo apt install python3-pil`) may be needed if pip wheel fails
- **ffmpeg**: must be `sudo apt install ffmpeg`; ffmpeg-python is just a Python wrapper
- **Inky SPI**: enable SPI via `sudo raspi-config` → Interface Options → SPI
- **GPIO group**: run as `pi` user or add to `gpio` group: `sudo usermod -aG gpio pi`
- **Memory**: Pi Zero W has 512MB RAM; avoid headless browsers, heavy ML deps

## Safe-to-Push Checklist

- [ ] `archive/` is in .gitignore and not tracked (`git status` confirms)
- [ ] `secrets.yaml` is in .gitignore and not tracked
- [ ] `media/*.mp4` files are in .gitignore
- [ ] No hardcoded passwords/tokens in any committed file
- [ ] `bandit -r talevision/ -ll` → 0 HIGH/MEDIUM findings
- [ ] `pip-audit -r requirements.txt` → 0 known CVEs
- [ ] Manual scan: `grep -rn "password=\|api_key=\|token=\|ssid=\|Authorization:" talevision/ config.yaml`

## Open Questions / Assumptions

- [ASSUMPTION] Inky Impression 7-color display, 800×480 px
- [ASSUMPTION] Pi Zero W running Raspberry Pi OS Bullseye or Bookworm
- [ASSUMPTION] ffmpeg installed system-wide via apt
- [QUESTION] Do we want optional HTTP basic auth on the dashboard?
- [QUESTION] Should LitClock and SlowMovie share a single quotes/fallback CSV pool or keep separate?
