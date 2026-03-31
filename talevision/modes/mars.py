"""Mars Rover Photos mode — NASA/JPL Curiosity raw image feed."""
import io
import json
import logging
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

_UA       = {"User-Agent": "TaleVision/1.0"}
# api.nasa.gov/mars-photos was deprecated (Heroku free tier shutdown).
# JPL direct API: no key required, always current.
_MARS_JPL = "https://mars.nasa.gov/api/v1/raw_image_items"

# Preferred cameras: colour/scenic first, hazard cams last
_CAMERA_PREF = [
    "MAST_RIGHT",    # Mastcam colour — right eye
    "MAST_LEFT",     # Mastcam colour — left eye
    "MAHLI",         # Hand lens macro imager
    "CHEMCAM_RMI",   # Remote micro-imager
    "NAV_LEFT_B",    # Navigation (B&W)
    "NAV_RIGHT_B",
    "FHAZ_LEFT_B",   # Front hazard (last resort)
    "FHAZ_RIGHT_B",
    "RHAZ_LEFT_B",
    "RHAZ_RIGHT_B",
]


def _camera_score(name: str) -> int:
    try:
        return _CAMERA_PREF.index(name)
    except ValueError:
        return len(_CAMERA_PREF)


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _fmt_date(iso: str) -> str:
    """'2026-03-30T23:00:15.000Z' or '2026-03-30' → '30 March 2026'"""
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return d.strftime("%-d %B %Y")
    except Exception:
        return iso


def _fmt_count(n: int) -> str:
    return f"{n:,}"


def _camera_full_name(photo: dict) -> str:
    """Extract camera label from title 'Sol N: Mast Camera (Mastcam)' → 'Mast Camera (Mastcam)'."""
    title = photo.get("title", "")
    parts = title.split(": ", 1)
    return parts[1] if len(parts) > 1 else photo.get("instrument", "")


