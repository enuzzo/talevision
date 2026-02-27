"""SlowMovie display mode.

Preserves exact rendering logic from archive/slowmovie/sm.py:
- SHA256 video cache via VideoInfoCache
- PIL adjustments chain: Brightness → Gamma → Contrast → autocontrast? → Color
- cover/contain fit modes
- RGBA overlay with rounded-rect box + QR code (imdb_search)
- Metadata from sidecar .json files
"""
import json
import logging
import random
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from talevision.config.schema import AppConfig, SlowMovieConfig
from talevision.render.frame_cache import VideoInfoCache, extract_frame_ffmpeg
from talevision.render.typography import FontManager, get_text_dimensions
from .base import DisplayMode, ModeState

log = logging.getLogger(__name__)

try:
    import qrcode
    from qrcode.image.pil import PilImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    log.warning("qrcode not available; QR codes disabled")


def _apply_gamma(image: Image.Image, gamma: float) -> Image.Image:
    """Apply gamma correction via PIL LUT.

    Preserves exact logic from sm.py _apply_gamma().
    """
    if gamma == 1.0:
        return image
    inv_gamma = 1.0 / gamma
    table = bytes(int(((i / 255.0) ** inv_gamma) * 255 + 0.5) for i in range(256))
    try:
        if image.mode == "L":
            return image.point(table)
        elif image.mode in ("RGB", "RGBA"):
            bands = list(image.split())
            bands[0] = bands[0].point(table)
            bands[1] = bands[1].point(table)
            bands[2] = bands[2].point(table)
            return Image.merge(image.mode, bands)
        else:
            img_rgb = image.convert("RGB")
            bands = list(img_rgb.split())
            bands[0] = bands[0].point(table)
            bands[1] = bands[1].point(table)
            bands[2] = bands[2].point(table)
            return Image.merge("RGB", bands)
    except Exception as exc:
        log.error(f"apply_gamma error: {exc}")
        return image


