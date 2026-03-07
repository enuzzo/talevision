"""API Blueprint — /api/* JSON endpoints."""
import logging
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from talevision.config.loader import detect_available_languages

log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


def _orchestrator():
    return current_app.orchestrator  # type: ignore[attr-defined]


def _config():
    return current_app.tv_config  # type: ignore[attr-defined]


def _base_dir() -> Path:
    return current_app.base_dir  # type: ignore[attr-defined]


@api_bp.get("/status")
def status():
    """GET /api/status — current mode, suspension state, last update."""
    try:
        data = _orchestrator().get_status()
        return jsonify(data)
    except Exception as exc:
        log.error(f"Status error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.post("/mode")
def switch_mode():
    """POST /api/mode — {"mode": "litclock"|"slowmovie"}"""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "")
    if not mode:
        return jsonify({"error": "Missing 'mode' field"}), 400
    try:
        _orchestrator().switch_mode(mode)
        return jsonify({"ok": True, "mode": mode})
    except Exception as exc:
        log.error(f"Switch mode error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.post("/refresh")
def force_refresh():
    """POST /api/refresh — force immediate render cycle."""
    try:
        _orchestrator().force_refresh()
        return jsonify({"ok": True})
    except Exception as exc:
        log.error(f"Force refresh error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.post("/language")
def set_language():
    """POST /api/language — {"lang": "it"}"""
    body = request.get_json(silent=True) or {}
    lang = body.get("lang", "")
    if not lang:
        return jsonify({"error": "Missing 'lang' field"}), 400
    try:
        _orchestrator().set_language(lang)
        return jsonify({"ok": True, "lang": lang})
    except Exception as exc:
        log.error(f"Set language error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/languages")
def list_languages():
    """GET /api/languages — list detected language codes."""
    try:
        lang_dir = _base_dir() / _config().litclock.data_dir
        langs = detect_available_languages(lang_dir)
        return jsonify({"languages": langs})
    except Exception as exc:
        log.error(f"List languages error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.post("/suspend")
def update_suspend():
    """POST /api/suspend — {"enabled": bool, "start": "HH:MM", "end": "HH:MM", "days": [0..6]}"""
    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled", True)
    start = body.get("start", "23:00")
    end = body.get("end", "07:00")
    days = body.get("days", list(range(7)))
    try:
        _orchestrator().set_suspend_schedule(start, end, days, enabled)
        return jsonify({"ok": True})
    except Exception as exc:
        log.error(f"Suspend update error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.post("/playlist")
def set_playlist():
    """POST /api/playlist — {"modes": ["litclock", "slowmovie"], "rotation_interval": 300}"""
    body = request.get_json(silent=True) or {}
    modes = body.get("modes", [])
    rotation_interval = body.get("rotation_interval", 300)
    if not modes or not isinstance(modes, list):
        return jsonify({"error": "Missing or invalid 'modes' list"}), 400
    try:
        _orchestrator().set_playlist(modes, int(rotation_interval))
        return jsonify({"ok": True})
    except Exception as exc:
        log.error(f"Set playlist error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/interval")
def get_intervals():
    """GET /api/interval — effective refresh intervals for all modes."""
    try:
        return jsonify(_orchestrator().get_status().get("intervals", {}))
    except Exception as exc:
        log.error(f"Get intervals error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.post("/interval")
def set_interval():
    """POST /api/interval — {"mode": "litclock", "seconds": 120}"""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "")
    seconds = body.get("seconds")
    if not mode or seconds is None:
        return jsonify({"error": "Missing 'mode' or 'seconds'"}), 400
    try:
        _orchestrator().set_mode_interval(mode, int(seconds))
        return jsonify({"ok": True})
    except Exception as exc:
        log.error(f"Set interval error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.delete("/interval/<mode>")
def reset_interval(mode: str):
    """DELETE /api/interval/<mode> — reset to config.yaml default."""
    try:
        _orchestrator().reset_mode_interval(mode)
        return jsonify({"ok": True})
    except Exception as exc:
        log.error(f"Reset interval error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/frame")
def get_frame():
    """GET /api/frame — serve last rendered frame for current mode."""
    return _serve_frame(mode=None)


@api_bp.get("/frame/<mode>")
def get_frame_mode(mode: str):
    """GET /api/frame/<mode> — serve frame for specific mode."""
    return _serve_frame(mode=mode)


def _serve_frame(mode=None):
    try:
        frame_path = _orchestrator().get_frame_path(mode)
        if frame_path is None:
            return jsonify({"error": "No frame available"}), 404
        mimetype = "image/jpeg" if frame_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        return send_file(str(frame_path), mimetype=mimetype)
    except Exception as exc:
        log.error(f"Serve frame error: {exc}")
        return jsonify({"error": str(exc)}), 500
