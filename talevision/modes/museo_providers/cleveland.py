"""Cleveland Museum of Art provider."""
import json
import logging
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://openaccess-api.clevelandart.org/api/artworks"


class ClevelandProvider(MuseoProvider):
    @property
    def name(self) -> str:
        return "cleveland"

    @property
    def museum_display_name(self) -> str:
        return "Cleveland Museum of Art"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        url = f"{_API}/?has_image=1&cc0=1&limit=1"
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("info", {}).get("total", 0)
        log.info(f"Cleveland catalogue: {total} artworks")
        return {"total": total}

    def pick_random_id(self, cache_data: dict) -> str:
        total = cache_data.get("total", 0)
        if total == 0:
            raise RuntimeError("Cleveland cache is empty")
        return str(random.randint(0, total - 1))

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        skip = int(artwork_id)
        url = f"{_API}/?has_image=1&cc0=1&limit=1&skip={skip}"
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"Cleveland fetch failed at skip={skip}: {exc}")
            return None
        items = data.get("data", [])
        if not items:
            return None
        raw = items[0]
        img_url = (raw.get("images") or {}).get("web", {}).get("url", "")
        if not img_url:
            return None
        return self._normalize(raw)

    def _normalize(self, raw: dict) -> ArtworkInfo:
        creators = raw.get("creators", [])
        artist = creators[0].get("description", "Unknown") if creators else "Unknown"
        img_url = (raw.get("images") or {}).get("web", {}).get("url", "")
        return ArtworkInfo(
            title=raw.get("title", "Untitled"),
            artist=artist,
            date=raw.get("creation_date", ""),
            department=raw.get("collection", ""),
            museum="Cleveland Museum of Art",
            image_url=img_url,
            object_url=raw.get("url", ""),
            provider="cleveland",
            artwork_id=str(raw.get("id", "")),
        )
