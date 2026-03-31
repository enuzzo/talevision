"""APOD display mode — NASA Astronomy Picture of the Day."""
import io
import json
import logging
import random
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

_UA       = {"User-Agent": "TaleVision/1.0"}
_APOD_URL = "https://api.nasa.gov/planetary/apod"
_PANEL_W  = 300
_PANEL_BG = (0, 0, 0)


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _wrap_text(text: str, draw: ImageDraw.ImageDraw, font, max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _fmt_date(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return d.strftime(f"{d.day} %B %Y")
    except Exception:
        return iso


def _first_sentence(text: str, max_chars: int = 160) -> str:
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
        self._font_lobster = _load_font(fonts_dir / "Lobster-Regular.ttf", 26)
        self._font_body    = _load_font(fonts_dir / "Taviraj-Italic.ttf", 16)
        self._font_mono    = _load_font(fonts_dir / "InconsolataNerdFontMono-Regular.ttf", 14)
        self._font_mono_lg = _load_font(fonts_dir / "InconsolataNerdFontMono-Regular.ttf", 17)

        self._cache_dir    = base_dir / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._data_cache   = self._cache_dir / "apod_data.json"
        self._image_cache  = self._cache_dir / "apod_image.jpg"
        self._image_date_f = self._cache_dir / "apod_image_date.txt"

        self._last_title:      str = ""
        self._last_date:       str = ""
        self._last_media_type: str = "image"

    @property
    def name(self) -> str:
        return "apod"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def _pick_apod_date(self) -> str:
        """Pick a random historical APOD date, deterministic per refresh interval."""
        interval_key = int(datetime.now().timestamp() / self._cfg.refresh_interval)
        rng   = random.Random(interval_key)
        start = date(1995, 6, 16)
        end   = date.today() - timedelta(days=1)
        delta = (end - start).days
        return (start + timedelta(days=rng.randint(0, delta))).isoformat()

    def render(self) -> Image.Image:
        w, h        = self._display.width, self._display.height
        target_date = self._pick_apod_date()

        data = self._load_cached_data(target_date)
        if data is None:
            data = self._fetch_apod_data(target_date)
            if data:
                self._save_cached_data(data, target_date)

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

        img = self._load_cached_image(target_date)
        if img is None:
            img = self._fetch_image(img_url) if img_url else None
            if img is None:
                if self._image_cache.exists():
                    try:
                        img = Image.open(str(self._image_cache)).convert("RGB")
                    except Exception:
                        pass
            if img is None:
                return self._error_image(w, h, data.get("title", "APOD"))
            try:
                img.save(str(self._image_cache), format="JPEG", quality=90)
                self._image_date_f.write_text(target_date)
            except Exception as exc:
                log.warning("APOD: image cache write failed: %s", exc)

        img = self._enhance(img)
        return self._draw_frame(img, data)

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _load_cached_data(self, target_date: str) -> Optional[dict]:
        if not self._data_cache.exists():
            return None
        try:
            data = json.loads(self._data_cache.read_text(encoding="utf-8"))
            if data.get("_cached_for") == target_date:
                return data
        except Exception:
            pass
        return None

    def _save_cached_data(self, data: dict, target_date: str) -> None:
        try:
            payload = dict(data)
            payload["_cached_for"] = target_date
            self._data_cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            log.warning("APOD: data cache write failed: %s", exc)

    def _load_cached_image(self, target_date: str) -> Optional[Image.Image]:
        if not self._image_cache.exists() or not self._image_date_f.exists():
            return None
        if self._image_date_f.read_text().strip() != target_date:
            return None
        try:
            return Image.open(str(self._image_cache)).convert("RGB")
        except Exception:
            return None

    # ── Network ───────────────────────────────────────────────────────────────

    def _fetch_apod_data(self, target_date: str = "") -> Optional[dict]:
        try:
            url = f"{_APOD_URL}?api_key={self._api_key}&thumbs=true"
            if target_date:
                url += f"&date={target_date}"
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

    def _draw_frame(self, image: Image.Image, data: dict) -> Image.Image:
        W, H    = self._display.width, self._display.height
        IMG_W   = W - _PANEL_W   # 500px
        lx      = IMG_W + 16     # panel text left edge
        rw      = _PANEL_W - 32  # 268px usable width

        # Canvas: dark background + image panel on the left
        canvas = Image.new("RGB", (W, H), _PANEL_BG)
        img_panel = ImageOps.fit(image, (IMG_W, H), Image.LANCZOS)
        canvas.paste(img_panel, (0, 0))

        draw = ImageDraw.Draw(canvas)

        # Vertical separator line between image and panel
        draw.line([(IMG_W, 0), (IMG_W, H)], fill=(60, 60, 60), width=2)

        ly = 18

        # "APOD  ·  18 May 2014" on one line — saves vertical space for text
        apod_date = data.get("date", "")
        draw.text((lx, ly), "APOD", font=self._font_mono_lg, fill=(255, 255, 255))
        if apod_date:
            apod_w  = int(draw.textlength("APOD  ·  ", font=self._font_mono_lg))
            dot_x   = lx + int(draw.textlength("APOD  ", font=self._font_mono_lg))
            draw.text((dot_x, ly), "·", font=self._font_mono_lg, fill=(80, 80, 80))
            draw.text((lx + apod_w, ly + 1), _fmt_date(apod_date),
                      font=self._font_mono, fill=(180, 180, 180))
        ly += self._font_mono_lg.size + 14

        # Title (Lobster, word-wrapped, max 3 lines)
        title = data.get("title", "")
        if title:
            lines = _wrap_text(title, draw, self._font_lobster, rw)
            for line in lines[:3]:
                draw.text((lx, ly), line, font=self._font_lobster, fill=(255, 255, 255))
                ly += self._font_lobster.size + 4
        ly += 12

        # Explanation (as many lines as fit before the footer area)
        explanation = data.get("explanation", "")
        footer_top  = H - 60
        if explanation:
            for line in _wrap_text(explanation, draw, self._font_body, rw):
                if ly + self._font_body.size > footer_top:
                    break
                draw.text((lx, ly), line, font=self._font_body, fill=(200, 200, 200))
                ly += self._font_body.size + 3

        # Separator before footer — brighter and thicker
        draw.line([(lx, H - 50), (W - 16, H - 50)], fill=(100, 100, 100), width=2)

        # Copyright
        copyright_s = data.get("copyright", "").strip().replace("\n", " ")
        if copyright_s:
            cr = f"© {copyright_s}"
            while cr and draw.textlength(cr, font=self._font_mono) > rw:
                cr = cr[:-1]
            if len(cr) < len(f"© {copyright_s}"):
                cr = cr.rstrip() + "…"
            draw.text((lx, H - 44), cr, font=self._font_mono, fill=(140, 140, 140))

        # Clock footer
        now = datetime.now()
        footer_str = f"{now.strftime('%H:%M')}  ·  {now.day} {now.strftime('%B %Y')}"
        draw.text((lx, H - 26), footer_str, font=self._font_mono_lg,
                  fill=(255, 255, 255), anchor="lt")

        return canvas

    def _video_fallback(self, w: int, h: int, data: dict) -> Image.Image:
        img  = Image.new("RGB", (w, h), _PANEL_BG)
        draw = ImageDraw.Draw(img)
        cx   = w // 2
        draw.text((cx, h // 2 - 50), "APOD — Video today",
                  font=self._font_lobster, fill=(180, 178, 220), anchor="mm")
        title = data.get("title", "")
        if title:
            draw.text((cx, h // 2 + 10), title,
                      font=self._font_body, fill=(140, 138, 180), anchor="mm")
        apod_date = data.get("date", "")
        if apod_date:
            draw.text((cx, h // 2 + 50), apod_date,
                      font=self._font_mono, fill=(95, 90, 130), anchor="mm")
        return img

    def _error_image(self, w: int, h: int, title: str = "APOD") -> Image.Image:
        img  = Image.new("RGB", (w, h), _PANEL_BG)
        draw = ImageDraw.Draw(img)
        draw.text((w // 2, h // 2 - 20), title,
                  font=self._font_lobster, fill=(155, 152, 200), anchor="mm")
        draw.text((w // 2, h // 2 + 30), "the stars are quiet today",
                  font=self._font_body, fill=(95, 90, 130), anchor="mm")
        return img

    def get_state(self) -> ModeState:
        return ModeState(mode="apod", extra={
            "title":      self._last_title,
            "date":       self._last_date,
            "media_type": self._last_media_type,
        })
