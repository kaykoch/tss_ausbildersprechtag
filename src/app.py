# ------------------------------------------------------------------------------
#  APP-FACTORY
# ------------------------------------------------------------------------------

import locale
import logging
from pathlib import Path

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from src.config import BaseConfig
from src.extensions import state
from src.models import Berater
from src.routes import register_routes
from src.services.config_service import load_defaults


logger = logging.getLogger(__name__)

# Beispiel-Berater für den ersten App-Start
_DEFAULT_BERATER = [
    ("Koch", "Kay", "koch@tssbit.de"),
    ("Rass", "Markus", "koch@tssbit.de"),
    ("Tigges", "Ute", "koch@tssbit.de"),
    ("Dinstuhl", "Ralf", "koch@tssbit.de"),
    ("Kues", "Max", "koch@tssbit.de"),
    ("Brungs", "Thomas", "koch@tssbit.de"),
    ("Röder", "David", "koch@tssbit.de"),
    ("Recht", "Christian", "koch@tssbit.de"),
    ("Glatt", "Sebastian", "koch@tssbit.de"),
    ("Weber", "Marius", "koch@tssbit.de"),
    ("Marweld", "Torsten", "koch@tssbit.de"),
]

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

logging.basicConfig(
    filename=state.logfile,
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

    # _register_blueprints(app)
    register_routes(app)

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
        _init_db()
        load_defaults()
        state.limiter.init_app(app)
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


def _init_db() -> None:
    """Initialisiert die SQLite-Datenbank beim App-Start.

    Erstellt alle Tabellen, legt einen Standard-ConfigSetting-Eintrag an
    und befüllt die Berater-Tabelle mit Beispieldaten, falls sie leer ist.

    Args:
        state: Appstate-Objekt mit db, app und weiteren Laufzeit-Variablen.
    """

    try:
        Path(state.app.instance_path).mkdir(parents=True, exist_ok=True)

        # Import hier, damit Modelle registriert sind, bevor create_all() aufgerufen wird
        import src.models  # noqa: F401

        # Locale für Datumsformatierung setzen (Fallback auf C.UTF-8)
        locale.setlocale(locale.LC_TIME, "C.UTF-8")

        state.db.create_all()
        _seed_defaults(src.models)
        state.db.session.commit()

        logger.info("Datenbanktabellen erstellt/überprüft.")

    except SQLAlchemyError as e:
        logger.exception("Fehler beim Erstellen der Datenbanktabellen: %s", e)
        raise
    except Exception as e:
        logger.exception("_init_db -> Fehler bei der Datenbankinitialisierung: %s", e)


def _seed_defaults(models) -> None:
    """Legt Standard-Datenbankeinträge an, falls die Tabellen noch leer sind.

    Args:
        models: Das src.models-Modul (nach dem Import in _init_db).
    """
    if not models.ConfigSetting.query.first():
        state.db.session.add(models.ConfigSetting())

    if not Berater.query.first():
        state.db.session.add_all(
            Berater(berater_nachname=n, berater_vorname=v, berater_mail=m) for n, v, m in _DEFAULT_BERATER
        )


# ------------------------------------------------------------------------------
# Einstiegspunkt
# ------------------------------------------------------------------------------

app = create_app(BaseConfig)

if __name__ == "__main__":
    app.run(debug=True)
