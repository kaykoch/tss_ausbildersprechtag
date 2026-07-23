import logging

from flask import flash
from markupsafe import Markup


logger = logging.getLogger(__name__)


def _copy_model_attributes(obj) -> dict:
    """Kopiert alle öffentlichen, nicht-aufrufbaren Attribute eines SQLAlchemy-Objekts.

    Args:
        obj: SQLAlchemy-Modell-Instanz.

    Returns:
        Dictionary mit den kopierten Attributen, oder {} wenn obj None ist.
    """
    if obj is None:
        return {}
    return {key: getattr(obj, key) for key in dir(obj) if not key.startswith("_") and not callable(getattr(obj, key))}


def flash_form_errors(context: str, form) -> None:
    logger.error("Formular-Fehler in %s: %s", context, form.errors)
    texts = [msg for messages in form.errors.values() for msg in messages]
    flash(Markup("<br>".join(texts)), "error")
