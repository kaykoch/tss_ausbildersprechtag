# ------------------------------------------------------------------------------
# Überprüft durch Claude  Hailku
# ==============================================================================

import logging

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask.typing import ResponseReturnValue

from src.forms import BuchungDeleteForm, BuchungShowForm, LehrkraftForm
from src.models import Lehrkraft
from src.services.buchung_service import delete_buchung, get_buchung_by_token_or_abort
from src.services.lehrkraft_service import (
    create_lehrkraft,
    get_lehrkraft_by_token_or_abort,
    update_lehrkraft,
)
from src.services.mail_service import send_anmeldung_mail_to_lehrkraft
from src.services.pdf_service import export_to_pdf
from src.utils.auth import requires_auth
from src.utils.helpers import flash_form_errors
from src.utils.roles import _ALLOWED_ROLES_TSS


logger = logging.getLogger(__name__)
lehrkraft_bp = Blueprint("lehrkraft", __name__)

# ------------------------------------------------------------------------------
# Modulkonstanten
# ------------------------------------------------------------------------------

_TITLE_LEHRKRAFT = "Administration - Lehrkräfte"
_TITLE_LEHRKRAFT_MANIPULATE = "Lehrkräfte"
_TITLE_BUCHUNGEN = "Buchungen"
_TITLE_BUCHUNGEN_DELETE = "Buchung löschen"

_TEMPLATE_LEHRKRAFT = "lehrkraft/lehrkraft_dashboard.html"
_TEMPLATE_LEHRKRAFT_MANIPULATE = "lehrkraft/lehrkraft_bearbeiten.html"

_TEMPLATE_BUCHUNGEN_SHOW = "lehrkraft/buchungen_anzeigen.html"
_TEMPLATE_BUCHUNGEN_DELETE = "lehrkraft/buchung_loeschen.html"


# ------------------------------------------------------------------------------
# Routen
# ==============================================================================


# ----- Lehrkraft --------------------------------------------------------------
@lehrkraft_bp.route("/", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_TSS, allow_token_bypass=True)
def route_lehrkraft() -> ResponseReturnValue:
    """Zeigt alle administrativen Aufgaben auf einer Webseite.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    lehrkraft_token: str | None = request.values.get("token")
    lehrkraft = get_lehrkraft_by_token_or_abort(lehrkraft_token)

    if lehrkraft is None:
        return redirect(url_for("lehrkraft.route_lehrkraft_neu"))

    return render_template(
        _TEMPLATE_LEHRKRAFT,
        title=_TITLE_LEHRKRAFT,
        lehrkraft=lehrkraft,
        is_create=False,
    )


@lehrkraft_bp.route("/lehrkraft_bearbeiten.html", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_TSS, allow_token_bypass=True)
def route_lehrkraft_bearbeiten() -> ResponseReturnValue:
    """Zeigt die Anmeldeseite für Lehrkräfte und deren Einstellungen.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    lehrkraft_token: str | None = request.values.get("token")
    lehrkraft: Lehrkraft | None = get_lehrkraft_by_token_or_abort(lehrkraft_token) if lehrkraft_token else None
    form = LehrkraftForm(obj=lehrkraft)

    if form.validate_on_submit():
        ## Lehrkraft aktualisieren
        message, category = update_lehrkraft(form, lehrkraft)
        flash(message, category)
        # Weiterleiten zum Dashboard
        return redirect(url_for("lehrkraft.route_lehrkraft", token=lehrkraft.lehrkraft_token))

    elif form.is_submitted():
        flash_form_errors("", form)

    return render_template(
        _TEMPLATE_LEHRKRAFT_MANIPULATE,
        title=_TITLE_LEHRKRAFT_MANIPULATE,
        form=form,
        lehrkraft=lehrkraft,
    )


@lehrkraft_bp.route("/lehrkraft_neu", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_TSS)
def route_lehrkraft_neu() -> ResponseReturnValue:
    """Erstellt eine Lehrkraft und schickt eine Mail an sie
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    form = LehrkraftForm()

    if form.validate_on_submit():
        # Lehrkraft erstellen

        message, category, lehrkraft = create_lehrkraft(form)
        flash(message, category)
        if category != "success":
            return redirect(url_for("lehrkraft.route_lehrkraft"))

        # Mail an Lehrkraft senden
        message, category = send_anmeldung_mail_to_lehrkraft(lehrkraft)
        flash(message, category)

        # Weiterleiten zum Dashboard
        return redirect(url_for("lehrkraft.route_lehrkraft", token=lehrkraft.lehrkraft_token))

    elif form.is_submitted():
        flash_form_errors(form)

    return render_template(
        _TEMPLATE_LEHRKRAFT_MANIPULATE,
        title=_TITLE_LEHRKRAFT,
        form=form,
        is_create=True,
    )


# ----- Buchung-- --------------------------------------------------------------
@lehrkraft_bp.route("/buchungen.html", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_TSS, allow_token_bypass=True)
def route_buchungen_anzeigen() -> ResponseReturnValue:
    """Zeigt alle Buchungen einer Lehrkraft an.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    lehrkraft_token: str | None = request.values.get("token")
    lehrkraft = get_lehrkraft_by_token_or_abort(lehrkraft_token, to_abort=True)

    form = BuchungShowForm()
    if form.validate_on_submit():
        if form.buchung_action.data == "download":
            message, category, pdf_io = export_to_pdf(lehrkraft)
            flash(message, category)
            if category != "danger":
                return send_file(
                    pdf_io,
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name=f"{lehrkraft.lehrkraft_nachname}_{lehrkraft.lehrkraft_vorname}.pdf",
                    conditional=False,
                )

    elif form.is_submitted():
        flash_form_errors("route_buchung_neu", form)

    return render_template(
        _TEMPLATE_BUCHUNGEN_SHOW,
        title=_TITLE_BUCHUNGEN,
        form=form,
        lehrkraft=lehrkraft,
    )


@lehrkraft_bp.route("/buchung/loeschen/<string:buchung_token>", methods=["GET", "POST"])
@requires_auth(_ALLOWED_ROLES_TSS, allow_token_bypass=True)
def route_buchung_loeschen(buchung_token: str) -> ResponseReturnValue:
    """Zeigt die Löschbestätigung und löscht ein Thema nach POST.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    buchung = get_buchung_by_token_or_abort(buchung_token, to_abort=True)

    form = BuchungDeleteForm()
    # Token in die Form eintragen
    if not form.is_submitted():
        form.buchung_token.data = buchung_token

    if form.validate_on_submit():
        lehrkraft_token = buchung.lehrkraft.lehrkraft_token
        messsage, category = delete_buchung(form.buchung_token.data)
        flash(messsage, category)
        return redirect(url_for("lehrkraft.route_buchungen_anzeigen", token=lehrkraft_token))

    elif form.is_submitted():
        flash_form_errors("route_buchung_loeschen", form)

    return render_template(
        _TEMPLATE_BUCHUNGEN_DELETE,
        title=_TITLE_BUCHUNGEN_DELETE,
        form=form,
        buchung=buchung,
    )
