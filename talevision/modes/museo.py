"""Museo display mode — random public-domain artworks from world museums."""
import collections
import datetime
import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState
from talevision.modes.museo_cache import MuseoCache
from talevision.modes.museo_providers import PROVIDERS

log = logging.getLogger(__name__)

try:
    import qrcode
    from qrcode.image.pil import PilImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

import urllib.request

_UA = {"User-Agent": "TaleVision/1.0"}
_MAX_RETRIES = 5
_RECENT_BUFFER_SIZE = 50


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


class MuseoMode(DisplayMode):

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.museo
        self._display = config.display
        self._base_dir = base_dir
        self._font_dir = base_dir / self._cfg.fonts.dir

        self._cache = MuseoCache(
            cache_dir=base_dir / "cache",
            max_age=self._cfg.cache_max_age,
        )

        self._provider_index = 0
        self._recent_ids: collections.deque = collections.deque(maxlen=_RECENT_BUFFER_SIZE)
        self._last_artwork = None

        self._bold_font: Optional[ImageFont.FreeTypeFont] = None
        self._light_font: Optional[ImageFont.FreeTypeFont] = None
        self._mono_font: Optional[ImageFont.FreeTypeFont] = None
        self._lobster_font: Optional[ImageFont.FreeTypeFont] = None
        self._fallback_font: Optional[ImageFont.FreeTypeFont] = None
        self._load_fonts()

    def _load_fonts(self) -> None:
        size = self._cfg.overlay.font_size
        self._bold_font = _load_font(self._font_dir / self._cfg.fonts.bold, size)
        self._light_font = _load_font(self._font_dir / self._cfg.fonts.light, size)
        self._mono_font = _load_font(self._font_dir / self._cfg.fonts.mono, 12)
        self._lobster_font = _load_font(self._font_dir / "Lobster-Regular.ttf", 50)
        self._fallback_font = _load_font(self._font_dir / "Taviraj-Italic.ttf", 18)

    @property
    def name(self) -> str:
        return "museo"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info("Museo mode activated")
        provider = PROVIDERS[self._provider_index % len(PROVIDERS)]
        if self._cache.needs_refresh(provider.name):
            try:
                data = provider.fetch_catalogue_meta(timeout=self._cfg.timeout)
                self._cache.save(provider.name, data)
            except Exception as exc:
                log.warning(f"Museo cache refresh on activate failed for {provider.name}: {exc}")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height
        provider = PROVIDERS[self._provider_index % len(PROVIDERS)]
        self._provider_index += 1

        if self._cache.needs_refresh(provider.name):
            try:
                data = provider.fetch_catalogue_meta(timeout=self._cfg.timeout)
                self._cache.save(provider.name, data)
            except Exception as exc:
                log.warning(f"Museo cache refresh failed for {provider.name}: {exc}")

        cache_data = self._cache.load(provider.name)
        if cache_data is None:
            log.error(f"No cache for {provider.name}, using fallback")
            return self._fallback_image(w, h)

        artwork = None
        for attempt in range(_MAX_RETRIES):
            try:
                art_id = provider.pick_random_id(cache_data)
                if art_id in self._recent_ids:
                    continue
                info = provider.fetch_artwork(art_id, timeout=10)
                if info is None:
                    continue
                img = self._fetch_image(info.image_url)
                if img is None:
                    continue
                artwork = info
                self._recent_ids.append(art_id)
                break
            except Exception as exc:
                log.warning(f"Museo attempt {attempt + 1} failed: {exc}")

        if artwork is None or img is None:
            log.error("All Museo fetch attempts failed, using fallback")
            return self._fallback_image(w, h)

        self._last_artwork = artwork

        img = self._enhance(img)
        img = ImageOps.fit(img, (w, h), Image.LANCZOS)
        img = self._draw_overlay(img, artwork)

        self._save_success(img)
        return img

    def _fetch_image(self, url: str) -> Optional[Image.Image]:
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                raw = resp.read()
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            log.warning(f"Museo image fetch failed: {exc}")
            return None

    def _enhance(self, img: Image.Image) -> Image.Image:
        img = ImageEnhance.Brightness(img).enhance(self._cfg.brightness)
        img = ImageEnhance.Contrast(img).enhance(self._cfg.contrast)
        img = ImageEnhance.Color(img).enhance(self._cfg.color)
        return img

    def _draw_overlay(self, image: Image.Image, artwork) -> Image.Image:
        overlay_cfg = self._cfg.overlay
        if not overlay_cfg.show_info and not (overlay_cfg.qr_enabled and QRCODE_AVAILABLE):
            return image

        img_rgba = image.convert("RGBA")
        overlay_layer = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay_layer)

        img_w, img_h = img_rgba.size
        b_margin = overlay_cfg.bottom_margin
        margin_l = 20
        radius = 8
        pad = 10

        if overlay_cfg.show_info and self._bold_font and self._light_font:
            title_date = artwork.title
            if artwork.date:
                title_date += f" \u00b7 {artwork.date}"
            artist_line = artwork.artist or "Unknown"
            museum_line = artwork.museum
            if artwork.department:
                museum_line += f" \u00b7 {artwork.department}"

            qr_reserve = (overlay_cfg.qr_size + 2 * pad + 40) if (overlay_cfg.qr_enabled and QRCODE_AVAILABLE) else 0
            max_text_w = img_w - margin_l - 2 * pad - qr_reserve

            if draw.textlength(title_date, font=self._bold_font) > max_text_w:
                while len(title_date) > 10 and draw.textlength(title_date + " ...", font=self._bold_font) > max_text_w:
                    title_date = title_date[:-1]
                title_date = title_date.rstrip() + " ..."

            w1 = draw.textlength(title_date, font=self._bold_font)
            h1 = self._bold_font.size
            w2 = draw.textlength(artist_line, font=self._light_font)
            h2 = self._light_font.size
            w3 = draw.textlength(museum_line, font=self._mono_font) if self._mono_font else 0
            h3 = self._mono_font.size if self._mono_font else 0

            txt_w = max(w1, w2, w3)
            line_gap = 6
            txt_h = h1 + line_gap + h2 + line_gap + h3
            box_w = txt_w + 2 * pad
            box_h = txt_h + 2 * pad
            x0 = margin_l
            y0 = img_h - box_h - b_margin

            draw.rounded_rectangle(
                [(x0, y0), (x0 + box_w, y0 + box_h)],
                radius=radius,
                fill=(0, 0, 0, 190),
            )
            tx = x0 + pad
            ty = y0 + pad
            draw.text((tx, ty), title_date, font=self._bold_font,
                      fill=(255, 255, 255, 255), anchor="lt")
            ty += h1 + line_gap
            draw.text((tx, ty), artist_line, font=self._light_font,
                      fill=(255, 255, 255, 255), anchor="lt")
            ty += h2 + line_gap
            if self._mono_font:
                draw.text((tx, ty), museum_line, font=self._mono_font,
                          fill=(200, 200, 200, 255), anchor="lt")

        if overlay_cfg.qr_enabled and QRCODE_AVAILABLE and artwork.object_url:
            try:
                qr_size = overlay_cfg.qr_size
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=2,
                )
                qr.add_data(artwork.object_url)
                qr.make(fit=True)
                qr_img = qr.make_image(
                    fill_color="black", back_color="white",
                    image_factory=PilImage,
                ).resize((qr_size, qr_size), Image.Resampling.NEAREST)

                qr_rgba = qr_img.convert("RGBA")
                r, g, b, a = qr_rgba.split()
                new_r = r.point(lambda v: 255 if v < 128 else 0)
                new_g = g.point(lambda v: 255 if v < 128 else 0)
                new_b = b.point(lambda v: 255 if v < 128 else 0)
                new_a = r.point(lambda v: 255 if v < 128 else 0)
                qr_rgba = Image.merge("RGBA", (new_r, new_g, new_b, new_a))

                qr_margin = 20
                box_side = qr_size + 2 * pad
                x0q = img_w - box_side - qr_margin
                y0q = img_h - box_side - b_margin
                draw.rounded_rectangle(
                    [(x0q, y0q), (x0q + box_side, y0q + box_side)],
                    radius=radius,
                    fill=(0, 0, 0, 190),
                )
                overlay_layer.paste(qr_rgba, (x0q + pad, y0q + pad), mask=qr_rgba)
            except Exception as exc:
                log.error(f"Museo QR error: {exc}")

        final = Image.alpha_composite(img_rgba, overlay_layer)
        return final.convert("RGB")

    def _save_success(self, img: Image.Image) -> None:
        try:
            cache_dir = self._base_dir / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            img.save(str(cache_dir / "museo_last_frame.png"), format="PNG")
            ts = datetime.datetime.now().isoformat()
            (cache_dir / "museo_last_success.txt").write_text(ts)
        except Exception as exc:
            log.warning(f"Museo save success failed: {exc}")

    def _fallback_image(self, w: int, h: int) -> Image.Image:
        cache_frame = self._base_dir / "cache" / "museo_last_frame.png"
        if cache_frame.exists():
            try:
                return Image.open(str(cache_frame)).convert("RGB")
            except Exception:
                pass

        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        if self._lobster_font:
            text = "MUSEO"
            tw = draw.textlength(text, font=self._lobster_font)
            draw.text(((w - tw) / 2, h / 2 - 60), text, font=self._lobster_font,
                      fill=(0, 0, 0))
        if self._fallback_font:
            msg = "La connessione non \u00e8 disponibile"
            mw = draw.textlength(msg, font=self._fallback_font)
            draw.text(((w - mw) / 2, h / 2 + 20), msg, font=self._fallback_font,
                      fill=(130, 130, 130))
            ts_file = self._base_dir / "cache" / "museo_last_success.txt"
            if ts_file.exists():
                ts = ts_file.read_text().strip()
                ts_text = f"Ultimo aggiornamento: {ts}"
                tsw = draw.textlength(ts_text, font=self._fallback_font)
                draw.text(((w - tsw) / 2, h / 2 + 60), ts_text,
                          font=self._fallback_font, fill=(170, 170, 170))
        return img

    def get_state(self) -> ModeState:
        extra = {}
        if self._last_artwork:
            a = self._last_artwork
            extra = {
                "title": a.title,
                "artist": a.artist,
                "museum": a.museum,
                "provider": a.provider,
                "object_url": a.object_url,
            }
        return ModeState(mode="museo", extra=extra)
