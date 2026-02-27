"""Video info cache and ffmpeg helpers for SlowMovie.

Preserves exact logic from archive/slowmovie/sm.py:
- SHA256 file hash as cache key
- ffprobe via ffmpeg-python for duration/fps/total_frames
- ffmpeg frame extraction at millisecond timecode
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)

try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False
    log.warning("ffmpeg-python not available; SlowMovie frame extraction disabled")


def _calculate_file_hash(filepath: Path) -> Optional[str]:
    """Return SHA256 hex digest of file, or None on error."""
    sha = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(4096):
                sha.update(chunk)
        return sha.hexdigest()
    except FileNotFoundError:
        return None
    except OSError as exc:
        log.error(f"Error reading file for hash {filepath}: {exc}")
        return None


def get_video_info_ffprobe(video_path: Path) -> Optional[Dict]:
    """Run ffprobe and return dict with duration, fps, total_frames."""
    if not FFMPEG_AVAILABLE:
        log.error("ffmpeg-python not installed")
        return None
    try:
        probe = ffmpeg.probe(str(video_path))
        stream = next(
            (s for s in probe["streams"] if s["codec_type"] == "video"), None
        )
        if not stream:
            log.error(f"No video stream in {video_path.name}")
            return None

        dur = 0.0
        fps = 24.0
        frames = 0

        dur_s = probe["format"].get("duration", stream.get("duration"))
        fps_s = stream.get("avg_frame_rate", "0/0")
        frames_s = stream.get("nb_frames", "0")

        if dur_s:
            try:
                dur = float(dur_s)
            except ValueError:
                log.warning(f"Invalid duration '{dur_s}'")

        if "/" in fps_s:
            n, d = fps_s.split("/")
            try:
                d_f = float(d)
                fps = float(n) / d_f if d_f != 0 else 0.0
            except ValueError:
                pass
        elif fps_s != "0/0":
            try:
                fps = float(fps_s)
            except ValueError:
                pass

        if fps <= 0.0:
            log.warning(f"Invalid FPS ({fps_s}), defaulting to 24.0")
            fps = 24.0

        if frames_s.isdigit():
            frames = int(frames_s)
        if frames == 0 and dur > 0 and fps > 0:
            frames = int(dur * fps)
            log.debug("Frame count estimated from duration × fps")

        return {"duration": dur, "fps": fps, "total_frames": frames}

    except Exception as exc:
        stderr = ""
        if hasattr(exc, "stderr") and exc.stderr:
            stderr = exc.stderr.decode(errors="ignore")
        log.error(f"ffprobe/video analysis error for {video_path.name}: {stderr or exc}")
        return None


def extract_frame_ffmpeg(video_path: Path, timecode_ms: int, output_path: Path) -> bool:
    """Extract a single frame from video at timecode_ms milliseconds.

    Returns True on success, False on failure.
    Preserves exact logic from sm.py _generate_frame().
    """
    if not FFMPEG_AVAILABLE:
        log.error("ffmpeg-python not installed")
        return False

    timecode = f"{timecode_ms}ms"
    log.debug(f"Extracting frame from {video_path.name} at {timecode} → {output_path.name}")
    try:
        (
            ffmpeg
            .input(str(video_path), ss=timecode, threads=0)
            .output(str(output_path), vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except Exception as exc:
        stderr = ""
        if hasattr(exc, "stderr") and exc.stderr:
            stderr = exc.stderr.decode(errors="ignore")
        log.error(f"ffmpeg/frame extraction error for {video_path.name}: {stderr or exc}")
        return False

    if not output_path.is_file() or output_path.stat().st_size == 0:
        log.error(f"Extraction failed: {output_path.name} not created or empty")
        output_path.unlink(missing_ok=True)
        return False

    log.info(f"Frame extracted at {timecode} from {video_path.name}")
    return True


class VideoInfoCache:
    """Persistent JSON cache for video metadata keyed by SHA256 file hash."""

    def __init__(self, cache_path: Path):
        self._path = cache_path
        self._data: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.is_file():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                log.info(f"Video info cache loaded ({len(self._data)} entries)")
            except (json.JSONDecodeError, IOError) as exc:
                log.warning(f"Cache load error: {exc}. Starting fresh.")
                self._data = {}
        else:
            log.debug("No video info cache file found; will create on first use")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
        except IOError as exc:
            log.error(f"Cannot save video info cache: {exc}")

    def get(self, video_path: Path) -> Tuple[Optional[Dict], bool]:
        """Return (info_dict, cache_hit).

        Computes SHA256 hash of the video file and checks the cache.
        If hash matches cached entry, returns cached info without calling ffprobe.
        """
        key = str(video_path.resolve())
        cached = self._data.get(key)
        current_hash = None
        cache_hit = False

        if cached:
            current_hash = _calculate_file_hash(video_path)
            if current_hash and cached.get("hash") == current_hash:
                log.info(f"Video info for {video_path.name} served from cache")
                return cached["info"].copy(), True
            else:
                log.info(f"Hash changed for {video_path.name}; refreshing")

        info = get_video_info_ffprobe(video_path)
        if info is None:
            return None, False

        if current_hash is None:
            current_hash = _calculate_file_hash(video_path)
        if current_hash:
            self._data[key] = {"hash": current_hash, "info": info}
            self._save()
        else:
            log.warning(f"No hash computed for {video_path.name}; info not cached")

        return info.copy(), False
