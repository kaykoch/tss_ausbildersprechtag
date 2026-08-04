# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

import logging
from smtplib import SMTPAuthenticationError, SMTPException
from typing import Literal

from flask import render_template
from flask_mail import Message
from markupsafe import Markup

from src.extensions import state
from src.models import Berater, Buchung


logger = logging.getLogger(__name__)

_SUBJECT_BUCHER = "Bestätigung: Ausbildersprechtag"
_SUBJECT_BERATER = "Anmeldung: Ausbildersprechtag"
_SUBJECT_STORNO = "Storno: Ausbildersprechtag"
_SUBJECT_ANMELDUNG = "Registrierung: Ausbildersprechtag"


def _send_mail(msg: Message) -> bool:
    """Sendet eine Flask-Mail-Message.

    Returns:
        True bei erfolgreichem Versand, sonst False.
    """
    try:
        # state.mail.send(msg)
        print(msg.html)
        logger.debug("Mail gesendet an: %s", msg.recipients)
        return True

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
    try:
        local, domain = addr.split("@", 1)
        return f"{local[:2]}***@{domain}"
    except Exception:
        return "***"


# ------------------------------------------------------------------------------
# Mail – öffentlich
# ------------------------------------------------------------------------------


def send_mail_to_bucher(buchung: Buchung) -> tuple[Markup, Literal["success", "warning", "error"]]:
    """Sendet eine Bestätigungsmail an den Bucher nach der Terminbuchung.

    Args:
        buchung: Die neu erstellte Buchung.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
    """
    msg = _build_mail_msg(
        _SUBJECT_BUCHER,
        buchung.betrieb_mail,
        "mail/mail_bucher.html",
        buchung=buchung,
        time_to_wait=state.infos.sprechtag.sprechtag_wartezeit,
    )
    sent = _send_mail(msg)
    masked_mail = _mask(buchung.betrieb_mail)
    if sent:
        logger.info("Mail verschickt an: %s (%s)", buchung.betrieb_name, masked_mail)
        info = (
            f"Die Mail wurde an {masked_mail} gesendet<br>Bitte bestätigen Sie Ihre Daten innerhalb von "
            f"{state.infos.sprechtag.sprechtag_wartezeit} Minuten"
        )
        result = "warning"
    else:
        logger.error("Mailversand fehlgeschlagen an: %s (%s)", buchung.betrieb_name, masked_mail)
        info = f"Die Mail an {buchung.betrieb_mail} konnte nicht versandt werden."
        result = "error"

    return (Markup(info), result)


def send_mail_to_berater(buchung: dict | Buchung, berater: Berater, delete: bool = False) -> None:
    """Benachrichtigt eine Lehrkraft per Mail über eine neue oder stornierte Buchung.

    Wird nur gesendet, wenn ``berater.berater_will_mail`` True ist,

    Args:
        buchung: Die betroffene Buchung.
        berater: Berater der Buchung
        delete:  True, wenn es sich um eine Stornierung handelt

    Args:
        buchung (dict | Buchung): Die betroffene Buchung, (Kopie der Buchung als dict,
                wenn sie storniert, also gelöscht wurde)
        delete (bool, optional): True, wenn es sich um eine Stornierung handelt. Defaults to False.
    """
    if not berater.berater_will_mail:
        return

    subject = _SUBJECT_STORNO if delete else _SUBJECT_BERATER
    msg = _build_mail_msg(
        subject,
        berater.berater_mail,
        "mail/mail_berater.html",
        buchung=buchung,
        berater=berater,
        delete=delete,
    )
    sent = _send_mail(msg)

    if sent:
        logger.info("Mail verschickt an: %s (%s)", berater.berater_nachname, berater.berater_mail)
    else:
        logger.error("Mailversand fehlgeschlagen an: %s", berater.berater_mail)


def send_anmeldung_mail_to_berater(berater: Berater) -> tuple[Markup, Literal["success", "warning", "error"]]:
    """Sendet eine Registrierungsbestätigung an eine neu angemeldete Lehrkraft.

    Args:
        berater: Die neu registrierte Lehrkraft.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
    """
    msg = _build_mail_msg(
        _SUBJECT_ANMELDUNG,
        berater.berater_mail,
        "mail/mail_anmeldungberater.html",
        berater=berater,
    )
    sent = _send_mail(msg)
    masked_mail = _mask(berater.berater_mail)
    if sent:
        logger.info("Mail verschickt an: %s", berater.berater_mail)
        return (Markup(f"Die Mail wurde an {masked_mail} gesendet"), "success")

    logger.error("Mailversand fehlgeschlagen an: %s", berater.berater_mail)
    return (Markup(f"Die Mail an {masked_mail} konnte nicht versandt werden."), "error")
