"""Views Blueprint — HTML page routes."""
import logging
from pathlib import Path

from flask import Blueprint, render_template, current_app, send_file

log = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)


@views_bp.get("/")
def dashboard():
    """Main dashboard page. Serves the built React app if available."""
    base_dir: Path = current_app.base_dir  # type: ignore[attr-defined]
    built = base_dir / "talevision" / "web" / "static" / "dist" / "index.html"
    if built.exists():
        return send_file(str(built))
    # Fallback to legacy Jinja template
    config = current_app.tv_config  # type: ignore[attr-defined]
    return render_template(
        "dashboard.html",
        default_mode=config.app.default_mode,
        web_port=config.web.port,
    )
