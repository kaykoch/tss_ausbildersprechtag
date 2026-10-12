# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ==============================================================================

from __future__ import annotations

from io import BytesIO
import logging
from typing import Literal

from flask import render_template
from weasyprint import CSS, HTML

from src.extensions import state
from src.models import Lehrkraft


logger = logging.getLogger(__name__)


def export_to_pdf(lehrkraft: Lehrkraft) -> tuple[str, Literal["success", "warning", "danger"], BytesIO | None]:
    """Erzeugt ein PDF für einen Lehrkraft und gibt es als BytesIO zurück.

    Args:
        lehrkraft: Lehrkraft-Objekt, dessen Daten ins PDF einfließen.

    Returns:
        Tuple (message, category, BytesIO oder None)
        - "success": PDF erfolgreich erzeugt
        - "warning": PDF ohne Stylesheet erzeugt
        - "danger": Fehler beim PDF-Rendering
    """
    try:
        logger.info("PDF wird erzeugt für Lehrkraft: %s", lehrkraft.full_name)

        html_content = render_template("pdf_layout.html", lehrkraft=lehrkraft)
        css_path = state.staticfolder / "pdf.css"

        if not css_path.exists():
            logger.warning("PDF-CSS nicht gefunden: %s", css_path)
            stylesheets = []
        else:
            stylesheets = [CSS(filename=str(css_path))]

        pdf_io = BytesIO()
        HTML(string=html_content).write_pdf(target=pdf_io, stylesheets=stylesheets)
        pdf_io.seek(0)

    except Exception as e:
        error_msg = f"Fehler beim Erzeugen des PDF für Lehrkraft {lehrkraft.lehrkraft_id}: {str(e)}"
        logger.exception(error_msg)
        return (error_msg, "danger", None)

    else:
        category = "warning" if not css_path.exists() else "success"
        message = f"PDF erfolgreich erzeugt für {lehrkraft.full_name}"
        logger.info(message)
        return (message, category, pdf_io)
