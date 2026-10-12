# ------------------------------------------------------------------------------
# Überprüft durch Claude  Hailku
# ==============================================================================

import logging

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    url_for,
)
from flask.typing import ResponseReturnValue

from src.forms import ConfigForm, LehrkraftDeleteForm, LehrkraftShowForm
from src.services.config_service import apply_config_form, load_config, load_defaults
from src.services.lehrkraft_service import delete_lehrkraft, get_lehrkraft_by_token_or_abort, get_lehrkraft_liste
from src.services.mail_service import send_anmeldung_mail_to_lehrkraft
from src.utils.auth import requires_auth
from src.utils.helpers import commit_config, flash_form_errors
from src.utils.logging import apply_logging_level_change
from src.utils.roles import _ALLOWED_ROLES_ADMIN


logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)

# ------------------------------------------------------------------------------
# Modulkonstanten
# ------------------------------------------------------------------------------

_TITLE_ADMIN = "Administration - Ausbilderbetriebe WebUntis"
_TITLE_CONFIG = "Einstellungen - Ausbilderbetriebe WebUntis"
_TITLE_LEHRKRAFT = "Anzeige der Lehrkräfte"

_TEMPLATE_ADMIN = "admin/admin_dashboard.html"
_TEMPLATE_CONFIG = "admin/config.html"
_TEMPLATE_BERATER = "admin/lehrkraft_anzeigen.html"
_TEMPLATE_LEHRKRAFT_DELETE = "admin/lehrkraft_loeschen.html"


_HASH_PASSWORD_FIELDS: frozenset[str] = frozenset({"admin_password", "tss_password"})
_SYSTEM_FIELDS: frozenset[str] = frozenset({"csrf_token", "submit"})
_EXCLUDED_FIELDS: frozenset[str] = _HASH_PASSWORD_FIELDS | _SYSTEM_FIELDS

_ALLOWED_BERATER_ACTIONS: frozenset[str] = frozenset({"update", "show", "send", "delete"})
_BERATER_DEFAULT_INFO = "Für weitere Informationen mit der Maus über die Kopfzeile fahren"
_BERATER_DEFAULT_RESULT = "warning"


# ------------------------------------------------------------------------------
# Routen
# ==============================================================================


@admin_bp.route("/", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_ADMIN)
def route_admin() -> ResponseReturnValue:
    """Zeigt alle administrativen Aufgaben auf einer Webseite.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    return render_template(
        _TEMPLATE_ADMIN,
        title=_TITLE_ADMIN,
    )


@admin_bp.route("/config", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_ADMIN)
def route_config() -> ResponseReturnValue:
    """Zeigt die Konfigurationsseite an und speichert Änderungen."""
    # Ohne Konfiguration ist die App nicht lauffähig, daher Abbruch
    message, category, cfg = load_config()
    if category != "success":
        abort(make_response(f"{message}", 400))

    form = ConfigForm(obj=cfg)

    if form.validate_on_submit():
        # 1. Formularwerte in das Objekt übernehmen (Rollback erfolgt im Service bei Fehlern)
        message, category, _ = apply_config_form(form, cfg)

        if category == "success":
            # 2. Speichern (Rollback erfolgt im Helper bei Fehlern)
            message, category, _ = commit_config()

            # 3. Logging-Level sofort anwenden
            if category == "success":
                apply_logging_level_change(form)

            # 4. App-Config neu laden. Fehler melden, ohne die Erfolgsmeldung zu überschreiben.
            defaults_message, defaults_category, _ = load_defaults()
            if defaults_category != "success":
                flash(defaults_message, defaults_category)

        flash(message, category)

    return render_template(
        _TEMPLATE_CONFIG,
        title=_TITLE_CONFIG,
        form=form,
    )


# ----- Lehrkraft --------------------------------------------------------------
@admin_bp.route("/lehrkraft", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_ADMIN)
def route_lehrkraft_anzeigen() -> ResponseReturnValue:
    """Zeigt die Übersicht aller Lehrkräfte an und verarbeitet Aktionen.

    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """

    form = LehrkraftShowForm()

    if form.validate_on_submit() and form.action.data in _ALLOWED_BERATER_ACTIONS:
        response = _handle_lehrkraft_action(form)
        if response is not None:
            return response
    elif form.is_submitted():
        flash_form_errors(form)

    flash(_BERATER_DEFAULT_INFO, _BERATER_DEFAULT_RESULT)
    return _render_lehrkraft_liste(form)


@admin_bp.route("/lehrkraft/loeschen/<string:token>", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_ADMIN)
def route_lehrkraft_loeschen(token: str) -> ResponseReturnValue:
    """Zeigt die Löschbestätigung und löscht ein Thema nach POST.

    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    lehrkraft = get_lehrkraft_by_token_or_abort(token, to_abort=True)

    form = LehrkraftDeleteForm()
    # Token in die Form eintragen
    if not form.is_submitted():
        form.lehrkraft_token.data = token

    if form.validate_on_submit():
        token = lehrkraft.lehrkraft_token
        message, category = delete_lehrkraft(form.lehrkraft_token.data)
        flash(message, category)
        return redirect(url_for("admin.route_lehrkraft_anzeigen"))

    elif form.is_submitted():
        flash_form_errors(form)

    return render_template(
        _TEMPLATE_LEHRKRAFT_DELETE,
        title=_TITLE_LEHRKRAFT,
        form=form,
        lehrkraft=lehrkraft,
    )


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Lehrkraft
# ==============================================================================


def _handle_lehrkraft_action(form: LehrkraftShowForm) -> ResponseReturnValue | None:
    """Verarbeitet die gewählte Aktion auf einen Lehrkraft.

    Returns:
        ResponseReturnValue | None: Redirect bei update/show, None bei send/delete.
    """
    lehrkraft = get_lehrkraft_by_token_or_abort(form.token.data)

    print(lehrkraft)

    match form.action.data:
        case "update":
            return redirect(url_for("lehrkraft.route_lehrkraft_bearbeiten", token=lehrkraft.lehrkraft_token))
        case "show":
            return redirect(url_for("lehrkraft.route_buchungen_anzeigen", token=lehrkraft.lehrkraft_token))
        case "delete":
            return redirect(url_for("admin.route_lehrkraft_loeschen", token=lehrkraft.lehrkraft_token))
        case "send":
            message, category = send_anmeldung_mail_to_lehrkraft(lehrkraft)
        case _:
            message = category = None

    flash(message, category)
    return None


def _render_lehrkraft_liste(form: LehrkraftShowForm) -> ResponseReturnValue:
    """Lädt alle Lehrkraft aus der DB und rendert die Übersichtsseite."""
    lehrkraft_liste = get_lehrkraft_liste()

    return render_template(
        _TEMPLATE_BERATER,
        title=_TITLE_LEHRKRAFT,
        lehrkraft_liste=lehrkraft_liste,
        form=form,
    )
