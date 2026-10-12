# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

from functools import wraps
import logging

from flask import Response, current_app, request
from werkzeug.security import check_password_hash

from src.extensions import state
from src.services.lehrkraft_service import (
    get_lehrkraft_by_token_or_abort,
)
from src.utils.roles import UserRole


logger = logging.getLogger(__name__)


def _check_auth_and_get_type(username: str, password: str) -> UserRole | None:
    """Prüft Zugangsdaten gegen die Datenbank bzw. toml und gibt den Login-Typ zurück.

    Hinweis: admin_login/admin_password kommen aus app.config (DB),
             tss_login kommt aus state.infos (TOML)
             Beide Passwörter stammen aus der DB

    Args:
        username: Benutzername aus der HTTP-Basic-Auth-Anfrage.
        password: Klartext-Passwort aus der HTTP-Basic-Auth-Anfrage.

    Returns:
        UserRole bei Erfolg, None bei ungültigen Daten.
    """

    admin_login = current_app.config.get("ADMIN_LOGIN")
    admin_password_hash = current_app.config.get("ADMIN_PASSWORD")
    tss_login = state.infos.schule.lehrkraftlogin
    tss_password_hash = current_app.config.get("TSS_PASSWORD")

    if not tss_login:
        logger.warning("_check_auth_and_get_type: tss_login nicht in state.infos gefunden.")
        return None

    if not admin_login or not admin_password_hash or not tss_password_hash:
        logger.warning("_check_auth_and_get_type: Passwort-Hashes nicht in app.config gefunden.")
        return None

    if username == admin_login and check_password_hash(admin_password_hash, password):
        return UserRole.ADMIN

    if username == tss_login and check_password_hash(tss_password_hash, password):
        return UserRole.TSS

    return None


def _authenticate() -> Response:
    """Gibt eine 401-Response zurück, die den Browser zur Eingabe von Zugangsdaten auffordert."""
    return Response(
        "Login erforderlich",
        401,
        {"WWW-Authenticate": 'Basic realm="Login erforderlich"'},
    )


def requires_auth(
    allowed_roles: frozenset[UserRole] | UserRole | list[UserRole], allow_token_bypass: bool = False
) -> callable:
    """Dekorator-Fabrik: Schützt eine Route auf bestimmte Benutzerrollen.

    Args:
        allowed_roles: Erlaubte Rolle(n) (UserRole oder frozenset von UserRoles).

    Returns:
        Dekorator-Funktion.

    Usage:
        @requires_auth(UserRole.ADMIN)
        @requires_auth(frozenset({UserRole.ADMIN, UserRole.TSS}))
        @requires_auth(_ALLOWED_ROLES_TSS)
    """
    # Normalisiere die Input-Rollen
    if isinstance(allowed_roles, UserRole):
        allowed_roles = frozenset({allowed_roles})
    elif isinstance(allowed_roles, list):
        allowed_roles = frozenset(allowed_roles)
    elif not isinstance(allowed_roles, frozenset):
        raise ValueError(f"allowed_roles muss UserRole, list oder frozenset sein, nicht {type(allowed_roles)}")

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Token-Bypass: nur wenn explizit erlaubt und Token gültig
            if allow_token_bypass:
                token = request.args.get("token")

                if token:
                    lehrkraft = get_lehrkraft_by_token_or_abort(token)
                    if lehrkraft is not None:
                        logger.info("Token-Bypass akzeptiert für: %s", token[:8] + "...")
                        return f(*args, **kwargs)
            # Normaler Basic-Auth-Flow
            auth = request.authorization
            if not auth:
                return _authenticate()

            # Prüfe Zugangsdaten
            user_role = _check_auth_and_get_type(auth.username, auth.password)

            if user_role in allowed_roles:
                return f(*args, **kwargs)

            # Fehlgeschlagener Login-Versuch
            xff = request.headers.get("X-Forwarded-For")
            client_ip = xff.split(",")[0].strip() if xff else request.remote_addr
            logger.warning("Fehlgeschlagener Login-Versuch: user=%s, ip=%s", auth.username, client_ip)
            return _authenticate()

        return decorated

    return decorator
