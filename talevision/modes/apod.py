"""APOD display mode — NASA Astronomy Picture of the Day."""
import io
import json
import logging
import urllib.request
from datetime import date
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_APOD_URL = "https://api.nasa.gov/planetary/apod"


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _first_sentence(text: str, max_chars: int = 160) -> str:
    """Return first sentence of text, truncated at max_chars."""
    end = text.find(". ")
    if 0 < end < max_chars:
        return text[:end + 1]
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


class APODMode(DisplayMode):

    def __init__(self, config: AppConfig, base_dir: Path = Path("."), api_key: str = "DEMO_KEY"):
        self._cfg = config.apod
        self._display = config.display
        self._api_key = api_key
        if api_key == "DEMO_KEY":
            log.warning("APOD: using DEMO_KEY — rate-limited to 30 req/hour. Add apod_api_key to secrets.yaml.")

        fonts_dir = base_dir / "assets" / "fonts"
        self._font_title = _load_font(fonts_dir / "Signika-Bold.ttf", 28)
        self._font_body  = _load_font(fonts_dir / "Taviraj-Italic.ttf", 17)
        self._font_mono  = _load_font(fonts_dir / "InconsolataNerdFontMono-Regular.ttf", 15)

        self._cache_dir  = base_dir / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._data_cache  = self._cache_dir / "apod_data.json"
        self._image_cache = self._cache_dir / "apod_image.jpg"

        self._last_title:      str = ""
        self._last_date:       str = ""
        self._last_media_type: str = "image"

    @property
    def name(self) -> str:
        return "apod"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height
        today = date.today().isoformat()

        data = self._load_cached_data(today)
        is_fresh = data is not None
        if data is None:
            data = self._fetch_apod_data()
            if data:
                self._save_cached_data(data)
                is_fresh = True

        if data is None:
            return self._error_image(w, h, "APOD unavailable")

        self._last_title      = data.get("title", "")
        self._last_date       = data.get("date", "")
        self._last_media_type = data.get("media_type", "image")

        if data.get("media_type") == "video":
            img_url = data.get("thumbnail_url")
            if not img_url:
                return self._video_fallback(w, h, data)
        else:
            img_url = data.get("url") or data.get("hdurl")

        img = self._load_cached_image(is_fresh)
        if img is None:
            img = self._fetch_image(img_url) if img_url else None
            if img is None:
                # stale image cache better than nothing
                if self._image_cache.exists():
                    try:
                        img = Image.open(str(self._image_cache)).convert("RGB")
                    except Exception:
                        pass
            if img is None:
                return self._error_image(w, h, data.get("title", "APOD"))
            if is_fresh:
                try:
                    img.save(str(self._image_cache), format="JPEG", quality=90)
                except Exception as exc:
                    log.warning("APOD: image cache write failed: %s", exc)

        img = self._enhance(img)
        img = ImageOps.fit(img, (w, h), Image.LANCZOS)
        return self._draw_overlay(img, data)

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _load_cached_data(self, today: str) -> Optional[dict]:
        if not self._data_cache.exists():
            return None
        try:
            data = json.loads(self._data_cache.read_text(encoding="utf-8"))
            if data.get("_cached_for") == today:
                return data
        except Exception:
            pass
        return None

    def _save_cached_data(self, data: dict) -> None:
        try:
            payload = dict(data)
            payload["_cached_for"] = date.today().isoformat()
            self._data_cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            log.warning("APOD: data cache write failed: %s", exc)

    def _load_cached_image(self, is_fresh_data: bool) -> Optional[Image.Image]:
        if not self._image_cache.exists() or not is_fresh_data:
            return None
        try:
            return Image.open(str(self._image_cache)).convert("RGB")
        except Exception:
            return None

    # ── Network ───────────────────────────────────────────────────────────────

    def _fetch_apod_data(self) -> Optional[dict]:
        try:
            url = f"{_APOD_URL}?api_key={self._api_key}&thumbs=true"
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            log.info("APOD: fetched %s — %s", data.get("date"), data.get("title"))
            return data
        except Exception as exc:
            log.warning("APOD: metadata fetch failed: %s", exc)
            return None

    def _fetch_image(self, url: str) -> Optional[Image.Image]:
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                raw = resp.read()
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            log.warning("APOD: image fetch failed: %s", exc)
            return None

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _enhance(self, img: Image.Image) -> Image.Image:
        img = ImageEnhance.Brightness(img).enhance(self._cfg.brightness)
        img = ImageEnhance.Contrast(img).enhance(self._cfg.contrast)
        img = ImageEnhance.Color(img).enhance(self._cfg.color)
        return img

    def _draw_overlay(self, image: Image.Image, data: dict) -> Image.Image:
        img_rgba = image.convert("RGBA")
        overlay  = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
        draw     = ImageDraw.Draw(overlay)
        w, h     = img_rgba.size
        band_h   = 130
        pad      = 16

        # Bottom dark band
        draw.rectangle([(0, h - band_h), (w, h)], fill=(0, 0, 0, 185))

        # Date label — top right
        apod_date = data.get("date", "")
        if apod_date:
            draw.text((w - 12, 10), f"APOD · {apod_date}",
                      font=self._font_mono, fill=(255, 255, 255, 170), anchor="rt")

        title       = data.get("title", "")
        explanation = data.get("explanation", "")
        copyright_s = data.get("copyright", "").strip().replace("\n", " ")

        ty = h - band_h + 12

        # Title (truncated to fit)
        if title:
            max_w = w - 2 * pad
            t = title
            while t and draw.textlength(t, font=self._font_title) > max_w:
                t = t[:-1]
            if len(t) < len(title):
                t = t.rstrip() + "…"
            draw.text((pad, ty), t, font=self._font_title,
                      fill=(255, 255, 255, 255), anchor="lt")
            ty += self._font_title.size + 7

        # Excerpt — first sentence, truncated to one line
        if explanation:
            excerpt = _first_sentence(explanation)
            max_w   = w - 2 * pad
            while excerpt and draw.textlength(excerpt, font=self._font_body) > max_w:
                excerpt = excerpt[:-1]
            if len(excerpt) < len(_first_sentence(explanation)):
                excerpt = excerpt.rstrip() + "…"
            draw.text((pad, ty), excerpt, font=self._font_body,
                      fill=(215, 215, 215, 225), anchor="lt")

        # Copyright — bottom right
        if copyright_s:
            draw.text((w - pad, h - 10), f"© {copyright_s}",
                      font=self._font_mono, fill=(175, 175, 175, 200), anchor="rb")

        return Image.alpha_composite(img_rgba, overlay).convert("RGB")

    def _video_fallback(self, w: int, h: int, data: dict) -> Image.Image:
        img  = Image.new("RGB", (w, h), (8, 8, 18))
        draw = ImageDraw.Draw(img)
        title     = data.get("title", "")
        apod_date = data.get("date", "")
        cx = w // 2

        draw.text((cx, h // 2 - 50), "APOD — Video today",
                  font=self._font_title, fill=(180, 180, 220), anchor="mm")
        if title:
            draw.text((cx, h // 2 + 10), title,
                      font=self._font_body, fill=(140, 140, 180), anchor="mm")
        if apod_date:
            draw.text((cx, h // 2 + 50), apod_date,
                      font=self._font_mono, fill=(100, 100, 140), anchor="mm")
        return img

    def _error_image(self, w: int, h: int, title: str = "APOD") -> Image.Image:
        img  = Image.new("RGB", (w, h), (8, 8, 18))
        draw = ImageDraw.Draw(img)
        draw.text((w // 2, h // 2 - 20), title,
                  font=self._font_title, fill=(160, 160, 200), anchor="mm")
        draw.text((w // 2, h // 2 + 30), "the stars are quiet today",
                  font=self._font_body, fill=(100, 100, 140), anchor="mm")
        return img

    def get_state(self) -> ModeState:
        return ModeState(mode="apod", extra={
            "title":      self._last_title,
            "date":       self._last_date,
            "media_type": self._last_media_type,
        })
