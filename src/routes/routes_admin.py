# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
# ------------------------------------------------------------------------------

import logging

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from src.extensions import state
from src.forms import BeraterShowForm, ConfigForm
from src.models import ConfigSetting
from src.services.berater_service import _get_berater_liste, delete_berater, get_berater_by_token_or_abort
from src.services.config_service import load_config, load_defaults
from src.services.crypto_service import get_encrypted_mail_password
from src.services.mail_service import send_anmeldung_mail_to_berater
from src.utils.auth import requires_auth
from src.utils.helpers import flash_form_errors


logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)

# ------------------------------------------------------------------------------
# Modulkonstanten
# ------------------------------------------------------------------------------

_TITLE_ADMIN = "Administration - Ausbilderbetriebe WebUntis"
_TITLE_CONFIG = "Einstellungen - Ausbilderbetriebe WebUntis"
_TITLE_BERATER = "Anzeige der Lehrkräfte"

_TEMPLATE_ADMIN = "admin/admin.html"
_TEMPLATE_CONFIG = "admin/config.html"
_TEMPLATE_BERATER = "admin/berater_anzeige.html"

_HASH_PASSWORD_FIELDS: frozenset[str] = frozenset({"admin_password", "tss_password"})
_SYSTEM_FIELDS: frozenset[str] = frozenset({"csrf_token", "submit"})
_EXCLUDED_FIELDS: frozenset[str] = _HASH_PASSWORD_FIELDS | _SYSTEM_FIELDS

_ALLOWED_BERATER_ACTIONS: frozenset[str] = frozenset({"update", "show", "send", "delete"})
_BERATER_DEFAULT_INFO = "Für weitere Informationen mit der Maus über die Kopfzeile fahren"
_BERATER_DEFAULT_RESULT = "warning"


# ------------------------------------------------------------------------------
# Routen
# ------------------------------------------------------------------------------


@admin_bp.route("/", methods=["GET", "POST"])
@requires_auth("admin")
def route_admin() -> ResponseReturnValue:
    """Zeigt alle administrativen Aufgaben auf einer Webseite."""
    return render_template(
        _TEMPLATE_ADMIN,
        title=_TITLE_ADMIN,
    )


@admin_bp.route("/config.html", methods=["GET", "POST"])
@requires_auth("admin")
def route_config() -> ResponseReturnValue:
    """Zeigt die Webseite zur Eingabe der Konfigurationsdaten an."""
    cfg = load_config()

    try:
        form = ConfigForm(obj=cfg)

        if form.validate_on_submit():
            _save_config(form, cfg)
        elif request.method == "POST":
            flash_form_errors("route_config", form)

        return render_template(
            _TEMPLATE_CONFIG,
            title=_TITLE_CONFIG,
            form=form,
        )

    except Exception as e:
        logger.error("Fehler in route_config: %s", e)
        abort(500)


@admin_bp.route("/berater.html", methods=["GET", "POST"])
@requires_auth("admin")
def route_berateranzeige() -> ResponseReturnValue:
    """Zeigt die Übersicht aller Lehrkräfte an und verarbeitet Aktionen."""
    form = BeraterShowForm()

    if form.validate_on_submit() and form.action.data in _ALLOWED_BERATER_ACTIONS:
        response = _handle_berater_action(form)
        if response is not None:
            return response

    flash(_BERATER_DEFAULT_INFO, _BERATER_DEFAULT_RESULT)
    return _render_berater_liste(form)


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Config
# ------------------------------------------------------------------------------


def _save_config(form: ConfigForm, cfg: ConfigSetting | None) -> ConfigSetting:
    """Speichert die Konfiguration aus dem Formular in die Datenbank."""
    if cfg is None:
        cfg = ConfigSetting()
        state.db.session.add(cfg)

    _apply_non_password_fields(form, cfg)
    _apply_password_fields(form, cfg)

    try:
        # neue Daten speichern
        state.db.session.commit()
        # geänderte Daten wieder neu einlesen
        load_defaults()
        flash("Konfiguration erfolgreich gespeichert.", "success")
    except SQLAlchemyError:
        state.db.session.rollback()
        current_app.logger.exception("DB-Fehler beim Speichern der Config")
        flash("Datenbankfehler beim Speichern der Konfiguration.", "error")

    return cfg


def _apply_non_password_fields(form: ConfigForm, cfg: ConfigSetting) -> None:
    """Schreibt alle Nicht-Passwort- und Nicht-Systemfelder in das Config-Objekt."""
    for fieldname, value in form.data.items():
        if fieldname not in _EXCLUDED_FIELDS:
            setattr(cfg, fieldname, value)


def _apply_password_fields(form: ConfigForm, cfg: ConfigSetting) -> None:
    """Verarbeitet Passwörter: Admin/TSS werden gehasht, Mail wird verschlüsselt."""

    # 1. Admin & TSS Passwörter HASHTEN (One-Way)
    for field in _HASH_PASSWORD_FIELDS:
        if form[field].data:
            hashed_password = generate_password_hash(form[field].data)
            setattr(cfg, field, hashed_password)

    # 2. Mail-Passwort VERSCHLÜSSELN (Two-Way)
    if form.mail_password.data:
        encrypted = get_encrypted_mail_password(form.mail_password.data)
        if encrypted is None:
            logger.error("E-Mail-Passwort konnte nicht verschlüsselt werden.")
            flash("Fehler: Mail-Passwort konnte nicht verschlüsselt werden.", "error")
        else:
            cfg.mail_password = encrypted


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Berater
# ------------------------------------------------------------------------------


def _handle_berater_action(form: BeraterShowForm) -> ResponseReturnValue | None:
    """Verarbeitet die gewählte Aktion auf einen Berater.

    Returns:
        ResponseReturnValue | None: Redirect bei update/show, None bei send/delete.
    """
    berater = get_berater_by_token_or_abort(form.token.data)

    match form.action.data:
        case "update":
            return redirect(url_for("tss.route_lehrkraftanmeldung", token=berater.token))
        case "show":
            return redirect(url_for("tss.route_buchungenanzeige", token=berater.token))
        case "send":
            info, result = send_anmeldung_mail_to_berater(berater)
        case "delete":
            info, result = delete_berater(berater)

    flash(info, result)
    return None


def _render_berater_liste(form: BeraterShowForm) -> ResponseReturnValue:
    """Lädt alle Berater aus der DB und rendert die Übersichtsseite."""
    try:
        berater_liste = _get_berater_liste()
        return render_template(
            _TEMPLATE_BERATER,
            title=_TITLE_BERATER,
            berater_liste=berater_liste,
            form=form,
        )

    except Exception as e:
        logger.error("Fehler in route_berateranzeige: %s", e)
        abort(500)
