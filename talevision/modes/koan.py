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
        self._font_error = _load_font(fonts_dir / "Taviraj-Italic.ttf", 28)
        self._font_error_small = _load_font(fonts_dir / "InconsolataNerdFontMono-Bold.ttf", 14)

        bg_path = base_dir / "assets" / "img" / "haiku-bg-min.png"
        try:
            self._bg_image = Image.open(bg_path).convert("RGB")
        except Exception:
            log.warning("Koan: background image not found at %s", bg_path)
            self._bg_image = None

        self._archive = KoanArchive(
            archive_path=base_dir / self._cfg.archive_dir,
            seed_data_path=base_dir / self._cfg.seed_data,
        )
        self._api_key, self._backend = self._load_api_config(base_dir / "secrets.yaml")
        self._last_haiku: dict = {}

    @staticmethod
    def _load_api_config(secrets_path: Path) -> tuple:
        """Return (api_key, backend) from secrets.yaml. Groq first, then Gemini."""
        try:
            import yaml
            data = yaml.safe_load(secrets_path.read_text()) or {}
        except Exception:
            return ("", "none")
        groq = data.get("groq_api_key", "")
        if groq:
            return (groq, "groq")
        gemini = data.get("gemini_api_key", "")
        if gemini:
            return (gemini, "gemini")
        return ("", "none")

    @property
    def name(self) -> str:
        return "koan"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info("Koan mode activated")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height

        seed_word = self._archive.get_random_seed_word()
        prompt_q = get_random_prompt()
        result = generate_haiku(
            api_key=self._api_key,
            backend=self._backend,
            seed_word=seed_word,
            prompt_question=prompt_q,
        )

        if result:
            haiku_id = self._archive.append(
                lines=result["lines"],
                seed_word=seed_word,
                author_name=result["author_name"],
                source=self._backend,
                generation_time_ms=result["generation_time_ms"],
                model=result.get("model", ""),
                prompt_tokens=result.get("prompt_tokens", 0),
                completion_tokens=result.get("completion_tokens", 0),
                total_tokens=result.get("total_tokens", 0),
            )
            haiku = {
                "id": haiku_id,
                "lines": result["lines"],
                "seed_word": seed_word,
                "author_name": result["author_name"],
                "source": self._backend,
                "generation_time_ms": result["generation_time_ms"],
                "model": result.get("model", ""),
                "total_tokens": result.get("total_tokens", 0),
            }
            self._last_haiku = haiku
            log.info("Koan: fresh haiku #%d (seed=%s, %.1fs)",
                     haiku_id, seed_word, result["generation_time_ms"] / 1000.0)
            return self._draw_frame(w, h, haiku)

        log.warning("Koan: generation failed, showing error frame")
        return self._error_image(w, h)

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

        # --- Theme + №: top-right ---
        header_text = f"{seed_word} \u00b7 \u2116 {haiku_id}"
        hw = draw.textbbox((0, 0), header_text, font=self._font_mono)[2]
        draw.text((RIGHT_EDGE - hw, TOP_MARGIN), header_text,
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
        gen_ms = haiku.get("generation_time_ms", 0)
        model = haiku.get("model", "")
        if gen_ms > 0 and model:
            gen_s = gen_ms / 1000.0
            model_short = model.split("/")[-1]
            tokens = haiku.get("total_tokens", 0)
            tech_text = f"{model_short} \u00b7 {gen_s:.1f}s \u00b7 {tokens}tok"
        else:
            tech_text = f"seed:{seed_word}"
        tw = draw.textbbox((0, 0), tech_text, font=self._font_tech)[2]
        draw.text((RIGHT_EDGE - tw, pen_y + 26), tech_text,
                  font=self._font_tech, fill=FILL)

        return img

    def _error_image(self, w: int, h: int) -> Image.Image:
        """Poetic error screen — visually distinct from haiku layout."""
        img = Image.new("RGB", (w, h), (245, 240, 230))
        draw = ImageDraw.Draw(img)
        RIGHT_EDGE = w - 50
        ERROR_FILL = (160, 100, 80)

        lines = [
            "the poet is silent today",
            "words could not cross the wire",
        ]
        y = int(h * 0.32)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=self._font_error)
            lw = bbox[2] - bbox[0]
            draw.text((RIGHT_EDGE - lw, y), line,
                      font=self._font_error, fill=ERROR_FILL)
            y += 42

        status = f"CONNECTION ERROR \u00b7 {self._backend} \u00b7 {self._archive.count()} haiku in archive"
        sw = draw.textbbox((0, 0), status, font=self._font_error_small)[2]
        draw.text((RIGHT_EDGE - sw, h - 60), status,
                  font=self._font_error_small, fill=(140, 140, 140))

        return img
