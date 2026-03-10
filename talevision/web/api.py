"""API Blueprint — /api/* JSON endpoints."""
import json
import logging
import urllib.parse
import urllib.request
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


@api_bp.get("/weather/location")
def get_weather_location():
    """GET /api/weather/location — current location setting."""
    weather = _orchestrator()._modes.get("weather")
    location = weather._location if weather and hasattr(weather, "_location") else ""
    return jsonify({"location": location})


@api_bp.post("/weather/location")
def set_weather_location():
    """POST /api/weather/location — {"location": "Milano"}"""
    body = request.get_json(silent=True) or {}
    location = body.get("location", "").strip()
    if not location:
        return jsonify({"error": "Missing 'location' field"}), 400
    try:
        _orchestrator().set_weather_location(location)
        return jsonify({"ok": True, "location": location})
    except Exception as exc:
        log.error(f"Set weather location error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/weather/search")
def search_weather_location():
    """GET /api/weather/search?q=Milano — city autocomplete via Nominatim."""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"results": []})
    try:
        encoded = urllib.parse.quote(q)
        url = (
            f"https://nominatim.openstreetmap.org/search"
            f"?q={encoded}&format=json&limit=5&addressdetails=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        for item in data:
            addr = item.get("address", {})
            name = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or item.get("display_name", "").split(",")[0]
            )
            results.append({"name": name, "display": item.get("display_name", "")})
        return jsonify({"results": results})
    except Exception as exc:
        log.error(f"Weather search error: {exc}")
        return jsonify({"results": []})


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
