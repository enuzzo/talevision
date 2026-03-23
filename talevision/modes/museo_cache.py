"""File-based cache for museum catalogue data with TTL."""
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class MuseoCache:
    def __init__(self, cache_dir: Path, max_age: int = 86400):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_age = max_age

    def _path(self, provider: str) -> Path:
        return self._dir / f"museo_{provider}.json"

    def needs_refresh(self, provider: str) -> bool:
        p = self._path(provider)
        if not p.exists():
            return True
        age = time.time() - os.path.getmtime(str(p))
        return age > self._max_age

    def save(self, provider: str, data: dict) -> None:
        p = self._path(provider)
        with open(str(p), "w", encoding="utf-8") as f:
            json.dump(data, f)
        log.info(f"Museo cache saved: {p.name}")

    def load(self, provider: str) -> Optional[dict]:
        p = self._path(provider)
        if not p.exists():
            return None
        try:
            with open(str(p), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning(f"Museo cache load failed for {provider}: {exc}")
            return None
