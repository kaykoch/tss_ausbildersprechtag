from io import BytesIO

from flask import render_template
from weasyprint import CSS, HTML

from src.extensions import state
from src.models import Berater


def _export_to_pdf(berater: Berater) -> BytesIO:
    """Erzeugt ein PDF für einen Berater und gibt es als BytesIO zurück.

    Args:
        berater: Berater-Objekt, dessen Daten ins PDF einfließen.

    Returns:
        BytesIO mit dem PDF-Inhalt
    """

    html_content = render_template("pdf_layout.html", berater=berater, titel="")
    css_path = state.staticfolder / "pdf.css"

    pdf_io = BytesIO()
    HTML(string=html_content).write_pdf(target=pdf_io, stylesheets=[CSS(filename=css_path)])
    pdf_io.seek(0)
    return pdf_io
