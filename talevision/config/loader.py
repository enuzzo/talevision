"""Config loading utilities for TaleVision."""
import logging
from pathlib import Path
from typing import List, Optional

import yaml
import dacite

from .schema import AppConfig

log = logging.getLogger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(config_path: Path) -> AppConfig:
    """Load and validate config.yaml, returning an AppConfig dataclass."""
    if not config_path.exists():
        log.warning(f"Config file not found: {config_path}. Using defaults.")
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    try:
        cfg = dacite.from_dict(
            data_class=AppConfig,
            data=raw,
            config=dacite.Config(strict=False),
        )
        log.info(f"Config loaded from {config_path}")
        return cfg
    except dacite.DaciteError as exc:
        log.error(f"Config validation error: {exc}. Using defaults.")
        return AppConfig()


def load_secrets(secrets_path: Path) -> dict:
    """Load secrets.yaml if it exists. Returns empty dict if missing."""
    if not secrets_path.exists():
        return {}
    try:
        with secrets_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        log.debug("secrets.yaml loaded")
        return data
    except Exception as exc:
        log.error(f"Failed to load secrets.yaml: {exc}")
        return {}


def detect_available_languages(lang_dir: Path) -> List[str]:
    """Return list of language codes for which quotes-{lang}.csv exists."""
    if not lang_dir.is_dir():
        return []
    langs = []
    for p in sorted(lang_dir.glob("quotes-*.csv")):
        lang_code = p.stem.replace("quotes-", "")
        if lang_code:
            langs.append(lang_code)
    return langs
