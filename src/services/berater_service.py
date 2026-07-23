import logging

from flask import abort, make_response

from src.extensions import state
from src.forms import BeraterForm
from src.models import Berater


logger = logging.getLogger(__name__)


def delete_berater(berater: Berater) -> tuple[str, str]:
    """Löscht eine Lehrkraft und alle verbundenen Buchungen.

    Args:
        berater: Zu löschendes Berater-Objekt.

    Returns:
        Tuple (Nachricht, Kategorie) mit Kategorie in {"success", "error"}.
    """
    name = f"{berater.berater_vorname} {berater.berater_nachname}"
    try:
        state.db.session.delete(berater)
        state.db.session.commit()
        info = f"{name} und alle Termine gelöscht."
        logger.info(info)
        return (info, "success")

    except Exception as e:
        state.db.session.rollback()
        info = f"Fehler beim Löschen der Lehrkraft {name}: {e}"
        logger.error(info)
        return (info, "error")


def get_berater_by_token_or_abort(berater_token: str | None = None) -> Berater:
    """Lädt einen Berater anhand seines Tokens oder bricht mit HTTP-Fehler ab.

    Args:
        berater_token: Token des gesuchten Beraters.

    Returns:
        Berater-Objekt zum Token.

    Raises:
        HTTPException (400): Wenn kein Token angegeben oder kein Berater gefunden.
        HTTPException (500): Bei einem Datenbankfehler.
    """
    if not berater_token:
        abort(make_response("bad request! (Kein Token angegeben)", 400))

    try:
        stmt = state.db.select(Berater).where(Berater.token == berater_token)
        berater = state.db.session.execute(stmt).scalar_one_or_none()

        if berater is None:
            logger.warning("Kein Berater mit Token '%s' gefunden.", berater_token)
            abort(make_response("bad request! (Der angegebene Token ist ungültig oder abgelaufen)", 400))

        return berater

    except Exception as e:
        logger.error("Fehler beim Laden des Beraters mit Token '%s': %s", berater_token, e)
        abort(make_response("bad request! (Fehler beim Laden des Beraters)", 500))


def _create_berater(form: BeraterForm) -> Berater:
    """Erstellt einen neuen Berater aufgrund der form und liefert den berater zurück

    Args:
        form (BeraterForm): Flask Form

    Returns:
        Berater: erstelleter Berater
    """
    berater = Berater()
    form.populate_obj(berater)
    state.db.session.add(berater)
    state.db.session.commit()
    return berater


def _update_berater(form: BeraterForm, berater: Berater) -> None:
    """Aktualisiert einen Berater aufgrund der Daten in Form

    Args:
        form (BeraterForm): Flask Form
        berater (Berater): Berater, der aktualsiert wird
    """
    form.populate_obj(berater)
    state.db.session.commit()


def _get_berater_liste() -> list[Berater]:
    """Lädt alle Berater aus der DB."""

    stmt = state.db.select(Berater).order_by(
        Berater.berater_nachname,
        Berater.berater_vorname,
    )

    return state.db.session.execute(stmt).scalars().all()
