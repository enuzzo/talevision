"""Metropolitan Museum of Art provider."""
import json
import logging
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://collectionapi.metmuseum.org/public/collection/v1"


class MetProvider(MuseoProvider):
    @property
    def name(self) -> str:
        return "met"

    @property
    def museum_display_name(self) -> str:
        return "The Met"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        url = f"{_API}/search?hasImages=true&isPublicDomain=true&q=*"
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"objectIDs": data.get("objectIDs", [])}

    def pick_random_id(self, cache_data: dict) -> str:
        ids = cache_data.get("objectIDs", [])
        if not ids:
            raise RuntimeError("Met cache is empty")
        return str(random.choice(ids))

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        url = f"{_API}/objects/{artwork_id}"
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"Met fetch failed for {artwork_id}: {exc}")
            return None
        if not raw.get("primaryImageSmall"):
            return None
        return self._normalize(raw)

    def _normalize(self, raw: dict) -> ArtworkInfo:
        return ArtworkInfo(
            title=raw.get("title", "Untitled"),
            artist=raw.get("artistDisplayName", "Unknown"),
            date=raw.get("objectDate", ""),
            department=raw.get("department", ""),
            museum="The Met",
            image_url=raw.get("primaryImageSmall", ""),
            object_url=raw.get("objectURL", ""),
            provider="met",
            artwork_id=str(raw.get("objectID", "")),
        )
