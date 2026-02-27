"""Typography utilities: font loading, text wrapping, dimension calculation.

Preserves the exact rendering logic from archive/litclock/lc.py:
- wrap_text_line() / wrap_text_block() — word-wrap at max_width px using textbbox
- process_html_tags() — strips <br> → newline, removes other HTML tags
- get_text_dimensions() — returns (width, height) tuple via textbbox
"""
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PIL import ImageDraw, ImageFont

from talevision.config.schema import FontsConfig, SlowMovieFontsConfig

log = logging.getLogger(__name__)

# Type alias
FontType = Any  # ImageFont.FreeTypeFont when available


def process_html_tags(text: str) -> str:
    """Convert <br> tags to newlines and strip all other HTML tags."""
    processed = re.sub(r"(?i)<br\s*/?>", "\n", text)
    processed = re.sub(r"<[^>]+>", "", processed)
    return processed.strip()


def get_text_dimensions(text: str, font: FontType, draw: ImageDraw.Draw) -> Tuple[int, int]:
    """Return (width, height) of text rendered with font."""
    if not text or not font:
        return 0, 0
    try:
        bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception as exc:
        log.error(f"get_text_dimensions error for '{text[:20]}': {exc}")
        return 0, 0


def wrap_text_line(text: str, font: FontType, max_width: int, draw: ImageDraw.Draw) -> List[str]:
    """Word-wrap a single line of text to fit within max_width pixels."""
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    current_line = words[0]
    for word in words[1:]:
        test = f"{current_line} {word}"
        w, _ = get_text_dimensions(test, font, draw)
        if w <= max_width:
            current_line = test
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines


def wrap_text_block(text: str, font: FontType, max_width: int, draw: ImageDraw.Draw) -> List[str]:
    """Word-wrap a potentially multi-line text block."""
    raw_lines = text.splitlines()
    wrapped: List[str] = []
    for line in raw_lines:
        if line.strip():
            wrapped.extend(wrap_text_line(line, font, max_width, draw))
        else:
            wrapped.append("")
    return wrapped


def calculate_wrapped_text_size(
    lines: List[str],
    font: FontType,
    draw: ImageDraw.Draw,
    line_spacing: int,
) -> Tuple[int, int]:
    """Return (max_width, total_height) of a list of wrapped lines."""
    if not lines or not font:
        return 0, 0
    max_w = 0
    total_h = 0
    for i, line in enumerate(lines):
        w, h = get_text_dimensions(line, font, draw)
        max_w = max(max_w, w)
        total_h += h
        if i < len(lines) - 1:
            total_h += line_spacing
    return max_w, total_h


class FontManager:
    """Load and cache fonts from a FontsConfig.

    Supports both LitClock FontsConfig and SlowMovie SlowMovieFontsConfig.
    """

    def __init__(self, fonts_cfg: FontsConfig, base_dir: Path = Path(".")):
        self._fonts: Dict[str, FontType] = {}
        self._base_dir = base_dir
        self._load_litclock_fonts(fonts_cfg)

    def _load_litclock_fonts(self, cfg: FontsConfig) -> None:
        font_dir = self._base_dir / cfg.dir
        entries = {
            "header": cfg.header,
            "quote": cfg.quote,
            "quote_italic": cfg.quote_italic,
            "author": cfg.author,
            "title": cfg.title,
            "fallback": cfg.fallback,
        }
        for key, entry in entries.items():
            if not entry.file:
                continue
            path = font_dir / entry.file
            if not path.is_file():
                log.warning(f"Font file not found for '{key}': {path}")
                continue
            try:
                self._fonts[key] = ImageFont.truetype(str(path), entry.size)
                log.debug(f"Loaded font '{key}' from {path.name} at size {entry.size}")
            except Exception as exc:
                log.error(f"Failed to load font '{key}' ({path}): {exc}")

    def load_slowmovie_fonts(self, cfg: SlowMovieFontsConfig) -> None:
        """Load bold + light fonts for SlowMovie overlay."""
        font_dir = self._base_dir / cfg.dir
        # We need font_size from overlay config; caller must set it externally.
        # This is handled in SlowMovieMode which passes the size.
        for key, filename in [("bold", cfg.bold), ("light", cfg.light)]:
            path = font_dir / filename
            if not path.is_file():
                log.warning(f"SlowMovie font not found for '{key}': {path}")
                continue
            try:
                # Store path for deferred loading with size
                self._fonts[f"sm_{key}_path"] = str(path)  # type: ignore[assignment]
            except Exception as exc:
                log.error(f"Failed to register SlowMovie font '{key}': {exc}")

    def load_slowmovie_fonts_with_size(self, cfg: SlowMovieFontsConfig, size: int) -> None:
        """Load bold + light fonts for SlowMovie overlay at specified size."""
        font_dir = self._base_dir / cfg.dir
        for key, filename in [("sm_bold", cfg.bold), ("sm_light", cfg.light)]:
            path = font_dir / filename
            if not path.is_file():
                log.warning(f"SlowMovie font not found for '{key}': {path}")
                continue
            try:
                self._fonts[key] = ImageFont.truetype(str(path), size)
                log.debug(f"Loaded SM font '{key}' from {path.name} at size {size}")
            except Exception as exc:
                log.error(f"Failed to load SM font '{key}': {exc}")

    def get(self, key: str) -> Optional[FontType]:
        font = self._fonts.get(key)
        if font is None:
            log.warning(f"Font '{key}' not loaded")
        return font
