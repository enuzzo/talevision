"""Cucina mode — random dishes from world cuisines via TheMealDB."""
import io
import json
import logging
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

try:
    import qrcode
    from qrcode.image.pil import PilImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

_UA = {"User-Agent": "TaleVision/1.5"}
_API_URL = "https://www.themealdb.com/api/json/v1/1/random.php"


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


class CucinaMode(DisplayMode):

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.cucina
        self._display = config.display
        self._base_dir = base_dir

        fonts = base_dir / "assets" / "fonts"
        self._font_title = _load_font(fonts / "Signika-Bold.ttf", 28)
        self._font_origin = _load_font(fonts / "InconsolataNerdFontMono-Bold.ttf", 16)
        self._font_tags = _load_font(fonts / "Taviraj-Italic.ttf", 16)
        self._font_label = _load_font(fonts / "InconsolataNerdFontMono-Bold.ttf", 14)
        self._font_fallback = _load_font(fonts / "Lobster-Regular.ttf", 50)
        self._font_fallback_sub = _load_font(fonts / "Taviraj-Regular.ttf", 18)

        self._last_meal: dict = {}
        self._cache_path = base_dir / "cache" / "cucina_last_frame.png"

    @property
    def name(self) -> str:
        return "cucina"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info("Cucina mode activated")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height

        try:
            meal = self._fetch_random_meal()
        except Exception as exc:
            log.warning("Cucina: fetch failed: %s", exc)
            return self._fallback_image(w, h)

        if not meal:
            return self._fallback_image(w, h)

        self._last_meal = meal

        try:
            food_img = self._fetch_image(meal.get("strMealThumb", ""))
        except Exception:
            food_img = None

        return self._compose(w, h, meal, food_img)

    def get_state(self) -> ModeState:
        m = self._last_meal
        if not m:
            return ModeState(mode="cucina")
        return ModeState(mode="cucina", extra={
            "meal": m.get("strMeal", ""),
            "area": m.get("strArea", ""),
            "category": m.get("strCategory", ""),
            "tags": m.get("strTags", ""),
        })

    def _fetch_random_meal(self) -> Optional[dict]:
        req = urllib.request.Request(_API_URL, headers=_UA)
        with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        meals = data.get("meals")
        if meals and len(meals) > 0:
            return meals[0]
        return None

    def _fetch_image(self, url: str) -> Optional[Image.Image]:
        if not url:
            return None
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
            img = Image.open(io.BytesIO(resp.read())).convert("RGB")
        img = ImageEnhance.Brightness(img).enhance(self._cfg.brightness)
        img = ImageEnhance.Contrast(img).enhance(self._cfg.contrast)
        img = ImageEnhance.Color(img).enhance(self._cfg.color)
        return img

    def _compose(self, w: int, h: int, meal: dict, food_img: Optional[Image.Image]) -> Image.Image:
        canvas = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # --- Food photo: left side, square, with rounded overlay ---
        PHOTO_SIZE = 340
        PHOTO_X, PHOTO_Y = 24, 24
        if food_img:
            photo = ImageOps.fit(food_img, (PHOTO_SIZE, PHOTO_SIZE), Image.LANCZOS)
            canvas.paste(photo, (PHOTO_X, PHOTO_Y))

        # --- Text area: right side ---
        TEXT_X = PHOTO_X + PHOTO_SIZE + 30
        TEXT_MAX_W = w - TEXT_X - 30
        y = PHOTO_Y + 10

        # Dish name
        title = meal.get("strMeal", "Unknown Dish")
        title_lines = _wrap_text(title.upper(), self._font_title, TEXT_MAX_W, draw)
        for line in title_lines[:3]:
            draw.text((TEXT_X, y), line, font=self._font_title, fill=(30, 30, 30))
            y += 36
        y += 12

        # Origin · Category
        area = meal.get("strArea", "")
        category = meal.get("strCategory", "")
        origin_parts = [p for p in [area, category] if p]
        if origin_parts:
            origin_text = " · ".join(origin_parts)
            draw.text((TEXT_X, y), origin_text, font=self._font_origin, fill=(180, 80, 40))
            y += 28

        # Separator
        y += 8
        draw.line([(TEXT_X, y), (TEXT_X + min(TEXT_MAX_W, 200), y)],
                  fill=(220, 210, 200), width=1)
        y += 16

        # Tags
        tags = meal.get("strTags") or ""
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            tag_text = ", ".join(tag_list)
            tag_lines = _wrap_text(tag_text, self._font_tags, TEXT_MAX_W, draw)
            for line in tag_lines[:2]:
                draw.text((TEXT_X, y), line, font=self._font_tags, fill=(140, 140, 140))
                y += 24

        # --- QR code: bottom-right ---
        qr_url = (meal.get("strYoutube") or meal.get("strSource") or
                  f"https://www.themealdb.com/meal/{meal.get('idMeal', '')}")
        if QRCODE_AVAILABLE and qr_url:
            try:
                qr = qrcode.QRCode(version=1, box_size=3, border=1,
                                   error_correction=qrcode.constants.ERROR_CORRECT_L)
                qr.add_data(qr_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img = qr_img.resize((70, 70), Image.NEAREST)
                canvas.paste(qr_img, (w - 90, h - 90))
            except Exception:
                pass

        # --- Mode label: bottom-left ---
        label = "CUCINA"
        draw.text((PHOTO_X, h - 36), label,
                  font=self._font_label, fill=(200, 200, 200))

        # --- Origin flag indicator: below photo ---
        if area:
            area_text = area.upper()
            aw = draw.textbbox((0, 0), area_text, font=self._font_label)[2]
            ax = PHOTO_X + (PHOTO_SIZE - aw) // 2
            draw.text((ax, PHOTO_Y + PHOTO_SIZE + 8), area_text,
                      font=self._font_label, fill=(160, 160, 160))

        # Save cache
        try:
            canvas.save(str(self._cache_path))
        except Exception:
            pass

        return canvas

    def _fallback_image(self, w: int, h: int) -> Image.Image:
        if self._cache_path.exists():
            try:
                return Image.open(self._cache_path).convert("RGB")
            except Exception:
                pass
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        title = "CUCINA"
        bbox = draw.textbbox((0, 0), title, font=self._font_fallback)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, int(h * 0.35)), title,
                  font=self._font_fallback, fill=(200, 180, 160))
        sub = "connection unavailable"
        sbbox = draw.textbbox((0, 0), sub, font=self._font_fallback_sub)
        sw = sbbox[2] - sbbox[0]
        draw.text(((w - sw) // 2, int(h * 0.35) + 70), sub,
                  font=self._font_fallback_sub, fill=(200, 200, 200))
        return img
