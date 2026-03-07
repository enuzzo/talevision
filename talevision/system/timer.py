"""Interruptible timer for main render loop."""
import threading
import logging
log = logging.getLogger(__name__)

class InterruptibleTimer:
    """A timer that can be interrupted early (e.g. for force-refresh).

    Interrupt signals are preserved even if raised before wait() is called.
    """
    def __init__(self):
        self._event = threading.Event()

    def wait(self, interval: int) -> bool:
        """Wait for up to `interval` seconds.
        Returns True if interrupted early, False if timed out normally.
        If interrupt() was called before wait(), returns immediately.
        """
        interrupted = self._event.wait(timeout=interval)
        self._event.clear()  # clear AFTER wait, not before
        return interrupted

    def interrupt(self) -> None:
        """Signal the timer to wake up immediately."""
        self._event.set()
        log.debug("InterruptibleTimer interrupted")
