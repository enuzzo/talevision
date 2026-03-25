"""Koan mode — AI-generated introspective haiku on e-ink."""
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState
from talevision.modes.koan_archive import KoanArchive
from talevision.modes.koan_generator import BackgroundKoanGenerator

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
            archive_path=base_dir / self._cfg.archive_dir,
            seed_data_path=base_dir / self._cfg.seed_data,
        )
        self._last_haiku: dict = {}
        self._last_shown_id: int = 0
        api_key = self._load_groq_key(base_dir / "secrets.yaml")
        self._bg_gen = BackgroundKoanGenerator(
            api_key=api_key,
            archive=self._archive,
            interval=float(self._cfg.refresh_interval),
        )
        self._bg_gen.start()

    @staticmethod
    def _load_groq_key(secrets_path: Path) -> str:
        try:
            import yaml
            data = yaml.safe_load(secrets_path.read_text()) or {}
            return data.get("groq_api_key", "")
        except Exception:
            return ""

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
            "seed_prompt": h.get("seed_word", ""),
            "pen_name": h.get("author_name", ""),
            "lines": h.get("lines", []),
            "source": h.get("source", ""),
            "archive_count": self._archive.count(),
            "generation_time_ms": h.get("generation_time_ms", 0),
        })

    def _pick_haiku(self) -> dict:
        latest = self._archive.get_latest()
        if latest and latest.get("id", 0) != self._last_shown_id:
            self._last_shown_id = latest["id"]
            log.info("Koan: showing haiku #%d (%s)", latest["id"], latest.get("source", ""))
            return latest
        rnd = self._archive.get_random()
        if rnd:
            log.info("Koan: no new haiku, showing random #%d", rnd.get("id", 0))
            return rnd
        log.warning("Koan: archive empty, using curated fallback")
        return self._archive.get_curated_haiku()

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
        if source == "groq" and gen_ms > 0:
            gen_s = gen_ms / 1000.0
            tech_text = f"Groq \u00b7 {gen_s:.1f}s \u00b7 seed:{seed_word}"
        elif source == "curated":
            tech_text = f"CURATED \u00b7 seed:{seed_word}"
        else:
            tech_text = f"seed:{seed_word}"
        tw = draw.textbbox((0, 0), tech_text, font=self._font_tech)[2]
        draw.text((RIGHT_EDGE - tw, pen_y + 26), tech_text,
                  font=self._font_tech, fill=FILL)

        return img

    def _fallback_image(self, w: int, h: int) -> Image.Image:
        if self._bg_image:
            img = ImageOps.fit(self._bg_image.copy(), (w, h), Image.LANCZOS)
        else:
            img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        RIGHT_EDGE = w - 50
        FILL = (80, 80, 80)
        title = "KOAN"
        bbox = draw.textbbox((0, 0), title, font=self._font_fallback)
        tw = bbox[2] - bbox[0]
        draw.text((RIGHT_EDGE - tw, int(h * 0.30)), title,
                  font=self._font_fallback, fill=(170, 170, 170))
        lines = [
            "generating haiku in background",
            "this may take hours on Pi Zero W",
            "patience is the first poem",
        ]
        y = int(h * 0.30) + 70
        for line in lines:
            sbbox = draw.textbbox((0, 0), line, font=self._font_fallback_sub)
            sw = sbbox[2] - sbbox[0]
            draw.text((RIGHT_EDGE - sw, y), line,
                      font=self._font_fallback_sub, fill=FILL)
            y += 28
        return img
