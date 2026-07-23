import logging
from smtplib import SMTPAuthenticationError, SMTPException

from flask import render_template, request
from flask_mail import Message
from markupsafe import Markup

from src.extensions import state
from src.models import Berater, Buchung


logger = logging.getLogger(__name__)

_SUBJECT_BUCHER = "Bestätigung; Ausbildersprechtag"
_SUBJECT_BERATER = "Anmeldung; Ausbildersprechtag"
_SUBJECT_ANMELDUNG = "Registration; Ausbildersprechtag"


def __send_mail(msg: Message) -> bool:
    """Sendet eine Flask-Mail-Message.

    Returns:
        True bei erfolgreichem Versand, sonst False.
    """
    try:
        state.mail.send(msg)
        logger.debug("Mail gesendet an: %s", msg.recipients)
        return True

    except SMTPAuthenticationError:
        logger.error("Mail-Fehler: Authentifizierung am SMTP-Server fehlgeschlagen.")
    except SMTPException as e:
        logger.error("Allgemeiner SMTP-Fehler beim Mailversand: %s", e)
    except Exception as e:
        logger.exception("Unerwarteter Fehler beim E-Mail-Versand: %s", e)

    return False


def __build_mail_msg(subject: str, recipient: str, template: str, **ctx) -> Message:
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
    msg.html = render_template(template, server_url=f"https://{request.host}", **ctx)
    return msg


# ------------------------------------------------------------------------------
# Mail – öffentlich
# ------------------------------------------------------------------------------


def _send_mail_to_bucher(buchung: Buchung) -> tuple[Markup, str]:
    """Sendet eine Bestätigungsmail an den Bucher nach der Terminbuchung.

    Args:
        buchung: Die neu erstellte Buchung.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
    """
    msg = __build_mail_msg(
        _SUBJECT_BUCHER,
        buchung.betrieb_mail,
        "mail/mail_bucher.html",
        buchung=buchung,
        sprechtag=state.sprechtag,
    )
    sent = __send_mail(msg)

    if sent:
        logger.info("Mail verschickt an: %s (%s)", buchung.betrieb_name, buchung.betrieb_mail)
        info = (
            f"Die Mail wurde an {buchung.betrieb_mail} gesendet<br>"
            "Bitte bestätigen Sie Ihre Daten innerhalb von 2 Stunden"
        )
        result = "warning"
    else:
        logger.error("Mailversand fehlgeschlagen an: %s", buchung.betrieb_mail)
        info = f"Die Mail an {buchung.betrieb_mail} konnte nicht versandt werden."
        result = "error"

    return (Markup(info), result)


def _send_mail_to_berater(buchung: Buchung, delete: bool = False) -> None:
    """Benachrichtigt eine Lehrkraft per Mail über eine neue oder gelöschte Buchung.

    Wird nur gesendet, wenn ``berater.berater_will_mail`` True ist.

    Args:
        buchung: Die betroffene Buchung.
        delete:  True, wenn es sich um eine Stornierung handelt.
    """
    berater: Berater = buchung.berater
    if not berater.berater_will_mail:
        return

    msg = __build_mail_msg(
        _SUBJECT_BERATER,
        berater.berater_mail,
        "mail/mail_berater.html",
        buchung=buchung,
        sprechtag=state.sprechtag,
        delete=delete,
    )
    sent = __send_mail(msg)

    if sent:
        logger.info("Mail verschickt an: %s (%s)", berater.berater_nachname, berater.berater_mail)
    else:
        logger.error("Mailversand fehlgeschlagen an: %s", berater.berater_mail)


def _send_anmeldung_mail_to_berater(berater: Berater) -> tuple[Markup, str]:
    """Sendet eine Registrierungsbestätigung an eine neu angemeldete Lehrkraft.

    Args:
        berater: Die neu registrierte Lehrkraft.

    Returns:
        Tuple (Markup-Nachricht, Kategorie).
    """
    msg = __build_mail_msg(
        _SUBJECT_ANMELDUNG,
        berater.berater_mail,
        "mail/mail_anmeldungberater.html",
        berater=berater,
    )
    sent = __send_mail(msg)

    if sent:
        logger.info("Mail verschickt an: %s", berater.berater_mail)
        return (Markup(f"Die Mail wurde an {berater.berater_mail} gesendet"), "success")

    logger.error("Mailversand fehlgeschlagen an: %s", berater.berater_mail)
    return (Markup(f"Die Mail an {berater.berater_mail} konnte nicht versandt werden."), "error")
