"""Suspend schedule logic.

Handles overnight windows correctly (e.g. 23:00–07:00).
Day filtering: only suspend if weekday in days list (empty = all days).
"""
import datetime
import logging
import threading
from typing import List, Optional

from talevision.config.schema import SuspendConfig

log = logging.getLogger(__name__)


class SuspendScheduler:
    """Determines whether the display should be suspended at a given time."""

    def __init__(self, config: SuspendConfig):
        self._lock = threading.Lock()
        self._enabled = config.enabled
        self._start_str = config.start
        self._end_str = config.end
        self._days: List[int] = list(config.days) if config.days else list(range(7))
        self._start = self._parse_time(config.start)
        self._end = self._parse_time(config.end)

    @staticmethod
    def _parse_time(s: str) -> datetime.time:
        try:
            return datetime.datetime.strptime(s, "%H:%M").time()
        except ValueError:
            log.error(f"Invalid suspend time format: '{s}'. Defaulting to midnight.")
            return datetime.time(0, 0)

    def is_suspended(self, dt: Optional[datetime.datetime] = None) -> bool:
        """Return True if dt falls within suspend window on an active day."""
        with self._lock:
            if not self._enabled:
                return False
            dt = dt or datetime.datetime.now()
            # Day filter (empty = all days)
            if self._days and dt.weekday() not in self._days:
                return False
            t = dt.time()
            start = self._start
            end = self._end
            # Overnight window: e.g. 23:00–07:00
            if start <= end:
                return start <= t < end
            else:
                return t >= start or t < end

    def next_wake_time(self, dt: Optional[datetime.datetime] = None) -> Optional[datetime.datetime]:
        """Return next datetime when suspension ends, or None if not suspended."""
        with self._lock:
            if not self._enabled:
                return None
            dt = dt or datetime.datetime.now()
            if not self.is_suspended(dt):
                return None
            # Wake is at _end time on the appropriate day
            end = self._end
            candidate = dt.replace(
                hour=end.hour,
                minute=end.minute,
                second=0,
                microsecond=0,
            )
            if candidate <= dt:
                candidate += datetime.timedelta(days=1)
            return candidate

    def update(
        self,
        start: str,
        end: str,
        days: List[int],
        enabled: bool,
    ) -> None:
        """Thread-safe config update (called from API handler)."""
        with self._lock:
            self._enabled = enabled
            self._start_str = start
            self._end_str = end
            self._start = self._parse_time(start)
            self._end = self._parse_time(end)
            self._days = list(days) if days else list(range(7))
        log.info(f"Suspend schedule updated: enabled={enabled}, {start}–{end}, days={days}")
