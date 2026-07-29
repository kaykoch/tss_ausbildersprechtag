# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
# ------------------------------------------------------------------------------

import logging

from flask import flash
from flask_wtf import FlaskForm
from markupsafe import Markup
from sqlalchemy import inspect


logger = logging.getLogger(__name__)


def _copy_model_attributes(obj) -> dict:
    """Kopiert alle Tabellenspalten-Attribute eines SQLAlchemy-Objekts.
    Args:
        obj: SQLAlchemy-Modell-Instanz.

    Returns:
        Dictionary mit den kopierten Spaltenattributen, oder {} wenn obj None ist."""
    if obj is None:
        return {}
    mapper = inspect(type(obj))
    return {col.key: getattr(obj, col.key) for col in mapper.column_attrs}


def flash_form_errors(context: str, form: FlaskForm) -> None:
    """Loggt Formularfehler und zeigt sie als Flash-Nachricht an.

    Args:
        context: Name der aufrufenden Funktion/Route (für das Log).
        form:    WTForms-Formularinstanz mit .errors-Dictionary.
    """
    logger.error("Formular-Fehler in %s: %s", context, form.errors)
    texts = [msg for messages in form.errors.values() for msg in messages]
    flash(Markup("<br>".join(texts)), "error")
