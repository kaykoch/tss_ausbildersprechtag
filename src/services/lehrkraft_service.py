# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ==============================================================================
from __future__ import annotations

import logging
from secrets import token_urlsafe
from typing import Literal

from flask import abort, make_response
from markupsafe import Markup
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException

from src.extensions import state
from src.forms import LehrkraftForm
from src.models import Lehrkraft


logger = logging.getLogger(__name__)

TOKEN_LENGTH = 12


def delete_lehrkraft(lehrkraft_token: str) -> tuple[Markup, Literal["success", "danger"]]:
    """Löscht eine Lehrkraft und alle verbundenen Buchungen.

    Args:
        lehrkraft_token: Token des zu löschenden Lehrkraft-Objekts.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
        - "success": Lehrkraft erfolgreich gelöscht
        - "danger": Fehler beim Löschen der Lehrkraft

    Note:
        Löscht auch alle verbundenen Buchungen (Cascade-Delete).
    """
    lehrkraft = get_lehrkraft_by_token_or_abort(lehrkraft_token)
    if not lehrkraft:
        return ("Lehrkraft existiert nicht.", "danger")

    name = f"{lehrkraft.lehrkraft_vorname} {lehrkraft.lehrkraft_nachname}"
    try:
        state.db.session.delete(lehrkraft)
        state.db.session.commit()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("Fehler beim Löschen der Lehrkraft %s: %s", name, e)
        return ("Fehler beim Löschen der Lehrkraft.", "danger")
    else:
        logger.info("Lehrkraft gelöscht: %s", name)
        return (f"Lehrkraft: {name} wurde erfolgreich gelöscht.", "success")


def get_lehrkraft_by_token_or_abort(lehrkraft_token: str | None, to_abort: bool = False) -> Lehrkraft | None:
    """Lädt einen Lehrkraft anhand seines Tokens oder bricht mit HTTP-Fehler ab.

    Args:
        lehrkraft_token/str): Token des gesuchten Lehrkrafts.
        abort (bool): Flag ob bei fehler abgebrochen  wird, default = False

    Returns:
        Lehrkraft-Objekt zum Token.


    Raises:
        HTTPException (400): Wenn kein Token angegeben oder kein Lehrkraft gefunden.
        HTTPException (500): Bei einem Datenbankfehler.
    """
    if lehrkraft_token is None and to_abort:
        abort(make_response("bad request! (Kein Token angegeben)", 400))

    try:
        stmt = state.db.select(Lehrkraft).where(Lehrkraft.lehrkraft_token == lehrkraft_token)
        lehrkraft = state.db.session.execute(stmt).scalar_one_or_none()

        if lehrkraft is None and to_abort:
            logger.warning("Kein Lehrkraft mit Token '%s' gefunden.", lehrkraft_token)
            abort(make_response("bad request! (Der angegebene Token ist ungültig oder abgelaufen)", 400))

    except SQLAlchemyError as e:
        logger.error("Fehler beim Laden der Lehrkraft mit Token '%s': %s", lehrkraft_token, e)
        abort(make_response("bad request! (Datenbankfehler)", 500))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Fehler beim Laden der Lehrkraft mit Token '%s': %s", lehrkraft_token, e)
        abort(make_response("bad request! (Fehler beim Laden der Lehrkraft)", 500))

    else:
        return lehrkraft


def get_lehrkraft_by_id_or_none(lehrkraft_id: int) -> Lehrkraft | None:
    """Lädt einen Lehrkraft anhand seiner ID.

    Args:
        lehrkraft_id: ID des gesuchten Lehrkrafts.

    Returns:
        Lehrkraft-Objekt zur ID oder None, wenn nicht gefunden.

    Raises:
        Exception: Bei Datenbankfehlern.
    """
    if not lehrkraft_id:
        return None

    try:
        stmt = state.db.select(Lehrkraft).where(Lehrkraft.lehrkraft_id == lehrkraft_id)
        lehrkraft = state.db.session.execute(stmt).scalar_one_or_none()

        if lehrkraft is None:
            logger.warning("Kein Lehrkraft mit ID '%s' gefunden.", lehrkraft_id)

        return lehrkraft

    except Exception as e:
        logger.error("Fehler beim Laden des Lehrkrafts mit ID '%s': %s", lehrkraft_id, e)
        raise


