"""Physical button handler for Inky Impression GPIO buttons.

Non-fatal on non-Pi hardware: logs a warning and does nothing.
Inky Impression standard GPIO map: A=5, B=6, C=16, D=24.
"""
import logging
import threading
import time
from typing import Callable, Dict, Optional

log = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
except RuntimeError:
    GPIO_AVAILABLE = False


class InkyButtonHandler:
    """Polls Inky Impression physical buttons via RPi.GPIO.

    Calls action_callback(action_name) when a configured button is pressed.
    action_callback is expected to be thread-safe.
    """

    DEBOUNCE_MS = 300

    def __init__(self, gpio_map: Dict[str, int], actions: Dict[str, Optional[str]], action_callback: Callable[[str], None]):
        self._gpio_map = gpio_map       # {"a": 5, "b": 6, "c": 16, "d": 24}
        self._actions = actions         # {"a": "switch_mode", "b": "force_refresh", ...}
        self._callback = action_callback
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start background polling thread. No-op on non-Pi hardware."""
        if not GPIO_AVAILABLE:
            log.warning("RPi.GPIO not available — button handler disabled (non-Pi hardware)")
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="buttons")
        self._thread.start()
        log.info("Button handler started")

    def stop(self) -> None:
        """Stop the polling thread gracefully."""
        self._stop_event.set()
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            GPIO.setmode(GPIO.BCM)
            for pin in self._gpio_map.values():
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            log.debug(f"GPIO pins configured: {self._gpio_map}")

            last_press: Dict[str, float] = {}

            while not self._stop_event.is_set():
                for button, pin in self._gpio_map.items():
                    if GPIO.input(pin) == GPIO.LOW:
                        now = time.monotonic()
                        last = last_press.get(button, 0.0)
                        if (now - last) * 1000 >= self.DEBOUNCE_MS:
                            last_press[button] = now
                            action = self._actions.get(button)
                            if action:
                                log.info(f"Button '{button}' pressed → action: {action}")
                                try:
                                    self._callback(action)
                                except Exception as exc:
                                    log.error(f"Button callback error: {exc}")
                time.sleep(0.05)
        except Exception as exc:
            log.error(f"Button handler error: {exc}")
        finally:
            try:
                GPIO.cleanup()
            except Exception:
                pass
