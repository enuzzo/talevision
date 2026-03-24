"""Harvard Art Museums provider."""
import json
import logging
import os
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://api.harvardartmuseums.org"
_FIELDS = "objectid,title,dated,department,classification,primaryimageurl,people,url"


class HarvardProvider(MuseoProvider):
    def __init__(self, api_key: str = ""):
        self._api_key = api_key or os.environ.get("HARVARD_ART_API_KEY", "")

    @property
    def name(self) -> str:
        return "harvard"

    @property
    def museum_display_name(self) -> str:
        return "Harvard Art Museums"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        if not self._api_key:
            raise RuntimeError("Harvard API key not configured")
        url = (f"{_API}/object?apikey={self._api_key}"
               f"&hasimage=1&q=imagepermissionlevel:0&size=0")
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("info", {}).get("totalrecords", 0)
        pages = data.get("info", {}).get("pages", 0)
        log.info(f"Harvard catalogue: {total} open-access artworks, {pages} pages")
        return {"total": total, "pages": pages}

    def pick_random_id(self, cache_data: dict) -> str:
        total = cache_data.get("total", 0)
        pages = cache_data.get("pages", 0)
        if total == 0 or pages == 0:
            raise RuntimeError("Harvard cache is empty")
        return str(random.randint(1, pages))

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        page = int(artwork_id)
        url = (f"{_API}/object?apikey={self._api_key}"
               f"&hasimage=1&q=imagepermissionlevel:0"
               f"&size=1&sort=random&page={page}&fields={_FIELDS}")
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"Harvard fetch failed (page={page}): {exc}")
            return None
        records = data.get("records", [])
        if not records:
            return None
        raw = records[0]
        if not raw.get("primaryimageurl"):
            return None
        return self._normalize(raw)

    def _normalize(self, raw: dict) -> ArtworkInfo:
        people = raw.get("people", [])
        artist = "Unknown"
        for p in (people or []):
            if p.get("role") == "Artist":
                artist = p.get("displayname", "Unknown")
                break
        if artist == "Unknown" and people:
            artist = people[0].get("displayname", "Unknown")
        img_url = raw.get("primaryimageurl", "")
        if img_url and "?" not in img_url:
            img_url += "?height=600&width=800"
        return ArtworkInfo(
            title=raw.get("title", "Untitled"),
            artist=artist,
            date=raw.get("dated", ""),
            department=raw.get("department", ""),
            museum="Harvard Art Museums",
            image_url=img_url,
            object_url=raw.get("url", ""),
            provider="harvard",
            artwork_id=str(raw.get("objectid", "")),
        )
