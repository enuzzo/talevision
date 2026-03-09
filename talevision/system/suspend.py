"""Suspend schedule logic.

Handles overnight windows correctly (e.g. 23:00–07:00).
Day semantics: `days` = days the device is fully OFF (suspend days).
Days NOT in the list are "active days" — suspend applies only during
the time window. Empty list = time window applies to all days.
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
        self._days: List[int] = list(config.days) if config.days else []
        self._start = self._parse_time(config.start)
        self._end = self._parse_time(config.end)

    @staticmethod
    def _parse_time(s: str) -> datetime.time:
        try:
            return datetime.datetime.strptime(s, "%H:%M").time()
        except ValueError:
            log.error(f"Invalid suspend time format: '{s}'. Defaulting to midnight.")
            return datetime.time(0, 0)

    def _in_time_window(self, t: datetime.time) -> bool:
        start, end = self._start, self._end
        if start <= end:
            return start <= t < end
        else:
            return t >= start or t < end

    def _is_suspended_unlocked(self, dt: datetime.datetime) -> bool:
        if not self._enabled:
            return False
        weekday = dt.weekday()
        if self._days and weekday in self._days:
            return True
        return self._in_time_window(dt.time())

    def is_suspended(self, dt: Optional[datetime.datetime] = None) -> bool:
        """Return True if suspended: full-suspend day OR within time window."""
        with self._lock:
            dt = dt or datetime.datetime.now()
            return self._is_suspended_unlocked(dt)

    def next_wake_time(self, dt: Optional[datetime.datetime] = None) -> Optional[datetime.datetime]:
        """Return next datetime when suspension ends, or None if not suspended."""
        with self._lock:
            if not self._enabled:
                return None
            dt = dt or datetime.datetime.now()
            if not self._is_suspended_unlocked(dt):
                return None
            end = self._end
            candidate = dt.replace(
                hour=end.hour,
                minute=end.minute,
                second=0,
                microsecond=0,
            )
            if candidate <= dt:
                candidate += datetime.timedelta(days=1)
            if self._days:
                for _ in range(7):
                    if candidate.weekday() not in self._days:
                        break
                    candidate += datetime.timedelta(days=1)
                else:
                    return None  # all 7 days are suspend days — device never wakes
            return candidate

    def get_config(self) -> dict:
        """Return the current schedule config as a dict (thread-safe)."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "start": self._start_str,
                "end": self._end_str,
                "days": list(self._days),
            }

    def update(self, start: str, end: str, days: List[int], enabled: bool) -> None:
        """Thread-safe config update (called from API handler)."""
        with self._lock:
            self._enabled = enabled
            self._start_str = start
            self._end_str = end
            self._start = self._parse_time(start)
            self._end = self._parse_time(end)
            self._days = list(days) if days else []
        log.info(f"Suspend schedule updated: enabled={enabled}, {start}–{end}, days={days}")