def _format_time(seconds: float) -> str:
    """Convert seconds to HH:MM:SS string."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "N/A"
    try:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "N/A"


class SlowMovieMode(DisplayMode):
    """SlowMovie mode: plays a film at ~1 frame per refresh cycle.

    Rendering logic exactly matches archive/slowmovie/sm.py.
    """

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._app_cfg = config
        self._cfg: SlowMovieConfig = config.slowmovie
        self._suspend_cfg = config.suspend
        self._display_cfg = config.display
        self._base_dir = base_dir

        cache_path = base_dir / self._cfg.cache_file
        self._cache = VideoInfoCache(cache_path)

        self._frame_path = base_dir / "cache" / "current_frame.jpg"
        self._frame_path.parent.mkdir(parents=True, exist_ok=True)

        self._bold_font: Optional[object] = None
        self._light_font: Optional[object] = None
        self._load_fonts()

        self._last_state: Dict = {}
        self._resolution = (self._display_cfg.width, self._display_cfg.height)

    @property
    def name(self) -> str:
        return "slowmovie"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def _load_fonts(self) -> None:
        font_dir = self._base_dir / self._cfg.fonts.dir
        size = self._cfg.overlay.font_size
        for attr, filename in [("_bold_font", self._cfg.fonts.bold), ("_light_font", self._cfg.fonts.light)]:
            path = font_dir / filename
            if path.is_file():
                try:
                    setattr(self, attr, ImageFont.truetype(str(path), size))
                    log.debug(f"SlowMovie font loaded: {filename} at {size}px")
                except Exception as exc:
                    log.error(f"Failed to load SlowMovie font {filename}: {exc}")
            else:
                log.warning(f"SlowMovie font not found: {path}")

    def _select_video(self) -> Optional[Path]:
        """Select video file according to config.video_file setting."""
        media_dir = self._base_dir / self._cfg.media_dir
        if not media_dir.is_dir():
            log.error(f"Media directory not found: {media_dir}")
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                log.error(f"Cannot create media dir: {exc}")
            return None

        video_choice = self._cfg.video_file
        if video_choice.lower() != "random":
            candidate = media_dir / video_choice
            if candidate.is_file():
                return candidate
            log.warning(f"Configured video '{video_choice}' not found; selecting random")

        extensions = ("*.mp4", "*.avi", "*.mkv", "*.mov")
        available = [f for ext in extensions for f in media_dir.glob(ext) if f.is_file()]
        if not available:
            log.error(f"No video files found in {media_dir}")
            return None
        selected = random.choice(available)
        log.info(f"Selected video: {selected.name}")
        return selected

    def _load_metadata(self, video_path: Path) -> Dict:
        """Load sidecar .json metadata file if it exists."""
        meta_path = video_path.with_suffix(".json")
        if meta_path.is_file():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                log.warning(f"Metadata load error for {meta_path.name}: {exc}")
        return {}

    def _process_image(self, image_path: Path) -> Optional[Image.Image]:
        """Load frame, apply PIL adjustments, fit to display resolution.

        Preserves exact order and logic from sm.py _process_image().
        """
        log.info(f"Processing image: {image_path.name}")
        try:
            img = Image.open(image_path)
            orig_size = img.size
            log.debug(f"Loaded frame {orig_size[0]}x{orig_size[1]}")

            adj = self._cfg.image
            brightness = adj.brightness
            contrast = adj.contrast
            color = adj.color
            gamma = adj.gamma
            use_autocontrast = adj.use_autocontrast

            # PIL adjustments chain (exact order from sm.py)
            if brightness != 1.0:
                img = ImageEnhance.Brightness(img).enhance(brightness)
            if gamma != 1.0:
                img = _apply_gamma(img, gamma)
            if contrast != 1.0:
                img = ImageEnhance.Contrast(img).enhance(contrast)
            if use_autocontrast:
                img = ImageOps.autocontrast(img.convert("RGB"))
            if color != 1.0:
                img = ImageEnhance.Color(img.convert("RGB")).enhance(color)

            # Fit to display resolution
            fit_mode = adj.fit_mode
            img_rgb = img.convert("RGB") if img.mode != "RGB" else img

            if fit_mode == "cover":
                resized = ImageOps.fit(img_rgb, self._resolution, method=Image.Resampling.LANCZOS)
            else:  # contain
                img_copy = img_rgb.copy()
                img_copy.thumbnail(self._resolution, Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", self._resolution, (0, 0, 0))
                cx = (self._resolution[0] - img_copy.width) // 2
                cy = (self._resolution[1] - img_copy.height) // 2
                canvas.paste(img_copy, (cx, cy))
                resized = canvas

            log.info(
                f"Image processed: {orig_size[0]}x{orig_size[1]} → "
                f"{self._resolution[0]}x{self._resolution[1]} ({fit_mode})"
            )
            return resized

        except FileNotFoundError:
            log.error(f"Frame file not found: {image_path}")
            return None
        except Exception as exc:
            log.error(f"Image processing error: {exc}")
            return None

    def _get_text_size(self, draw: ImageDraw.Draw, text: str, font) -> Tuple[int, int]:
        try:
            bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception as exc:
            log.error(f"get_text_size error for '{text[:20]}': {exc}")
            return 100, 20

    def _draw_overlay(
        self,
        image: Image.Image,
        metadata: Dict,
        frame_time: str,
        default_title: str,
    ) -> Image.Image:
        """Draw RGBA overlay with info box and QR code.

        Preserves exact logic from sm.py _draw_overlay().
        """
        overlay_cfg = self._cfg.overlay
        show_info = overlay_cfg.show_info
        qr_enabled = overlay_cfg.qr_enabled and QRCODE_AVAILABLE

        if not show_info and not qr_enabled:
            return image.convert("RGB") if image.mode != "RGB" else image

        if show_info and (not self._bold_font or not self._light_font):
            log.warning("Overlay fonts not loaded; info disabled")
            show_info = False

        if not show_info and not qr_enabled:
            return image.convert("RGB") if image.mode != "RGB" else image

        img_rgba = image.convert("RGBA") if image.mode != "RGBA" else image.copy()
        overlay_layer = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay_layer)

        img_w, img_h = img_rgba.size
        b_margin = overlay_cfg.bottom_margin
        margin_l = 20
        radius = 8

        if show_info:
            title = metadata.get("title", default_title)
            director = metadata.get("director", "N/A")
            year = metadata.get("year", "N/A")

            l1b = str(title)
            l1l = f" - {year}"
            l2 = f"{director} - {frame_time}"

            try:
                w1b, h1b = self._get_text_size(draw, l1b, self._bold_font)
                w1l, h1l = self._get_text_size(draw, l1l, self._light_font)
                l1w = w1b + w1l
                l1h = max(h1b, h1l)
                l2w, l2h = self._get_text_size(draw, l2, self._light_font)
            except Exception as exc:
                log.error(f"Text dimension error: {exc}")
                show_info = False

            if show_info:
                txt_w = max(l1w, l2w)
                txt_h = l1h + l2h + 6
                pad = 10
                box_w = txt_w + 2 * pad
                box_h = txt_h + 2 * pad
                x0i = margin_l
                y0i = img_h - box_h - b_margin

                draw.rounded_rectangle(
                    [(x0i, y0i), (x0i + box_w, y0i + box_h)],
                    radius=radius,
                    fill=(0, 0, 0, 190),
                )
                tx = x0i + pad
                ty1 = y0i + pad
                ty2 = ty1 + l1h + 6
                draw.text((tx, ty1), l1b, font=self._bold_font, fill=(255, 255, 255, 255), anchor="lt")
                draw.text((tx + w1b, ty1), l1l, font=self._light_font, fill=(255, 255, 255, 255), anchor="lt")
                draw.text((tx, ty2), l2, font=self._light_font, fill=(255, 255, 255, 255), anchor="lt")

        if qr_enabled:
            qr_type = overlay_cfg.qr_content
            qr_size = overlay_cfg.qr_size
            qr_margin = 20

            title_search = metadata.get("title", default_title)
            qr_data = ""
            if qr_type == "imdb_search":
                qr_data = f"https://www.imdb.com/find?q={title_search}"
            elif qr_type == "tmdb_search":
                qr_data = f"https://www.themoviedb.org/search?query={title_search}"

            if qr_data:
                try:
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=2,
                    )
                    qr.add_data(qr_data)
                    qr.make(fit=True)
                    qr_img = qr.make_image(
                        fill_color="black",
                        back_color="white",
                        image_factory=PilImage,
                    ).resize((qr_size, qr_size), Image.Resampling.NEAREST)
                    x0q = img_w - qr_size - qr_margin
                    y0q = img_h - qr_size - b_margin
                    overlay_layer.paste(qr_img, (x0q, y0q))
                    log.debug(f"QR code placed at ({x0q}, {y0q})")
                except Exception as exc:
                    log.error(f"QR generation error: {exc}")

        final = Image.alpha_composite(img_rgba, overlay_layer)
        return final.convert("RGB")

    def render(self, is_suspended: bool = False) -> Image.Image:
        """Render next SlowMovie frame or suspend screen."""
        from talevision.render.layout import draw_suspend_screen
        if is_suspended:
            return draw_suspend_screen(
                self._suspend_cfg,
                FontManager(self._app_cfg.litclock.fonts, self._base_dir),
                self._display_cfg.width,
                self._display_cfg.height,
                self._base_dir,
            )
        return self._run_cycle()

    def _run_cycle(self) -> Image.Image:
        """Select video, extract frame, process, overlay. Returns RGB image."""
        video_path = self._select_video()
        if video_path is None:
            return self._error_image("No video files in media/")

        video_info, _ = self._cache.get(video_path)
        if video_info is None:
            return self._error_image(f"Cannot read video info: {video_path.name}")

        duration = video_info["duration"]
        fps = video_info["fps"]
        total_frames = video_info["total_frames"]

        if total_frames <= 1:
            return self._error_image(f"Too few frames in {video_path.name}")

        sel = self._cfg.frame_selection
        skip_start = sel.skip_start_seconds
        skip_end = sel.skip_end_seconds
        min_time = float(skip_start)
        max_time = duration - float(skip_end)

        if fps > 0:
            min_frame = int(min_time * fps)
            max_frame = int(max_time * fps) - 1
            if max_time <= min_time or min_frame >= max_frame:
                log.warning("Skip seconds invalid for this video duration; using full range")
                min_frame, max_frame = 0, total_frames - 1
        else:
            min_frame, max_frame = 0, total_frames - 1

        min_frame = max(0, min_frame)
        max_frame = min(total_frames - 1, max_frame)
        if min_frame >= max_frame:
            min_frame, max_frame = 0, total_frames - 1

        random_frame = random.randint(min_frame, max_frame)
        frame_time_sec = random_frame / fps if fps > 0 else 0.0
        frame_time_str = _format_time(frame_time_sec)
        timecode_ms = int(frame_time_sec * 1000)

        metadata = self._load_metadata(video_path)
        default_title = video_path.stem

        if not extract_frame_ffmpeg(video_path, timecode_ms, self._frame_path):
            return self._error_image(f"Frame extraction failed: {video_path.name}")

        processed = self._process_image(self._frame_path)
        if processed is None:
            return self._error_image("Image processing failed")

        final = self._draw_overlay(processed, metadata, frame_time_str, default_title)

        self._last_state = {
            "video": video_path.name,
            "frame": random_frame,
            "frame_time": frame_time_str,
            "title": metadata.get("title", default_title),
            "director": metadata.get("director", ""),
            "year": metadata.get("year", ""),
        }

        return final

    def _error_image(self, msg: str) -> Image.Image:
        """Return a plain error image."""
        log.error(msg)
        img = Image.new("RGB", self._resolution, (30, 30, 30))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((20, self._resolution[1] // 2), f"SlowMovie: {msg}", fill=(255, 80, 80), font=font)
        return img

    def get_state(self) -> ModeState:
        return ModeState(mode=self.name, extra=dict(self._last_state))
