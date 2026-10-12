# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ==============================================================================

from __future__ import annotations

import logging
from typing import Literal

from flask import (
    current_app,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect
from werkzeug.security import generate_password_hash

from src.extensions import state
from src.forms import ConfigForm
from src.models import ConfigSetting
from src.services.crypto_service import get_decrypted_mail_password, get_encrypted_mail_password


logger = logging.getLogger(__name__)

# ---------- Felder / Policy ----------
# Felder, die gehasht werden (one-way)
_HASH_PASSWORD_FIELDS: frozenset[str] = frozenset({"admin_password", "tss_password"})

# Felder, die verschlüsselt/entschlüsselt werden (two-way)
_SECRET_FIELDS: frozenset[str] = frozenset({"mail_password"})

# System-/Form-Felder
_SYSTEM_FIELDS: frozenset[str] = frozenset({"csrf_token", "submit"})

# Für Nicht-Passwort-Bulk-Updates ausschließen (setzt cfg-Felder)
_EXCLUDED_FIELDS: frozenset[str] = _HASH_PASSWORD_FIELDS | _SECRET_FIELDS | _SYSTEM_FIELDS

# mail_encryption wird nicht direkt in app.config übernommen,
# sondern separat in MAIL_USE_TLS / MAIL_USE_SSL übersetzt
_EXCLUDED_FOR_APP_CONFIG: frozenset[str] = _SECRET_FIELDS | frozenset({"mail_encryption"})


def _config_to_dict(cfg: ConfigSetting) -> dict:
    """Wandelt ein ConfigSetting-Objekt in ein Dictionary um (ohne 'id')."""
    mapper = inspect(cfg).mapper
    data = {c.key: getattr(cfg, c.key) for c in mapper.columns}
    data.pop("id", None)
    return data


def load_defaults() -> tuple[str, Literal["success", "warning", "danger"], None]:
    """Lädt dynamische Konfigurationswerte aus der DB in die Flask-App-Konfiguration.

    Sensible Felder (Passwörter / Secrets) werden nicht im Bulk übertragen.
    Die Felder werden zu Uppercase konvertiert.
    MAIL_PASSWORD wird separat aus der verschlüsselten DB-Spalte entschlüsselt.

    Returns:
        Tuple (message, category, None).
        - "success": Konfiguration erfolgreich geladen
        - "warning": Keine Konfiguration in der Datenbank vorhanden
        - "danger": Fehler beim Laden der Konfiguration
    """
    # Validierung: Ohne Konfiguration kann nichts geladen werden
    message, category, cfg = load_config()
    if category != "success":
        return (message, category, None)

    data = _config_to_dict(cfg)

    # Sensible Felder vor dem Bulk-Update entfernen
    filtered = {k.upper(): v for k, v in data.items() if k not in _EXCLUDED_FOR_APP_CONFIG}
    current_app.config.update(filtered)

    # MAIL_PASSWORD separat entschlüsseln
    current_app.config["MAIL_PASSWORD"] = None
    if cfg.mail_password:
        try:
            decrypted = get_decrypted_mail_password(cfg.mail_password)
            current_app.config["MAIL_PASSWORD"] = decrypted or None
        except Exception as e:  # Hier den konkreten Exception-Typ eintragen, sobald bekannt
            logger.exception("Fehler beim Entschlüsseln des Mail-Passworts: %s", e)

    # Mail-Verschlüsselung zuordnen
    if cfg.mail_encryption:
        _assign_mail_encryption(cfg.mail_encryption)
    else:
        _assign_mail_encryption()

    # Sprechtag festlegen
    state.set_sprechtag(
        data["sprechtag_termin"], data["sprechtag_beginn"], data["sprechtag_ende"], data["sprechtag_storno"]
    )

    logger.info("Konfiguration erfolgreich geladen.")
    return ("Konfiguration erfolgreich geladen.", "success", None)


def load_config() -> tuple[str, Literal["success", "warning", "danger"], ConfigSetting | None]:
    """Lädt den ersten Konfigurationsdatensatz aus der Datenbank.

    Returns:
        Tuple (message, category, ConfigSetting oder None).
        - "success": Konfiguration erfolgreich geladen
        - "warning": Keine Konfiguration in der Datenbank vorhanden
        - "danger": Fehler beim Laden der Konfiguration
    """
    stmt = state.db.select(ConfigSetting).limit(1)

    try:
        config = state.db.session.execute(stmt).scalar_one_or_none()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("DB-Fehler beim Laden der Konfiguration: %s", e)
        return ("Fehler beim Laden der Konfiguration.", "danger", None)

    except Exception as e:
        state.db.session.rollback()
        logger.exception("Unerwarteter Fehler beim Laden der Konfiguration: %s", e)
        return ("Unerwarteter Fehler beim Laden der Konfiguration.", "danger", None)

    else:
        if config is None:
            logger.warning("Keine Konfiguration in der Datenbank gefunden.")
            return ("Keine Konfiguration vorhanden.", "warning", None)

        logger.info("Konfiguration geladen.")
        return ("", "success", config)


def apply_config_form(
    form: ConfigForm, cfg: ConfigSetting
) -> tuple[str, Literal["success", "danger"], ConfigSetting | None]:
    """Überträgt Formularwerte in das ConfigSetting-Objekt, ohne zu committen.

    Der Commit erfolgt im Aufrufer (Route). Bei Fehlern werden die Änderungen
    an der Session per Rollback verworfen.

    Args:
        form: Flask-Form mit Daten, die übernommen werden sollen.
        cfg: DB-Model, in dem die Werte gesetzt werden.

    Returns:
        Tuple (message, category, ConfigSetting oder None).
        - "success": Werte erfolgreich in das Objekt übernommen
        - "danger": Fehler beim Übernehmen der Werte

    Raises:
        Keine. Fehler werden geloggt und als Tuple zurückgegeben.
    """

    try:
        _apply_non_password_fields(form, cfg)
        _apply_password_fields(form, cfg)

    except RuntimeError as e:
        # Teilweise gesetzte Felder verwerfen, bevor die Route etwas committet
        state.db.session.rollback()
        logger.error("Verschlüsselungsfehler bei der Konfiguration: %s", e)
        return ("Konfiguration konnte nicht gespeichert werden.", "danger", None)

    except Exception as e:
        state.db.session.rollback()
        logger.exception("Unerwarteter Fehler beim Übernehmen der Konfiguration: %s", e)
        return ("Unerwarteter Fehler beim Speichern der Konfiguration.", "danger", None)

    else:
        logger.info("Konfigurationswerte übernommen, Commit folgt in der Route.")
        return ("Konfiguration erfolgreich übernommen.", "success", cfg)


def _apply_non_password_fields(form: ConfigForm, cfg: ConfigSetting) -> None:
    """Schreibt alle Nicht-Passwort-/Nicht-Secret- und Nicht-Systemfelder in das Config-Objekt.

    Args:
        form (ConfigForm): Flask-Form mit Daten die gespeichert werden sollen
        cfg (ConfigSetting): DB-Model, in dem gespeichert wird

    """
    for fieldname, value in form.data.items():
        if fieldname in _EXCLUDED_FIELDS:
            continue
        if not hasattr(cfg, fieldname):
            logger.warning("_apply_non_password_fields: Unbekanntes Feld '%s' ignoriert", fieldname)
            continue
        if isinstance(value, str) and not value.strip():
            value = None
        setattr(cfg, fieldname, value)


def _apply_password_fields(form: ConfigForm, cfg: ConfigSetting) -> None:
    """Verarbeitet Passwörter: Admin/TSS werden gehasht (one-way), Mail wird verschlüsselt (two-way).

    Nur Felder mit Werten werden aktualisiert. Leere Felder werden ignoriert.

    Args:
        form: Flask-Form mit Daten die gespeichert werden sollen.
        cfg: DB-Model, in dem gespeichert wird.

    Raises:
        RuntimeError: Bei Verschlüsselungsfehlern.
    """
    # 1) Admin & TSS Passwörter hashen (nur wenn etwas eingegeben wurde)
    for field in _HASH_PASSWORD_FIELDS:
        password = getattr(form, field).data
        if password and password.strip():  # ← Auch Whitespace prüfen
            hashed_password = generate_password_hash(password.strip())
            setattr(cfg, field, hashed_password)

    # 2) Mail-Passwort verschlüsseln (nur wenn etwas eingegeben wurde)
    mail_password = getattr(form, "mail_password").data
    if mail_password and mail_password.strip():  # ← Auch Whitespace prüfen
        try:
            cfg.mail_password = get_encrypted_mail_password(mail_password)
        except Exception as exc:
            raise RuntimeError(
                "ENCRYPTION_KEY ist kein gültiger Fernet-Key. Neu generieren mit: Fernet.generate_key().decode()"
            ) from exc


def _assign_mail_encryption(enc_choice: str = "none") -> None:
    """Weist den Encryption-Typ des Mailtransportes zu.

    Args:
        enc_choice: Typ (none | tls | ssl). Defaults to "none".
    """

    enc_choice = (enc_choice or "none").lower()
    if enc_choice not in ("none", "tls", "ssl"):
        logger.warning("_assign_mail_encryption: Unbekannter Wert '%s', verwende 'none'", enc_choice)
        enc_choice = "none"
    # Booleans für Flask-Mail übersetzen
    mail_use_tls = enc_choice == "tls"
    mail_use_ssl = enc_choice == "ssl"

    # In der Flask-App-Config oder Datenbank setzen
    current_app.config["MAIL_USE_TLS"] = mail_use_tls
    current_app.config["MAIL_USE_SSL"] = mail_use_ssl
