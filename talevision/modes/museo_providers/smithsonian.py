"""Smithsonian Open Access provider (SAAM, NPG, Cooper Hewitt, Freer)."""
import json
import logging
import os
import random
import urllib.request
from typing import Optional

from .base import ArtworkInfo, MuseoProvider

log = logging.getLogger(__name__)

_UA = {"User-Agent": "TaleVision/1.0"}
_API = "https://api.si.edu/openaccess/api/v1.0"
_ART_UNITS = ["SAAM", "NPG", "CHNDM", "FSG"]
_UNIT_NAMES = {
    "SAAM": "Smithsonian American Art Museum",
    "NPG": "National Portrait Gallery",
    "CHNDM": "Cooper Hewitt, Smithsonian Design Museum",
    "FSG": "National Museum of Asian Art",
}


class SmithsonianProvider(MuseoProvider):
    def __init__(self, api_key: str = ""):
        self._api_key = api_key or os.environ.get("SMITHSONIAN_API_KEY", "DEMO_KEY")

    @property
    def name(self) -> str:
        return "smithsonian"

    @property
    def museum_display_name(self) -> str:
        return "Smithsonian"

    def fetch_catalogue_meta(self, timeout: int = 30) -> dict:
        totals = {}
        for unit in _ART_UNITS:
            q = f"unit_code:{unit}+AND+online_media_type:Images"
            url = f"{_API}/search?q={q}&rows=0&api_key={self._api_key}"
            req = urllib.request.Request(url, headers=_UA)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                totals[unit] = data.get("response", {}).get("rowCount", 0)
            except Exception as exc:
                log.warning(f"Smithsonian catalogue count for {unit} failed: {exc}")
                totals[unit] = 0
        grand_total = sum(totals.values())
        log.info(f"Smithsonian catalogue: {grand_total} artworks ({totals})")
        return {"totals": totals, "grand_total": grand_total}

    def pick_random_id(self, cache_data: dict) -> str:
        totals = cache_data.get("totals", {})
        weighted = [(u, c) for u, c in totals.items() if c > 0]
        if not weighted:
            raise RuntimeError("Smithsonian cache is empty")
        unit = random.choices(
            [u for u, _ in weighted],
            weights=[c for _, c in weighted],
            k=1,
        )[0]
        offset = random.randint(0, totals[unit] - 1)
        return f"{unit}:{offset}"

    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]:
        unit, offset_str = artwork_id.split(":", 1)
        offset = int(offset_str)
        q = f"unit_code:{unit}+AND+online_media_type:Images"
        url = (f"{_API}/search?q={q}&start={offset}&rows=1"
               f"&api_key={self._api_key}")
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning(f"Smithsonian fetch failed ({artwork_id}): {exc}")
            return None
        rows = data.get("response", {}).get("rows", [])
        if not rows:
            return None
        raw = rows[0]
        img_url = self._extract_image_url(raw)
        if not img_url:
            return None
        return self._normalize(raw, unit, img_url)

    def _extract_image_url(self, raw: dict) -> str:
        content = raw.get("content", {})
        desc = content.get("descriptiveNonRepeating", {})
        media = desc.get("online_media", {})
        media_list = media.get("media", [])
        for m in media_list:
            if m.get("type", "").startswith("Images"):
                ids_id = m.get("idsId", "")
                if ids_id:
                    return f"https://ids.si.edu/ids/deliveryService?id={ids_id}&max_w=800"
                content_url = m.get("content", "")
                if content_url:
                    return content_url
        return ""

    def _normalize(self, raw: dict, unit: str, img_url: str) -> ArtworkInfo:
        title = raw.get("title", "Untitled")
        content = raw.get("content", {})
        freetext = content.get("freetext", {})

        artist = "Unknown"
        for entry in freetext.get("name", []):
            if entry.get("label", "").lower() in ("artist", "maker", "creator"):
                artist = entry.get("content", "Unknown")
                break
        if artist == "Unknown":
            names = freetext.get("name", [])
            if names:
                artist = names[0].get("content", "Unknown")

        date = ""
        for entry in freetext.get("date", []):
            date = entry.get("content", "")
            break

        department = ""
        for entry in freetext.get("setName", []):
            department = entry.get("content", "")
            break

        museum = _UNIT_NAMES.get(unit, "Smithsonian")

        desc = content.get("descriptiveNonRepeating", {})
        record_link = desc.get("record_link", "")
        record_id = desc.get("record_ID", raw.get("id", ""))

        return ArtworkInfo(
            title=title,
            artist=artist,
            date=date,
            department=department,
            museum=museum,
            image_url=img_url,
            object_url=record_link,
            provider="smithsonian",
            artwork_id=str(record_id),
        )
