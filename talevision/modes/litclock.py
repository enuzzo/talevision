"""LitClock display mode.

Preserves exact rendering logic from archive/litclock/lc.py:
- _choose_quote(): time-keyed lookup with random selection + fallback
- _is_em_italic(): detect <em> tag in raw quote for italic font switch
- draw_header(): Babel locale formatting, separator line
- draw_centered_text_block(): word-wrap at max_width, center alignment
- Details row: em-dash author + " - " + title on one line, centered
- vertical_centering_adjustment: px offset applied to vertical center calc
"""
import csv
import datetime
import logging
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig, LitClockConfig
from talevision.render.typography import (
    FontManager,
    calculate_wrapped_text_size,
    get_text_dimensions,
    process_html_tags,
    wrap_text_block,
)
from talevision.render.layout import (
    draw_centered_text_block,
    draw_header,
)
from .base import DisplayMode, ModeState

log = logging.getLogger(__name__)

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)


def _load_quotes_csv(fp: Path) -> Dict[str, List[Dict[str, str]]]:
    """Load main quotes CSV. Expects columns: ora, quote, titolo, autore."""
    quotes: Dict[str, List[Dict[str, str]]] = {}
    try:
        with fp.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
            field_map = {h.strip().lower(): h for h in (reader.fieldnames or [])}

            def get_col(opts):
                return next((field_map[o] for o in opts if o in field_map), None)

            time_h = get_col(["ora", "time"])
            quote_h = get_col(["quote", "citazione"])
            title_h = get_col(["titolo", "title"])
            author_h = get_col(["autore", "author"])

            if not time_h or not quote_h:
                log.error(f"Required columns missing in {fp.name}")
                return {}

            for row in reader:
                time_s = row[time_h].strip()
                if not re.fullmatch(r"\d{2}:\d{2}", time_s):
                    continue
                data = {
                    "quote": row[quote_h].strip(),
                    "titolo": row[title_h].strip() if title_h and title_h in row else "",
                    "autore": row[author_h].strip() if author_h and author_h in row else "",
                }
                quotes.setdefault(time_s, []).append(data)
    except FileNotFoundError:
        log.error(f"Quotes file not found: {fp}")
    except Exception as exc:
        log.error(f"Error loading quotes from {fp.name}: {exc}")
    return quotes


def _load_fallback_csv(fp: Path) -> List[Dict[str, str]]:
    """Load fallback quotes CSV. Expects columns: citazione, autore."""
    fallback: List[Dict[str, str]] = []
    try:
        with fp.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            field_map = {h.strip().lower(): h for h in (reader.fieldnames or [])}

            def get_col(opts):
                return next((field_map[o] for o in opts if o in field_map), None)

            quote_h = get_col(["citazione", "quote"])
            author_h = get_col(["autore", "author"])

            if not quote_h or not author_h:
                log.error(f"Required columns missing in fallback {fp.name}")
                return []

            for row in reader:
                fallback.append({
                    "quote": row[quote_h].strip(),
                    "autore": row[author_h].strip(),
                    "titolo": "",
                })
    except FileNotFoundError:
        log.error(f"Fallback file not found: {fp}")
    except Exception as exc:
        log.error(f"Error loading fallback from {fp.name}: {exc}")
    return fallback


