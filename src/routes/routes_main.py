# ------------------------------------------------------------------------------
# Überprüft durch Claude  Hailku
# ==============================================================================

import logging

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue

from src.extensions import state
from src.models import Buchung
from src.services.buchung_service import (
    confirm_buchung,
    create_buchung,
    delete_buchung,
    delete_unconfirmed_buchungen,
    get_buchung_by_token_or_abort,
    get_freie_zeiten_fuer_lehrkraft,
    get_gebuchte_zeiten,
    init_buchung_form,
    slot_is_used,
)
from src.services.lehrkraft_service import get_lehrkraft_by_id_or_none, get_lehrkraft_liste
from src.services.mail_service import send_mail_to_bucher, send_mail_to_lehrkraft
from src.utils.helpers import copy_model_attributes, flash_form_errors


logger = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)


# ------------------------------------------------------------------------------
# Modulkonstanten
# ------------------------------------------------------------------------------

_TITLE_INDEX = "Ausbildersprechtag der TSS"
_TITLE_BESTAETIGUNG = "Bestätigung"

_TEMPLATE_INDEX = "index.html"
_TEMPLATE_BESTAETIGUNG = "bestaetigung.html"
_TEMPLATE_IMPRESSUM = "impressum.html"


# ------------------------------------------------------------------------------
# Routen
# ------------------------------------------------------------------------------


@main_bp.route("/", methods=["GET", "POST"])
@state.limiter.limit("10 per minute")
def index() -> ResponseReturnValue:
    """Startseite – Buchungsformular anzeigen und verarbeiten.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    # 1.) nicht bestätigte, abgelaufene Buchungen löschen
    message, category = delete_unconfirmed_buchungen()
    if category != "success":
        flash(message, category)

    # 2.) erstellt das Auswahlfeld der Lehrkräfte
    lehrkraft_liste = get_lehrkraft_liste()
    selected_lehrkraft_id = request.form.get("lehrkraft_id", type=int)
    form = init_buchung_form(lehrkraft_liste, selected_lehrkraft_id)

    if form.validate_on_submit():
        lehrkraft_id = form.lehrkraft_id.data
        uhrzeit_id = form.uhrzeit_id.data

        lehrkraft = get_lehrkraft_by_id_or_none(lehrkraft_id)
        if not lehrkraft:
            flash("Es gibt keine Lehrkraft mit dieser ID.", "danger")
            return redirect(url_for("main.index"))

        # 3.) Überprüft, ob der slot wirklich frei ist
        message, category, slot_used = slot_is_used(lehrkraft_id, uhrzeit_id)
        if category != "success":
            flash(message, category)
            return redirect(url_for("main.index"))

        if slot_used:
            flash(f"Der Termin um {uhrzeit_id}h bei {lehrkraft.full_name} ist leider schon vergeben.", "danger")
            return redirect(url_for("main.index"))

        # 4.)Buchung erstellen
        message, category, buchung = create_buchung(form, lehrkraft)
        flash(message, category)
        if category != "success":
            return redirect(url_for("main.index"))

        form = init_buchung_form(lehrkraft_liste, None)

        # 5.) Mail an Bucher versenden
        message, category = send_mail_to_bucher(buchung)
        flash(message, category)

    elif form.is_submitted():
        flash_form_errors(form)

    return render_template(
        _TEMPLATE_INDEX,
        title=_TITLE_INDEX,
        lehrkraft_liste=lehrkraft_liste,
        form=form,
    )


@main_bp.route("/bestaetigung", methods=["GET"])
def bestaetigung() -> ResponseReturnValue:
    """Buchung wird durch Aufruf bestätigt oder gelöscht.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    buchung_token = request.args.get("token")
    action = request.args.get("action")

    if not all([buchung_token, action]):
        abort(make_response("bad request! (Fehlende Parameter)", 400))

    # Abbruch, wenn es die Buchung nicht gibt
    buchung = get_buchung_by_token_or_abort(buchung_token, to_abort=True)

    # Verarbeitet die Aktion für die Buchung (löschen oder bestätigen)
    buchung = _handle_buchung(action, buchung)

    return render_template(
        _TEMPLATE_BESTAETIGUNG,
        title=_TITLE_BESTAETIGUNG,
        buchung=buchung,
        storno=state.sprechtag.storno,
    )


@main_bp.route("/api/freie_zeiten/<int:lehrkraft_id>")
@state.limiter.limit("30 per minute")
def freie_zeiten(lehrkraft_id: int) -> ResponseReturnValue:
    """API – Gibt freie Zeiten für einen Lehrkraft zurück.
    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    message, category, freie_zeiten = get_freie_zeiten_fuer_lehrkraft(lehrkraft_id)
    if category != "success":
        flash(message, category)
    return jsonify(freie_zeiten)


@main_bp.route("/api/gebuchte_zeiten/<int:lehrkraft_id>")
@state.limiter.limit("30 per minute")
def gebuchte_zeiten(lehrkraft_id: int) -> ResponseReturnValue:
    """API – Gibt gebuchte Zeiten für einen Lehrkraft zurück.

    Note:
        Fehlerbehandlung erfolgt in den Services (create_buchung, send_mail_to_bucher).
        Die Route prüft nur die Kategorie und rendert entsprechend.
    """
    message, category, gebuchte_zeiten = get_gebuchte_zeiten(lehrkraft_id)
    if category != "success":
        flash(message, category)
    return jsonify(gebuchte_zeiten)


@main_bp.route("/impressum.html", methods=["GET"])
def route_impressum() -> ResponseReturnValue:
    """Impressum anzeigen."""
    return render_template(_TEMPLATE_IMPRESSUM)


# ------------------------------------------------------------------------------
# Hilfsfunktionen
# ==============================================================================


def _handle_buchung(action: str, buchung: Buchung) -> Buchung:
    """Verarbeitet die Aktion für die Buchung (löschen oder bestätigen).

    Args:
        action: "confirm" oder "delete"
        buchung: Buchung-Objekt

    Returns:
        Buchung-Objekt (ggf. modifiziert)
    """
    match action:
        case "confirm":
            message, category = confirm_buchung(buchung)
            flash(message, category)
            if category == "success":
                send_mail_to_lehrkraft(buchung, buchung.lehrkraft)

        case "delete":
            # Temporäre buchung erstellen speichern und Lehrkraft, um die Daten beim Mailversand zu nutzen
            buchung_temp = copy_model_attributes(buchung)
            lehrkraft = buchung.lehrkraft

            # Buchung löschen
            message, category = delete_buchung(buchung)
            flash(message, category)

            # Temporäre Buchnung zurückspeichern zum Mailversand und zur Ausgabe
            buchung = buchung_temp
            if category == "success":
                send_mail_to_lehrkraft(buchung, lehrkraft, is_deleted=True)
        case _:
            logger.warning("Ungültige Aktion: %s", action)
            flash("Ungültige Aktion.", "danger")

    return buchung
