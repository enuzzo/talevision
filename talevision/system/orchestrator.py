"""Orchestrator — main application loop and thread-safe mode controller.

Runs in the main thread. Flask runs in a daemon thread.
Communication via _action_queue + threading.Lock.
"""
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from PIL import Image

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode
from talevision.render.canvas import InkyCanvas
from talevision.system.suspend import SuspendScheduler
from talevision.system.timer import InterruptibleTimer
from talevision.system.buttons import InkyButtonHandler

log = logging.getLogger(__name__)


class Orchestrator:
    """Main application loop.

    Thread-safe mode switching. Runs render → display → save_frame → sleep cycle.
    Flask reads state via get_status(); POST /api/action writes via action queue.
    """

    def __init__(
        self,
        config: AppConfig,
        modes: Dict[str, DisplayMode],
        canvas: InkyCanvas,
        scheduler: SuspendScheduler,
        button_handler: Optional[InkyButtonHandler],
        base_dir: Path = Path("."),
    ):
        self._config = config
        self._modes = modes
        self._canvas = canvas
        self._scheduler = scheduler
        self._button_handler = button_handler
        self._base_dir = base_dir

        self._current_mode_name: str = config.app.default_mode
        if self._current_mode_name not in self._modes:
            self._current_mode_name = next(iter(self._modes))

        self._lock = threading.Lock()
        self._timer = InterruptibleTimer()
        self._action_queue: queue.Queue = queue.Queue()

        # Frame save paths for web serving
        self._frame_paths: Dict[str, Path] = {
            "litclock": base_dir / "cache" / "litclock_frame.png",
            "slowmovie": base_dir / "cache" / "slowmovie_frame.jpg",
        }
        for p in self._frame_paths.values():
            p.parent.mkdir(parents=True, exist_ok=True)

        self._last_render_time: float = 0.0
        self._last_error: Optional[str] = None
        self._suspended_displayed: bool = False

    # ------------------------------------------------------------------
    # Public API (called from Flask thread — must be thread-safe)
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        with self._lock:
            mode_name = self._current_mode_name
            active = self._modes.get(mode_name)
            state = active.get_state() if active else None
            is_suspended = self._scheduler.is_suspended()
            next_wake = self._scheduler.next_wake_time()
            return {
                "mode": mode_name,
                "is_suspended": is_suspended,
                "last_update": self._last_render_time,
                "next_wake": next_wake.isoformat() if next_wake else None,
                "last_error": self._last_error,
                "state": state.extra if state else {},
            }

    def get_frame_path(self, mode: Optional[str] = None) -> Optional[Path]:
        """Return path to last saved frame for given mode (or current mode)."""
        with self._lock:
            m = mode or self._current_mode_name
        p = self._frame_paths.get(m)
        return p if p and p.is_file() else None

    def switch_mode(self, mode_name: str) -> None:
        """Enqueue a mode switch action."""
        if mode_name not in self._modes:
            log.warning(f"Unknown mode: {mode_name}")
            return
        self._action_queue.put(("switch_mode", mode_name))
        self._timer.interrupt()

    def force_refresh(self) -> None:
        """Enqueue a force-refresh action."""
        self._action_queue.put(("force_refresh", None))
        self._timer.interrupt()

    def toggle_suspend(self) -> None:
        """Enqueue a toggle-suspend action."""
        self._action_queue.put(("toggle_suspend", None))
        self._timer.interrupt()

    def set_language(self, lang: str) -> None:
        """Enqueue a language change for LitClock."""
        self._action_queue.put(("set_language", lang))
        self._timer.interrupt()

    def set_suspend_schedule(self, start: str, end: str, days: list, enabled: bool) -> None:
        """Update suspend schedule immediately (thread-safe via scheduler.update)."""
        self._scheduler.update(start, end, days, enabled)

    def handle_button_action(self, action: str) -> None:
        """Handle GPIO button press — dispatches to appropriate method."""
        if action == "switch_mode":
            with self._lock:
                modes = list(self._modes.keys())
                idx = modes.index(self._current_mode_name) if self._current_mode_name in modes else 0
                next_mode = modes[(idx + 1) % len(modes)]
            self.switch_mode(next_mode)
        elif action == "force_refresh":
            self.force_refresh()
        elif action == "toggle_suspend":
            self.toggle_suspend()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_actions(self) -> None:
        """Drain the action queue and apply actions."""
        while not self._action_queue.empty():
            try:
                action, payload = self._action_queue.get_nowait()
            except queue.Empty:
                break

            if action == "switch_mode":
                old = self._current_mode_name
                if payload in self._modes:
                    with self._lock:
                        self._modes[old].on_deactivate()
                        self._current_mode_name = payload
                        self._modes[payload].on_activate()
                        self._suspended_displayed = False
                    log.info(f"Mode switched: {old} → {payload}")

            elif action == "force_refresh":
                log.info("Force refresh requested")

            elif action == "toggle_suspend":
                cfg = self._config.suspend
                new_enabled = not self._scheduler.is_suspended()
                self._scheduler.update(cfg.start, cfg.end, list(cfg.days), new_enabled)
                log.info(f"Suspend toggled: enabled={new_enabled}")

            elif action == "set_language":
                litclock_mode = self._modes.get("litclock")
                if litclock_mode and hasattr(litclock_mode, "set_language"):
                    litclock_mode.set_language(payload)

    def _save_frame(self, image: Image.Image, mode_name: str) -> None:
        """Save rendered frame to disk for web serving."""
        p = self._frame_paths.get(mode_name)
        if not p:
            return
        try:
            fmt = "JPEG" if p.suffix.lower() in (".jpg", ".jpeg") else "PNG"
            image.save(str(p), format=fmt)
            log.debug(f"Frame saved: {p.name}")
        except Exception as exc:
            log.error(f"Failed to save frame: {exc}")

    def run(self) -> None:
        """Main loop. Blocks forever. Call from main thread."""
        with self._lock:
            active_name = self._current_mode_name
        active = self._modes[active_name]
        active.on_activate()

        if self._button_handler:
            self._button_handler.start()

        log.info(f"Orchestrator starting. Default mode: {active_name}")

        while True:
            try:
                self._process_actions()

                with self._lock:
                    active_name = self._current_mode_name
                active = self._modes[active_name]

                is_suspended = self._scheduler.is_suspended()

                if is_suspended and self._suspended_displayed:
                    # Already showing suspend screen; just wait
                    self._timer.wait(active.refresh_interval)
                    continue

                frame = active.render(is_suspended=is_suspended)

                if is_suspended:
                    self._suspended_displayed = True
                else:
                    self._suspended_displayed = False

                self._canvas.show(frame)
                self._save_frame(frame, active_name)

                with self._lock:
                    self._last_render_time = time.time()
                    self._last_error = None

                self._timer.wait(active.refresh_interval)

            except KeyboardInterrupt:
                log.info("Orchestrator stopped by KeyboardInterrupt")
                break
            except Exception as exc:
                log.error(f"Orchestrator loop error: {exc}", exc_info=True)
                with self._lock:
                    self._last_error = str(exc)
                self._timer.wait(10)
