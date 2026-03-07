"""Auto-generate TMDB sidecar .json files for videos that don't have one.

Called from SlowMovie.on_activate() in a background thread.
Silent if tmdb_api_key is absent or network is unavailable.
"""
import json
import logging
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v"}
TMDB_BASE = "https://api.themoviedb.org/3"

_lock = threading.Lock()  # prevent concurrent runs (e.g. mode switched twice fast)


def _load_api_key(secrets_path: Path) -> str:
    try:
        import yaml
        data = yaml.safe_load(secrets_path.read_text()) or {}
        return data.get("tmdb_api_key", "")
    except ImportError:
        pass
    except Exception:
        pass
    # Manual parse fallback (no PyYAML)
    try:
        for line in secrets_path.read_text().splitlines():
            if "tmdb_api_key" in line:
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _parse_filename(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem
    stem = re.sub(r'[_]+[a-z]+$', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'[_]+[a-z]+$', '', stem, flags=re.IGNORECASE)
    stem = stem.strip('_ ')
    m = re.match(r'^(.+?)\s*-\s*(\d{4})\s*$', stem)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', stem)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return stem.strip(), ""


def _tmdb_search(title: str, year: str, api_key: str) -> Optional[dict]:
    params: dict = {"api_key": api_key, "query": title, "language": "en-US"}
    if year:
        params["year"] = year
    url = f"{TMDB_BASE}/search/movie?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            results = json.loads(resp.read()).get("results", [])
        return results[0] if results else None
    except Exception as exc:
        log.debug(f"TMDB search error for '{title}': {exc}")
        return None


def _tmdb_credits(movie_id: int, api_key: str) -> str:
    url = f"{TMDB_BASE}/movie/{movie_id}/credits?api_key={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            crew = json.loads(resp.read()).get("crew", [])
        directors = [p["name"] for p in crew if p.get("job") == "Director"]
        return ", ".join(directors) if directors else "N/A"
    except Exception:
        return "N/A"


def _fetch_sidecar(video_path: Path, api_key: str) -> dict:
    title, year = _parse_filename(video_path.name)
    result = _tmdb_search(title, year, api_key)
    if not result and year:
        result = _tmdb_search(title, "", api_key)
    if not result:
        log.debug(f"Sidecars: no TMDB match for '{title}' — writing minimal sidecar")
        return {"title": title, "year": year or "N/A", "director": "N/A"}
    movie_id = result["id"]
    return {
        "title": result.get("title", title),
        "year": (result.get("release_date") or "")[:4] or year or "N/A",
        "director": _tmdb_credits(movie_id, api_key),
        "tmdb_id": movie_id,
        "imdb_url": f"https://www.themoviedb.org/movie/{movie_id}",
    }


def auto_generate_missing(media_dir: Path, secrets_path: Path) -> None:
    """Scan media_dir and generate .json sidecars for any video that lacks one.

    Designed to run in a daemon thread — never raises, logs at DEBUG/INFO only.
    """
    if not _lock.acquire(blocking=False):
        log.debug("Sidecars: generation already running, skipping")
        return
    try:
        api_key = _load_api_key(secrets_path)
        if not api_key:
            log.debug("Sidecars: no tmdb_api_key in secrets.yaml — skipping auto-generation")
            return

        if not media_dir.is_dir():
            return

        missing = [
            f for f in media_dir.iterdir()
            if f.suffix.lower() in VIDEO_EXTENSIONS
            and not f.with_suffix(".json").exists()
        ]
        if not missing:
            return

        log.info(f"Sidecars: {len(missing)} video(s) missing .json — fetching from TMDB")
        for video in sorted(missing):
            try:
                data = _fetch_sidecar(video, api_key)
                out = video.with_suffix(".json")
                out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                log.info(f"Sidecars: wrote {out.name} — {data['title']} ({data['year']})")
            except Exception as exc:
                log.warning(f"Sidecars: failed for {video.name}: {exc}")
    finally:
        _lock.release()
