"""Wikipedia Random display mode — fetches a random article and renders with PIL."""
import datetime
import io
import json
import logging
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

LANGS = ["it", "en", "de", "es", "fr", "pt"]
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_ACCENT = (117, 81, 255)
COLOR_MUTED = (110, 110, 110)

LANG_TO_BABEL = {
    "it": "it_IT", "en": "en_US", "de": "de_DE",
    "es": "es_ES", "fr": "fr_FR", "pt": "pt_PT",
}

QR_MORE_MSG = {
    "it": "… scansiona il QR per saperne di più",
    "en": "… scan QR to read more",
    "de": "… QR scannen für mehr",
    "es": "… escanea el QR para leer más",
    "fr": "… scannez le QR pour lire la suite",
    "pt": "… digitalize o QR para ler mais",
}

THUMB_W = 180
THUMB_H = 135
QR_SIZE = 80


def _fetch_article(lang: str, timeout: int = 10) -> Dict:
    """Fetch a random Wikipedia article summary. Returns the raw API dict."""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/random/summary"
    req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    data["lang"] = lang
    return data


def _fetch_thumbnail(url: str, timeout: int = 10) -> Optional[Image.Image]:
    """Download and return thumbnail image, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        log.warning(f"Wikipedia thumbnail fetch failed: {exc}")
        return None


def _make_qr(url: str, size: int) -> Image.Image:
    """Generate a QR code image for the given URL."""
    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=3,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((size, size), Image.NEAREST)


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _wrap_text(text: str, font, draw: ImageDraw.Draw, max_width: int) -> List[str]:
    """Word-wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class WikipediaMode(DisplayMode):
    """Displays a random Wikipedia article with thumbnail image and QR link."""

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.wikipedia
        self._display = config.display
        self._base_dir = base_dir
        self._language = self._cfg.language
        self._last_article: Optional[Dict] = None
        self._font_dir = base_dir / "assets" / "fonts"

    @property
    def name(self) -> str:
        return "wikipedia"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info(f"Wikipedia mode activated (lang={self._language})")

    def set_language(self, lang: str) -> None:
        if lang in LANGS:
            self._language = lang
            log.info(f"Wikipedia language set to: {lang}")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height
        timeout = self._cfg.timeout

        try:
            article = _fetch_article(self._language, timeout=timeout)
            self._last_article = article
        except Exception as exc:
            log.error(f"Wikipedia fetch failed: {exc}")
            article = self._last_article or {
                "title": "Wikipedia",
                "extract": "Could not load article. Check network connection.",
                "lang": self._language,
            }

        thumb_url = (article.get("thumbnail") or {}).get("source")
        thumbnail: Optional[Image.Image] = None
        if thumb_url:
            thumbnail = _fetch_thumbnail(thumb_url, timeout=timeout)

        article_url = (
            (article.get("content_urls") or {})
            .get("desktop", {})
            .get("page", "")
        )
        qr_img = _make_qr(article_url, QR_SIZE) if article_url else None

        img = Image.new("RGB", (w, h), COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        font_time  = _load_font(self._font_dir / "Taviraj-Bold.ttf", 46)
        font_date  = _load_font(self._font_dir / "Taviraj-SemiBold.ttf", 30)
        font_lang  = _load_font(self._font_dir / "Taviraj-Regular.ttf", 24)
        font_title = _load_font(self._font_dir / "Signika-Bold.ttf", 26)
        font_body  = _load_font(self._font_dir / "Taviraj-Regular.ttf", 22)

        pad = 30
        now = datetime.datetime.now()
        y = pad

        # ── Time header ───────────────────────────────────────────────────────
        time_str = now.strftime("%H:%M")
        year_short = now.strftime("'%y")
        try:
            from babel.dates import format_date
            locale = LANG_TO_BABEL.get(self._language, "en_US")
            date_str = format_date(now, format="d MMMM", locale=locale)
        except Exception:
            date_str = now.strftime("%d %B")
        full_date_str = f"{date_str} {year_short}"
        lang_label = f"Wikipedia · {self._language.upper()}"

        # Time (large serif bold)
        draw.text((pad, y), time_str, font=font_time, fill=COLOR_BLACK)
        time_w = int(draw.textlength(time_str, font=font_time))

        # Date + year (same baseline area, slightly lower to align visually)
        date_offset = 12
        draw.text((pad + time_w + 20, y + date_offset), full_date_str,
                  font=font_date, fill=COLOR_BLACK)

        # Wikipedia · LANG (right, vertically centered)
        lang_w = int(draw.textlength(lang_label, font=font_lang))
        lang_offset = 16
        draw.text((w - pad - lang_w, y + lang_offset), lang_label,
                  font=font_lang, fill=COLOR_BLACK)

        y += 60
        draw.line([(pad, y), (w - pad, y)], fill=COLOR_ACCENT, width=2)
        y += 14

        content_top = y

        # ── Thumbnail (right column) ──────────────────────────────────────────
        thumb_x = w - pad - THUMB_W

        if thumbnail is not None:
            orig_w, orig_h = thumbnail.size
            target_ratio = THUMB_W / THUMB_H
            orig_ratio = orig_w / orig_h
            if orig_ratio > target_ratio:
                new_w = int(orig_h * target_ratio)
                left = (orig_w - new_w) // 2
                thumb = thumbnail.crop((left, 0, left + new_w, orig_h))
            else:
                new_h = int(orig_w / target_ratio)
                thumb = thumbnail.crop((0, 0, orig_w, new_h))
            thumb = thumb.resize((THUMB_W, THUMB_H), Image.LANCZOS)
            img.paste(thumb, (thumb_x, content_top))

        # ── Article title ─────────────────────────────────────────────────────
        title = article.get("title", "")
        text_max_w = (thumb_x - pad - 16) if thumbnail is not None else (w - 2 * pad)
        title_lines = _wrap_text(title, font_title, draw, text_max_w)

        y = content_top
        for line in title_lines[:2]:
            draw.text((pad, y), line, font=font_title, fill=COLOR_BLACK)
            y += 32
        y += 8

        # ── Extract body ──────────────────────────────────────────────────────
        extract = article.get("extract", "")
        body_lines = _wrap_text(extract, font_body, draw, text_max_w)

        qr_reserved = QR_SIZE + 20 if qr_img else pad
        avail_h = h - y - qr_reserved
        line_h = 28
        max_lines = max(0, avail_h // line_h)

        displayed = list(body_lines[:max_lines])
        if len(body_lines) > max_lines and max_lines > 0 and qr_img:
            qr_msg = QR_MORE_MSG.get(self._language, QR_MORE_MSG["en"])
            displayed[-1] = qr_msg
        for i, line in enumerate(displayed):
            is_qr_msg = i == len(displayed) - 1 and len(body_lines) > max_lines and qr_img
            draw.text((pad, y), line, font=font_body,
                      fill=COLOR_MUTED if is_qr_msg else COLOR_BLACK)
            y += line_h

        # ── QR code (bottom right) ────────────────────────────────────────────
        if qr_img:
            qr_x = w - pad - QR_SIZE
            qr_y = h - pad - QR_SIZE
            draw.rectangle(
                [qr_x - 4, qr_y - 4, qr_x + QR_SIZE + 4, qr_y + QR_SIZE + 4],
                fill=COLOR_WHITE,
            )
            img.paste(qr_img, (qr_x, qr_y))

        return img

    def get_state(self) -> ModeState:
        article = self._last_article or {}
        return ModeState(
            mode="wikipedia",
            extra={
                "title": article.get("title", ""),
                "language": self._language,
                "url": (
                    (article.get("content_urls") or {})
                    .get("desktop", {})
                    .get("page", "")
                ),
            },
        )
