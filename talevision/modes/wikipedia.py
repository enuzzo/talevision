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

LANGS = ["it", "es", "pt", "en", "fr", "de"]
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


def _fetch_full_extract(title: str, lang: str, timeout: int = 10) -> str:
    """Fetch a longer plain-text extract via the MediaWiki action API."""
    import urllib.parse
    encoded = urllib.parse.quote(title)
    url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&prop=extracts&titles={encoded}"
        f"&format=json&explaintext=1&exsectionformat=plain&exchars=3000"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract", "")
        if extract:
            return extract
    return ""


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
            # Enrich with full article text (beyond the intro-only summary)
            try:
                full = _fetch_full_extract(article.get("title", ""), self._language, timeout=timeout)
                if len(full) > len(article.get("extract", "")):
                    article["extract"] = full
            except Exception as exc:
                log.warning(f"Wikipedia full extract fetch failed: {exc}")
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

        font_header = _load_font(self._font_dir / "Taviraj-SemiBold.ttf", 32)
        font_lang   = _load_font(self._font_dir / "Taviraj-Regular.ttf", 24)
        font_title  = _load_font(self._font_dir / "Signika-Bold.ttf", 26)
        font_body   = _load_font(self._font_dir / "Taviraj-Regular.ttf", 22)

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
        header_str = f"{time_str} · {date_str} {year_short}"
        lang_label = f"Wikipedia · {self._language.upper()}"

        # Time · Date — same font, same size, same baseline
        draw.text((pad, y), header_str, font=font_header, fill=COLOR_BLACK)

        # Wikipedia · LANG (right-aligned, same baseline)
        lang_w = int(draw.textlength(lang_label, font=font_lang))
        lang_offset = 5
        draw.text((w - pad - lang_w, y + lang_offset), lang_label,
                  font=font_lang, fill=COLOR_BLACK)

        y += 48
        draw.line([(pad, y), (w - pad, y)], fill=COLOR_ACCENT, width=2)
        y += 14

        content_top = y

        # ── Thumbnail (right column) ──────────────────────────────────────────
        thumb_x = w - pad - THUMB_W
        actual_thumb_h = 0

        if thumbnail is not None:
            orig_w, orig_h = thumbnail.size
            actual_thumb_h = int(THUMB_W * orig_h / orig_w)
            thumb = thumbnail.resize((THUMB_W, actual_thumb_h), Image.LANCZOS)
            img.paste(thumb, (thumb_x, content_top))

        # ── Article title ─────────────────────────────────────────────────────
        title = article.get("title", "")
        narrow_w = (thumb_x - pad - 16) if thumbnail is not None else (w - 2 * pad)
        full_w = w - 2 * pad
        title_lines = _wrap_text(title, font_title, draw, narrow_w)

        y = content_top
        for line in title_lines[:2]:
            draw.text((pad, y), line, font=font_title, fill=COLOR_BLACK)
            y += 32
        y += 8

        # ── Extract body ──────────────────────────────────────────────────────
        extract = article.get("extract", "")
        line_h = 28
        font_qr_msg = _load_font(self._font_dir / "Signika-Regular.ttf", 16)

        body_start_y = y
        thumb_end_y = content_top + actual_thumb_h
        qr_x = w - pad - QR_SIZE
        qr_y = h - pad - QR_SIZE
        qr_safe_w = qr_x - pad - 8  # text must stop before the QR left edge

        # Per-line max width: beside thumbnail → narrow, in QR zone → qr_safe, else full
        def _line_max_w(line_idx: int) -> int:
            line_y = body_start_y + line_idx * line_h
            if line_y < thumb_end_y:
                return narrow_w
            if line_y + line_h > qr_y:
                return qr_safe_w
            return full_w

        avail_h = h - body_start_y - pad
        max_lines = max(0, avail_h // line_h)

        # Word-by-word wrap respecting per-line widths
        words = extract.split()
        body_lines: List[str] = []
        word_idx = 0
        for i in range(max_lines):
            if word_idx >= len(words):
                break
            mw = _line_max_w(i)
            current = ""
            while word_idx < len(words):
                candidate = (current + " " + words[word_idx]).strip()
                if draw.textlength(candidate, font=font_body) <= mw:
                    current = candidate
                    word_idx += 1
                else:
                    break
            if current:
                body_lines.append(current)
            elif word_idx < len(words):
                body_lines.append(words[word_idx])
                word_idx += 1

        was_clipped = word_idx < len(words)

        # Append ellipsis to last body line if clipped
        if was_clipped and body_lines:
            last = body_lines[-1]
            ellipsis_line = last + " …"
            mw = _line_max_w(len(body_lines) - 1)
            while last and draw.textlength(ellipsis_line, font=font_body) > mw:
                last = last.rsplit(" ", 1)[0]
                ellipsis_line = last + " …"
            body_lines[-1] = ellipsis_line

        for line in body_lines:
            draw.text((pad, y), line, font=font_body, fill=COLOR_BLACK)
            y += line_h

        # QR message: sans-serif, smaller, vertically centred in QR zone
        if qr_img and was_clipped:
            qr_msg = QR_MORE_MSG.get(self._language, QR_MORE_MSG["en"])
            qr_msg_h = font_qr_msg.size
            qr_msg_y = qr_y + (QR_SIZE - qr_msg_h) // 2
            draw.text((pad, qr_msg_y), qr_msg, font=font_qr_msg, fill=COLOR_MUTED)

        # ── QR code (bottom right) ────────────────────────────────────────────
        if qr_img:
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
