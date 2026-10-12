# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ==============================================================================

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Literal

from flask import abort, make_response
from markupsafe import Markup
from sqlalchemy import false
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import HTTPException

from src.extensions import state
from src.forms import BuchungForm
from src.models import Buchung, Lehrkraft


logger = logging.getLogger(__name__)

_MSG_CONFIRM_INFO = (
    " <p><b>Wichtig: </b> Wenn Sie Ihren Termin nicht wahrnehmen können, nutzen Sie den"
    " Stornierungslink in Ihrer <span class='nobr'>Bestätigungs-E-Mail</span>"
    " — so geben Sie den Platz für andere Betriebe frei.</p>"
)
DEFAULT_TIMETOWAIT = 120


def delete_unconfirmed_buchungen(
    timetowait: int = DEFAULT_TIMETOWAIT,
) -> tuple[str, Literal["success", "warning", "danger"]]:
    """Löscht nicht bestätigte Buchungen, die älter als die konfigurierte Wartezeit sind.

    Args:
        timetowait: Zeit in Minuten seit Anmeldung. Defaults to DEFAULT_TIMETOWAIT.

    Returns:
        Tuple (message, category).
        - "success": Buchungen gelöscht
        - "warning": Keine Buchungen zum Löschen
        - "danger": Datenbankfehler oder ungültige Eingabe

    Raises:
        SQLAlchemyError: Bei Datenbankfehler
    """
    # 1. Eingabe validieren
    if timetowait <= 0:
        logger.warning("Ungültige Wartezeit: %d Minuten", timetowait)
        return ("Wartezeit muss größer als 0 sein.", "danger")

    try:
        # 2. Zeitlimit berechnen
        zeitlimit = datetime.now() - timedelta(minutes=timetowait)

        # 3. Unbestätigte Buchungen löschen
        stmt = state.db.delete(Buchung).where(
            Buchung.created_at < zeitlimit,
            Buchung.bestaetigt == false(),
        )
        result = state.db.session.execute(stmt)
        state.db.session.commit()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("DB-Fehler beim Löschen unbestätigter Buchungen: %s", e)
        return ("Fehler beim Löschen der unbestätigten Buchungen aus der Datenbank.", "danger")

    except Exception as e:
        state.db.session.rollback()
        logger.exception("Unerwarteter Fehler beim Löschen unbestätigter Buchungen: %s", e)
        return ("Unerwarteter Fehler beim Löschen der unbestätigten Buchungen.", "danger")

    else:
        deleted_count = result.rowcount if result.rowcount is not None else 0

        if deleted_count == 0:
            message = "Keine unbestätigten Buchungen zum Löschen gefunden."
            logger.info(message)
            return (message, "success")

        message = f"{deleted_count} unbestätigte Buchungen gelöscht."
        logger.info(message)
        return (message, "success")


def _generiere_zeiten(dauer: int = 15) -> tuple[str, Literal["success", "warning", "danger"], list[str]]:
    """Erstellt eine Liste von Uhrzeiten von Sprechtag-Beginn bis Ende.

    Args:
        dauer: Dauer eines Termins in Minuten.

    Returns:
        Tuple (message, category, Liste mit Uhrzeiten, z. B. ["16:00", "16:15", ...]).
        - "success": Zeiten erfolgreich generiert
        - "danger": Fehler beim Parsen der Uhrzeiten
    """
    if state.sprechtag is None:
        logger.error("state.sprechtag ist nicht gesetzt.")
        return ("Fehler beim Erstellen der freien Zeiten.", "danger", [])

    try:
        start = datetime.strptime(state.sprechtag.beginn, "%H:%M")
        ende = datetime.strptime(state.sprechtag.ende, "%H:%M")
    except ValueError as e:
        logger.error("Fehler beim Parsen der Uhrzeiten: %s", e)
        return ("Fehler beim Erstellen der freien Zeiten.", "danger", [])
    else:
        zeiten = []
        while start <= ende:
            zeiten.append(start.strftime("%H:%M"))
            start += timedelta(minutes=dauer)

        return ("", "success", zeiten)


def get_gebuchte_zeiten(lehrkraft_id: int) -> tuple[str, Literal["success", "warning", "danger"], list[str]]:
    """Gibt alle bereits gebuchten Uhrzeiten einer Lehrkraft zurück.

    Args:
        lehrkraft_id: ID der Lehrkraft.

    Returns:
        Tuple (message, category, Liste gebuchter Uhrzeiten, z. B. ["16:00", "16:15", "16:45"]) oder [].
        - "success": Zeiten gefunden
        - "warning": Keine Zeiten vorhanden
        - "danger": Datenbankfehler
    """
    if not lehrkraft_id or not isinstance(lehrkraft_id, int):
        return ("Lehrkraft_ID ist erforderlich.", "warning", [])

    try:
        stmt = state.db.select(Buchung.uhrzeit_id).where(Buchung.lehrkraft_id == lehrkraft_id)
        result = list(state.db.session.execute(stmt).scalars().all())
    except SQLAlchemyError as e:
        logger.error("DB-Fehler: %s", e)
        return ("Fehler beim Abrufen der gebuchten Zeiten aus der Datenbank.", "danger", [])

    except Exception as e:
        logger.exception("Unerwarteter Fehler: %s", e)
        return ("Unerwarteter Fehler beim Abrufen der gebuchten Zeiten.", "danger", [])

    else:
        if not result:
            return ("Keine gebuchten Zeiten vorhanden.", "warning", [])
        return ("", "success", result)


