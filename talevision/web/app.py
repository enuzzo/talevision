"""Flask application factory for TaleVision web dashboard."""
import logging
from pathlib import Path

from flask import Flask, send_from_directory

log = logging.getLogger(__name__)


def create_app(orchestrator, config, base_dir: Path = Path(".")) -> Flask:
    """Create and configure the Flask app.

    Args:
        orchestrator: Orchestrator instance for state reads/action dispatch.
        config: AppConfig instance.
        base_dir: Project root directory.
    """
    template_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
    )
    app.config["SECRET_KEY"] = "talevision-dev-key-not-for-production"

    # Attach orchestrator and config for use in blueprints
    app.orchestrator = orchestrator  # type: ignore[attr-defined]
    app.tv_config = config           # type: ignore[attr-defined]
    app.base_dir = base_dir          # type: ignore[attr-defined]

    # Register blueprints
    from .api import api_bp
    from .views import views_bp
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(views_bp)

    return app
