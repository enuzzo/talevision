"""Mars Rover Photos mode — NASA Mars rover imagery (Curiosity + Perseverance)."""
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
_MARS_API = "https://api.nasa.gov/mars-photos/api/v1/rovers"
_ROVERS   = ["curiosity", "perseverance"]

# Preferred cameras: best scenic/color shots first
_CAMERA_PREF = [
    "MAST",              # Curiosity: colour mast cam — landscape shots
    "MCZ_RIGHT",         # Perseverance: Mastcam-Z right — colour
    "MCZ_LEFT",          # Perseverance: Mastcam-Z left — colour
    "NAVCAM_LEFT",       # Perseverance: B&W navigation
    "NAVCAM_RIGHT",
    "NAVCAM",            # Curiosity: B&W navigation
    "MAHLI",             # Curiosity: macro hand-lens
    "SHERLOC_WATSON",    # Perseverance: macro/close-up
    "CHEMCAM",           # Curiosity: remote micro-imager
    "SUPERCAM_RMI",      # Perseverance: remote micro-imager
    "FHAZ",              # Front hazard cam
    "RHAZ",              # Rear hazard cam
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
    """'2026-03-31' → '31 March 2026'"""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return d.strftime("%-d %B %Y")
    except Exception:
        return iso


def _fmt_count(n: int) -> str:
    """695423 → '695,423'"""
    return f"{n:,}"


class MarsMode(DisplayMode):

    def __init__(self, config: AppConfig, base_dir: Path = Path("."), api_key: str = "DEMO_KEY"):
        self._cfg     = config.mars
        self._display = config.display
        self._api_key = api_key

        fonts_dir        = base_dir / "assets" / "fonts"
        self._font_title = _load_font(fonts_dir / "Signika-Bold.ttf", 26)
        self._font_body  = _load_font(fonts_dir / "Taviraj-Italic.ttf", 17)
        self._font_mono  = _load_font(fonts_dir / "InconsolataNerdFontMono-Regular.ttf", 14)

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
        rover = _ROVERS[date.today().toordinal() % 2]

        photos = self._load_cached_photos(today, rover)
        if not photos:
            photos = self._fetch_latest_photos(rover)
            if photos:
                self._save_cached_photos(photos, today, rover)

        if not photos:
            return self._error_image(w, h)

        # Sort by camera preference, then pick by current hour for intra-day variety
        photos_sorted = sorted(photos, key=lambda p: _camera_score(p["camera"]["name"]))
        photo = photos_sorted[datetime.now().hour % len(photos_sorted)]
        photo_id = str(photo["id"])

        img = self._load_cached_image(photo_id)
        if img is None:
            img = self._fetch_image(photo["img_src"])
            if img is None:
                # Try a few alternatives before giving up
                for alt in photos_sorted[:8]:
                    if str(alt["id"]) == photo_id:
                        continue
                    img = self._fetch_image(alt["img_src"])
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

        self._last_rover       = photo["rover"]["name"]
        self._last_camera      = photo["camera"]["name"]
        self._last_camera_full = photo["camera"]["full_name"]
        self._last_sol         = photo["sol"]
        self._last_earth_date  = photo["earth_date"]
        self._last_photo_id    = photo["id"]
        self._last_total       = photo["rover"].get("total_photos", 0)

        img = self._enhance(img)
        img = ImageOps.fit(img, (w, h), Image.LANCZOS)
        return self._draw_overlay(img, photo)

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cached_photos(self, today: str, rover: str) -> list:
        if not self._photos_cache.exists():
            return []
        try:
            data = json.loads(self._photos_cache.read_text(encoding="utf-8"))
            if data.get("_date") == today and data.get("_rover") == rover:
                return data.get("photos", [])
        except Exception:
            pass
        return []

    def _save_cached_photos(self, photos: list, today: str, rover: str) -> None:
        try:
            payload = {"_date": today, "_rover": rover, "photos": photos}
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

    def _fetch_latest_photos(self, rover: str) -> list:
        try:
            url = f"{_MARS_API}/{rover}/latest_photos?api_key={self._api_key}"
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            photos = data.get("latest_photos", [])
            log.info("Mars: %d photos from %s (sol %s)",
                     len(photos), rover,
                     photos[0]["sol"] if photos else "?")
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
        band_h   = 140
        pad      = 16

        # Dark rust-tinted bottom band
        draw.rectangle([(0, h - band_h), (w, h)], fill=(22, 10, 4, 192))

        # "MARS" label — top right, terracotta
        draw.text((w - 12, 10), "MARS",
                  font=self._font_mono, fill=(210, 85, 35, 220), anchor="rt")

        rover_name  = photo["rover"]["name"].upper()
        camera_full = photo["camera"]["full_name"]
        sol         = photo["sol"]
        earth_date  = photo["earth_date"]
        photo_id    = photo["id"]
        total       = photo["rover"].get("total_photos", 0)

        ty = h - band_h + 12

        # Line 1 — rover + camera name
        title = f"{rover_name}  ·  {camera_full}"
        max_w = w - 2 * pad
        while title and draw.textlength(title, font=self._font_title) > max_w:
            title = title[:-1]
        if len(title) < len(f"{rover_name}  ·  {camera_full}"):
            title = title.rstrip() + "…"
        draw.text((pad, ty), title, font=self._font_title,
                  fill=(255, 255, 255, 255), anchor="lt")
        ty += self._font_title.size + 6

        # Line 2 — sol + earth date (received on Earth)
        subtitle = f"Sol {sol}  ·  Received on Earth: {_fmt_date(earth_date)}"
        draw.text((pad, ty), subtitle, font=self._font_body,
                  fill=(240, 175, 110, 235), anchor="lt")
        ty += self._font_body.size + 5

        # Line 3 — photo ID + total mission photos
        detail = f"Photo #{photo_id:,}  ·  {_fmt_count(total)} total transmissions from {photo['rover']['name'].capitalize()}"
        while detail and draw.textlength(detail, font=self._font_mono) > max_w:
            detail = detail[:-1]
        if detail[-1] not in ("y", "e", "r"):
            detail = detail.rstrip() + "…"
        draw.text((pad, ty), detail, font=self._font_mono,
                  fill=(180, 130, 90, 200), anchor="lt")

        return Image.alpha_composite(img_rgba, overlay).convert("RGB")

    def _error_image(self, w: int, h: int) -> Image.Image:
        img  = Image.new("RGB", (w, h), (12, 5, 2))
        draw = ImageDraw.Draw(img)
        draw.text((w // 2, h // 2 - 20), "MARS",
                  font=self._font_title, fill=(160, 70, 30), anchor="mm")
        draw.text((w // 2, h // 2 + 30), "signal lost",
                  font=self._font_body, fill=(100, 50, 25), anchor="mm")
        return img

    def get_state(self) -> ModeState:
        return ModeState(mode="mars", extra={
            "rover":       self._last_rover,
            "camera":      self._last_camera,
            "camera_full": self._last_camera_full,
            "sol":         self._last_sol,
            "earth_date":  self._last_earth_date,
            "photo_id":    self._last_photo_id,
            "total_photos": self._last_total,
        })
