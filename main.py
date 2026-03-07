#!/usr/bin/env python3
"""TaleVision — entry point.

Usage:
  python main.py                          # normal run
  python main.py --render-only            # render one frame and exit (sim)
  python main.py --render-only --mode slowmovie
  python main.py --config /path/to.yaml
"""
import argparse
import logging
import socket
import subprocess
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _get_all_ips() -> list[str]:
    """Return all non-loopback IPv4 addresses via hostname -I (most reliable on Pi)."""
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        return [ip for ip in out.split() if ":" not in ip and not ip.startswith("127.")]
    except Exception:
        pass
    # Fallback: socket
    try:
        ips = []
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addr = info[4][0]
            if addr and not addr.startswith("127.") and ":" not in addr and addr not in ips:
                ips.append(addr)
        return ips
    except Exception:
        return []


def _log_network_info(log, port: int) -> None:
    """Log hostname, LAN IPs and Tailscale IP in a readable block."""
    hostname = socket.gethostname()
    all_ips = _get_all_ips()
    lan_ips = [ip for ip in all_ips if not ip.startswith("100.")]
    tailscale_ip = next((ip for ip in all_ips if ip.startswith("100.")), None)

    log.info("─" * 54)
    log.info(f"  hostname   →  http://{hostname}.local:{port}")
    for ip in lan_ips:
        log.info(f"  LAN        →  http://{ip}:{port}")
    if tailscale_ip:
        log.info(f"  Tailscale  →  http://{tailscale_ip}:{port}")
    else:
        log.info("  Tailscale  →  not detected")
    log.info("─" * 54)


def parse_args():
    p = argparse.ArgumentParser(description="TaleVision e-ink display")
    p.add_argument("--config", default=str(BASE_DIR / "config.yaml"), help="Path to config.yaml")
    p.add_argument("--render-only", action="store_true", help="Render one frame to file and exit")
    p.add_argument("--mode", default=None, help="Override startup mode (litclock|slowmovie)")
    return p.parse_args()


def _make_web_runner(flask_app, port: int):
    """Return a callable that starts the best available WSGI server."""
    def run():
        try:
            from waitress import serve
            serve(flask_app, host="0.0.0.0", port=port, threads=4,
                  connection_limit=20, cleanup_interval=10)
        except ImportError:
            # Fallback to Flask dev server (not recommended for production)
            flask_app.run(host="0.0.0.0", port=port, debug=False,
                         use_reloader=False, threaded=True)
    return run


def main():
    args = parse_args()
    config_path = Path(args.config)
    secrets_path = BASE_DIR / "secrets.yaml"

    # ── Config ────────────────────────────────────────────────────────────────
    from talevision.config.loader import load_config, load_secrets
    config = load_config(config_path)
    _secrets = load_secrets(secrets_path)  # noqa: F841 — reserved for future auth

    if args.mode:
        config.app.default_mode = args.mode

    # ── Logging ───────────────────────────────────────────────────────────────
    from talevision.system.logging_setup import configure_logging
    log_cfg = config.logging
    configure_logging(
        level=log_cfg.level,
        file_path=log_cfg.file,
        max_bytes=log_cfg.max_bytes,
        backup_count=log_cfg.backup_count,
    )

    log = logging.getLogger("talevision")
    log.info("TaleVision starting up")
    log.info(f"Config: {config_path}")
    log.info(f"Default mode: {config.app.default_mode}")

    # ── Display canvas ────────────────────────────────────────────────────────
    from talevision.render.canvas import InkyCanvas
    canvas = InkyCanvas(config.display, sim_output_path=BASE_DIR / "talevision_frame.png")

    # ── Display modes ─────────────────────────────────────────────────────────
    from talevision.modes.litclock import LitClockMode
    from talevision.modes.slowmovie import SlowMovieMode

    modes = {
        "litclock": LitClockMode(config, base_dir=BASE_DIR),
        "slowmovie": SlowMovieMode(config, base_dir=BASE_DIR),
    }

    # ── Render-only mode (dev/CI) ─────────────────────────────────────────────
    if args.render_only:
        mode_name = config.app.default_mode
        mode = modes[mode_name]
        log.info(f"Render-only: rendering {mode_name} frame…")
        img = mode.render(is_suspended=False)
        out_path = BASE_DIR / "talevision_frame.png"
        img.save(str(out_path), format="PNG")
        log.info(f"Frame saved to: {out_path}")
        return

    # ── Suspend scheduler ─────────────────────────────────────────────────────
    from talevision.system.suspend import SuspendScheduler
    scheduler = SuspendScheduler(config.suspend)

    # ── Button handler ────────────────────────────────────────────────────────
    from talevision.system.buttons import InkyButtonHandler
    buttons_cfg = config.buttons
    button_handler = None
    if buttons_cfg.enabled:
        def _on_button(action: str):
            orchestrator.handle_button_action(action)

        button_handler = InkyButtonHandler(
            gpio_map=buttons_cfg.gpio_map,
            actions=buttons_cfg.actions,
            action_callback=_on_button,
        )

    # ── Orchestrator ──────────────────────────────────────────────────────────
    from talevision.system.orchestrator import Orchestrator
    orchestrator = Orchestrator(
        config=config,
        modes=modes,
        canvas=canvas,
        scheduler=scheduler,
        button_handler=button_handler,
        base_dir=BASE_DIR,
    )

    # ── Web server (daemon thread) ────────────────────────────────────────────
    from talevision.web.app import create_app
    flask_app = create_app(orchestrator, config, base_dir=BASE_DIR)
    port = config.web.port

    web_thread = threading.Thread(
        target=_make_web_runner(flask_app, port),
        daemon=True,
        name="web",
    )
    web_thread.start()

    _log_network_info(log, port)

    # ── Main loop (blocks forever) ────────────────────────────────────────────
    try:
        orchestrator.run()
    except KeyboardInterrupt:
        log.info("Shutdown requested")
    finally:
        log.info("TaleVision stopped")


if __name__ == "__main__":
    main()
