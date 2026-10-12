# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ==============================================================================

from __future__ import annotations

import logging
from typing import Literal

from flask import flash
from flask_wtf import FlaskForm
from markupsafe import Markup
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from src.extensions import state


logger = logging.getLogger(__name__)


def commit_config() -> tuple[str, Literal["success", "danger"], None]:
    """Speichert die offenen Änderungen der Session in der Datenbank.

    Returns:
        Tuple (message, category, None).
        - "success": Änderungen erfolgreich gespeichert
        - "danger": Fehler beim Speichern, Änderungen wurden verworfen

    Raises:
        Keine. Fehler werden geloggt und als Tuple zurückgegeben.
    """
    try:
        state.db.session.commit()

    except SQLAlchemyError as e:
        state.db.session.rollback()
        logger.error("DB-Fehler beim Speichern der Konfiguration: %s", e)
        return ("Fehler beim Speichern der Konfiguration.", "danger", None)

    else:
        logger.info("Konfiguration in der Datenbank gespeichert.")
        return ("Konfiguration erfolgreich gespeichert.", "success", None)


def copy_model_attributes(obj: object | None) -> dict:
    """Kopiert alle Tabellenspalten-Attribute eines SQLAlchemy-Objekts.

    Args:
        obj: SQLAlchemy-Modell-Instanz oder None.

    Returns:
        Dictionary mit den kopierten Spaltenattributen, oder {} wenn obj None ist.
    """
    if obj is None:
        return {}

    try:
        mapper = inspect(type(obj))
        return {col.key: getattr(obj, col.key) for col in mapper.column_attrs}
    except Exception as e:
        logger.exception("Fehler beim Kopieren der Modell-Attribute: %s", e)
        return {}


def flash_form_errors(form: FlaskForm) -> None:
    """Loggt Formularfehler und zeigt sie als Flash-Nachricht an.

    Args:
        form: WTForms-Formularinstanz mit .errors-Dictionary.

    Returns:
        None. Fehler werden geloggt und als Flash-Nachricht angezeigt.
    """
    try:
        logger.error("Formularfehler: %s", form.errors)
        messages = []
        for field, errors in form.errors.items():
            for error in errors:
                messages.append(f"{field}: {error}")

        if messages:
            flash(Markup("<br>".join(messages)), "danger")
        else:
            logger.warning("flash_form_errors: form.errors ist leer")
    except Exception as e:
        logger.exception("Fehler beim Anzeigen von Formularfehlern: %s", e)
        flash("Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.", "danger")
