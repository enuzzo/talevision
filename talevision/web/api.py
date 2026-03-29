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


@api_bp.get("/health")
def health():
    """GET /api/health — lightweight liveness probe for systemd / monitoring."""
    try:
        orch = _orchestrator()
        return jsonify({"status": "ok", "mode": orch._current_mode_name})
    except Exception as exc:
        return jsonify({"status": "error", "detail": str(exc)}), 500


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
    """GET /api/weather/location — current city + coordinates."""
    weather = _orchestrator()._modes.get("weather")
    if not weather:
        return jsonify({"city": "", "lat": 0, "lon": 0})
    return jsonify({
        "city": weather._city,
        "lat": weather._lat,
        "lon": weather._lon,
    })


@api_bp.post("/weather/location")
def set_weather_location():
    """POST /api/weather/location — {"city": "Milano", "lat": 45.46, "lon": 9.19}"""
    body = request.get_json(silent=True) or {}
    city = body.get("city", "").strip()
    lat = body.get("lat")
    lon = body.get("lon")
    if not city or lat is None or lon is None:
        return jsonify({"error": "Missing city, lat, or lon"}), 400
    try:
        _orchestrator().set_weather_location(city, float(lat), float(lon))
        return jsonify({"ok": True, "city": city})
    except Exception as exc:
        log.error(f"Set weather location error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/weather/search")
def search_weather_location():
    """GET /api/weather/search?q=Milano — city autocomplete via Open-Meteo."""
    q = request.args.get("q", "").strip()
    lang = request.args.get("lang", "en")
    if not q or len(q) < 2:
        return jsonify({"results": []})
    try:
        encoded = urllib.parse.quote(q)
        url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?count=6&language={lang}&format=json&name={encoded}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "TaleVision/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        for item in data.get("results", []):
            name = item.get("name", "")
            admin1 = item.get("admin1", "")
            country = item.get("country", "")
            display = ", ".join(p for p in [name, admin1, country] if p)
            results.append({
                "name": name,
                "display": display,
                "lat": round(item.get("latitude", 0), 4),
                "lon": round(item.get("longitude", 0), 4),
            })
        return jsonify({"results": results})
    except Exception as exc:
        log.error(f"Weather search error: {exc}")
        return jsonify({"results": []})


@api_bp.get("/weather/units")
def get_weather_units():
    """GET /api/weather/units — current unit system."""
    weather = _orchestrator()._modes.get("weather")
    units = weather._units if weather else "m"
    return jsonify({"units": units})


@api_bp.post("/weather/units")
def set_weather_units():
    """POST /api/weather/units — {"units": "m"|"u"}"""
    body = request.get_json(silent=True) or {}
    units = body.get("units", "")
    if units not in ("m", "u", "M"):
        return jsonify({"error": "Invalid units (m, u, or M)"}), 400
    try:
        weather = _orchestrator()._modes.get("weather")
        if weather and hasattr(weather, "set_units"):
            weather.set_units(units)
        _orchestrator()._save_prefs()
        _orchestrator()._action_queue.put(("force_refresh", None))
        _orchestrator()._timer.interrupt()
        return jsonify({"ok": True, "units": units})
    except Exception as exc:
        log.error(f"Set weather units error: {exc}")
        return jsonify({"error": str(exc)}), 500


@api_bp.get("/koan/archive")
def koan_archive():
    """GET /api/koan/archive — list all generated haiku/koan. ?type=haiku|koan|all"""
    koan = _orchestrator()._modes.get("koan")
    if not koan:
        return jsonify({"haiku": [], "count": 0})
    archive = koan._archive
    files = archive._list_files()
    type_filter = request.args.get("type", "all")
    items = []
    for fp in reversed(files):  # newest first
        entry = archive._load_file(fp)
        if entry:
            if type_filter != "all" and entry.get("type", "haiku") != type_filter:
                continue
            items.append(entry)
    return jsonify({"haiku": items, "count": len(items)})


@api_bp.get("/koan/archive/export")
def koan_archive_export():
    """GET /api/koan/archive/export — download all haiku as a ZIP."""
    import io
    import zipfile

    koan = _orchestrator()._modes.get("koan")
    if not koan:
        return jsonify({"error": "Koan mode not available"}), 404
    files = koan._archive._list_files()
    if not files:
        return jsonify({"error": "No haiku in archive"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in files:
            zf.write(str(fp), fp.name)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True, download_name="koan_archive.zip")


@api_bp.get("/flora/archive")
def flora_archive():
    """GET /api/flora/archive — list all archived botanical specimens (newest first)."""
    flora = _orchestrator()._modes.get("flora")
    if not flora:
        return jsonify({"specimens": [], "count": 0})
    archive_dir = flora._archive_dir
    entries = []
    for json_path in sorted(archive_dir.glob("*.json"), reverse=True):
        try:
            entry = json.loads(json_path.read_text(encoding="utf-8"))
            entry["has_image"] = (archive_dir / f"{json_path.stem}.png").exists()
            entries.append(entry)
        except Exception:
            pass
    return jsonify({"specimens": entries, "count": len(entries)})


@api_bp.get("/flora/archive/<date_str>")
def flora_archive_image(date_str: str):
    """GET /api/flora/archive/<YYYY-MM-DD> — serve the PNG for that day."""
    import re
    flora = _orchestrator()._modes.get("flora")
    if not flora:
        return jsonify({"error": "Flora mode not available"}), 404
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return jsonify({"error": "Invalid date format (YYYY-MM-DD expected)"}), 400
    png_path = flora._archive_dir / f"{date_str}.png"
    if not png_path.exists():
        return jsonify({"error": "No specimen for this date"}), 404
    return send_file(str(png_path), mimetype="image/png")


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