def get_freie_zeiten_fuer_lehrkraft(
    lehrkraft_id: int,
) -> tuple[str, Literal["success", "warning", "danger"], list[str]]:
    """Gibt alle noch freien Termine einer Lehrkraft zurück.

    Args:
        lehrkraft_id: ID der Lehrkraft.

    Returns:
        Tuple (message, category, Liste freier Uhrzeiten, z. B. ["16:00", "16:15", "16:45"]) oder [].
        - "success": Zeiten gefunden
        - "warning": Keine Zeiten vorhanden
        - "danger": Datenbankfehler
    """
    if not lehrkraft_id or not isinstance(lehrkraft_id, int):
        return ("Lehrkraft_ID ist erforderlich.", "warning", [])

    try:
        # Lehrkraftspezifische Dauer eines Termins auslesen
        stmt = state.db.select(Lehrkraft.lehrkraft_dauer).where(Lehrkraft.lehrkraft_id == lehrkraft_id)
        dauer = state.db.session.execute(stmt).scalars().first()

    except SQLAlchemyError as e:
        logger.error("DB-Fehler: %s", e)
        return ("Fehler beim Abrufen der freien Zeiten aus der Datenbank.", "danger", [])

    except Exception as e:
        logger.exception("Unerwarteter Fehler: %s", e)
        return ("Unerwarteter Fehler beim Abrufen der freien Zeiten.", "danger", [])

    else:
        if dauer is None:
            logger.warning("Keine Lehrkraft mit ID %d gefunden.", lehrkraft_id)
            return ("Keine Lehrkraft mit dieser ID gefunden.", "warning", [])

        # Mögliche Zeiten generieren
        message, category, alle_zeiten = _generiere_zeiten(dauer)
        if category != "success":
            logger.warning("Fehler beim Generieren der Zeiten für Lehrkraft %d", lehrkraft_id)
            return ("Fehler beim Erstellen der freien Zeiten.", "danger", [])

        # Bereits gebuchte Zeiten der Lehrkraft auslesen
        message, category, gebuchte_zeiten_list = get_gebuchte_zeiten(lehrkraft_id)
        if category == "danger":
            return (message, category, [])
        gebuchte_zeiten = set(gebuchte_zeiten_list)

        # Freie Zeiten extrahieren
        result = [z for z in alle_zeiten if z not in gebuchte_zeiten]

        if not result:
            return ("Keine freien Zeiten vorhanden.", "warning", [])

        return ("", "success", result)


def delete_buchung(buchung_token: str) -> tuple[str, Literal["success", "danger"]]:
    """Löscht eine Buchung

    Args:
        buchung_token (str): buchung_token, der zu löschenden Buchung

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
        - "success": Buchung erfolgreich gelöscht
        - "danger": Fehler beim Löschen der Buchung

    Raises:
        Exception: Bei Datenbankfehlern.
    """
    buchung = get_buchung_by_token_or_abort(buchung_token)
    if not buchung:
        return ("Buchung existiert nicht.", "danger")

    termin = f"{buchung.betrieb_name} ({buchung.uhrzeit_id}h)"
    try:
        state.db.session.delete(buchung)
        state.db.session.commit()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("Fehler beim Löschen der Buchung %s: %s", termin, e)
        return ("Fehler beim Löschen der Buchung.", "danger")
    else:
        logger.info("Buchung gelöscht: %s", termin)
        return (f"Buchung: {termin} wurde erfolgreich gelöscht.", "success")


def get_buchung_by_token_or_abort(token: str | None, to_abort: bool = False) -> Buchung | None:
    """Liefert eine Buchung aufgrund seines Tokens.

    Args:
        token: Token der Buchung.
        to_abort: Wenn True, wird bei Fehler abgebrochen (abort 400/500).

    Returns:
        Buchung | None: gesuchte Buchung

    Raises:
        HTTPException: Wenn to_abort=True und Buchung nicht gefunden.
    """
    if token is None:
        if to_abort:
            abort(make_response("bad request! (Kein Token angegeben)", 400))
        else:
            logger.warning("Token ist None")
            return None
    try:
        stmt = (
            state.db.select(Buchung)
            .options(joinedload(Buchung.lehrkraft))
            .where(
                Buchung.buchung_token == token,
            )
        )
        buchung = state.db.session.execute(stmt).scalar_one_or_none()

        if buchung is None and to_abort:
            logger.warning("Keine Buchung mit Token '%s' gefunden.", token)
            abort(make_response("bad request! (Der angegebene Token ist ungültig oder abgelaufen)", 400))

    except HTTPException:
        # abort() wirft HTTPException – einfach weitergeben
        raise

    except (SQLAlchemyError, Exception) as e:
        logger.error("Fehler beim Laden der Buchung mit Token '%s': %s", token, e)
        abort(make_response("bad request! (Fehler beim Laden der Buchung)", 500))

    else:
        return buchung


