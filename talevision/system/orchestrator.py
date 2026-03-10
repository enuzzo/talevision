"""Orchestrator — main application loop and thread-safe mode controller."""
import datetime
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
            "litclock":  base_dir / "cache" / "litclock_frame.png",
            "slowmovie": base_dir / "cache" / "slowmovie_frame.jpg",
            "wikipedia": base_dir / "cache" / "wikipedia_frame.png",
            "weather":   base_dir / "cache" / "weather_frame.png",
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
        self._playlist: list = [self._current_mode_name]
        self._playlist_index: int = 0
        self._rotation_interval: int = 300
        self._prefs_path = base_dir / "user_prefs.json"
        self._load_prefs()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        with self._status_lock:
            status = dict(self._status_cache)
        with self._lock:
            intervals = {
                name: {
                    "effective": self._effective_interval(name, mode.refresh_interval),
                    "default": mode.refresh_interval,
                    "overridden": name in self._interval_overrides,
                }
                for name, mode in self._modes.items()
            }
            playlist = list(self._playlist)
            playlist_index = self._playlist_index
            rotation_interval = self._rotation_interval
        status["intervals"] = intervals
        status["suspend"] = self._scheduler.get_config()
        status["playlist"] = playlist
        status["playlist_index"] = playlist_index
        status["rotation_interval"] = rotation_interval
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

    def set_weather_location(self, location: str) -> None:
        weather = self._modes.get("weather")
        if weather and hasattr(weather, "set_location"):
            weather.set_location(location)
        self._action_queue.put(("force_refresh", None))
        self._timer.interrupt()

    def set_suspend_schedule(self, start: str, end: str, days: list, enabled: bool) -> None:
        self._scheduler.update(start, end, days, enabled)
        self._suspended_displayed = False
        self._timer.interrupt()

    def set_playlist(self, modes: list, rotation_interval: int = 300) -> None:
        valid = [m for m in modes if m in self._modes]
        with self._lock:
            if not valid:
                valid = [self._current_mode_name]
            self._playlist = valid
            self._rotation_interval = max(30, min(rotation_interval, 3600))
            self._playlist_index = 0
            switch_needed = valid[0] != self._current_mode_name
        if switch_needed:
            self._action_queue.put(("switch_mode", valid[0]))
            self._timer.interrupt()
        self._save_prefs()
        log.info(f"Playlist set: {self._playlist}, rotation={self._rotation_interval}s")

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
                saved_playlist = data.get("playlist", [])
                valid = [m for m in saved_playlist if m in self._modes]
                if valid:
                    self._playlist = valid
                    self._current_mode_name = valid[0]
                self._rotation_interval = data.get("rotation_interval", 300)
                log.debug(f"Loaded user prefs: intervals={self._interval_overrides}, playlist={self._playlist}")
        except Exception as exc:
            log.warning(f"Could not load user_prefs.json: {exc}")

    def _save_prefs(self) -> None:
        try:
            data = {
                "intervals": self._interval_overrides,
                "playlist": self._playlist,
                "rotation_interval": self._rotation_interval,
            }
            self._prefs_path.write_text(json.dumps(data, indent=2))
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
                current = self._scheduler.get_config()
                new_enabled = not current["enabled"]
                self._scheduler.update(current["start"], current["end"], current["days"], new_enabled)
                log.info(f"Suspend toggled: enabled={new_enabled}")

            elif action == "set_language":
                active = self._modes.get(self._current_mode_name)
                if active and hasattr(active, "set_language"):
                    active.set_language(payload)
                    log.info(f"Language set to '{payload}' on mode '{self._current_mode_name}'")

    def _render_suspend_screen(self) -> Image.Image:
        from talevision.render.suspend_screen import render_suspend_screen
        cfg = self._scheduler.get_config()
        next_wake = self._scheduler.next_wake_time()
        size = (self._canvas.width, self._canvas.height)
        suspend_days = cfg["days"]
        active_days = [d for d in range(7) if d not in suspend_days]
        try:
            return render_suspend_screen(
                start=cfg["end"],
                end=cfg["start"],
                days=active_days,
                enabled=cfg["enabled"],
                next_wake=next_wake,
                canvas_size=size,
                base_dir=self._base_dir,
            )
        except Exception as exc:
            log.error(f"Suspend screen render error: {exc}")
            img = Image.new("RGB", size, (0, 0, 0))
            return img

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

    def _render_welcome_screen(self) -> Image.Image:
        from talevision.render.welcome_screen import render_welcome_screen
        size = (self._canvas.width, self._canvas.height)
        return render_welcome_screen(
            port=self._config.web.port,
            mode=self._current_mode_name,
            playlist=self._playlist,
            canvas_size=size,
            base_dir=self._base_dir,
        )

    def run(self) -> None:
        """Main loop. Blocks forever. Call from main thread."""
        # ── Welcome screen (15 s boot splash) ─────────────────────────
        try:
            log.info("Rendering welcome screen…")
            welcome = self._render_welcome_screen()
            self._canvas.show(welcome)
            log.info("Welcome screen displayed, waiting 15 s…")
            self._timer.wait(15)
        except Exception as exc:
            log.error(f"Welcome screen error: {exc}", exc_info=True)

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

                if is_suspended:
                    if not self._suspended_displayed:
                        frame = self._render_suspend_screen()
                        self._canvas.show(frame)
                        self._suspended_displayed = True
                        self._save_frame(frame, active_name)
                        self._update_status_cache(active_name, time.time(), None, {})
                    next_wake = self._scheduler.next_wake_time()
                    if next_wake:
                        sleep_secs = max(10, min(
                            (next_wake - datetime.datetime.now()).total_seconds(),
                            86400,
                        ))
                    else:
                        sleep_secs = 60
                    log.debug(f"LOOP ── suspended, sleeping {sleep_secs:.0f}s until wake")
                    self._timer.wait(sleep_secs)
                    continue

                log.debug(f"LOOP ── render() starting ...")
                frame = active.render()
                log.debug("LOOP ── render() done. canvas.show() starting ...")

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

                rotating = len(self._playlist) > 1
                interval = self._rotation_interval if rotating else self._effective_interval(active_name, active.refresh_interval)
                log.debug(f"LOOP ── sleeping {interval}s (rotation={rotating}) ...")
                interrupted = self._timer.wait(interval)
                log.debug(f"LOOP ── awake. interrupted={interrupted}, queue={self._action_queue.qsize()}")

                if not interrupted and rotating:
                    with self._lock:
                        self._playlist_index = (self._playlist_index + 1) % len(self._playlist)
                        next_mode = self._playlist[self._playlist_index]
                        if next_mode != self._current_mode_name:
                            old = self._current_mode_name
                            self._modes[old].on_deactivate()
                            self._current_mode_name = next_mode
                            self._modes[next_mode].on_activate()
                            self._suspended_displayed = False
                            log.info(f"Playlist advance: {old} → {next_mode}")

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
