# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

import logging

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


def load_defaults() -> None:
    """Lädt dynamische Konfigurationswerte aus der DB in die Flask-App-Konfiguration.

    Sensible Felder (Passwörter / Secrets) werden nicht im Bulk übertragen.
    Die Felder werden zu uppercase Konvertiert.
    MAIL_PASSWORD wird separat aus der verschlüsselten DB-Spalte entschlüsselt.
    """
    try:
        cfg = load_config()
        if cfg is None:
            logger.warning("load_defaults: Keine Konfiguration in der Datenbank gefunden.")
            return

        data = _config_to_dict(cfg)

        # entferne sensitive Felder aus dem Bulk-Update
        filtered = {k.upper(): v for k, v in data.items() if k not in _EXCLUDED_FOR_APP_CONFIG}
        # Bulk-Update (nicht-sensitive Felder)
        state.app.config.update(filtered)

        # MAIL_PASSWORD separat aus der (verschlüsselten) DB-Spalte lesen und entschlüsseln
        if getattr(cfg, "mail_password", None):
            try:
                decrypted = get_decrypted_mail_password(cfg.mail_password)
                state.app.config["MAIL_PASSWORD"] = decrypted or None
            except Exception:
                logger.exception("Fehler beim Entschlüsseln des Mail-Passworts")
                state.app.config["MAIL_PASSWORD"] = None
        else:
            state.app.config["MAIL_PASSWORD"] = None

        # MAIL_ENCRYPTION_TYPE zuordnen
        if getattr(cfg, "mail_encryption", None):
            try:
                _assign_mail_encryption(cfg.mail_encryption)
            except Exception:
                logger.exception("Fehler beim Zuordnen der Verschlüsselung")
        else:
            _assign_mail_encryption()

        # Sprechtag festlegen
        state.set_sprechtag()

    except Exception:
        logger.exception("Konnte App-Konfiguration nicht aus DB laden")


def load_config() -> ConfigSetting | None:
    """Lädt den ersten Konfigurationsdatensatz aus der Datenbank."""
    stmt = state.db.select(ConfigSetting).limit(1)
    return state.db.session.execute(stmt).scalar_one_or_none()


# ---------- Anwenden einer Config aus dem Formular ----------
def apply_config_form(form: ConfigForm, cfg: ConfigSetting) -> None:
    """Überträgt Formularwerte in das ConfigSetting-Objekt.

    Achtung: Diese Funktion wirft Exceptions bei Kryptofehlern, der Aufrufer muss
    die Transaktion (commit/rollback) behandeln.

    Args:
        form (ConfigForm): Flask-Form mit Daten die gespeichert werden sollen
        cfg (ConfigSetting): DB-Model, in dem gespeichert wird
    """
    _apply_non_password_fields(form, cfg)
    _apply_password_fields(form, cfg)


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

    Bei Fehlern in der Verschlüsselung wird eine Exception geworfen, damit der Aufrufer
    ein Rollback durchführen kann und kein Klartext in der DB landet.

    Args:
        form (ConfigForm): Flask-Form mit Daten die gespeichert werden sollen
        cfg (ConfigSetting): DB-Model, in dem gespeichert wird

    """
    # 1) Admin & TSS Passwörter hashen (nur wenn etwas eingegeben wurde)
    for field in _HASH_PASSWORD_FIELDS:
        if getattr(form, field).data:
            hashed_password = generate_password_hash(getattr(form, field).data)
            setattr(cfg, field, hashed_password)

    # 2) Mail-Passwort verschlüsseln (nur wenn etwas eingegeben wurde)
    if getattr(form, "mail_password").data:
        try:
            cfg.mail_password = get_encrypted_mail_password(form.mail_password.data)
        except Exception as exc:
            raise RuntimeError(
                "ENCRYPTION_KEY ist kein gültiger Fernet-Key. Neu generieren mit: Fernet.generate_key().decode()"
            ) from exc


def _assign_mail_encryption(enc_choice: str = "none"):
    """weist den Encryption Typ des Mailtransportes zu

    Args:
        enc_choice (str, optional): Typ (none | tls | ssl). Defaults to "none".
    """
    enc_choice = (enc_choice or "none").lower()
    if enc_choice not in ("none", "tls", "ssl"):
        logger.warning("_assign_mail_encryption: Unbekannter Wert '%s', verwende 'none'", enc_choice)
        enc_choice = "none"
    # Booleans für Flask-Mail übersetzen
    mail_use_tls = enc_choice == "tls"
    mail_use_ssl = enc_choice == "ssl"

    # In der Flask-App-Config oder Datenbank setzen
    state.app.config["MAIL_USE_TLS"] = mail_use_tls
    state.app.config["MAIL_USE_SSL"] = mail_use_ssl
