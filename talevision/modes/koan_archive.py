"""Folder-based archive for Koan haiku — one JSON file per haiku."""
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class KoanArchive:
    def __init__(self, archive_path: Path, seed_data_path: Path):
        self._dir = Path(archive_path)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._seed_path = Path(seed_data_path)
        self._seeds: Optional[dict] = None

    def _load_seeds(self) -> dict:
        if self._seeds is None:
            try:
                with open(self._seed_path, "r", encoding="utf-8") as f:
                    self._seeds = json.load(f)
            except Exception as exc:
                log.warning("Koan seed data load failed: %s", exc)
                self._seeds = {"seed_words": [], "pen_names": []}
        return self._seeds

    def _list_files(self) -> list[Path]:
        """Return all haiku JSON files sorted by name (chronological)."""
        return sorted(self._dir.glob("*.json"))

    def append(self, lines: list, seed_word: str, author_name: str,
               source: str = "generated", generation_time_ms: int = 0,
               model: str = "", prompt_tokens: int = 0,
               completion_tokens: int = 0, total_tokens: int = 0,
               entry_type: str = "haiku") -> int:
        files = self._list_files()
        new_id = len(files) + 1
        ts = datetime.now(timezone.utc)
        ts_str = ts.strftime("%Y%m%d-%H%M%S")
        entry = {
            "id": new_id,
            "type": entry_type,
            "timestamp": ts.isoformat(),
            "lines": lines,
            "seed_word": seed_word,
            "author_name": author_name,
            "source": source,
            "generation_time_ms": generation_time_ms,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        slug = seed_word.replace(" ", "-")[:40]
        filename = f"{ts_str}_{slug}.json"
        filepath = self._dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        log.info("Koan archive: saved #%d → %s", new_id, filename)
        return new_id

    def _load_file(self, path: Path) -> Optional[dict]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def get_latest(self) -> Optional[dict]:
        files = self._list_files()
        if not files:
            return None
        return self._load_file(files[-1])

    def count(self) -> int:
        return len(self._list_files())

    def get_random_seed_word(self) -> str:
        seeds = self._load_seeds()
        words = seeds.get("seed_words", ["a towel that never fully dries"])
        return random.choice(words)
