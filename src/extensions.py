# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
# ------------------------------------------------------------------------------


from dataclasses import dataclass
import logging
from pathlib import Path
import tomllib

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

from src.utils.formatters import formatiere_datum_deutsch


logger = logging.getLogger(__name__)

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
# Flask-Extensions (noch ohne App – werden in create_app gebunden)
# ------------------------------------------------------------------------------

db = SQLAlchemy()
mail = Mail()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10 per minute"],
    storage_uri="memory://",
)

# ------------------------------------------------------------------------------
# Datenstrukturen
# ------------------------------------------------------------------------------


@dataclass
class Sprechtagdata:
    """Unveränderliche Datenstruktur für die Sprechtag-Eckdaten."""

    tag: str
    beginn: str
    ende: str


class TomlState:
    """verkörpert die Texte aus einer Tomldatei"""

    def __init__(self, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                # Verschachtelte Dictionaries ebenfalls umwandeln
                setattr(self, key, TomlState(value))
            else:
                setattr(self, key, value)


# ------------------------------------------------------------------------------
# App-State
# ------------------------------------------------------------------------------


class AppState:
    """Speichert den globalen Laufzeit-Zustand der Applikation.

    Wird einmalig als Modul-Singleton `state` instanziiert und in
    `create_app` mit der Flask-App verknüpft.
    """

    # Datei- und Ordnernamen als Klassenkonstanten
    _ROOT_DIR = Path(__file__).resolve().parent.parent
    _LOG_DIR = _ROOT_DIR / "logs"
    _STATIC_DIR = Path(__file__).resolve().parent / "static"
    _LOG_FILE = "sprechtag.log"
    _TOML_FILE = "texts.toml"

    def __init__(self) -> None:
        self.db: SQLAlchemy = db
        self.mail: Mail = mail
        self.app: Flask | None = None
        self.limiter: Limiter = limiter

        self.staticfolder: Path = self._STATIC_DIR
        self.sprechtag: Sprechtagdata | None = None

        self.logfile: Path = self._ensure_file_exists(self._LOG_DIR, self._LOG_FILE)
        self.tomlfile: Path = self._ensure_file_exists(self._ROOT_DIR, self._TOML_FILE)

        # Texte aus text.toml
        self.infos: TomlState = TomlState({})

    # ------------------------------------------------------------------
    # Öffentliche Setter
    # ------------------------------------------------------------------

    def set_data(self, app: Flask) -> None:
        """Verknüpft die Flask-App mit dem State.

        Args:
            app: Die laufende Flask-Applikation.
        """
        self.app = app

        # Textbausteine laden
        self.infos = self.load_texts(self.tomlfile)

    def set_sprechtag(self) -> None:
        """Setzt die Sprechtag-Eckdaten.

        Args:
            tag:    Datum des Sprechtags.
            beginn: Startzeit (z. B. "16:00").
            ende:   Endzeit   (z. B. "19:00").
        """

        self.sprechtag = Sprechtagdata(
            tag=formatiere_datum_deutsch(self.app.config.get("SPRECHTAG_TERMIN", "?")),
            beginn=self.app.config.get("SPRECHTAG_BEGINN", "?"),
            ende=self.app.config.get("SPRECHTAG_ENDE", "?"),
        )

    def load_texts(self, tomlfile: Path | str | None) -> TomlState:
        """Lädt die Texte aus der TOML-Datei in den internen Cache."""
        if tomlfile is None:
            logger.warning("Keine TOML-Datei angegeben; verwende leere Texte.")
            return TomlState({})
        try:
            with open(tomlfile, "rb") as f:
                data = tomllib.load(f)
            logger.info("Texte geladen aus: %s", tomlfile)
            return TomlState(data)

        except FileNotFoundError:
            logger.error("texts.toml nicht gefunden: %s", tomlfile)
            return TomlState({})
        except tomllib.TOMLDecodeError:
            logger.exception("Fehler beim Parsen von texts.toml")
            return TomlState({})

    # ------------------------------------------------------------------
    # Interne Hilfsmethoden
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_file_exists(directory: Path | str | None, filename: str) -> Path:
        """Stellt sicher, dass eine Datei (und ihr Verzeichnis) existiert.

        Args:
            directory: Zielverzeichnis. Wird zu "." normalisiert, wenn None.
            filename:  Dateiname innerhalb des Verzeichnisses.

        Returns:
            Absoluter Pfad zur Datei, oder Path() bei einem Fehler.
        """
        filepath = Path(directory or ".") / filename

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.touch(exist_ok=True)
            return filepath.resolve()
        except Exception as e:
            logger.exception("Kann Datei nicht anlegen: %s (%s)", filepath, e)
            return Path()


# ------------------------------------------------------------------------------
# Modul-Singleton
# ------------------------------------------------------------------------------

state = AppState()
