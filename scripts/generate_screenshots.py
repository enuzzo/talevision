#!/usr/bin/env python3
"""Generate e-ink dithered screenshots for all modes + compose grid for README."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "docs" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 7-colour Inky Impression palette (pure RGB values)
EINK_PALETTE = [
    0, 0, 0,        # Black
    255, 255, 255,   # White
    255, 0, 0,       # Red
    0, 255, 0,       # Green
    0, 0, 255,       # Blue
    255, 255, 0,     # Yellow
    255, 128, 0,     # Orange
]
# Pad palette to 256 colours (PIL requirement)
EINK_PALETTE += [0] * (256 * 3 - len(EINK_PALETTE))

MODES = ["litclock", "slowmovie", "wikipedia", "weather", "museo", "koan", "cucina"]

MODE_LABELS = {
    "litclock": "LitClock",
    "slowmovie": "SlowMovie",
    "wikipedia": "Wikipedia",
    "weather": "Weather",
    "museo": "Museo",
    "koan": "Koan",
    "cucina": "Cucina",
}


def apply_eink_dither(img: Image.Image) -> Image.Image:
    """Quantize image to 7-colour e-ink palette with Floyd-Steinberg dithering."""
    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette(EINK_PALETTE)
    return img.convert("RGB").quantize(
        colors=7, palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG
    ).convert("RGB")


def render_mode(mode: str) -> Path:
    """Render a single mode frame and return path."""
    print(f"  Rendering {mode}...")
    result = subprocess.run(
        [sys.executable, "main.py", "--render-only", "--mode", mode],
        capture_output=True, text=True, cwd=str(BASE_DIR), timeout=30
    )
    if result.returncode != 0:
        print(f"    WARNING: {mode} render failed: {result.stderr[:200]}")
    return BASE_DIR / "talevision_frame.png"


def generate_individual(mode: str) -> Path:
    """Generate dithered screenshot for one mode."""
    frame_path = render_mode(mode)
    if not frame_path.exists():
        print(f"    SKIP: no frame for {mode}")
        return None

    img = Image.open(frame_path).convert("RGB")
    dithered = apply_eink_dither(img)
    out_path = OUT_DIR / f"{mode}.png"
    dithered.save(str(out_path))
    print(f"    Saved: {out_path.name}")
    return out_path


def compose_grid(paths: dict, cols: int = 4) -> Path:
    """Compose all screenshots into a labelled grid."""
    items = [(mode, path) for mode, path in paths.items() if path]
    if not items:
        print("No screenshots to compose!")
        return None

    # Load first to get dimensions
    sample = Image.open(items[0][1])
    fw, fh = sample.size

    # Scale down for grid
    scale = 0.5
    tw = int(fw * scale)
    th = int(fh * scale)

    rows = (len(items) + cols - 1) // cols
    LABEL_H = 32
    PAD = 12
    OUTER_PAD = 16

    grid_w = OUTER_PAD * 2 + cols * tw + (cols - 1) * PAD
    grid_h = OUTER_PAD * 2 + rows * (th + LABEL_H) + (rows - 1) * PAD

    grid = Image.new("RGB", (grid_w, grid_h), (24, 20, 16))
    draw = ImageDraw.Draw(grid)

    try:
        font = ImageFont.truetype(
            str(BASE_DIR / "assets" / "fonts" / "Signika-Bold.ttf"), 16)
    except Exception:
        font = ImageFont.load_default(size=16)

    for idx, (mode, path) in enumerate(items):
        col = idx % cols
        row = idx // cols
        x = OUTER_PAD + col * (tw + PAD)
        y = OUTER_PAD + row * (th + LABEL_H + PAD)

        thumb = Image.open(path).resize((tw, th), Image.LANCZOS)
        grid.paste(thumb, (x, y))

        label = MODE_LABELS.get(mode, mode)
        bbox = draw.textbbox((0, 0), label, font=font)
        lw = bbox[2] - bbox[0]
        lx = x + (tw - lw) // 2
        ly = y + th + 6
        draw.text((lx, ly), label, font=font, fill=(200, 190, 170))

    out_path = OUT_DIR / "grid.png"
    grid.save(str(out_path), quality=95)
    print(f"\nGrid saved: {out_path}")
    return out_path


def main():
    print("Generating e-ink dithered screenshots...\n")
    paths = {}
    for mode in MODES:
        path = generate_individual(mode)
        paths[mode] = path

    print("\nComposing grid...")
    grid_path = compose_grid(paths)

    print("\nDone! Files in docs/screenshots/")
    if grid_path:
        print(f"Grid: {grid_path}")


if __name__ == "__main__":
    main()
