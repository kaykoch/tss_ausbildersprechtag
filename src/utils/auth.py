# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
# ------------------------------------------------------------------------------


from functools import wraps
import logging

from flask import Response, request
from werkzeug.security import check_password_hash

from src.extensions import state


logger = logging.getLogger(__name__)


def _check_auth_and_get_type(username: str, password: str) -> str | None:
    """Prüft Zugangsdaten gegen die Datenbank bzw. toml und gibt den Login-Typ zurück.

    Hinweis: admin_login/admin_password kommen aus app.config (DB),
             tss_login kommt aus state.infos (TOML)
             Beide Passwörter stammen aus der DB

    Args:
        username: Benutzername aus der HTTP-Basic-Auth-Anfrage.
        password: Klartext-Passwort aus der HTTP-Basic-Auth-Anfrage.

    Returns:
        "admin" | "tss" bei Erfolg, None bei ungültigen Daten.
    """

    admin_login = state.app.config.get("ADMIN_LOGIN")
    admin_password_hash = state.app.config.get("ADMIN_PASSWORD")
    tss_login = state.infos.schule.lehrkraftlogin
    tss_password_hash = state.app.config.get("TSS_PASSWORD")

    if not tss_login:
        logger.warning("_check_auth_and_get_type: tss_login nicht in state.infos gefunden.")
        return None

    if not admin_login or not admin_password_hash or not tss_password_hash:
        logger.warning("_check_auth_and_get_type: Passwort-Hashes nicht in app.config gefunden.")
        return None

    if username == admin_login and check_password_hash(admin_password_hash, password):
        return "admin"

    if username == tss_login and check_password_hash(tss_password_hash, password):
        return "tss"

    return None


def _authenticate() -> Response:
    """Gibt eine 401-Response zurück, die den Browser zur Eingabe von Zugangsdaten auffordert."""
    return Response(
        "Login erforderlich",
        401,
        {"WWW-Authenticate": 'Basic realm="Login erforderlich"'},
    )


def requires_auth(allowed_login_types: str | list | tuple | frozenset):
    """Dekorator-Fabrik: Schützt eine Route auf bestimmte Login-Typen.

    Args:
        allowed_login_types: Erlaubter Typ oder Liste von Typen ("admin", "tss").

    Usage:
        @requires_auth("admin")
        @requires_auth(["admin", "tss"])
    """
    if not isinstance(allowed_login_types, (list, tuple, frozenset)):
        allowed_login_types = (allowed_login_types,)
    allowed_login_types = frozenset(allowed_login_types)

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Normaler Basic-Auth-Flow
            auth = request.authorization
            if not auth:
                return _authenticate()
            # Erfolgreicher Login
            login_type = _check_auth_and_get_type(auth.username, auth.password)

            if login_type in allowed_login_types:
                return f(*args, **kwargs)
            # Fehlgeschlagener Login-Versuch
            xff = request.headers.get("X-Forwarded-For")
            client_ip = xff.split(",")[0].strip() if xff else request.remote_addr
            logger.warning("Fehlgeschlagener Login-Versuch: user=%s, ip=%s", auth.username, client_ip)
            return _authenticate()

        return decorated

    return decorator
