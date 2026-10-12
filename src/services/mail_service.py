# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ==============================================================================

from __future__ import annotations

import logging
from smtplib import SMTPAuthenticationError, SMTPException
from typing import Literal

from flask import render_template
from flask_mail import Message
from markupsafe import Markup

from src.extensions import state
from src.models import Buchung, Lehrkraft


logger = logging.getLogger(__name__)

_SUBJECT_BUCHER = "Bestätigung: Ausbildersprechtag"
_SUBJECT_BERATER = "Anmeldung: Ausbildersprechtag"
_SUBJECT_STORNO = "Storno: Ausbildersprechtag"
_SUBJECT_ANMELDUNG = "Registrierung: Ausbildersprechtag"


# ------------------------------------------------------------------------------
# Mail – öffentlich
# ==============================================================================


def send_mail_to_bucher(buchung: Buchung) -> tuple[Markup, Literal["success", "warning", "danger"]]:
    """Sendet eine Bestätigungsmail an den Bucher nach der Terminbuchung.

    Args:
        buchung: Die neu erstellte Buchung.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
        - "success": Mail erfolgreich versendet
        - "warning": Mail versendet, aber Bestätigung erforderlich
        - "danger": Mailversand fehlgeschlagen
    """

    msg = _build_mail_msg(
        _SUBJECT_BUCHER,
        buchung.betrieb_mail,
        "mail/mail_bucher.html",
        buchung=buchung,
        time_to_wait=state.sprechtag.storno,
    )
    sent = _send_mail(msg)
    masked_mail = _mask(buchung.betrieb_mail)
    if sent:
        logger.info("Mail (Anmeldung) verschickt an: %s", buchung.full_name)
        message = (
            f"Die Mail wurde an {masked_mail} gesendet<br>Bitte bestätigen Sie Ihre Daten innerhalb von "
            f"{state.sprechtag.storno} Minuten"
        )
        category = "warning"
    else:
        logger.error("Mailversand (Anmeldung) fehlgeschlagen an: %s", buchung.full_name)
        message = f"Die Mail an {masked_mail} konnte nicht versandt werden."
        category = "danger"

    return (Markup(message), category)


def send_mail_to_lehrkraft(
    buchung: dict | Buchung, lehrkraft: Lehrkraft, is_deleted: bool = False
) -> tuple[Markup, Literal["success", "danger"]]:
    """Benachrichtigt eine Lehrkraft per Mail über eine neue oder stornierte Buchung.

    Wird nur gesendet, wenn ``lehrkraft.lehrkraft_will_mail`` True ist.

    Args:
        buchung: Die betroffene Buchung (dict oder Buchung-Objekt).
        lehrkraft: Lehrkraft der Buchung.
        is_deleted: True, wenn es sich um eine Stornierung handelt. Defaults to False.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
        - "success": Mail erfolgreich versendet
        - "danger": Mailversand fehlgeschlagen
    """

    if not lehrkraft.lehrkraft_will_mail:
        return

    subject = _SUBJECT_STORNO if is_deleted else _SUBJECT_BERATER
    msg = _build_mail_msg(
        subject,
        lehrkraft.lehrkraft_mail,
        "mail/mail_lehrkraft.html",
        buchung=buchung,
        is_deleted=is_deleted,
    )
    sent = _send_mail(msg)

    if sent:
        message = f"Mail (Buchung) verschickt an: {lehrkraft.full_name})"
        logger.info(message)
        category = "success"
    else:
        message = f"Mailversand (Buchung) fehlgeschlagen an: {lehrkraft.full_names}"
        category = "danger"
        logger.error(message)

    return (Markup(message), category)


def send_anmeldung_mail_to_lehrkraft(lehrkraft: Lehrkraft) -> tuple[Markup, Literal["success", "danger"]]:
    """Sendet eine Registrierungsbestätigung an eine neu angemeldete Lehrkraft.

    Args:
        lehrkraft: Die neu registrierte Lehrkraft.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
        - "success": Mail erfolgreich versendet
        - "danger": Mailversand fehlgeschlagen
    """

    msg = _build_mail_msg(
        _SUBJECT_ANMELDUNG,
        lehrkraft.lehrkraft_mail,
        "mail/mail_anmeldunglehrkraft.html",
        lehrkraft=lehrkraft,
    )
    sent = _send_mail(msg)

    if sent:
        message = f"Mail (Anmeldung) verschickt an:{lehrkraft.full_name}"
        logger.info(message)
        category = "success"
    else:
        message = f"Mailversand  (Anmeldung) fehlgeschlagen an: {lehrkraft.full_name}"
        logger.error(message)
        category = "danger"
    return (Markup(message), category)


# ------------------------------------------------------------------------------
# Mail – Hilfsfunktionen
# ==============================================================================


def _send_mail(msg: Message) -> bool:
    """Sendet eine Flask-Mail-Message.

    Returns:
        True bei erfolgreichem Versand, sonst False.
    """
    try:
        if state.infos.app.testmodus:
            # Im Testmodus wird nicht gesendet, sondern ausgegeben
            print(msg.html)
            return True
        else:
            # Mail wird versendet
            state.mail.send(msg)
            logger.debug("Mail gesendet an: %s", msg.recipients)

    except SMTPAuthenticationError:
        logger.error("Mail-Fehler: Authentifizierung am SMTP-Server fehlgeschlagen.")
    except SMTPException as e:
        logger.error("Allgemeiner SMTP-Fehler beim Mailversand: %s", e)
    except Exception as e:
        logger.exception("Unerwarteter Fehler beim E-Mail-Versand: %s", e)

    return False


def _build_mail_msg(subject: str, recipient: str, template: str, **ctx) -> Message:
    """Erstellt eine Flask-Mail-Message mit gerendertem HTML-Template.

    Args:
        subject:   Betreffzeile.
        recipient: Empfänger-Adresse.
        template:  Pfad zum Jinja2-Template (relativ zu templates/).
        **ctx:     Template-Kontext-Variablen.

    Returns:
        Fertige Message-Instanz.
    """
    msg = Message(subject=subject, recipients=[recipient])
    msg.body = "Bitte öffnen Sie die E-Mail in einem HTML-fähigen Client."
    msg.html = render_template(
        template,
        server_url=state.infos.schule.url,
        sprechtag=state.sprechtag,
        **ctx,
    )
    return msg


def _mask(addr: str) -> str:
    """Maskiert eine E-Mail-Adresse für Logging-Zwecke.

    Args:
        addr: E-Mail-Adresse.

    Returns:
        Maskierte E-Mail-Adresse (z.B. "ma***@example.com").
    """
    try:
        local, domain = addr.split("@", 1)
        # Mindestens 2 Zeichen zeigen, Rest maskieren
        visible = max(2, len(local) // 3)
        return f"{local[:visible]}***@{domain}"
    except Exception:
        return "***@***"
