# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
# ------------------------------------------------------------------------------

import logging

from cryptography.fernet import Fernet, InvalidToken

from src.extensions import state


logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet | None:
    """ "Liest den Fernet-Key aus app.config['ENCRYPTION_KEY'] und gibt ein Fernet-Objekt zurück.

    Raises:
        RuntimeError: ungültigem Key

    Returns:
        Fernet | None: Fernet-Objekt. None, wenn kein App-Kontext/Key vorhanden
    """
    app = getattr(state, "app", None)
    if app is None:
        logger.warning("App-Kontext nicht gesetzt: kann Mail-Passwort nicht ver-/entschlüsseln.")
        return None

    secret_key = app.config.get("ENCRYPTION_KEY")
    if not secret_key:
        logger.warning("ENCRYPTION_KEY nicht gesetzt: kann Mail-Passwort nicht ver-/entschlüsseln.")
        return None

    key_bytes = secret_key if isinstance(secret_key, (bytes, bytearray)) else str(secret_key).encode()

    try:
        return Fernet(key_bytes)
    except Exception as exc:
        raise RuntimeError(
            "ENCRYPTION_KEY ist kein gültiger Fernet-Key. Neu generieren mit: Fernet.generate_key().decode()"
        ) from exc


def get_decrypted_mail_password(mail_password: str) -> str:
    """Entschlüsselt das Mail-Passwort für den SMTP-Versand.

    Args:
        mail_password: Verschlüsseltes Passwort aus der Datenbank.

    Returns:
        Entschlüsseltes Passwort als String, oder "" bei fehlendem Key/Passwort.
    """
    if not mail_password:
        return ""

    # Optionaler Migrationspfad: Falls du Klartext erlauben willst:
    # if not mail_password.startswith("gAAAA"):  # typische Fernet-Token beginnen base64-url mit 'gAAAA'
    #     return mail_password

    f = _get_fernet()
    if f is None:
        return ""

    try:
        return f.decrypt(mail_password.encode()).decode()
    except InvalidToken:
        logger.warning("Mail-Passwort konnte nicht entschlüsselt werden (ungültiges Token).")
        return ""
    except Exception:
        logger.exception("Fehler beim Entschlüsseln des Mail-Passworts.")
        return ""


def get_encrypted_mail_password(plain_password: str) -> str | None:
    """Verschlüsselt das Mail-Password für die Speicherung in der DB

    Args:
        plain_password (str): uUnverschlüsseltes Passwort (leerer String wird abgelehnt).

    Returns:
        str | None: Verschlüsseltes Passwort, oder None bei fehlendem Key/Passwort.
    """
    if not plain_password:
        return None

    f = _get_fernet()
    if f is None:
        return None

    try:
        return f.encrypt(plain_password.encode()).decode()
    except Exception as exc:
        raise RuntimeError("Fehler beim Verschlüsseln des Mail-Passworts") from exc
