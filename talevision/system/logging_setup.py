"""Logging configuration for TaleVision.

Sets up RichHandler (if available) + optional RotatingFileHandler.
Compatible with systemd journal via PYTHONUNBUFFERED=1.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


def configure_logging(level: str = "INFO", file_path: Optional[str] = None, max_bytes: int = 10485760, backup_count: int = 3) -> None:
    """Configure root logging with Rich terminal handler + optional file handler.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        file_path: Optional path to rotating log file.
        max_bytes: Max log file size before rotation (bytes).
        backup_count: Number of backup log files to keep.
    """
    level_num = logging.getLevelName(level.upper())
    if not isinstance(level_num, int):
        level_num = logging.INFO

    handlers = []

    try:
        from rich.logging import RichHandler
        from rich.console import Console
        console = Console(log_time_format="[%Y-%m-%d %H:%M:%S]")
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=False,
            markup=True,
            log_time_format="[%H:%M:%S]",
        )
        rich_handler.setLevel(level_num)
        handlers.append(rich_handler)
        fmt = "%(message)s"
        datefmt = "[%X]"
    except ImportError:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        stream_handler.setLevel(level_num)
        handlers.append(stream_handler)
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"

    if file_path:
        try:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                str(p),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            file_handler.setLevel(level_num)
            handlers.append(file_handler)
        except Exception as exc:
            print(f"Warning: could not set up file logging at {file_path}: {exc}", file=sys.stderr)

    logging.basicConfig(level=level_num, handlers=handlers)

    # Silence noisy third-party loggers
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("PIL").setLevel(logging.WARNING)
