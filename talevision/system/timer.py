"""Interruptible timer for main render loop."""
import threading
import logging

log = logging.getLogger(__name__)


class InterruptibleTimer:
    """A timer that can be interrupted early (e.g. for force-refresh).

    Usage:
        timer = InterruptibleTimer()
        timer.start(interval=60)
        timer.wait()   # blocks until interval expires or interrupt() called
    """

    def __init__(self):
        self._event = threading.Event()

    def wait(self, interval: int) -> bool:
        """Wait for up to `interval` seconds.

        Returns True if interrupted early, False if timed out normally.
        """
        self._event.clear()
        interrupted = self._event.wait(timeout=interval)
        return interrupted

    def interrupt(self) -> None:
        """Signal the timer to wake up immediately."""
        self._event.set()
        log.debug("InterruptibleTimer interrupted")
