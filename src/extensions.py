# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import tomllib

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

from src.utils.formatters import get_formatted_date


logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Flask-Extensions (noch ohne App – werden in create_app gebunden)
# ------------------------------------------------------------------------------

db: SQLAlchemy = SQLAlchemy()
mail: Mail = Mail()

limiter: Limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10 per minute"],
    storage_uri="memory://",
)

# ------------------------------------------------------------------------------
# Datenstrukturen
# ------------------------------------------------------------------------------


@dataclass
class Sprechtagdata:
    """Unveränderliche Datenstruktur für die Sprechtag-Eckdaten.

    Attributes:
        tag: Formatiertes Datum des Sprechtags (z.B. "10. September 2025").
        beginn: Startzeit (z.B. "16:00").
        ende: Endzeit (z.B. "19:00").
        storno: Wartezeit, bis Buchung storniert wird (z.B.: 30).
    """

    tag: str
    beginn: str
    ende: str
    storno: int


class TomlState:
    """Verkörpert die Texte aus einer TOML-Datei als dynamische Attribute.

    Ermöglicht Zugriff auf TOML-Daten wie: state.infos.schule.name
    """

    def __init__(self, data: dict | None = None) -> None:
        """Initialisiert TomlState mit Daten aus einem Dictionary.

        Args:
            data: Dictionary mit Daten (verschachtelte Dicts werden rekursiv konvertiert).
        """
        if data is None:
            data = {}

        for key, value in data.items():
            if isinstance(value, dict):
                # Verschachtelte Dictionaries ebenfalls umwandeln
                setattr(self, key, TomlState(value))
            else:
                setattr(self, key, value)

    def __repr__(self) -> str:
        return f"<TomlState: {self.__dict__}>"

    def get(self, key: str, default: str | None = None) -> str | None:
        """Sicherer Zugriff auf Attribute mit Fallback.

        Args:
            key: Attribut-Name.
            default: Fallback-Wert wenn Attribut nicht existiert.

        Returns:
            Attribut-Wert oder Default.
        """
        return getattr(self, key, default)


# ------------------------------------------------------------------------------
# App-State
# ------------------------------------------------------------------------------


class AppState:
    """Speichert den globalen Laufzeit-Zustand der Applikation.

    Wird einmalig als Modul-Singleton `state` instanziiert und in
    `create_app` mit der Flask-App verknüpft.

    Attributes:
        db: SQLAlchemy-Instanz.
        mail: Flask-Mail-Instanz.
        limiter: Flask-Limiter-Instanz.
        staticfolder: Pfad zum Static-Ordner.
        sprechtag: Sprechtag-Eckdaten (wird später gesetzt).
        logfile: Pfad zur Log-Datei.
        tomlfile: Pfad zur TOML-Datei.
        infos: Texte aus der TOML-Datei.
    """

    # Datei- und Ordnernamen als Klassenkonstanten
    _ROOT_DIR: Path = Path(__file__).resolve().parent.parent
    _LOG_DIR: Path = _ROOT_DIR / "logs"
    _STATIC_DIR: Path = Path(__file__).resolve().parent / "static"
    _LOG_FILE: str = "sprechtag.log"
    _TOML_FILE: str = "texts.toml"

    # Instanz-Attribute mit Type-Hints
    db: SQLAlchemy
    mail: Mail
    limiter: Limiter
    staticfolder: Path
    sprechtag: Sprechtagdata | None
    logfile: Path
    tomlfile: Path
    infos: TomlState

    def __init__(self) -> None:
        """Initialisiert den AppState."""
        self.db = db
        self.mail = mail
        self.limiter = limiter

        self.staticfolder = self._STATIC_DIR
        self.sprechtag = None
        self.allowed_login_types: frozenset[str] = frozenset()

        self.logfile = self._ensure_file_exists(self._LOG_DIR, self._LOG_FILE)
        self.tomlfile = self._ensure_file_exists(self._ROOT_DIR, self._TOML_FILE)

        # Texte aus texts.toml
        self.infos = TomlState({})

    # ------------------------------------------------------------------
    # Öffentliche Setter
    # ------------------------------------------------------------------

    def set_data(self) -> None:
        """Liest Daten aus der TOML-Datei."""
        self.infos = self.load_texts(self.tomlfile)
        # Login-Typen aus texts.toml lesen
        if hasattr(self.infos, "login"):
            self.allowed_login_types = frozenset(self.infos.login.allowed_types)
        else:
            # Fallback
            self.allowed_login_types = frozenset({"admin", "tss"})
            logger.warning("Login-Typen nicht in texts.toml gefunden, verwende Fallback")

        logger.info("AppState initialisiert mit Login-Typen: %s", self.allowed_login_types)

    def set_sprechtag(self, termin: str, beginn: str, ende: str, storno: int) -> None:
        """Setzt die Sprechtag-Eckdaten.

        Args:
            termin: Datum des Sprechtags (z.B. "2025-09-10").
            beginn: Startzeit (z.B. "16:00").
            ende: Endzeit (z.B. "19:00").
            storno: Wartezeit bis löschen der Buchung (z.B. 20).
        """
        try:
            self.sprechtag = Sprechtagdata(tag=get_formatted_date(termin), beginn=beginn, ende=ende, storno=storno)
            logger.info("Sprechtag-Daten gesetzt: %s", self.sprechtag)
        except Exception as e:
            logger.exception("Fehler beim Setzen der Sprechtag-Daten: %s", e)

    def load_texts(self, tomlfile: Path | str | None) -> TomlState:
        """Lädt die Texte aus der TOML-Datei in den internen Cache.

        Args:
            tomlfile: Pfad zur TOML-Datei.

        Returns:
            TomlState mit geladenen Daten oder leeres TomlState bei Fehler.
        """
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
        except tomllib.TOMLDecodeError as e:
            logger.exception("Fehler beim Parsen von texts.toml: %s", e)
            return TomlState({})
        except Exception as e:
            logger.exception("Unerwarteter Fehler beim Laden von texts.toml: %s", e)
            return TomlState({})

    # ------------------------------------------------------------------
    # Interne Hilfsmethoden
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_file_exists(directory: Path | str | None, filename: str) -> Path:
        """Stellt sicher, dass eine Datei (und ihr Verzeichnis) existiert.

        Args:
            directory: Zielverzeichnis. Wird zu "." normalisiert, wenn None.
            filename: Dateiname innerhalb des Verzeichnisses.

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

state: AppState = AppState()
