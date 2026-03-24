"""Victoria and Albert Museum provider."""
import json
import logging
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://api.vam.ac.uk/v2"


class VandAProvider(MuseoProvider):
    @property
    def name(self) -> str:
        return "vanda"

    @property
    def museum_display_name(self) -> str:
        return "Victoria and Albert Museum"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        url = f"{_API}/objects/search?images_exist=true&page_size=1"
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("info", {}).get("record_count", 0)
        pages = data.get("info", {}).get("pages", 0)
        log.info(f"V&A catalogue: {total} artworks with images, {pages} pages")
        return {"total": total, "pages": pages}

    def pick_random_id(self, cache_data: dict) -> str:
        pages = cache_data.get("pages", 0)
        if pages == 0:
            raise RuntimeError("V&A cache is empty")
        return str(random.randint(1, pages))

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        page = int(artwork_id)
        url = f"{_API}/objects/search?images_exist=true&page_size=1&page={page}"
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"V&A fetch failed (page={page}): {exc}")
            return None
        records = data.get("records", [])
        if not records:
            return None
        raw = records[0]
        iiif_base = raw.get("_images", {}).get("_iiif_image_base_url", "")
        if not iiif_base:
            return None
        return self._normalize(raw, iiif_base)

    def _normalize(self, raw: dict, iiif_base: str) -> ArtworkInfo:
        maker = raw.get("_primaryMaker", {})
        artist = maker.get("name", "Unknown") if maker else "Unknown"
        sys_num = raw.get("systemNumber", "")
        return ArtworkInfo(
            title=raw.get("_primaryTitle", "Untitled"),
            artist=artist,
            date=raw.get("_primaryDate", ""),
            department=raw.get("objectType", ""),
            museum="V&A",
            image_url=f"{iiif_base}full/800,/0/default.jpg",
            object_url=f"https://collections.vam.ac.uk/item/{sys_num}",
            provider="vanda",
            artwork_id=sys_num,
        )
