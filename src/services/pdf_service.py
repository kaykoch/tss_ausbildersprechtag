# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations------------------------------------------------------------------------------

from io import BytesIO
import logging

from flask import render_template
from weasyprint import CSS, HTML

from src.extensions import state
from src.models import Berater


logger = logging.getLogger(__name__)


def _export_to_pdf(berater: Berater) -> BytesIO:
    """Erzeugt ein PDF für einen Berater und gibt es als BytesIO zurück.

    Args:
        berater: Berater-Objekt, dessen Daten ins PDF einfließen.

    Returns:
        BytesIO mit dem PDF-Inhalt.
    """
    logger.info(
        "PDF wird erzeugt für Berater: %s %s",
        berater.berater_vorname,
        berater.berater_nachname,
    )
    print(state.sprechtag)
    html_content = render_template(
        "pdf_layout.html",
        berater=berater,
    )
    css_path = state.staticfolder / "pdf.css"

    if not css_path.exists():
        logger.warning("PDF-CSS nicht gefunden: %s — PDF wird ohne Stylesheet erzeugt.", css_path)
        stylesheets = []
    else:
        stylesheets = [CSS(filename=str(css_path))]  # ✅ str() für Kompatibilität

    pdf_io = BytesIO()
    HTML(string=html_content).write_pdf(target=pdf_io, stylesheets=stylesheets)
    pdf_io.seek(0)
    return pdf_io
