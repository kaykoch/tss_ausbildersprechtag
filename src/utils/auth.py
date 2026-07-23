from functools import wraps
import logging

from flask import Response, request
from werkzeug.security import check_password_hash

from src.extensions import state
from src.models import ConfigSetting


logger = logging.getLogger(__name__)


def __check_auth_and_get_type(username: str, password: str) -> str | None:
    """Prüft Zugangsdaten gegen die Datenbank und gibt den Login-Typ zurück.

    Args:
        username: Benutzername aus der HTTP-Basic-Auth-Anfrage.
        password: Klartext-Passwort aus der HTTP-Basic-Auth-Anfrage.

    Returns:
        "admin" | "tss" bei Erfolg, None bei ungültigen Daten.
    """

    config = state.db.session.execute(state.db.select(ConfigSetting)).scalars().first()
    if not config:
        return None

    if username == config.admin_login and check_password_hash(config.admin_password, password):
        return "admin"

    if username == config.tss_login and check_password_hash(config.tss_password, password):
        return "tss"

    return None


def __authenticate() -> Response:
    """Gibt eine 401-Response zurück, die den Browser zur Eingabe von Zugangsdaten auffordert."""
    return Response(
        "Login erforderlich",
        401,
        {"WWW-Authenticate": 'Basic realm="Login erforderlich"'},
    )


def _requires_auth(allowed_login_types: str | list | tuple):
    """Dekorator-Fabrik: Schützt eine Route auf bestimmte Login-Typen.

    Args:
        allowed_login_types: Erlaubter Typ oder Liste von Typen ("admin", "tss").

    Usage:
        @_requires_auth("admin")
        @_requires_auth(["admin", "tss"])
    """
    if not isinstance(allowed_login_types, (list, tuple, frozenset)):
        allowed_login_types = [allowed_login_types]

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth:
                return __authenticate()

            login_type = __check_auth_and_get_type(auth.username, auth.password)
            if login_type in allowed_login_types:
                return f(*args, **kwargs)

            return __authenticate()

        return decorated

    return decorator
