"""Append-only JSON archive for Koan haiku."""
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class KoanArchive:
    def __init__(self, archive_path: Path, seed_data_path: Path):
        self._path = Path(archive_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seed_path = Path(seed_data_path)
        self._seeds: Optional[dict] = None

    def _load_seeds(self) -> dict:
        if self._seeds is None:
            try:
                with open(self._seed_path, "r", encoding="utf-8") as f:
                    self._seeds = json.load(f)
            except Exception as exc:
                log.warning(f"Koan seed data load failed: {exc}")
                self._seeds = {"seed_words": [], "pen_names": [], "curated_haiku": []}
        return self._seeds

    def load(self) -> dict:
        if not self._path.exists():
            return {"haiku": []}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning(f"Koan archive load failed: {exc}")
            return {"haiku": []}

    def _save(self, data: dict) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def append(self, lines: list, seed_word: str, author_name: str,
               source: str = "generated", generation_time_ms: int = 0) -> int:
        data = self.load()
        new_id = len(data["haiku"]) + 1
        entry = {
            "id": new_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lines": lines,
            "seed_word": seed_word,
            "author_name": author_name,
            "source": source,
            "generation_time_ms": generation_time_ms,
        }
        data["haiku"].append(entry)
        self._save(data)
        log.info(f"Koan archive: saved #{new_id} ({source})")
        return new_id

    def get_random(self) -> Optional[dict]:
        data = self.load()
        if data["haiku"]:
            return random.choice(data["haiku"])
        return self.get_curated_haiku()

    def get_latest(self) -> Optional[dict]:
        data = self.load()
        if data["haiku"]:
            return data["haiku"][-1]
        return self.get_curated_haiku()

    def count(self) -> int:
        return len(self.load()["haiku"])

    def get_random_seed_word(self) -> str:
        seeds = self._load_seeds()
        words = seeds.get("seed_words", ["silence"])
        return random.choice(words)

    def get_random_pen_name(self) -> str:
        seeds = self._load_seeds()
        names = seeds.get("pen_names", ["Null Poet"])
        return random.choice(names)

    def get_curated_haiku(self) -> Optional[dict]:
        seeds = self._load_seeds()
        curated = seeds.get("curated_haiku", [])
        if not curated:
            return None
        h = random.choice(curated)
        return {
            "id": 0,
            "timestamp": "",
            "lines": h["lines"],
            "seed_word": h["seed_word"],
            "author_name": h["author_name"],
            "source": "curated",
            "generation_time_ms": 0,
        }