class LitClockMode(DisplayMode):
    """Literature Clock mode.

    Renders the current time as a literary quote using exact typography
    logic from archive/litclock/lc.py.
    """

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._app_cfg = config
        self._cfg: LitClockConfig = config.litclock
        self._suspend_cfg = config.suspend
        self._display_cfg = config.display
        self._base_dir = base_dir

        self._fonts = FontManager(self._cfg.fonts, base_dir)
        self._quotes: Dict[str, List[Dict[str, str]]] = {}
        self._fallback: List[Dict[str, str]] = []
        self._language = self._cfg.language
        self._last_state: Dict = {}

        self._load_quotes()

    @property
    def name(self) -> str:
        return "litclock"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_rate

    def set_language(self, lang: str) -> None:
        """Switch quote language and reload data files."""
        self._language = lang
        self._load_quotes()
        log.info(f"LitClock language changed to: {lang}")

    def _load_quotes(self) -> None:
        data_dir = self._base_dir / self._cfg.data_dir
        quotes_file = data_dir / f"quotes-{self._language}.csv"
        fallback_file = data_dir / "fallback.csv"
        self._quotes = _load_quotes_csv(quotes_file)
        self._fallback = _load_fallback_csv(fallback_file)
        log.info(
            f"LitClock loaded {len(self._quotes)} time slots, "
            f"{len(self._fallback)} fallback quotes (lang={self._language})"
        )

    def _choose_quote(self, now: datetime.datetime) -> Tuple[Dict[str, str], str]:
        """Choose quote for current time. Returns (quote_data, source)."""
        time_s = now.strftime("%H:%M")
        quotes = self._quotes.get(time_s, [])
        if quotes:
            return random.choice(quotes), "main"
        if self._fallback:
            fb = random.choice(self._fallback).copy()
            fb["time_str"] = time_s
            return fb, "fallback"
        log.error(f"No quote for {time_s} and no fallback")
        return {"quote": "No quote found.", "autore": "", "titolo": ""}, "error"

    def _colors(self):
        """Return (bg_rgb, text_rgb) respecting invert_colors config."""
        if self._cfg.invert_colors:
            return COLOR_BLACK, COLOR_WHITE
        return COLOR_WHITE, COLOR_BLACK

    def render(self) -> Image.Image:
        """Render and return the clock image (RGB 800×480)."""
        return self._draw_clock_screen()

    def _draw_clock_screen(self) -> Image.Image:
        """Render main clock screen. Preserves lc.py _draw_clock_screen()."""
        width = self._display_cfg.width
        height = self._display_cfg.height
        bg_c, text_c = self._colors()

        img = Image.new("RGB", (width, height), bg_c)
        draw = ImageDraw.Draw(img)

        now = datetime.datetime.now()

        # Draw header
        header_end_y = draw_header(draw, self._cfg, self._fonts, width, text_c, now)

        # Choose quote
        quote_data, source = self._choose_quote(now)

        if source == "error":
            e_font = self._fonts.get("quote") or ImageFont.load_default()
            ew, eh = get_text_dimensions(quote_data["quote"], e_font, draw)
            ex = (width - ew) // 2
            ey = header_end_y + (height - header_end_y - eh) // 2
            draw.text((ex, ey), quote_data["quote"], fill=text_c, font=e_font)
            return img

        # Prepare quote text
        raw_quote = quote_data["quote"]
        quote_text = process_html_tags(raw_quote)

        # Select font — switch to italic if <em> present
        quote_font_key = "quote"
        if source == "main" and self._cfg.use_italic_for_em:
            if re.search(r"(?i)<em>", raw_quote):
                quote_font_key = "quote_italic"
        elif source == "fallback":
            quote_font_key = "fallback"

        quote_font = self._fonts.get(quote_font_key) or ImageFont.load_default()
        pad = self._cfg.text_block_padding
        max_w = width - 2 * pad

        # Get configured max_width for this font
        font_entry = getattr(self._cfg.fonts, quote_font_key, None)
        q_max_w = font_entry.max_width if font_entry else max_w

        line_sp = self._cfg.intra_line_spacing
        block_sep_sp = self._cfg.block_separator_spacing

        quote_lines = wrap_text_block(quote_text, quote_font, q_max_w, draw)

        # Prepare details
        total_d_h = 0
        auth_t = ""
        tit_t = ""
        sep_t = ""
        auth_f = quote_font
        tit_f = quote_font
        detail_lines: List[str] = []
        detail_font = None

        if source == "main":
            auth_t = f"— {quote_data.get('autore', '')}" if quote_data.get("autore") else ""
            tit_t = quote_data.get("titolo", "")
            auth_f = self._fonts.get("author") or quote_font
            tit_f = self._fonts.get("title") or quote_font
            sep_t = " - " if auth_t and tit_t else ""

            elements_to_measure = []
            if auth_t:
                elements_to_measure.append({"text": auth_t, "font": auth_f})
            if sep_t:
                elements_to_measure.append({"text": sep_t, "font": tit_f})
            if tit_t:
                elements_to_measure.append({"text": tit_t, "font": tit_f})

            if elements_to_measure:
                d_max_h = max(
                    get_text_dimensions(e["text"], e["font"], draw)[1]
                    for e in elements_to_measure
                )
                total_d_h = d_max_h
        else:  # fallback
            detail_font = self._fonts.get("fallback") or quote_font
            time_s = quote_data.get("time_str", "")
            autore = quote_data.get("autore", "")
            det_t = f"— {autore} ({time_s})" if time_s else f"— {autore}"
            fb_entry = self._cfg.fonts.fallback
            fb_max_w = fb_entry.max_width if fb_entry else max_w
            detail_lines = wrap_text_block(det_t, detail_font, fb_max_w, draw)
            _, total_d_h = calculate_wrapped_text_size(detail_lines, detail_font, draw, line_sp)

        # Vertical positioning
        _, total_q_h = calculate_wrapped_text_size(quote_lines, quote_font, draw, line_sp)
        total_content_h = total_q_h + block_sep_sp + total_d_h
        avail_h = height - header_end_y
        adjustment = self._cfg.vertical_centering_adjustment

        content_start_y = header_end_y
        if total_content_h < avail_h:
            content_start_y += (avail_h - total_content_h) // 2
        content_start_y -= adjustment
        content_start_y = max(header_end_y, content_start_y)

        # Draw quote block
        curr_y = draw_centered_text_block(
            draw, quote_lines, quote_font, content_start_y, width, line_sp, text_c
        )
        curr_y += block_sep_sp

        # Draw details
        if source == "main":
            w_auth, _ = get_text_dimensions(auth_t, auth_f, draw) if auth_t else (0, 0)
            w_sep, _ = get_text_dimensions(sep_t, tit_f, draw) if sep_t else (0, 0)
            w_tit, _ = get_text_dimensions(tit_t, tit_f, draw) if tit_t else (0, 0)
            total_det_w = w_auth + w_sep + w_tit

            # Use typographic baseline ("ls") so italic and regular variants align correctly.
            # Compute where the baseline must be so the top of the reference text lands at curr_y.
            _ref_t = tit_t or sep_t or auth_t
            _ref_f = tit_f if (tit_t or sep_t) else auth_f
            _ref_bb = draw.textbbox((0, 0), _ref_t, font=_ref_f, anchor="ls")
            # _ref_bb[1] is the offset from stroke-baseline to the top of the glyph (negative)
            baseline_y = curr_y - _ref_bb[1]

            curr_x = (width - total_det_w) // 2
            if auth_t:
                draw.text((curr_x, baseline_y), auth_t, fill=text_c, font=auth_f, anchor="ls")
                curr_x += w_auth
            if sep_t:
                draw.text((curr_x, baseline_y), sep_t, fill=text_c, font=tit_f, anchor="ls")
                curr_x += w_sep
            if tit_t:
                draw.text((curr_x, baseline_y), tit_t, fill=text_c, font=tit_f, anchor="ls")
        else:
            if detail_font and detail_lines:
                draw_centered_text_block(
                    draw, detail_lines, detail_font, curr_y, width, line_sp, text_c
                )

        # Save state for dashboard
        self._last_state = {
            "time": now.strftime("%H:%M:%S"),
            "quote": quote_text,
            "author": quote_data.get("autore", ""),
            "title": quote_data.get("titolo", "") if source == "main" else "",
            "source": source,
            "language": self._language,
        }

        return img

    def get_state(self) -> ModeState:
        return ModeState(mode=self.name, extra=dict(self._last_state))
