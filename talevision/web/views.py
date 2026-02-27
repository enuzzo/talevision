"""Views Blueprint — HTML page routes."""
import logging

from flask import Blueprint, render_template, current_app

log = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)


@views_bp.get("/")
def dashboard():
    """Main dashboard page."""
    config = current_app.tv_config  # type: ignore[attr-defined]
    return render_template(
        "dashboard.html",
        default_mode=config.app.default_mode,
        web_port=config.web.port,
    )
