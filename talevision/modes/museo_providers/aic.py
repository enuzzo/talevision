"""Art Institute of Chicago provider."""
import json
import logging
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://api.artic.edu/api/v1"
_IIIF = "https://www.artic.edu/iiif/2"
_FIELDS = "id,title,artist_display,date_display,image_id,department_title"
_BATCH_PAGES = 100
_BATCH_LIMIT = 100


class AICProvider(MuseoProvider):
    @property
    def name(self) -> str:
        return "aic"

    @property
    def museum_display_name(self) -> str:
        return "Art Institute of Chicago"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        ids = []
        for page in range(1, _BATCH_PAGES + 1):
            url = (f"{_API}/artworks/search"
                   f"?query[term][is_public_domain]=true"
                   f"&limit={_BATCH_LIMIT}&page={page}&fields=id")
            req = urllib.request.Request(url, headers=_UA)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                batch = [str(item["id"]) for item in data.get("data", [])]
                ids.extend(batch)
                if len(batch) < _BATCH_LIMIT:
                    break
            except Exception as exc:
                log.warning(f"AIC catalogue page {page} failed: {exc}")
                break
        log.info(f"AIC catalogue: cached {len(ids)} IDs")
        return {"ids": ids}

    def pick_random_id(self, cache_data: dict) -> str:
        ids = cache_data.get("ids", [])
        if not ids:
            raise RuntimeError("AIC cache is empty")
        return random.choice(ids)

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        url = f"{_API}/artworks/{artwork_id}?fields={_FIELDS}"
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"AIC fetch failed for {artwork_id}: {exc}")
            return None
        raw = data.get("data", {})
        if not raw.get("image_id"):
            return None
        return self._normalize(raw)

    def _normalize(self, raw: dict) -> ArtworkInfo:
        artist = raw.get("artist_display", "Unknown")
        if "\n" in artist:
            artist = artist.split("\n")[0].strip()
        image_id = raw.get("image_id", "")
        return ArtworkInfo(
            title=raw.get("title", "Untitled"),
            artist=artist,
            date=raw.get("date_display", ""),
            department=raw.get("department_title", ""),
            museum="Art Institute of Chicago",
            image_url=f"{_IIIF}/{image_id}/full/843,/0/default.jpg" if image_id else "",
            object_url=f"https://www.artic.edu/artworks/{raw.get('id', '')}",
            provider="aic",
            artwork_id=str(raw.get("id", "")),
        )
