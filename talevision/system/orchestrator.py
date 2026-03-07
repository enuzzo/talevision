"""Orchestrator — main application loop and thread-safe mode controller."""
import json
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

        self._frame_paths: Dict[str, Path] = {
            "litclock": base_dir / "cache" / "litclock_frame.png",
            "slowmovie": base_dir / "cache" / "slowmovie_frame.jpg",
        }
        for p in self._frame_paths.values():
            p.parent.mkdir(parents=True, exist_ok=True)

        self._status_lock = threading.Lock()
        self._status_cache: dict = {
            "mode": self._current_mode_name,
            "is_suspended": False,
            "last_update": None,
            "next_wake": None,
            "last_error": None,
            "state": {},
        }
        self._suspended_displayed: bool = False

        self._interval_overrides: Dict[str, int] = {}
        self._prefs_path = base_dir / "user_prefs.json"
        self._load_prefs()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        with self._status_lock:
            status = dict(self._status_cache)
        status["intervals"] = {
            name: {
                "effective": self._effective_interval(name, mode.refresh_interval),
                "default": mode.refresh_interval,
                "overridden": name in self._interval_overrides,
            }
            for name, mode in self._modes.items()
        }
        return status

    def get_frame_path(self, mode: Optional[str] = None) -> Optional[Path]:
        with self._status_lock:
            m = mode or self._status_cache.get("mode", self._current_mode_name)
        p = self._frame_paths.get(m)
        return p if p and p.is_file() else None

    def switch_mode(self, mode_name: str) -> None:
        if mode_name not in self._modes:
            log.warning(f"Unknown mode: {mode_name}")
            return
        log.info(f"switch_mode({mode_name}): enqueuing, queue was {self._action_queue.qsize()}")
        self._action_queue.put(("switch_mode", mode_name))
        self._timer.interrupt()
        log.info(f"switch_mode({mode_name}): done, queue now {self._action_queue.qsize()}")

    def force_refresh(self) -> None:
        self._action_queue.put(("force_refresh", None))
        self._timer.interrupt()

    def toggle_suspend(self) -> None:
        self._action_queue.put(("toggle_suspend", None))
        self._timer.interrupt()

    def set_language(self, lang: str) -> None:
        self._action_queue.put(("set_language", lang))
        self._timer.interrupt()

    def set_suspend_schedule(self, start: str, end: str, days: list, enabled: bool) -> None:
        self._scheduler.update(start, end, days, enabled)

    def set_mode_interval(self, mode_name: str, seconds: int) -> None:
        if mode_name not in self._modes:
            raise ValueError(f"Unknown mode: {mode_name}")
        self._interval_overrides[mode_name] = max(10, min(seconds, 86400))
        self._save_prefs()
        self._timer.interrupt()

    def reset_mode_interval(self, mode_name: str) -> None:
        self._interval_overrides.pop(mode_name, None)
        self._save_prefs()
        self._timer.interrupt()

    def handle_button_action(self, action: str) -> None:
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

    def _effective_interval(self, mode_name: str, default: int) -> int:
        return self._interval_overrides.get(mode_name, default)

    def _load_prefs(self) -> None:
        try:
            if self._prefs_path.exists():
                data = json.loads(self._prefs_path.read_text())
                self._interval_overrides = {k: int(v) for k, v in data.get("intervals", {}).items()}
                log.debug(f"Loaded user prefs: intervals={self._interval_overrides}")
        except Exception as exc:
            log.warning(f"Could not load user_prefs.json: {exc}")

    def _save_prefs(self) -> None:
        try:
            self._prefs_path.write_text(json.dumps({"intervals": self._interval_overrides}, indent=2))
        except Exception as exc:
            log.warning(f"Could not save user_prefs.json: {exc}")

    def _update_status_cache(self, mode_name: str, last_render_time: float,
                              last_error: Optional[str], state_extra: dict) -> None:
        is_suspended = self._scheduler.is_suspended()
        next_wake = self._scheduler.next_wake_time()
        with self._status_lock:
            self._status_cache = {
                "mode": mode_name,
                "is_suspended": is_suspended,
                "last_update": last_render_time,
                "next_wake": next_wake.isoformat() if next_wake else None,
                "last_error": last_error,
                "state": state_extra,
            }

    def _process_actions(self) -> None:
        qsize = self._action_queue.qsize()
        if qsize > 0:
            log.info(f"_process_actions: draining {qsize} action(s)")
        while not self._action_queue.empty():
            try:
                action, payload = self._action_queue.get_nowait()
            except queue.Empty:
                break

            log.info(f"_process_actions: action='{action}' payload='{payload}'")

            if action == "switch_mode":
                old = self._current_mode_name
                if payload in self._modes:
                    with self._lock:
                        self._modes[old].on_deactivate()
                        self._current_mode_name = payload
                        self._modes[payload].on_activate()
                        self._suspended_displayed = False
                    with self._status_lock:
                        self._status_cache["mode"] = payload
                    log.info(f"Mode switched: {old} → {payload}")
                else:
                    log.error(f"switch_mode: unknown mode '{payload}'")

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

        last_error: Optional[str] = None

        while True:
            try:
                log.debug(f"LOOP ── top. queue={self._action_queue.qsize()} mode={self._current_mode_name}")
                self._process_actions()

                with self._lock:
                    active_name = self._current_mode_name
                log.debug(f"LOOP ── active mode: {active_name}")
                active = self._modes[active_name]

                is_suspended = self._scheduler.is_suspended()

                if is_suspended and self._suspended_displayed:
                    log.debug("LOOP ── suspended, sleeping")
                    self._timer.wait(self._effective_interval(active_name, active.refresh_interval))
                    continue

                log.debug(f"LOOP ── render() starting ...")
                frame = active.render(is_suspended=is_suspended)
                log.debug("LOOP ── render() done. canvas.show() starting ...")

                if is_suspended:
                    self._suspended_displayed = True
                else:
                    self._suspended_displayed = False

                self._canvas.show(frame)
                log.debug("LOOP ── canvas.show() done. saving frame ...")

                self._save_frame(frame, active_name)
                log.debug("LOOP ── frame saved. updating status cache ...")

                mode_obj = self._modes.get(active_name)
                state = mode_obj.get_state() if mode_obj else None
                state_extra = state.extra if state else {}
                now = time.time()
                last_error = None
                self._update_status_cache(active_name, now, last_error, state_extra)
                log.debug("LOOP ── status cache updated.")

                interval = self._effective_interval(active_name, active.refresh_interval)
                log.debug(f"LOOP ── sleeping {interval}s ...")
                interrupted = self._timer.wait(interval)
                log.debug(f"LOOP ── awake. interrupted={interrupted}, queue={self._action_queue.qsize()}")

            except KeyboardInterrupt:
                log.info("Orchestrator stopped by KeyboardInterrupt")
                break
            except Exception as exc:
                log.error(f"LOOP ── error: {exc}", exc_info=True)
                last_error = str(exc)
                self._update_status_cache(
                    self._current_mode_name, time.time(), last_error, {}
                )
                self._timer.wait(10)
