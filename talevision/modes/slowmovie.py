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
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "N/A"
    try:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "N/A"


def _format_size(path: Path) -> str:
    try:
        mb = path.stat().st_size / 1_048_576
        return f"{mb:.0f} MB"
    except Exception:
        return "?"


class SlowMovieMode(DisplayMode):
    """SlowMovie mode: plays a film at ~1 frame per refresh cycle.

    Rendering logic exactly matches archive/slowmovie/sm.py.
    Frame selection is random but uses cached video info (SHA256-keyed)
    to avoid re-probing files on every render cycle.
    The current video is remembered in-memory; only re-selected if removed.
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

        # Persistent video selection — avoids re-selecting every render
        self._current_video: Optional[Path] = None
        self._current_video_info: Optional[Dict] = None

        # Scan media folder at startup
        self._scan_media()

    @property
    def name(self) -> str:
        return "slowmovie"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info("SlowMovie activated")
        available = self._get_available_videos()
        if available:
            log.info(f"  {len(available)} video(s) ready in media/")
        else:
            log.warning("  No videos found in media/ — add .mp4/.mkv/.avi/.mov files")
        import threading
        from talevision.media.sidecars import auto_generate_missing
        t = threading.Thread(
            target=auto_generate_missing,
            args=(self._base_dir / self._cfg.media_dir, self._base_dir / "secrets.yaml"),
            daemon=True,
        )
        t.start()

    def on_deactivate(self) -> None:
        log.info("SlowMovie deactivated")

    def _scan_media(self) -> None:
        """Scan media folder at startup and log what's available."""
        available = self._get_available_videos()
        if not available:
            log.info("SlowMovie: media/ folder is empty — no videos to play")
            return

        log.info("─" * 52)
        log.info(f"  SlowMovie — {len(available)} video(s) found:")
        for i, v in enumerate(available, 1):
            size = _format_size(v)
            log.info(f"  {i:2}. {v.name}  [{size}]")
        log.info("─" * 52)

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

    def _get_available_videos(self) -> list[Path]:
        media_dir = self._base_dir / self._cfg.media_dir
        if not media_dir.is_dir():
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                log.error(f"Cannot create media dir: {exc}")
            return []
        extensions = ("*.mp4", "*.avi", "*.mkv", "*.mov")
        return sorted([f for ext in extensions for f in media_dir.glob(ext) if f.is_file()])

    def _select_video(self) -> Optional[Path]:
        """Select video, reusing current if still valid."""
        available = self._get_available_videos()
        if not available:
            log.error("No video files found in media/")
            return None

        if self._current_video is None or self._current_video not in available:
            video_choice = self._cfg.video_file
            if video_choice.lower() != "random":
                candidate = self._base_dir / self._cfg.media_dir / video_choice
                if candidate.is_file():
                    self._current_video = candidate
                else:
                    log.warning(f"Configured video '{video_choice}' not found; picking random")
                    self._current_video = random.choice(available)
            else:
                self._current_video = random.choice(available)

            self._current_video_info = None
            log.info(f"Video selected: {self._current_video.name}  [{_format_size(self._current_video)}]")

        return self._current_video

    def _get_video_info(self, video_path: Path) -> Optional[Dict]:
        """Get video info from cache. Runs ffprobe only on first encounter."""
        if self._current_video_info is not None:
            return self._current_video_info

        log.info(f"Reading video info for: {video_path.name} ...")
        video_info, cache_hit = self._cache.get(video_path)
        if video_info is None:
            log.error(f"Cannot read video info: {video_path.name}")
            return None

        self._current_video_info = video_info
        source = "cache" if cache_hit else "ffprobe (now cached)"
        log.info(
            f"Video info [{source}]: {video_path.name} — "
            f"{video_info.get('total_frames', '?')} frames · "
            f"{video_info.get('fps', '?')} fps · "
            f"duration {_format_time(video_info.get('duration', 0))}"
        )
        return self._current_video_info

    def _load_metadata(self, video_path: Path) -> Dict:
        meta_path = video_path.with_suffix(".json")
        if meta_path.is_file():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                log.warning(f"Metadata load error for {meta_path.name}: {exc}")
        return {}

    def _process_image(self, image_path: Path) -> Optional[Image.Image]:
        try:
            img = Image.open(image_path)
            orig_size = img.size

            adj = self._cfg.image
            if adj.brightness != 1.0:
                img = ImageEnhance.Brightness(img).enhance(adj.brightness)
            if adj.gamma != 1.0:
                img = _apply_gamma(img, adj.gamma)
            if adj.contrast != 1.0:
                img = ImageEnhance.Contrast(img).enhance(adj.contrast)
            if adj.use_autocontrast:
                img = ImageOps.autocontrast(img.convert("RGB"))
            if adj.color != 1.0:
                img = ImageEnhance.Color(img.convert("RGB")).enhance(adj.color)

            img_rgb = img.convert("RGB") if img.mode != "RGB" else img

            if adj.fit_mode == "cover":
                resized = ImageOps.fit(img_rgb, self._resolution, method=Image.Resampling.LANCZOS)
            else:
                img_copy = img_rgb.copy()
                img_copy.thumbnail(self._resolution, Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", self._resolution, (0, 0, 0))
                cx = (self._resolution[0] - img_copy.width) // 2
                cy = (self._resolution[1] - img_copy.height) // 2
                canvas.paste(img_copy, (cx, cy))
                resized = canvas

            log.debug(f"Frame processed: {orig_size[0]}x{orig_size[1]} → {self._resolution[0]}x{self._resolution[1]}")
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

    def _draw_overlay(self, image: Image.Image, metadata: Dict,
                      frame_time: str, default_title: str) -> Image.Image:
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
                    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L,
                                       box_size=10, border=2)
                    qr.add_data(qr_data)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white",
                                           image_factory=PilImage).resize(
                        (qr_size, qr_size), Image.Resampling.NEAREST)
                    # Convert to white-on-transparent so it sits cleanly inside the dark box
                    qr_rgba = qr_img.convert("RGBA")
                    r, g, b, a = qr_rgba.split()
                    new_r = r.point(lambda v: 255 if v < 128 else 0)
                    new_g = g.point(lambda v: 255 if v < 128 else 0)
                    new_b = b.point(lambda v: 255 if v < 128 else 0)
                    new_a = r.point(lambda v: 255 if v < 128 else 0)
                    qr_rgba = Image.merge("RGBA", (new_r, new_g, new_b, new_a))
                    # Box styled like the info box: same radius, same semi-transparent dark fill
                    pad = 10
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
                    log.error(f"QR generation error: {exc}")

        final = Image.alpha_composite(img_rgba, overlay_layer)
        return final.convert("RGB")

    def render(self) -> Image.Image:
        return self._run_cycle()

    def _run_cycle(self) -> Image.Image:
        """Select video and extract a random frame using cached video info."""
        log.info("SlowMovie: starting render cycle")

        video_path = self._select_video()
        if video_path is None:
            return self._error_image("No video files in media/")

        video_info = self._get_video_info(video_path)
        if video_info is None:
            self._current_video = None
            self._current_video_info = None
            return self._error_image(f"Cannot read video info: {video_path.name}")

        duration = video_info["duration"]
        fps = video_info["fps"]
        total_frames = video_info["total_frames"]

        if total_frames <= 1:
            return self._error_image(f"Too few frames in {video_path.name}")

        sel = self._cfg.frame_selection
        min_time = float(sel.skip_start_seconds)
        max_time = duration - float(sel.skip_end_seconds)

        if fps > 0:
            min_frame = int(min_time * fps)
            max_frame = int(max_time * fps) - 1
            if max_time <= min_time or min_frame >= max_frame:
                log.warning("Skip range invalid for this video; using full range")
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

        log.info(
            f"Extracting frame {random_frame}/{total_frames} "
            f"at {frame_time_str} from '{video_path.name}' ..."
        )

        metadata = self._load_metadata(video_path)
        default_title = video_path.stem

        if not extract_frame_ffmpeg(video_path, timecode_ms, self._frame_path):
            return self._error_image(f"Frame extraction failed: {video_path.name}")

        log.info("Frame extracted — processing image ...")
        processed = self._process_image(self._frame_path)
        if processed is None:
            return self._error_image("Image processing failed")

        final = self._draw_overlay(processed, metadata, frame_time_str, default_title)

        title = metadata.get("title", default_title)
        log.info(f"SlowMovie render complete: '{title}' @ {frame_time_str}")

        self._last_state = {
            "video": video_path.name,
            "frame": random_frame,
            "frame_time": frame_time_str,
            "title": title,
            "director": metadata.get("director", ""),
            "year": metadata.get("year", ""),
        }

        return final

    def _error_image(self, msg: str) -> Image.Image:
        log.error(f"SlowMovie error: {msg}")
        img = Image.new("RGB", self._resolution, (30, 30, 30))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((20, self._resolution[1] // 2), f"SlowMovie: {msg}", fill=(255, 80, 80), font=font)
        return img

    def get_state(self) -> ModeState:
        return ModeState(mode=self.name, extra=dict(self._last_state))
