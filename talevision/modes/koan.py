"""Koan mode — AI-generated introspective haiku on e-ink."""
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState
from talevision.modes.koan_archive import KoanArchive
from talevision.modes.koan_generator import generate_haiku, get_random_prompt

log = logging.getLogger(__name__)


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
        self._font_haiku = _load_font(fonts_dir / "CrimsonText-Regular.ttf", 46)
        self._font_mono = _load_font(fonts_dir / "InconsolataNerdFontMono-Bold.ttf", 18)
        self._font_tech = _load_font(fonts_dir / "InconsolataNerdFontMono-Bold.ttf", 16)
        self._font_fallback = _load_font(fonts_dir / "Lobster-Regular.ttf", 50)
        self._font_fallback_sub = _load_font(fonts_dir / "Taviraj-Regular.ttf", 18)

        bg_path = base_dir / "assets" / "img" / "haiku-bg-min.png"
        try:
            self._bg_image = Image.open(bg_path).convert("RGB")
        except Exception:
            log.warning("Koan: background image not found at %s", bg_path)
            self._bg_image = None

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
        log.info("Koan mode activated — embedded LLM generation")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height

        haiku = self._generate()
        if haiku is None:
            log.warning("Koan: LLM generation failed, using curated fallback")
            haiku = self._archive.get_curated_haiku()
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
            "seed_prompt": h.get("seed_word", ""),
            "pen_name": h.get("author_name", ""),
            "lines": h.get("lines", []),
            "source": h.get("source", ""),
            "archive_count": self._archive.count(),
            "generation_time_ms": h.get("generation_time_ms", 0),
        })

    def _generate(self) -> dict:
        if not self._cfg.llm_binary or not self._cfg.llm_model:
            log.warning("Koan: llm_binary or llm_model not configured")
            return None

        seed_word = self._archive.get_random_seed_word()
        prompt_question = get_random_prompt()

        result = generate_haiku(
            llm_binary=self._cfg.llm_binary,
            llm_model=self._cfg.llm_model,
            seed_word=seed_word,
            prompt_question=prompt_question,
            timeout=self._cfg.llm_timeout,
        )
        if result is None:
            return None

        haiku_id = self._archive.append(
            lines=result["lines"],
            seed_word=seed_word,
            author_name=result["author_name"],
            source="generated",
            generation_time_ms=result["generation_time_ms"],
        )
        return {
            "id": haiku_id,
            "lines": result["lines"],
            "seed_word": seed_word,
            "author_name": result["author_name"],
            "source": "generated",
            "generation_time_ms": result["generation_time_ms"],
        }

    def _draw_frame(self, w: int, h: int, haiku: dict) -> Image.Image:
        if self._bg_image:
            img = ImageOps.fit(self._bg_image.copy(), (w, h), Image.LANCZOS)
        else:
            img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        RIGHT_EDGE = w - 50
        TOP_MARGIN = 40
        BOTTOM_MARGIN = 34
        FILL = (80, 80, 80)
        HAIKU_FILL = (30, 30, 30)

        lines = haiku.get("lines", [])
        haiku_id = haiku.get("id", 0)
        pen_name = haiku.get("author_name", "")
        seed_word = haiku.get("seed_word", "")

        # --- Seed №: top-right ---
        seed_text = f"\u2116 {haiku_id}"
        sw = draw.textbbox((0, 0), seed_text, font=self._font_mono)[2]
        draw.text((RIGHT_EDGE - sw, TOP_MARGIN), seed_text,
                  font=self._font_mono, fill=FILL)

        # --- Haiku: right-aligned, optical center ---
        line_spacing = 54
        line_widths = [draw.textbbox((0, 0), l, font=self._font_haiku)[2]
                       for l in lines]
        total_block_h = len(lines) * line_spacing
        optical_y = int(h * 0.38)
        top_y = optical_y - total_block_h // 2

        for i, line in enumerate(lines):
            lw = line_widths[i] if i < len(line_widths) else 0
            draw.text((RIGHT_EDGE - lw, top_y + i * line_spacing), line,
                      font=self._font_haiku, fill=HAIKU_FILL)

        # --- Pen name: bottom-right, uppercase ---
        pen_y = h - BOTTOM_MARGIN - 46
        if pen_name:
            pen_text = f"\u2014 {pen_name.upper()}"
            pw = draw.textbbox((0, 0), pen_text, font=self._font_mono)[2]
            draw.text((RIGHT_EDGE - pw, pen_y), pen_text,
                      font=self._font_mono, fill=FILL)

        # --- Tech stats: below pen name ---
        source = haiku.get("source", "archive")
        gen_ms = haiku.get("generation_time_ms", 0)
        if source == "generated" and gen_ms > 0:
            gen_s = gen_ms / 1000.0
            tech_text = f"LLM \u00b7 {gen_s:.1f}s \u00b7 seed:{seed_word} \u00b7 \u2116{haiku_id}"
        else:
            tech_text = f"CURATED \u00b7 seed:{seed_word} \u00b7 \u2116{haiku_id}"
        tw = draw.textbbox((0, 0), tech_text, font=self._font_tech)[2]
        draw.text((RIGHT_EDGE - tw, pen_y + 26), tech_text,
                  font=self._font_tech, fill=FILL)

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
