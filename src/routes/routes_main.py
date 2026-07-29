# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
# ------------------------------------------------------------------------------

import logging

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from markupsafe import Markup
from sqlalchemy.orm import joinedload

from src.extensions import state
from src.forms import BuchungForm
from src.models import Berater, Buchung
from src.services.berater_service import _get_berater_liste, get_berater_by_id
from src.services.buchung_service import (
    _delete_old_orders,
    _get_freie_zeiten_fuer_berater,
    _get_gebuchte_zeiten,
    delete_buchung,
)
from src.services.mail_service import send_mail_to_berater, send_mail_to_bucher
from src.utils.helpers import _copy_model_attributes, flash_form_errors


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

_MSG_CONFIRM_INFO = (
    " <p>⚠️ Der Termin wurde bestätigt</p>"
    " <p><b>Wichtig: </b> Wenn Sie Ihren Termin nicht wahrnehmen können, nutzen Sie den"
    " Stornierungslink in Ihrer Bestätigungs-E-Mail"
    " — so geben Sie den Platz für andere Betriebe frei.</p>"
)


# ------------------------------------------------------------------------------
# Routen
# ------------------------------------------------------------------------------


@main_bp.route("/", methods=["GET", "POST"])
@state.limiter.limit("5 per minute")
def index() -> ResponseReturnValue:
    """Startseite – Buchungsformular anzeigen und verarbeiten."""
    _delete_old_orders()
    berater_liste = _get_berater_liste()
    form = _init_buchung_form(berater_liste)

    if request.method == "POST":
        return _handle_buchung_post(form, berater_liste)

    form.uhrzeit_id.disabled = True
    return _render_index(form, berater_liste)


@main_bp.route("/bestaetigung", methods=["GET"])
def bestaetigung() -> ResponseReturnValue:
    """Buchung wird durch Aufruf bestätigt oder gelöscht."""
    token = request.args.get("token")
    action = request.args.get("action")

    if not token:
        flash("Kein Token angegeben.", "error")
        return _render_bestaetigung(buchung=None)

    if not action:
        flash("Keine Aktion angegeben.", "error")
        return _render_bestaetigung(buchung=None)

    try:
        buchung = _load_buchung_by_token(token)
        if buchung is None:
            flash("Diese Buchung existiert nicht oder ist abgelaufen.", "error")
            return _render_bestaetigung(buchung=None)
        buchung = _handle_bestaetigung_action(action, token, buchung)

    except Exception as e:
        state.db.session.rollback()
        logger.error("Fehler in bestaetigung (action: %s, token: %s): %s", action, token, e)
        flash("Ein Fehler ist aufgetreten. Bitte versuche es erneut.", "error")
        buchung = None

    return _render_bestaetigung(buchung=buchung, title=_TITLE_BESTAETIGUNG)


@main_bp.route("/api/freie_zeiten/<int:berater_id>")
@state.limiter.limit("30 per minute")
def freie_zeiten(berater_id: int) -> ResponseReturnValue:
    """API – Gibt freie Zeiten für einen Berater zurück."""
    return jsonify(_get_freie_zeiten_fuer_berater(berater_id))


@main_bp.route("/api/gebuchte_zeiten/<int:berater_id>")
@state.limiter.limit("30 per minute")
def gebuchte_zeiten(berater_id: int) -> ResponseReturnValue:
    """API – Gibt gebuchte Zeiten für einen Berater zurück."""
    return jsonify(_get_gebuchte_zeiten(berater_id))


@main_bp.route("/impressum.html", methods=["GET"])
def route_impressum() -> ResponseReturnValue:
    """Impressum anzeigen."""
    return render_template(_TEMPLATE_IMPRESSUM)


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Index / Buchung
# ------------------------------------------------------------------------------


def _init_buchung_form(berater_liste: list[Berater]) -> BuchungForm:
    """Initialisiert das Buchungsformular mit Berater-Choices."""
    form = BuchungForm()
    form.berater_id.choices = [("", "Bitte wählen...")] + [
        (b.berater_id, f"{b.berater_nachname}, {b.berater_vorname}") for b in berater_liste
    ]
    form.uhrzeit_id.choices = [("", "Bitte wählen Sie zuerst eine Lehrkraft aus")]
    return form


