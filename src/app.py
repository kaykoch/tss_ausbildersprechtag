# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

import locale
import logging
from pathlib import Path

from flask import Flask, current_app
from sqlalchemy.exc import SQLAlchemyError

from src.config import BaseConfig
from src.extensions import state
from src.models import Lehrkraft
from src.routes import register_routes
from src.services.config_service import load_defaults
from src.utils.logging import setup_logging


logger = logging.getLogger(__name__)
_LOG_SEPARATOR = "-" * 50
# ------------------------------------------------------------------------------
# Konstanten
# ------------------------------------------------------------------------------

# Beispiel-Lehrkraft für den ersten App-Start
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

    setup_logging()
    _print_logger_separator("  --> Ausbildersprechtag wird gestartet !!")

    # 1. Flask-App erstellen und Basiskonfiguration laden
    app = Flask(__name__)
    app.config.from_object(config_object)

    # 2. Datenbank-Extension initialisieren
    state.db.init_app(app)

    # Locale für Datumsformatierung setzen (Fallback auf C.UTF-8)
    _setup_locale()

    # 3. Im App-Context: DB anlegen, Konfiguration aus DB laden, Mail binden.
    with app.app_context():
        _bootstrap(app)

    # 4. Blueprints registrieren.
    register_routes(app)

    # 5. Globalen Schulnamen festlegen
    @app.context_processor
    def inject_globals():
        school_name = "TESTSCHULE"
        sprechtag_title = "Sprechtag"

        try:
            if hasattr(state, "infos") and hasattr(state.infos, "schule"):
                school_name = state.infos.schule.name
        except Exception as e:
            logger.warning("Fehler beim Laden des Schulnamens: %s", e)

        try:
            if hasattr(state, "sprechtag") and hasattr(state, "infos"):
                sprechtag_title = (
                    f"{state.infos.app.titel} "
                    f"{state.sprechtag.tag} ({state.sprechtag.beginn}h - {state.sprechtag.ende}h)"
                )
        except Exception as e:
            logger.warning("Fehler beim Laden des Sprechtag-Titels: %s", e)

        return {
            "school_name": school_name,
            "app_title": sprechtag_title,
        }

    _print_logger_separator("App: Ausbildersprechtag wurde erfolgreich gestartet !!")

    return app


def _bootstrap(app: Flask) -> None:
    """Führt alle Initialisierungsschritte innerhalb des App-Contexts aus.

    Reihenfolge ist wichtig:
        1. state.set_data(app) – Setzt die Flask-App im State
        2. _init_db() – Erstellt Datenbanktabellen
        3. load_defaults() – Lädt Konfiguration aus DB
        4. state.mail.init_app(app) – Bindet Mail
        5. state.limiter.init_app(app) – Bindet Rate-Limiter

    Args:
        app: Die laufende Flask-App.
    """
    try:
        # 1. Globale State-Variable initialisieren
        state.set_data()

        # 2. Datenbank sicherstellen (inkl. ConfigSettings)
        _init_db()

        # 3. Konfigwerte aus DB laden (Mail, Admin, Passwort, etc.)
        load_defaults()

        # 4. Mail initialisieren
        state.mail.init_app(app)

        # 5. Limiter an App binden
        state.limiter.init_app(app)

    except Exception as e:
        logger.exception("Fehler bei der App-Initialisierung: %s", e)
        raise


def _init_db() -> None:
    """Initialisiert die SQLite-Datenbank beim App-Start.

    Erstellt alle Tabellen, legt einen Standard-ConfigSetting-Eintrag an
    und befüllt die Lehrkraft-Tabelle mit Beispieldaten, falls sie leer ist.
    """

    try:
        Path(current_app.instance_path).mkdir(parents=True, exist_ok=True)

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


# ✅ Besser: Spezifischere Exception
def _seed_defaults(models) -> None:
    """Legt Standard-Datenbankeinträge an, falls die Tabellen noch leer sind.

    Args:
        models: Das src.models-Modul (nach dem Import in _init_db).

    Raises:
        SQLAlchemyError: Bei Datenbankfehler
    """
    try:
        stmt = state.db.select(models.ConfigSetting)
        if not state.db.session.execute(stmt).scalars().first():
            state.db.session.add(models.ConfigSetting())
            state.db.session.commit()
            _set_test_lehrkraft()
            logger.info("Standard-ConfigSetting angelegt.")

    except SQLAlchemyError as e:
        logger.exception("DB-Fehler beim Seeding: %s", e)
        raise
    except Exception as e:
        logger.exception("Fehler beim Seeding der Standarddaten: %s", e)
        raise


def _setup_locale() -> None:
    """Setzt die Locale für Datumsformatierung (Fallback auf C.UTF-8)."""
    try:
        locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    except locale.Error:
        locale.setlocale(locale.LC_TIME, "C.UTF-8")
        logger.warning("Locale de_DE.UTF-8 nicht verfügbar, Fallback auf C.UTF-8.")


def _print_logger_separator(text: str) -> None:
    """Gibt einen formatierten Log-Separator aus.

    Args:
        text: Der Text zwischen den Separatoren.
    """
    logger.warning(_LOG_SEPARATOR)
    logger.warning("  --> App: %s", text)
    logger.warning(_LOG_SEPARATOR)


def _set_test_lehrkraft():
    # NUR IN TESTPHASE: Test-Lehrkraft anlegen
    try:
        stmt = state.db.select(Lehrkraft)
        if not state.db.session.execute(stmt).scalars().first():
            state.db.session.add_all(
                Lehrkraft(lehrkraft_nachname=n, lehrkraft_vorname=v, lehrkraft_mail=m) for n, v, m in _TEST_BERATER
            )
            state.db.session.commit()
    except Exception as e:
        logger.exception("Fehler beim Seeding der Test-Lehrkraft: %s", e)
        raise
