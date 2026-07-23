from datetime import datetime
import logging


logger = logging.getLogger(__name__)


_WOCHENTAGE = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag",
}
_MONATE = {
    1: "Januar",
    2: "Februar",
    3: "März",
    4: "April",
    5: "Mai",
    6: "Juni",
    7: "Juli",
    8: "August",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Dezember",
}


def formatiere_datum_deutsch(dt: datetime) -> str:
    """Formatiert ein datetime-Objekt locale-unabhängig auf Deutsch.

    Args:
        dt: Zu formatierendes datetime-Objekt.

    Returns:
        Deutsches Datum, z. B. "Freitag, 25. Dezember 2026".
    """
    return f"{_WOCHENTAGE[dt.weekday()]}, {dt.day}. {_MONATE[dt.month]} {dt.year}"