class MarsMode(DisplayMode):

    def __init__(self, config: AppConfig, base_dir: Path = Path("."), api_key: str = "DEMO_KEY"):
        self._cfg     = config.mars
        self._display = config.display
        # api_key kept for signature compatibility — JPL API needs no key

        fonts_dir        = base_dir / "assets" / "fonts"
        self._font_title = _load_font(fonts_dir / "Signika-Bold.ttf", 28)
        self._font_body  = _load_font(fonts_dir / "Taviraj-Italic.ttf", 19)
        self._font_mono  = _load_font(fonts_dir / "InconsolataNerdFontMono-Regular.ttf", 16)

        self._cache_dir    = base_dir / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._photos_cache = self._cache_dir / "mars_photos.json"
        self._image_cache  = self._cache_dir / "mars_image.jpg"
        self._image_id_f   = self._cache_dir / "mars_image_id.txt"

        self._last_rover:       str = ""
        self._last_camera:      str = ""
        self._last_camera_full: str = ""
        self._last_sol:         int = 0
        self._last_earth_date:  str = ""
        self._last_photo_id:    int = 0
        self._last_total:       int = 0

    @property
    def name(self) -> str:
        return "mars"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def render(self) -> Image.Image:
        w, h  = self._display.width, self._display.height
        today = date.today().isoformat()

        photos = self._load_cached_photos(today)
        if not photos:
            photos = self._fetch_latest_photos()
            if photos:
                self._save_cached_photos(photos, today)

        if not photos:
            return self._error_image(w, h)

        # Sort by camera preference, pick by current hour for intra-day variety
        photos_sorted = sorted(photos, key=lambda p: _camera_score(p.get("instrument", "")))
        photo = photos_sorted[datetime.now().hour % len(photos_sorted)]
        photo_id = str(photo["id"])

        img = self._load_cached_image(photo_id)
        if img is None:
            img = self._fetch_image(photo["https_url"])
            if img is None:
                for alt in photos_sorted[:8]:
                    if str(alt["id"]) == photo_id:
                        continue
                    img = self._fetch_image(alt["https_url"])
                    if img:
                        photo = alt
                        photo_id = str(alt["id"])
                        break
            if img is None and self._image_cache.exists():
                try:
                    img = Image.open(str(self._image_cache)).convert("RGB")
                except Exception:
                    pass
            if img is None:
                return self._error_image(w, h)
            try:
                img.save(str(self._image_cache), format="JPEG", quality=90)
                self._image_id_f.write_text(photo_id)
            except Exception as exc:
                log.warning("Mars: image cache write failed: %s", exc)

        self._last_rover       = "Curiosity"
        self._last_camera      = photo.get("instrument", "")
        self._last_camera_full = _camera_full_name(photo)
        self._last_sol         = photo.get("sol", 0)
        received               = photo.get("date_received", photo.get("date_taken", ""))
        self._last_earth_date  = received[:10] if received else ""
        self._last_photo_id    = photo["id"]
        self._last_total       = photo.get("_total", 0)

        img = self._enhance(img)
        img = ImageOps.fit(img, (w, h), Image.LANCZOS)
        return self._draw_overlay(img, photo)

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cached_photos(self, today: str) -> list:
        if not self._photos_cache.exists():
            return []
        try:
            data = json.loads(self._photos_cache.read_text(encoding="utf-8"))
            if data.get("_date") == today:
                return data.get("photos", [])
        except Exception:
            pass
        return []

    def _save_cached_photos(self, photos: list, today: str) -> None:
        try:
            payload = {"_date": today, "photos": photos}
            self._photos_cache.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            log.warning("Mars: photos cache write failed: %s", exc)

    def _load_cached_image(self, photo_id: str) -> Optional[Image.Image]:
        if not self._image_cache.exists() or not self._image_id_f.exists():
            return None
        if self._image_id_f.read_text().strip() != photo_id:
            return None
        try:
            return Image.open(str(self._image_cache)).convert("RGB")
        except Exception:
            return None

    # ── Network ───────────────────────────────────────────────────────────────

    def _fetch_latest_photos(self) -> list:
        try:
            url = f"{_MARS_JPL}/?order=sol+desc&per_page=500"
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            photos = data.get("items", [])
            total  = data.get("total", 0)
            for p in photos:
                p["_total"] = total
            log.info("Mars: %d photos (sol %s, total %s)",
                     len(photos), photos[0]["sol"] if photos else "?", _fmt_count(total))
            return photos
        except Exception as exc:
            log.warning("Mars: photos fetch failed: %s", exc)
            return []

    def _fetch_image(self, url: str) -> Optional[Image.Image]:
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                raw = resp.read()
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            log.warning("Mars: image fetch failed: %s", exc)
            return None

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _enhance(self, img: Image.Image) -> Image.Image:
        img = ImageEnhance.Brightness(img).enhance(self._cfg.brightness)
        img = ImageEnhance.Contrast(img).enhance(self._cfg.contrast)
        img = ImageEnhance.Color(img).enhance(self._cfg.color)
        return img

    def _draw_overlay(self, image: Image.Image, photo: dict) -> Image.Image:
        img_rgba = image.convert("RGBA")
        overlay  = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
        draw     = ImageDraw.Draw(overlay)
        w, h     = img_rgba.size
        band_h   = 135
        pad      = 16

        # Pure-black bottom band (fully opaque)
        draw.rectangle([(0, h - band_h), (w, h)], fill=(0, 0, 0, 255))

        # "MARS" label — top right, terracotta
        draw.text((w - 14, 12), "MARS",
                  font=self._font_mono, fill=(210, 85, 35, 230), anchor="rt")

        camera_full = _camera_full_name(photo)
        sol         = photo.get("sol", 0)
        received    = photo.get("date_received", photo.get("date_taken", ""))
        earth_date  = received[:10] if received else ""
        photo_id    = photo["id"]
        total       = photo.get("_total", 0)

        ty = h - band_h + 14
        max_w = w - 2 * pad

        # Line 1 — rover + camera name
        line1 = f"CURIOSITY  ·  {camera_full}"
        while line1 and draw.textlength(line1, font=self._font_title) > max_w:
            line1 = line1[:-1]
        if line1 != f"CURIOSITY  ·  {camera_full}":
            line1 = line1.rstrip() + "…"
        draw.text((pad, ty), line1, font=self._font_title,
                  fill=(255, 255, 255, 255), anchor="lt")
        ty += self._font_title.size + 8

        # Line 2 — sol + received date
        line2 = f"Sol {sol}  ·  Received on Earth: {_fmt_date(earth_date)}"
        draw.text((pad, ty), line2, font=self._font_body,
                  fill=(240, 175, 110, 255), anchor="lt")
        ty += self._font_body.size + 6

        # Line 3 — photo ID + total (body size, more readable)
        line3 = f"Photo #{photo_id:,}  ·  {_fmt_count(total)} total transmissions from Curiosity"
        while line3 and draw.textlength(line3, font=self._font_body) > max_w:
            line3 = line3[:-1]
        if len(line3) < len(f"Photo #{photo_id:,}  ·  {_fmt_count(total)} total transmissions from Curiosity"):
            line3 = line3.rstrip() + "…"
        draw.text((pad, ty), line3, font=self._font_body,
                  fill=(190, 140, 100, 255), anchor="lt")
        ty += self._font_body.size + 6

        # Line 4 — clock (date + time)
        now = datetime.now()
        line4 = f"{now.strftime('%H:%M')}  ·  {now.day} {now.strftime('%B %Y')}"
        draw.text((pad, ty), line4, font=self._font_mono,
                  fill=(200, 200, 200, 255), anchor="lt")

        return Image.alpha_composite(img_rgba, overlay).convert("RGB")

    def _error_image(self, w: int, h: int) -> Image.Image:
        img  = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((w // 2, h // 2 - 20), "MARS",
                  font=self._font_title, fill=(160, 70, 30), anchor="mm")
        draw.text((w // 2, h // 2 + 30), "signal lost",
                  font=self._font_body, fill=(100, 50, 25), anchor="mm")
        return img

    def get_state(self) -> ModeState:
        return ModeState(mode="mars", extra={
            "rover":        self._last_rover,
            "camera":       self._last_camera,
            "camera_full":  self._last_camera_full,
            "sol":          self._last_sol,
            "earth_date":   self._last_earth_date,
            "photo_id":     self._last_photo_id,
            "total_photos": self._last_total,
        })
