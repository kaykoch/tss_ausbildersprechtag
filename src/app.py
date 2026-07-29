# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
# -------------------------------------------------------------------------------

import locale
import logging
from pathlib import Path
import types

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from src.config import BaseConfig
from src.extensions import state
from src.models import Berater
from src.routes import register_routes
from src.services.config_service import load_defaults


logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Konstanten
# ------------------------------------------------------------------------------

_SEPARATOR = "-" * 50

# Beispiel-Berater für den ersten App-Start
_TEST_BERATER = [
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


def create_app(config_object: type = BaseConfig) -> Flask:
    """Erstellt und konfiguriert die Flask-Applikation (App-Factory-Pattern).

    Ablauf:
        1. Flask-App erstellen und Basiskonfiguration laden.
        2. Datenbank-Extension initialisieren.
        3. Im App-Context: DB anlegen, Konfiguration aus DB laden, Mail binden.
        4. Blueprints registrieren.
        5. Globalen Schulnamen festlegen

    Args:
        config_object: Konfigurationsklasse (Standard: BaseConfig).

    Returns:
        Fertig konfigurierte Flask-App.
    """

    _setup_logging()
    logger.info("%s", _SEPARATOR)
    logger.info("%s", _SEPARATOR)
    logger.info("  --> !! App: Ausbildersprechtag wird gestartet !!")
    logger.info("%s", _SEPARATOR)

    # 1. Flask-App erstellen und Basiskonfiguration laden
    app = Flask(__name__)
    app.config.from_object(config_object)

    # 2. Datenbank-Extension initialisieren
    state.db.init_app(app)

    # Locale für Datumsformatierung setzen (Fallback auf C.UTF-8)
    try:
        locale.setlocale(locale.LC_TIME, "C.UTF-8")
    except locale.Error:
        logger.warning("Locale C.UTF-8 nicht verfügbar, Fallback auf Standard.")

    # 3. Im App-Context: DB anlegen, Konfiguration aus DB laden, Mail binden.
    with app.app_context():
        _bootstrap(app)

    # 4. Blueprints registrieren.
    register_routes(app)

    # 5. Globalen Schulnamen festlegen
    @app.context_processor
    def inject_globals():
        try:
            school_name = state.infos.schule.name
        except AttributeError:
            school_name = "TESTSCHULE"

        try:
            sprechtag_title = (
                f"{state.infos.sprechtag.sprechtag_titel}"
                f"{state.sprechtag.tag} ({state.sprechtag.beginn}h - {state.sprechtag.ende}h)"
            )
        except AttributeError:
            sprechtag_title = "Sprechtag"

        return {
            "school_name": school_name,
            "sprechtag_title": sprechtag_title,
        }

    logger.info("%s", _SEPARATOR)
    logger.info("  --> !! App: Ausbildersprechtag wurde erfolgreich gestartet !!")
    logger.info("%s", _SEPARATOR)

    return app


def _bootstrap(app: Flask) -> None:
    """Führt alle Initialisierungsschritte innerhalb des App-Contexts aus.

    Args:
        app: Die laufende Flask-App.
    """
    try:
        # globale statevariable initialisieren
        state.set_data(app)
        # Datenbank sicherstellen
        _init_db()
        # Konfigwerte aus DB laden (Mail, Admin, Passwort, etc)
        load_defaults()
        # Mail Funktion an app binden
        state.mail.init_app(app)
        # Limiter an app binden
        state.limiter.init_app(app)

    except Exception as e:
        logger.exception("Fehler bei der App-Initialisierung: %s", e)
        raise


def _init_db() -> None:
    """Initialisiert die SQLite-Datenbank beim App-Start.

    Erstellt alle Tabellen, legt einen Standard-ConfigSetting-Eintrag an
    und befüllt die Berater-Tabelle mit Beispieldaten, falls sie leer ist.

    """

    try:
        Path(state.app.instance_path).mkdir(parents=True, exist_ok=True)

        # Import hier, damit Modelle registriert sind, bevor create_all() aufgerufen wird
        import src.models  # noqa: F401

        # Datenbank erzeugen, wenn es sie nicht gibt
        state.db.create_all()

        # Default Werte der Config vorbesetzen, wenn die DB gerade neu erstellt wurde
        _seed_defaults(src.models)
        state.db.session.commit()

        logger.info("Datenbanktabellen erstellt/überprüft.")

    except SQLAlchemyError as e:
        logger.exception("Fehler beim Erstellen der Datenbanktabellen: %s", e)
        raise
    except Exception as e:
        logger.exception("_init_db -> Fehler bei der Datenbankinitialisierung: %s", e)
        raise


def _seed_defaults(models: types.ModuleType) -> None:
    """Legt Standard-Datenbankeinträge an, falls die Tabellen noch leer sind.

    Args:
        models: Das src.models-Modul (nach dem Import in _init_db).
    """
    if not models.ConfigSetting.query.first():
        state.db.session.add(models.ConfigSetting())

    if not Berater.query.first():
        state.db.session.add_all(
            Berater(berater_nachname=n, berater_vorname=v, berater_mail=m) for n, v, m in _TEST_BERATER
        )


def _setup_logging() -> None:
    logging.basicConfig(
        filename=state.logfile,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
