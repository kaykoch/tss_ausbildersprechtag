# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import secrets


logger = logging.getLogger(__name__)


def _get_env(name: str, default: str | None = None) -> str | None:
    """Liest eine Umgebungsvariable, gibt Default zurück wenn nicht gesetzt.

    Args:
        name: Name der Umgebungsvariable.
        default: Fallback-Wert wenn nicht gesetzt.

    Returns:
        Wert der Umgebungsvariable oder Default.
    """
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return val


def _get_env_int(name: str, default: int | None = None) -> int | None:
    """Liest eine Umgebungsvariable als Integer.

    Args:
        name: Name der Umgebungsvariable.
        default: Fallback-Wert wenn nicht gesetzt.

    Returns:
        Integer-Wert oder Default.

    Raises:
        RuntimeError: Wenn der Wert keine gültige Integer ist.
    """
    v = _get_env(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError as exc:
        raise RuntimeError(f"Umgebungsvariable {name} muss ein Integer sein, war: {v!r}") from exc


def _require_env(name: str) -> str:
    """Liest eine erforderliche Umgebungsvariable.

    Args:
        name: Name der Umgebungsvariable.

    Returns:
        Wert der Umgebungsvariable.

    Raises:
        RuntimeError: Wenn die Variable nicht gesetzt ist.
    """
    v = _get_env(name)
    if not v:
        raise RuntimeError(
            f"Erforderliche Umgebungsvariable {name} fehlt. Setze sie in der Umgebung oder in deiner .env-Datei."
        )
    return v


class BaseConfig:
    """Basis-Konfiguration für alle Umgebungen."""

    # Datenbank
    SQLALCHEMY_DATABASE_URI: str = _get_env("SQLALCHEMY_DATABASE_URI", "sqlite:///tss_ausbildersprechtag.sqlite")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # SQLAlchemy 2 Engine-Optionen
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "echo": False,  # Auf True setzen für SQL-Debugging
        "pool_pre_ping": True,  # Prüft DB-Verbindung vor Verwendung
        "pool_recycle": 3600,  # Recycelt Connections nach 1h
    }

    # Sicherheit
    SECRET_KEY: str | None = _get_env("SECRET_KEY")
    ENCRYPTION_KEY: str | None = _get_env("ENCRYPTION_KEY")

    # Upload
    MAX_CONTENT_LENGTH: int = _get_env_int("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) or 16 * 1024 * 1024


class ProductionConfig(BaseConfig):
    """Produktions-Config: Abbruch wenn kritische ENV fehlen."""

    DEBUG: bool = False
    TESTING: bool = False

    # Diese Zeilen führen beim Import eine Prüfung durch und werfen Fehler, falls nicht gesetzt.
    SECRET_KEY: str = _require_env("SECRET_KEY")
    ENCRYPTION_KEY: str = _require_env("ENCRYPTION_KEY")

    # SQLAlchemy 2 Engine-Optionen für Produktion
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_size": 10,
        "max_overflow": 20,
    }


class DevConfig(BaseConfig):
    """Entwicklungs-Config: generiert Fallbacks und loggt Warnungen.

    Hinweis: SECRET_KEY wird beim Modulimport generiert, falls nicht in .env gesetzt.
    Das bedeutet: bei jedem Neustart werden Sessions ungültig.
    Für stabile Sessions in der Entwicklung: SECRET_KEY in .env setzen.
    """

    DEBUG: bool = True
    TESTING: bool = False

    # SQLAlchemy 2 Engine-Optionen für Entwicklung
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "echo": True,  # SQL-Statements loggen
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }

    # SECRET_KEY
    if BaseConfig.SECRET_KEY:
        SECRET_KEY: str = BaseConfig.SECRET_KEY
    else:
        SECRET_KEY: str = secrets.token_urlsafe(32)
        logger.warning(
            "DEV: SECRET_KEY nicht gesetzt — temporärer Schlüssel wird erzeugt "
            "(Sessions werden bei Neustart ungültig; nicht für Produktion)."
        )

    # ENCRYPTION_KEY
    if BaseConfig.ENCRYPTION_KEY:
        ENCRYPTION_KEY: str = BaseConfig.ENCRYPTION_KEY
    else:
        try:
            from cryptography.fernet import Fernet

            ENCRYPTION_KEY: str = Fernet.generate_key().decode()
            logger.warning(
                "DEV: ENCRYPTION_KEY nicht gesetzt — temporärer Fernet-Key wird erzeugt (nicht für Produktion)."
            )
        except ImportError:
            logger.error("DEV: cryptography-Modul nicht installiert. Installiere es mit: pip install cryptography")
            raise RuntimeError("cryptography-Modul erforderlich. Installiere: pip install cryptography") from None


class TestConfig(BaseConfig):
    """Test-Config: In-Memory SQLite, keine Logs."""

    DEBUG: bool = True
    TESTING: bool = True

    # In-Memory DB für schnelle Tests
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"

    # Einfache Keys für Tests
    SECRET_KEY: str = "test-secret-key-do-not-use-in-production"
    ENCRYPTION_KEY: str = "test-encryption-key-do-not-use-in-production"

    # WTForms CSRF deaktivieren (optional für Tests)
    WTF_CSRF_ENABLED: bool = False

    # SQLAlchemy 2 Engine-Optionen für Tests
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "echo": False,
        "pool_pre_ping": False,
    }
