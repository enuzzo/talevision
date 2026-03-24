"""Koan mode — AI-generated introspective haiku on e-ink."""
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState
from talevision.modes.koan_archive import KoanArchive

log = logging.getLogger(__name__)

_NUMERO = "\u2116"  # №


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


class KoanMode(DisplayMode):
    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.koan
        self._display = config.display
        base_dir = Path(base_dir)

        fonts_dir = base_dir / "assets" / "fonts"
        self._font_haiku = _load_font(fonts_dir / "Taviraj-Regular.ttf", 32)
        self._font_pen = _load_font(fonts_dir / "Taviraj-Italic.ttf", 21)
        self._font_seed = _load_font(fonts_dir / "InconsolataNerdFontMono-Regular.ttf", 15)
        self._font_fallback = _load_font(fonts_dir / "Lobster-Regular.ttf", 50)
        self._font_fallback_sub = _load_font(fonts_dir / "Taviraj-Regular.ttf", 18)

        self._archive = KoanArchive(
            archive_path=base_dir / self._cfg.archive_file,
            seed_data_path=base_dir / self._cfg.seed_data,
        )
        self._last_haiku: dict = {}

    @property
    def name(self) -> str:
        return "koan"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info("Koan mode activated (sub_mode=%s)", self._cfg.sub_mode)

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height

        haiku = self._pick_haiku()
        if haiku is None:
            return self._fallback_image(w, h)

        self._last_haiku = haiku
        return self._draw_frame(w, h, haiku)

    def get_state(self) -> ModeState:
        h = self._last_haiku
        if not h:
            return ModeState(mode="koan")
        return ModeState(mode="koan", extra={
            "haiku_id": h.get("id", 0),
            "seed_word": h.get("seed_word", ""),
            "author_name": h.get("author_name", ""),
            "lines": h.get("lines", []),
            "source": h.get("source", ""),
            "archive_count": self._archive.count(),
        })

    def _pick_haiku(self) -> dict:
        if self._cfg.sub_mode == "generate":
            generated = self._try_generate()
            if generated:
                return generated
        return self._archive.get_random()

    def _try_generate(self) -> dict:
        # Phase 2: local LLM / free API generation
        return None

    def _draw_frame(self, w: int, h: int, haiku: dict) -> Image.Image:
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        margin = 50
        lines = haiku.get("lines", [])
        haiku_id = haiku.get("id", 0)
        pen_name = haiku.get("author_name", "")

        # --- Seed number: top-right ---
        seed_text = f"{_NUMERO} {haiku_id}"
        seed_bbox = draw.textbbox((0, 0), seed_text, font=self._font_seed)
        seed_w = seed_bbox[2] - seed_bbox[0]
        draw.text(
            (w - margin - seed_w, margin - 10),
            seed_text,
            font=self._font_seed,
            fill=(170, 170, 170),
        )

        # --- Haiku: optical center, flush-left block centered on longest line ---
        line_spacing = 51
        line_widths = []
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=self._font_haiku)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        max_line_w = max(line_widths) if line_widths else 0
        total_block_h = len(lines) * line_spacing
        block_x = (w - max_line_w) // 2
        optical_center_y = int(h * 0.38)
        block_top_y = optical_center_y - total_block_h // 2

        for i, line in enumerate(lines):
            y = block_top_y + i * line_spacing
            draw.text((block_x, y), line, font=self._font_haiku, fill=(0, 0, 0))

        # --- Pen name: bottom-right ---
        if pen_name:
            pen_text = f"\u2014 {pen_name}"
            pen_bbox = draw.textbbox((0, 0), pen_text, font=self._font_pen)
            pen_w = pen_bbox[2] - pen_bbox[0]
            pen_h = pen_bbox[3] - pen_bbox[1]
            draw.text(
                (w - margin - pen_w, h - margin - pen_h),
                pen_text,
                font=self._font_pen,
                fill=(130, 130, 130),
            )

        return img

    def _fallback_image(self, w: int, h: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        title = "KOAN"
        bbox = draw.textbbox((0, 0), title, font=self._font_fallback)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, int(h * 0.38)), title,
                  font=self._font_fallback, fill=(170, 170, 170))
        sub = "silence is the first haiku"
        sbbox = draw.textbbox((0, 0), sub, font=self._font_fallback_sub)
        sw = sbbox[2] - sbbox[0]
        draw.text(((w - sw) // 2, int(h * 0.38) + 70), sub,
                  font=self._font_fallback_sub, fill=(200, 200, 200))
        return img
