import logging

from cryptography.fernet import Fernet
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from markupsafe import Markup
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from src.extensions import state
from src.forms import BeraterShowForm, ConfigForm
from src.helpies import (
    _delete_berater,
    _encrypt_password,
    _flash_form_errors,
    _get_berater_by_token_or_abort,
    _load_config,
    _load_defaults,
    _requires_auth,
    _send_anmeldung_mail_to_berater,
)
from src.models import Berater, ConfigSetting, _get_berater_liste


logger = logging.getLogger(__name__)
bp = Blueprint("admin", __name__)

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


@bp.route("/", methods=["GET", "POST"])
@_requires_auth("admin")
def route_admin() -> ResponseReturnValue:
    """Zeigt alle administrativen Aufgaben auf einer Webseite."""
    return render_template(
        _TEMPLATE_ADMIN,
        title=_TITLE_ADMIN,
        sprechtag=state.sprechtag,
    )


@bp.route("/config.html", methods=["GET", "POST"])
@_requires_auth("admin")
def route_config() -> ResponseReturnValue:
    """Zeigt die Webseite zur Eingabe der Konfigurationsdaten an."""
    cfg = _load_config()

    try:
        form = ConfigForm(obj=cfg)

        if form.validate_on_submit():
            _save_config(form, cfg)
        elif request.method == "POST":
            _flash_form_errors("error", form)

        return render_template(
            _TEMPLATE_CONFIG,
            title=_TITLE_CONFIG,
            form=form,
            sprechtag=state.sprechtag,
        )

    except Exception as e:
        logger.error("Fehler in route_config: %s", e)
        abort(500)


@bp.route("/berater.html", methods=["GET", "POST"])
@_requires_auth("admin")
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
        _load_defaults()
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
        # Hole den Master-Key aus den Umgebungsvariablen der app (config.py)
        secret_key = state.app.config["ENCRYPTION_KEY"]

        if secret_key:
            cfg.mail_password = _encrypt_password(form.mail_password.data, secret_key)
        else:
            # Sicherheits-Fallback, falls du den Key vergessen hast einzurichten
            logger.error("E-Mail-Passwort konnte nicht verschlüsselt werden: ENCRYPTION_KEY fehlt!")
            flash("Fehler: Verschlüsselungs-Key nicht konfiguriert.", "error")


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Berater
# ------------------------------------------------------------------------------


def _handle_berater_action(form: BeraterShowForm) -> ResponseReturnValue | None:
    """Verarbeitet die gewählte Aktion auf einen Berater.

    Returns:
        ResponseReturnValue | None: Redirect bei update/show, None bei send/delete.
    """
    berater = _get_berater_by_token_or_abort(form.token.data)

    match form.action.data:
        case "update":
            return redirect(url_for("tss.route_lehrkraftanmeldung", token=berater.token))
        case "show":
            return redirect(url_for("tss.route_buchungenanzeige", token=berater.token))
        case "send":
            info, result = _send_anmeldung_mail_to_berater(berater)
        case "delete":
            info, result = _delete_berater(berater)

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
