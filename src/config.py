# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import secrets


logger = logging.getLogger(__name__)


def _get_env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return val


def _get_env_int(name: str, default: int | None = None) -> int | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError as exc:
        raise RuntimeError(f"Umgebungsvariable {name} muss ein Integer sein, war: {v!r}") from exc


def _require_env(name: str) -> str:
    v = _get_env(name)
    if not v:
        raise RuntimeError(
            f"Erforderliche Umgebungsvariable {name} fehlt. Setze sie in der Umgebung oder in deiner .env-Datei."
        )
    return v


class BaseConfig:
    # Default DB (relativer Pfad). In Prod kannst du SQLALCHEMY_DATABASE_URI setzen.
    SQLALCHEMY_DATABASE_URI: str = _get_env("SQLALCHEMY_DATABASE_URI", "sqlite:///tss_ausbildersprechtag.sqlite")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Secret / Encryption: können in Basisklasse gesetzt oder überschrieben werden
    SECRET_KEY: str | None = _get_env("SECRET_KEY")
    ENCRYPTION_KEY: str | None = _get_env("ENCRYPTION_KEY")

    # Max upload size: Default 16 MiB
    MAX_CONTENT_LENGTH: int | None = _get_env_int("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)


class ProductionConfig(BaseConfig):
    """Produktions-Config: Abbruch (RuntimeError) wenn kritische ENV fehlen."""

    DEBUG = False

    # Diese Zeilen führen beim Import eine Prüfung durch und werfen Fehler, falls nicht gesetzt.
    SECRET_KEY: str = _require_env("SECRET_KEY")
    ENCRYPTION_KEY: str = _require_env("ENCRYPTION_KEY")


class DevConfig(BaseConfig):
    """Entwicklungs-Config: generiert Fallbacks und loggt Warnungen.

    Hinweis: SECRET_KEY wird beim Modulimport generiert, falls nicht in .env gesetzt.
    Das bedeutet: bei jedem Neustart werden Sessions ungültig.
    Für stabile Sessions in der Entwicklung: SECRET_KEY in .env setzen.
    """

    DEBUG = True

    if BaseConfig.SECRET_KEY:
        SECRET_KEY = BaseConfig.SECRET_KEY
    else:
        SECRET_KEY = secrets.token_urlsafe(32)
        logger.warning(
            "DEV: SECRET_KEY nicht gesetzt — temporärer Schlüssel wird erzeugt "
            "(Sessions werden bei Neustart ungültig; nicht für Produktion)."
        )

    if BaseConfig.ENCRYPTION_KEY:
        ENCRYPTION_KEY = BaseConfig.ENCRYPTION_KEY
    else:
        # Gültigen Fernet-Key generieren statt Klartext-Fallback
        try:
            from cryptography.fernet import Fernet

            ENCRYPTION_KEY = Fernet.generate_key().decode()
        except ImportError:
            ENCRYPTION_KEY = None  # Fernet nicht installiert → Fehler erst beim Verwenden
        logger.warning("DEV: ENCRYPTION_KEY nicht gesetzt — temporärer Fernet-Key wird erzeugt (nicht für Produktion).")
