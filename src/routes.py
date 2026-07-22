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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from markupsafe import Markup

from src.extensions import state
from src.forms import BuchungForm
from src.helpies import (
    _copy_model_attributes,
    _delete_old_orders,
    _get_freie_zeiten_fuer_berater,
    _get_gebuchte_zeiten,
    _send_mail_to_berater,
    _send_mail_to_bucher,
)
from src.models import Berater, Buchung, _get_berater_liste


logger = logging.getLogger(__name__)
bp = Blueprint("main", __name__)


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


@bp.route("/", methods=["GET", "POST"])
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


@bp.route("/bestaetigung.html", methods=["GET"])
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
            flash(f"Buchung mit Token {token} existiert nicht.", "error")
            return _render_bestaetigung(buchung=None)

        buchung = _handle_bestaetigung_action(action, token, buchung)

    except Exception as e:
        state.db.session.rollback()
        logger.error("Fehler in bestaetigung (action: %s, token: %s): %s", action, token, e)
        flash("Ein Fehler ist aufgetreten. Bitte versuche es erneut.", "error")
        buchung = None

    return _render_bestaetigung(buchung=buchung, title=_TITLE_BESTAETIGUNG)


@bp.route("/api/freie_zeiten/<int:berater_id>")
def freie_zeiten(berater_id: int) -> ResponseReturnValue:
    """API – Gibt freie Zeiten für einen Berater zurück."""
    return jsonify(_get_freie_zeiten_fuer_berater(berater_id))


@bp.route("/api/gebuchte_zeiten/<int:berater_id>")
def gebuchte_zeiten(berater_id: int) -> ResponseReturnValue:
    """API – Gibt gebuchte Zeiten für einen Berater zurück."""
    return jsonify(_get_gebuchte_zeiten(berater_id))


@bp.route("/impressum.html", methods=["GET"])
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

    logger.error("Formular-Fehler in index: %s", form.errors)
    flash(str(form.errors), "error")
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
    state.db.session.add(buchung)
    state.db.session.commit()

    flash(
        f"Termin gebucht für: {berater.berater_vorname} {berater.berater_nachname} um {uhrzeit_id}h",
        "success",
    )
    info, result = _send_mail_to_bucher(buchung)
    flash(info, result)

    return redirect(url_for("main.index"))


def _render_index(form: BuchungForm, berater_liste: list[Berater]) -> ResponseReturnValue:
    """Rendert die Startseite."""
    return render_template(
        _TEMPLATE_INDEX,
        title=_TITLE_INDEX,
        berater_liste=berater_liste,
        sprechtag=state.sprechtag,
        form=form,
    )


# ------------------------------------------------------------------------------
# Hilfsfunktionen – Bestätigung
# ------------------------------------------------------------------------------


def _load_buchung_by_token(token: str) -> Buchung | None:
    """Lädt eine Buchung anhand ihres Tokens."""
    stmt = state.db.select(Buchung).where(Buchung.token == token)
    return state.db.session.execute(stmt).scalars().first()


def _handle_bestaetigung_action(action: str, token: str, buchung: Buchung) -> Buchung | None:
    """Verarbeitet die Bestätigungs- oder Löschaktion für eine Buchung."""
    match action:
        case "confirm":
            buchung.bestaetigt = True
            state.db.session.commit()
            _send_mail_to_berater(buchung)
            flash(Markup(_MSG_CONFIRM_INFO), "warning")
            return buchung

        case "delete":
            buchung_data = _copy_model_attributes(buchung)
            stmt = state.db.delete(Buchung).where(Buchung.token == token)
            state.db.session.execute(stmt)
            state.db.session.commit()
            _send_mail_to_berater(buchung_data, True)
            flash("Der Termin wurde gelöscht und wieder frei gegeben.", "warning")
            return None

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
        sprechtag=state.sprechtag,
    )
