from datetime import datetime, timedelta
import logging

from src.extensions import state
from src.models import Berater, Buchung


logger = logging.getLogger(__name__)


def _delete_old_orders() -> None:
    """Löscht nicht bestätigte Buchungen, die älter als die konfigurierte Wartezeit sind."""
    cutoff = datetime.now() - timedelta(minutes=state.app.config["SPRECHTAG_WARTEZEIT"])
    try:
        stmt = state.db.delete(Buchung).where(Buchung.bestaetigt.is_(False)).where(Buchung.erstellt_um < cutoff)
        result = state.db.session.execute(stmt)
        state.db.session.commit()
        logger.info("_delete_old_orders: %d alte Buchung(en) gelöscht.", result.rowcount)

    except Exception as e:
        state.db.session.rollback()
        logger.error("Fehler beim Löschen alter Buchungen: %s", e)


def _generiere_zeiten(dauer: int = 15) -> list[str]:
    """Erstellt eine Liste von Uhrzeiten von Sprechtag-Beginn bis Ende.

    Args:
        dauer: Dauer eines Termins in Minuten.

    Returns:
        Liste mit Uhrzeiten, z. B. ["16:00", "16:15", ...].
    """
    zeiten = []
    start = datetime.strptime(state.sprechtag.beginn, "%H:%M")
    ende = datetime.strptime(state.sprechtag.ende, "%H:%M")

    while start <= ende:
        zeiten.append(start.strftime("%H:%M"))
        start += timedelta(minutes=dauer)

    return zeiten


def _get_gebuchte_zeiten(berater_id: int) -> list[str]:
    """Gibt alle bereits gebuchten Uhrzeiten eines Beraters zurück.

    Args:
        berater_id: ID des Beraters.

    Returns:
        Liste gebuchter Uhrzeiten, z. B. ["16:30", "17:15"].
    """
    stmt = state.db.select(Buchung.uhrzeit_id).filter_by(berater_id=berater_id)
    return state.db.session.execute(stmt).scalars().all()


def _get_freie_zeiten_fuer_berater(berater_id: int) -> list[str]:
    """Gibt alle noch freien Termine eines Beraters zurück.

    Args:
        berater_id: ID des Beraters.

    Returns:
        Liste freier Uhrzeiten, z. B. ["16:00", "16:15", "16:45"].
    """
    stmt = state.db.select(Berater.berater_dauer).filter_by(berater_id=berater_id)
    dauer = state.db.session.execute(stmt).scalars().first()

    alle_zeiten = _generiere_zeiten(dauer)
    gebuchte_zeiten = set(_get_gebuchte_zeiten(berater_id))

    return [z for z in alle_zeiten if z not in gebuchte_zeiten]


def _delete_buchung(buchung: Buchung) -> None:
    """löscht eine Buchung

    Args:
        buchung (Buchung): zu löschende Buchung
    """
    state.db.session.delete(buchung)
    state.db.session.commit()


def _get_buchung_by_token(token: str) -> Buchung | None:
    """liefert eine Buchung aufgrund seines tokens

    Args:
        token (str): Token der Buchung

    Returns:
        Buchung | None: gesuchte Buchung
    """
    stmt = state.db.select(Buchung).where(Buchung.token == token)
    return state.db.session.execute(stmt).scalars().first()