def init_buchung_form(lehrkraft_liste: list[Lehrkraft], selected_lehrkraft_id: int | None) -> BuchungForm:
    """Initialisiert das Buchungsformular mit Lehrkraft-Choices.

    Args:
        lehrkraft_liste (list): Liste aller Lehrkraft.
        selected_lehrkraft_id: ID der aktuell ausgewählten Lehrkraft oder None

    Returns:
        Initialisierte BuchungForm.
    """
    form = BuchungForm()
    form.lehrkraft_id.choices = [("", "Bitte wählen...")] + [(b.lehrkraft_id, b.full_name) for b in lehrkraft_liste]

    if selected_lehrkraft_id:
        message, category, valid_zeiten = get_freie_zeiten_fuer_lehrkraft(selected_lehrkraft_id)
        if category != "success":
            logger.warning("Fehler beim Laden der Zeiten: %s", message)
            form.uhrzeit_id.choices = [("", "Keine Zeiten verfügbar")]
        else:
            form.uhrzeit_id.choices = [("", "Bitte Uhrzeit wählen...")] + [
                (zeit, f"{zeit} Uhr") for zeit in valid_zeiten
            ]
    else:
        form.uhrzeit_id.choices = [("", "Bitte wählen Sie zuerst eine Lehrkraft aus")]
        form.lehrkraft_id.data = 0
    return form


def slot_is_used(lehrkraft_id: int, uhrzeit_id: str) -> tuple[Markup, Literal["success", "danger"], bool]:
    """Prüft, ob ein Zeitslot bereits gebucht ist.

    Args:
        lehrkraft_id: ID des Lehrkrafts.
        uhrzeit_id: Zeitslot (z.B. "15:30").

    Returns:
        Tuple (Markup-Nachricht, Kategorie, is_used).
        - "success": DB - Abfrage erfolgreich
        - "danger": Fehler beim Abfragen des Slots
         True, wenn der Slot bereits gebucht ist, sonst False.
    """
    try:
        stmt = state.db.select(Buchung).where(
            Buchung.lehrkraft_id == lehrkraft_id,
            Buchung.uhrzeit_id == uhrzeit_id,
        )
        is_used = state.db.session.execute(stmt).scalars().first() is not None

    except SQLAlchemyError as e:
        info = "Fehler beim Prüfen des Zeitslots: %s", e
        logger.error(info)
        return (info, "danger", False)
    else:
        return ("", "success", is_used)


def create_buchung(
    form: BuchungForm, lehrkraft: Lehrkraft
) -> tuple[Markup, Literal["success", "danger"], Buchung | None]:
    """Erstellt eine neue Buchung aufgrund der Form.

    Args:
        form: Flask Form mit Buchung-Daten.
        lehrkraft: Lehrkraft-Objekt.

    Returns:
        Tuple (Markup-Nachricht, Kategorie, Buchung).
        - "success": Buchung erfolgreich erstellt
        - "danger": Fehler beim Erstellen der Buchung

    Raises:
        Exception: Bei Datenbankfehlern.
    """
    buchung = Buchung()
    form.populate_obj(buchung)
    try:
        state.db.session.add(buchung)
        state.db.session.commit()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("Fehler beim Erstellen der Buchung: %s", e)
        return ("Fehler beim Erstellen der Buchung", "danger", None)
    else:
        logger.info("Buchung %s erstellt.", buchung.buchung_id)
        return (f"Termin gebucht für: {lehrkraft.full_name} um {buchung.uhrzeit_id}h", "success", buchung)


def confirm_buchung(buchung: Buchung) -> tuple[Markup, Literal["success", "danger"]]:
    """Setzt den Bestätigt-Flag der Buchung.

    Args:
        buchung: Buchung, die bestätigt werden soll.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
        - "success": Buchung erfolgreich bestätigt
        - "danger": Fehler beim Bestätigen der Buchung

    Raises:
        Exception: Bei Datenbankfehlern.
    """

    if buchung is None:
        return ("Diese Buchung existiert nicht oder ist abgelaufen.", "danger")

    try:
        buchung.bestaetigt = True
        state.db.session.commit()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("Fehler beim Bestätigen der Buchung %s: %s", buchung.betrieb_mail, e)
        return ("Die Buchung konnte nicht bestätigt werden", "danger")
    else:
        logger.info("Die Buchung wurde bestätigt:%s", buchung.betrieb_mail)
        return (Markup(_MSG_CONFIRM_INFO), "warning")
