# ------------------------------------------------------------------------------
#  APP-FACTORY
# ------------------------------------------------------------------------------

import logging
from pathlib import Path

from flask import Flask

from src.config import BaseConfig
from src.extensions import state
from src.helpies import _init_db, _update_app


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

_LOG_FILE = Path(__file__).resolve().parent / "data" / "logfile.log"

logging.basicConfig(
    filename=_LOG_FILE,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    encoding="utf-8",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# App-Factory
# ------------------------------------------------------------------------------

_SEPARATOR = "-" * 50


def create_app(config_object: type = BaseConfig) -> Flask:
    """Erstellt und konfiguriert die Flask-Applikation (App-Factory-Pattern).

    Ablauf:
        1. Flask-App erstellen und Basiskonfiguration laden.
        2. Datenbank-Extension initialisieren.
        3. Im App-Context: DB anlegen, Konfiguration aus DB laden, Mail binden.
        4. Blueprints registrieren.

    Args:
        config_object: Konfigurationsklasse (Standard: BaseConfig).

    Returns:
        Fertig konfigurierte Flask-App.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Datenbank-Extension an App binden
    state.db.init_app(app)

    with app.app_context():
        _bootstrap(app)

    _register_blueprints(app)

    logger.info("%s", _SEPARATOR)
    logger.info("  --> !! App: Erfassungsbogen wurde erfolgreich gestartet !!")
    logger.info("%s", _SEPARATOR)

    return app


def _bootstrap(app: Flask) -> None:
    """Führt alle Initialisierungsschritte innerhalb des App-Contexts aus.

    Args:
        app: Die laufende Flask-App.
    """
    try:
        logger.info("%s", _SEPARATOR)
        state.set_data(app)
        _init_db(state)
        _update_app()
        state.mail.init_app(app)
    except Exception as e:
        logger.exception("Fehler bei der App-Initialisierung: %s", e)


def _register_blueprints(app: Flask) -> None:
    """Registriert alle Blueprints an der Flask-App.

    Args:
        app: Die laufende Flask-App.
    """
    from src.routes import bp as main_bp
    from src.routes_admin import bp as admin_bp
    from src.routes_lehrkraft import bp as tss_bp

    app.register_blueprint(main_bp, url_prefix="")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(tss_bp, url_prefix="/tss")


# ------------------------------------------------------------------------------
# Einstiegspunkt
# ------------------------------------------------------------------------------

app = create_app(BaseConfig)

if __name__ == "__main__":
    app.run(debug=True)
