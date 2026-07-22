# ------------------------------------------------------------------------------
#  EXTENSIONS UND APP-STATE
# ------------------------------------------------------------------------------

from dataclasses import dataclass
import logging
from pathlib import Path

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy


logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Flask-Extensions (noch ohne App – werden in create_app gebunden)
# ------------------------------------------------------------------------------

db = SQLAlchemy()
mail = Mail()

limiter = Limiter(
    get_remote_address,
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


# ------------------------------------------------------------------------------
# App-State
# ------------------------------------------------------------------------------


class AppState:
    """Speichert den globalen Laufzeit-Zustand der Applikation.

    Wird einmalig als Modul-Singleton `state` instanziiert und in
    `create_app` mit der Flask-App verknüpft.
    """

    # Datei- und Ordnernamen als Klassenkonstanten
    _DATA_DIR = Path(__file__).resolve().parent / "data"
    _STATIC_DIR = Path(__file__).resolve().parent / "static"
    _LOG_FILE = "logfile.log"

    def __init__(self) -> None:
        self.db: SQLAlchemy = db
        self.mail: Mail = mail
        self.app: Flask | None = None
        self.limiter: Limiter | None = Limiter(
            get_remote_address,
            default_limits=["10 per minute"],
            storage_uri="memory://",
        )

        self.datafolder: Path = self._DATA_DIR
        self.staticfolder: Path = self._STATIC_DIR
        self.sprechtag: Sprechtagdata | None = None

        self.logfile: Path = self._ensure_file_exists(self._DATA_DIR, self._LOG_FILE)

    # ------------------------------------------------------------------
    # Öffentliche Setter
    # ------------------------------------------------------------------

    def set_data(self, app: Flask) -> None:
        """Verknüpft die Flask-App mit dem State.

        Args:
            app: Die laufende Flask-Applikation.
        """
        self.app = app

    def set_sprechtag(self, tag: str, beginn: str, ende: str) -> None:
        """Setzt die Sprechtag-Eckdaten.

        Args:
            tag:    Datum des Sprechtags.
            beginn: Startzeit (z. B. "16:00").
            ende:   Endzeit   (z. B. "19:00").
        """
        self.sprechtag = Sprechtagdata(tag=tag, beginn=beginn, ende=ende)

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