def get_lehrkraft_by_mail(lehrkraft_mail: str) -> Lehrkraft | None:
    """Lädt einen Lehrkraft anhand seiner E-Mail-Adresse.

    Args:
        lehrkraft_mail: E-Mail-Adresse des Lehrkrafts.

    Returns:
        Lehrkraft-Objekt oder None, wenn nicht gefunden.

    Raises:
        Exception: Bei Datenbankfehlern.
    """
    if not lehrkraft_mail:
        return None

    try:
        stmt = state.db.select(Lehrkraft).where(Lehrkraft.lehrkraft_mail == lehrkraft_mail)
        return state.db.session.execute(stmt).scalar_one_or_none()
    except Exception as e:
        logger.error("Fehler beim Laden des Lehrkrafts mit Mail '%s': %s", lehrkraft_mail, e)
        raise


def create_lehrkraft(form: LehrkraftForm) -> tuple[Markup, Literal["success", "danger"], Lehrkraft]:
    """Erstellt einen neuen Lehrkraft aufgrund der Form und liefert den Lehrkraft zurück.

    Args:
        form: Flask Form mit Lehrkraft-Daten.

    Returns:
        Tuple (Markup-Nachricht, Kategorie, Lehrkraft).
        - "success": Lehrkraft erfolgreich erstellt
        - "danger": Fehler beim Erstellen der Lehrkraft

    Raises:
        Exception: Bei Datenbankfehlern.
    """
    lehrkraft = Lehrkraft()
    form.populate_obj(lehrkraft)

    # ✅ Neues Token generieren (überschreibt leeres Feld)
    lehrkraft.lehrkraft_token = token_urlsafe(TOKEN_LENGTH)

    try:
        state.db.session.add(lehrkraft)
        state.db.session.commit()

    except IntegrityError as e:  # ← Spezifisch zuerst!
        state.db.session.rollback()
        logger.error("Unique Constraint verletzt: %s", e)
        return ("Fehler beim Erstellen der Lehrkraft", "danger", None)
    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("Fehler beim Erstellen der Lehrkraft: %s", e)
        return ("Fehler beim Erstellen der Lehrkraft", "danger", None)

    else:
        logger.info("Lehrkraft %s erstellt.", lehrkraft.lehrkraft_id)
        return (f"{lehrkraft.full_name} wurde erfolgreich eingefügt", "success", lehrkraft)


def update_lehrkraft(form: LehrkraftForm, lehrkraft: Lehrkraft) -> tuple[Markup, Literal["success", "danger"]]:
    """Aktualisiert einen Lehrkraft aufgrund der Daten in Form.

    Args:
        form: Flask Form mit neuen Daten.
        lehrkraft: Lehrkraft, der aktualisiert wird.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
        - "success": Lehrkraft erfolgreich geändert
        - "danger": Fehler beim Ändern der Lehrkraft

    Raises:
        Exception: Bei Datenbankfehlern.
    """
    try:
        form.populate_obj(lehrkraft)
        state.db.session.commit()

    except Exception as e:
        state.db.session.rollback()
        logger.error("Fehler beim Update der Lehrkraft: %s", e)
        return (f"Fehler beim Update des Lehrkraft: {lehrkraft.full_name}", "danger")
    else:
        logger.info("Lehrkraft %s aktualisiert.", lehrkraft.full_name)
        return (f"Lehrkraft: {lehrkraft.full_name} wurde erfolgreich aktualisiert", "success")


def get_lehrkraft_liste() -> list[Lehrkraft]:
    """Lädt alle Lehrkraft aus der DB, sortiert nach Name.

    Returns:
        list[lekrkraft]: List mit allen Lehrkräfte
    """
    try:
        stmt = state.db.select(Lehrkraft).order_by(
            Lehrkraft.lehrkraft_nachname,
            Lehrkraft.lehrkraft_vorname,
        )
        liste_lehrkraft = state.db.session.execute(stmt).scalars().all()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("Fehler beim Laden der Liste mit Lehrkräften: %s", e)
        return []

    else:
        return liste_lehrkraft
