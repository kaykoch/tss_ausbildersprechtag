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
from markupsafe import Markup

from src.extensions import state
from src.forms import BeraterForm, BuchungShowForm
from src.helpies import (
    _export_to_pdf,
    _flash_form_errors,
    _get_berater_by_token_or_abort,
    _requires_auth,
    _send_anmeldung_mail_to_berater,
)
from src.models import (
    Berater,
    _create_berater,
    _delete_buchung,
    _get_buchung_by_token,
    _update_berater,
)


logger = logging.getLogger(__name__)
bp = Blueprint("tss", __name__)

# ------------------------------------------------------------------------------
# Modulkonstanten
# ------------------------------------------------------------------------------

_TITLE_LEHRKRAFT = "Administration - Lehrkräfte"
_TITLE_ANMELDUNG = "Lehrkräfte"
_TITLE_BUCHUNGEN = "Buchungen"

_TEMPLATE_LEHRKRAFT = "tss/lehrkraft.html"
_TEMPLATE_ANMELDUNG = "tss/lehrkraft_anmeldung.html"
_TEMPLATE_BUCHUNGEN = "tss/lehrkraft_buchungen.html"

_ALLOWED_ROLES_TSS: frozenset[str] = frozenset({"admin", "tss"})


# ------------------------------------------------------------------------------
# Routen
# ------------------------------------------------------------------------------


@bp.route("/", methods=["GET", "POST"])
@_requires_auth(_ALLOWED_ROLES_TSS)
def route_lehrkraft() -> ResponseReturnValue:
    """Zeigt alle administrativen Aufgaben auf einer Webseite."""
    berater_token: str | None = request.values.get("token")

    if berater_token:
        berater = _get_berater_by_token_or_abort(berater_token)
        return render_template(
            _TEMPLATE_LEHRKRAFT,
            title=_TITLE_LEHRKRAFT,
            sprechtag=state.sprechtag,
            berater=berater,
        )

    return redirect(url_for("tss.route_lehrkraftanmeldung"))


@bp.route("/lehrkraft_anmeldung.html", methods=["GET", "POST"])
@_requires_auth(_ALLOWED_ROLES_TSS)
def route_lehrkraftanmeldung() -> ResponseReturnValue:
    """Zeigt die Anmeldeseite für Lehrkräfte und deren Einstellungen."""
    berater_token: str | None = request.values.get("token")
    berater: Berater | None = _get_berater_by_token_or_abort(berater_token) if berater_token else None
    form = BeraterForm(obj=berater)

    if form.validate_on_submit():
        return _handle_anmeldung_submit(form, berater)

    if request.method == "POST":
        _flash_form_errors("route_lehrkraftanmeldung", form)

    return render_template(
        _TEMPLATE_ANMELDUNG,
        title=_TITLE_ANMELDUNG,
        form=form,
        sprechtag=state.sprechtag,
    )


@bp.route("/buchungen.html", methods=["GET", "POST"])
@_requires_auth(_ALLOWED_ROLES_TSS)
def route_buchungenanzeige() -> ResponseReturnValue:
    """Zeigt alle Buchungen einer Lehrkraft an."""
    berater_token: str | None = request.values.get("token")
    berater = _get_berater_by_token_or_abort(berater_token)
    form = BuchungShowForm()

    if form.validate_on_submit():
        match form.buchung_action.data:
            case "download":
                return _handle_buchung_download(berater)
            case "delete":
                return _handle_buchung_delete(form, berater_token)

    return render_template(
        _TEMPLATE_BUCHUNGEN,
        title=_TITLE_BUCHUNGEN,
        form=form,
        sprechtag=state.sprechtag,
        berater=berater,
    )


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Anmeldung
# ------------------------------------------------------------------------------


def _handle_anmeldung_submit(form: BeraterForm, berater: Berater | None) -> ResponseReturnValue:
    """Verarbeitet das abgeschickte Anmeldeformular (Erstanlage oder Update)."""
    try:
        berater_name = f"Berater: {berater.berater_vorname} {berater.berater_nachname}"
        if berater:
            _update_berater(form, berater)
            flash(Markup(f"{berater_name} wurde erfolgreich aktualisiert"), "success")

        else:
            berater = _create_berater(form)
            flash(Markup(f"{berater_name}  wurde erfolgreich eingefügt"), "success")
            mail_info, mail_result = _send_anmeldung_mail_to_berater(berater)
            flash(mail_info, mail_result)

        return redirect(url_for("tss.route_lehrkraftanmeldung", token=berater.token))

    except Exception as e:
        state.db.session.rollback()
        logger.error("Datenbankfehler beim Speichern des Beraters: %s", e)
        flash("Fehler beim Speichern. Bitte versuche es erneut.", "error")
        return render_template(
            _TEMPLATE_ANMELDUNG,
            title=_TITLE_ANMELDUNG,
            form=form,
        )


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Buchungen
# ------------------------------------------------------------------------------


def _handle_buchung_download(berater: Berater) -> ResponseReturnValue:
    """Exportiert alle Buchungen eines Beraters als PDF."""
    file_io = _export_to_pdf(berater)
    return send_file(
        file_io,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{berater.berater_nachname}_{berater.berater_vorname}.pdf",
        conditional=False,
    )


# routes_lehrkraft.py
def _handle_buchung_delete(form: BuchungShowForm, berater_token: str) -> ResponseReturnValue:
    redirect_url = url_for("tss.route_buchungenanzeige", token=berater_token)

    if not form.buchung_token.data:
        flash("Keine Buchungs-ID angegeben.", "error")
        return redirect(redirect_url)

    buchung = _get_buchung_by_token(form.buchung_token.data)
    if not buchung:
        flash("Buchung existiert nicht.", "error")
        return redirect(redirect_url)

    info = f"{buchung.betrieb_name} um {buchung.uhrzeit_id}h"
    try:
        _delete_buchung(buchung)  # ← Service übernimmt DB
        flash(f"Buchung: {info} wurde erfolgreich gelöscht.", "success")
    except Exception as e:
        logger.error("Fehler beim Löschen der Buchung (%s): %s", info, e)
        flash("Fehler beim Löschen. Bitte versuchen Sie es erneut.", "error")

    return redirect(redirect_url)