def _handle_buchung_post(form: BuchungForm, berater_liste: list[Berater]) -> ResponseReturnValue:
    """Verarbeitet den POST-Request des Buchungsformulars."""
    selected_berater_id = request.form.get("berater_id")

    if selected_berater_id:
        valid_zeiten = _get_freie_zeiten_fuer_berater(selected_berater_id)
        form.uhrzeit_id.choices = [("", "Bitte Uhrzeit wählen...")] + [(zeit, f"{zeit} Uhr") for zeit in valid_zeiten]

    if form.validate_on_submit():
        return _process_buchung(form)

    flash_form_errors("index", form)
    return _render_index(form, berater_liste)


def _process_buchung(form: BuchungForm) -> ResponseReturnValue:
    """Speichert eine neue Buchung und sendet Bestätigungsmails."""
    berater_id = form.berater_id.data
    uhrzeit_id = form.uhrzeit_id.data

    berater = state.db.session.get(Berater, berater_id)
    if not berater:
        flash("Es gibt keine Lehrkraft mit dieser ID.", "error")
        return redirect(url_for("main.index"))

    stmt = state.db.select(Buchung).filter(
        Buchung.berater_id == berater_id,
        Buchung.uhrzeit_id == uhrzeit_id,
    )
    if state.db.session.execute(stmt).scalars().first():
        flash(
            f"Der Termin um {uhrzeit_id}h bei"
            f" {berater.berater_vorname} {berater.berater_nachname} ist leider schon vergeben.",
            "error",
        )
        return redirect(url_for("main.index"))

    buchung = Buchung()
    form.populate_obj(buchung)
    try:
        state.db.session.add(buchung)
        state.db.session.commit()

    except Exception as e:
        state.db.session.rollback()
        logger.error("Fehler beim Speichern der Buchung: %s", e)
        flash("Fehler beim Speichern der Buchung.", "error")
        return redirect(url_for("main.index"))

    flash(
        f"Termin gebucht für: {berater.berater_vorname} {berater.berater_nachname} um {uhrzeit_id}h",
        "success",
    )
    info, result = send_mail_to_bucher(buchung)
    flash(info, result)
    return redirect(url_for("main.index"))


def _render_index(form: BuchungForm, berater_liste: list[Berater]) -> ResponseReturnValue:
    """Rendert die Startseite."""
    return render_template(
        _TEMPLATE_INDEX,
        title=_TITLE_INDEX,
        berater_liste=berater_liste,
        form=form,
    )


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Bestätigung
# ------------------------------------------------------------------------------


def _load_buchung_by_token(token: str) -> Buchung | None:
    """Lädt eine Buchung anhand ihres Tokens."""
    stmt = state.db.select(Buchung).options(joinedload(Buchung.berater)).where(Buchung.token == token)
    return state.db.session.execute(stmt).scalars().first()


def _handle_bestaetigung_action(action: str, token: str, buchung: Buchung) -> Buchung | None:
    """Verarbeitet die Bestätigungs- oder Löschaktion für eine Buchung."""
    match action:
        case "confirm":
            buchung.bestaetigt = True
            try:
                state.db.session.commit()
            except Exception as e:
                state.db.session.rollback()
                logger.error("Fehler beim Bestätigen der Buchung: %s", e)
                raise
            send_mail_to_berater(buchung, buchung.berater)
            flash(Markup(_MSG_CONFIRM_INFO), "warning")
            return buchung

        case "delete":
            # Kopie von buchung zur Ausgabe nach dem Löschen
            buchung_data = _copy_model_attributes(buchung)
            berater = get_berater_by_id(buchung.berater_id)

            delete_buchung(buchung)

            send_mail_to_berater(buchung_data, berater, True)
            flash("Der Termin wurde gelöscht und wieder frei gegeben.", "warning")
            return buchung_data

        case _:
            logger.warning("Ungültige Aktion: %s", action)
            flash("Ungültige Aktion.", "error")
            return buchung


def _render_bestaetigung(buchung: Buchung | None, title: str = _TITLE_BESTAETIGUNG) -> ResponseReturnValue:
    """Rendert die Bestätigungsseite."""
    return render_template(
        _TEMPLATE_BESTAETIGUNG,
        title=title,
        buchung=buchung,
    )
