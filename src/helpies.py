# ------------------------------------------------------------------------------
#  HILFSFUNKTIONEN
# ------------------------------------------------------------------------------

from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
import locale
import logging
from pathlib import Path
from smtplib import SMTPAuthenticationError, SMTPException

from cryptography.fernet import Fernet
from flask import Response, abort, flash, make_response, render_template, request
from flask_mail import Message
from markupsafe import Markup
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect
from weasyprint import CSS, HTML
from werkzeug.security import check_password_hash

from src.extensions import state
from src.models import Berater, Buchung, ConfigSetting


logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Konstanten
# ------------------------------------------------------------------------------

_IGNORE_CONFIG_KEYS = {"admin_login", "admin_password", "tss_login", "tss_password"}

_SUBJECT_BUCHER = "Bestätigung; Ausbildersprechtag"
_SUBJECT_BERATER = "Anmeldung; Ausbildersprechtag"
_SUBJECT_ANMELDUNG = "Registration; Ausbildersprechtag"

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

# Beispiel-Berater für den ersten App-Start
_DEFAULT_BERATER = [
    ("Koch", "Kay", "koch@tssbit.de"),
    ("Rass", "Markus", "koch@tssbit.de"),
    ("Tigges", "Ute", "koch@tssbit.de"),
    ("Dinstuhl", "Ralf", "koch@tssbit.de"),
    ("Kues", "Max", "koch@tssbit.de"),
    ("Brungs", "Thomas", "koch@tssbit.de"),
    ("Röder", "David", "koch@tssbit.de"),
    ("Recht", "Christian", "koch@tssbit.de"),
    ("Glatt", "Sebastian", "koch@tssbit.de"),
    ("Weber", "Marius", "koch@tssbit.de"),
    ("Marweld", "Torsten", "koch@tssbit.de"),
]


# ------------------------------------------------------------------------------
# Datenbank – Initialisierung
# ------------------------------------------------------------------------------


def _init_db() -> None:
    """Initialisiert die SQLite-Datenbank beim App-Start.

    Erstellt alle Tabellen, legt einen Standard-ConfigSetting-Eintrag an
    und befüllt die Berater-Tabelle mit Beispieldaten, falls sie leer ist.

    Args:
        state: Appstate-Objekt mit db, app und weiteren Laufzeit-Variablen.
    """

    try:
        Path(state.app.instance_path).mkdir(parents=True, exist_ok=True)

        # Import hier, damit Modelle registriert sind, bevor create_all() aufgerufen wird
        import src.models  # noqa: F401

        # Locale für Datumsformatierung setzen (Fallback auf C.UTF-8)
        locale.setlocale(locale.LC_TIME, "C.UTF-8")

        state.db.create_all()
        _seed_defaults(src.models)
        state.db.session.commit()

        logger.info("Datenbanktabellen erstellt/überprüft.")

    except SQLAlchemyError as e:
        logger.exception("Fehler beim Erstellen der Datenbanktabellen: %s", e)
        raise
    except Exception as e:
        logger.exception("_init_db -> Fehler bei der Datenbankinitialisierung: %s", e)


def _seed_defaults(models) -> None:
    """Legt Standard-Datenbankeinträge an, falls die Tabellen noch leer sind.

    Args:
        models: Das src.models-Modul (nach dem Import in _init_db).
    """
    if not models.ConfigSetting.query.first():
        state.db.session.add(models.ConfigSetting())

    if not Berater.query.first():
        state.db.session.add_all(
            Berater(berater_nachname=n, berater_vorname=v, berater_mail=m) for n, v, m in _DEFAULT_BERATER
        )


def _config_to_dict(cfg: ConfigSetting) -> dict:
    """Wandelt ein ConfigSetting-Objekt in ein Dictionary um (ohne 'id')."""
    mapper = inspect(cfg).mapper
    data = {c.key: getattr(cfg, c.key) for c in mapper.columns}
    data.pop("id", None)
    return data


def _load_defaults() -> None:
    """Lädt dynamische Konfigurationswerte aus der DB in die Flask-App-Konfiguration.

    Attributnamen des Modells werden in Großbuchstaben umgewandelt:
    ``sprechtag_beginn`` → ``app.config["SPRECHTAG_BEGINN"]``

    Passwort-Felder (admin_*, tss_*) werden übersprungen.
    Das Mail-Passwort wird vor dem Schreiben entschlüsselt.
    """
    try:
        cfg = _load_config()
        if cfg is None:
            logger.warning("_load_defaults: Keine Konfiguration in der Datenbank gefunden.")
            return

        data = _config_to_dict(cfg)

        state.app.config.update({key.upper(): value for key, value in data.items() if key not in _IGNORE_CONFIG_KEYS})

        state.app.config["MAIL_PASSWORD"] = _get_decrypted_mail_password(state.app.config["MAIL_PASSWORD"])

        state.set_sprechtag(
            tag=_formatiere_datum_deutsch(data["sprechtag_termin"]),
            beginn=data["sprechtag_beginn"],
            ende=data["sprechtag_ende"],
        )

    except Exception as e:
        logger.exception("Konnte App-Konfiguration nicht aus DB laden: %s", e)


def _load_config() -> ConfigSetting | None:
    """Lädt den ersten Konfigurationsdatensatz aus der Datenbank."""
    stmt = state.db.select(ConfigSetting).limit(1)
    return state.db.session.execute(stmt).scalar_one_or_none()


# ------------------------------------------------------------------------------
# Berater und Buchungen
# ------------------------------------------------------------------------------


def _delete_berater(berater: Berater) -> tuple[str, str]:
    """Löscht eine Lehrkraft und alle verbundenen Buchungen.

    Args:
        berater: Zu löschendes Berater-Objekt.

    Returns:
        Tuple (Nachricht, Kategorie) mit Kategorie in {"success", "error"}.
    """
    name = f"{berater.berater_vorname} {berater.berater_nachname}"
    try:
        state.db.session.delete(berater)
        state.db.session.commit()
        info = f"{name} und alle Termine gelöscht."
        logger.info(info)
        return (info, "success")

    except Exception as e:
        state.db.session.rollback()
        info = f"Fehler beim Löschen der Lehrkraft {name}: {e}"
        logger.error(info)
        return (info, "error")


def _get_berater_by_token_or_abort(berater_token: str | None = None) -> Berater:
    """Lädt einen Berater anhand seines Tokens oder bricht mit HTTP-Fehler ab.

    Args:
        berater_token: Token des gesuchten Beraters.

    Returns:
        Berater-Objekt zum Token.

    Raises:
        HTTPException (400): Wenn kein Token angegeben oder kein Berater gefunden.
        HTTPException (500): Bei einem Datenbankfehler.
    """
    if not berater_token:
        abort(make_response("bad request! (Kein Token angegeben)", 400))

    try:
        stmt = state.db.select(Berater).where(Berater.token == berater_token)
        berater = state.db.session.execute(stmt).scalar_one_or_none()

        if berater is None:
            logger.warning("Kein Berater mit Token '%s' gefunden.", berater_token)
            abort(make_response("bad request! (Der angegebene Token ist ungültig oder abgelaufen)", 400))

        return berater

    except Exception as e:
        logger.error("Fehler beim Laden des Beraters mit Token '%s': %s", berater_token, e)
        abort(make_response("bad request! (Fehler beim Laden des Beraters)", 500))


def _delete_old_orders() -> None:
    """Löscht nicht bestätigte Buchungen, die älter als die konfigurierte Wartezeit sind."""
    cutoff = datetime.now() - timedelta(minutes=state.app.config["SPRECHTAG_WARTEZEIT"])
    try:
        stmt = state.db.delete(Buchung).where(Buchung.bestaetigt.is_(False)).where(Buchung.erstellt_um < cutoff)
        result = state.db.session.execute(stmt)
        state.db.session.commit()
        logger.info("_delete_old_orders: %d alte Buchung(en) gelöscht.", result.rowcount)

    except Exception as e:
        state.db.session.rollback()
        logger.error("Fehler beim Löschen alter Buchungen: %s", e)


# ------------------------------------------------------------------------------
# Buchbare Zeiten
# ------------------------------------------------------------------------------


def _generiere_zeiten(dauer: int = 15) -> list[str]:
    """Erstellt eine Liste von Uhrzeiten von Sprechtag-Beginn bis Ende.

    Args:
        dauer: Dauer eines Termins in Minuten.

    Returns:
        Liste mit Uhrzeiten, z. B. ["16:00", "16:15", ...].
    """
    zeiten = []
    start = datetime.strptime(state.sprechtag.beginn, "%H:%M")
    ende = datetime.strptime(state.sprechtag.ende, "%H:%M")

    while start <= ende:
        zeiten.append(start.strftime("%H:%M"))
        start += timedelta(minutes=dauer)

    return zeiten


def _get_gebuchte_zeiten(berater_id: int) -> list[str]:
    """Gibt alle bereits gebuchten Uhrzeiten eines Beraters zurück.

    Args:
        berater_id: ID des Beraters.

    Returns:
        Liste gebuchter Uhrzeiten, z. B. ["16:30", "17:15"].
    """
    stmt = state.db.select(Buchung.uhrzeit_id).filter_by(berater_id=berater_id)
    return state.db.session.execute(stmt).scalars().all()


def _get_freie_zeiten_fuer_berater(berater_id: int) -> list[str]:
    """Gibt alle noch freien Termine eines Beraters zurück.

    Args:
        berater_id: ID des Beraters.

    Returns:
        Liste freier Uhrzeiten, z. B. ["16:00", "16:15", "16:45"].
    """
    stmt = state.db.select(Berater.berater_dauer).filter_by(berater_id=berater_id)
    dauer = state.db.session.execute(stmt).scalars().first()

    alle_zeiten = _generiere_zeiten(dauer)
    gebuchte_zeiten = set(_get_gebuchte_zeiten(berater_id))

    return [z for z in alle_zeiten if z not in gebuchte_zeiten]


# ------------------------------------------------------------------------------
# Mail – intern
# ------------------------------------------------------------------------------


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


# ------------------------------------------------------------------------------
# Verschlüsselung
# ------------------------------------------------------------------------------


def _get_decrypted_mail_password(mail_password: str) -> str:
    """Entschlüsselt das Mail-Passwort für den SMTP-Versand.

    Args:
        mail_password: Verschlüsseltes Passwort aus der Datenbank.

    Returns:
        Entschlüsseltes Passwort als String, oder "" bei fehlendem Key/Passwort.
    """
    secret_key = state.app.config.get("ENCRYPTION_KEY")
    if not secret_key or not mail_password:
        return ""
    return Fernet(secret_key.encode()).decrypt(mail_password.encode()).decode()


def _encrypt_password(plain: str, key: str) -> str:
    fernet = Fernet(key.encode())
    return fernet.encrypt(plain.encode()).decode()


# ------------------------------------------------------------------------------
# Diverses
# ------------------------------------------------------------------------------


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


def _formatiere_datum_deutsch(dt: datetime) -> str:
    """Formatiert ein datetime-Objekt locale-unabhängig auf Deutsch.

    Args:
        dt: Zu formatierendes datetime-Objekt.

    Returns:
        Deutsches Datum, z. B. "Freitag, 25. Dezember 2026".
    """
    return f"{_WOCHENTAGE[dt.weekday()]}, {dt.day}. {_MONATE[dt.month]} {dt.year}"


def _flash_form_errors(context: str, form) -> None:
    logger.error("Formular-Fehler in %s: %s", context, form.errors)
    texts = [msg for messages in form.errors.values() for msg in messages]
    flash(Markup("<br>".join(texts)), "error")


# ------------------------------------------------------------------------------
# Authentifizierung – intern
# ------------------------------------------------------------------------------


def __check_auth_and_get_type(username: str, password: str) -> str | None:
    """Prüft Zugangsdaten gegen die Datenbank und gibt den Login-Typ zurück.

    Args:
        username: Benutzername aus der HTTP-Basic-Auth-Anfrage.
        password: Klartext-Passwort aus der HTTP-Basic-Auth-Anfrage.

    Returns:
        "admin" | "tss" bei Erfolg, None bei ungültigen Daten.
    """

    config = state.db.session.execute(state.db.select(ConfigSetting)).scalars().first()
    if not config:
        return None

    if username == config.admin_login and check_password_hash(config.admin_password, password):
        return "admin"

    if username == config.tss_login and check_password_hash(config.tss_password, password):
        return "tss"

    return None


def __authenticate() -> Response:
    """Gibt eine 401-Response zurück, die den Browser zur Eingabe von Zugangsdaten auffordert."""
    return Response(
        "Login erforderlich",
        401,
        {"WWW-Authenticate": 'Basic realm="Login erforderlich"'},
    )


# ------------------------------------------------------------------------------
# Authentifizierung – Dekorator
# ------------------------------------------------------------------------------


def _requires_auth(allowed_login_types: str | list | tuple):
    """Dekorator-Fabrik: Schützt eine Route auf bestimmte Login-Typen.

    Args:
        allowed_login_types: Erlaubter Typ oder Liste von Typen ("admin", "tss").

    Usage:
        @_requires_auth("admin")
        @_requires_auth(["admin", "tss"])
    """
    if not isinstance(allowed_login_types, (list, tuple, frozenset)):
        allowed_login_types = [allowed_login_types]

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth:
                return __authenticate()

            login_type = __check_auth_and_get_type(auth.username, auth.password)
            if login_type in allowed_login_types:
                return f(*args, **kwargs)

            return __authenticate()

        return decorated

    return decorator


# ------------------------------------------------------------------------------
# DB-Migration – NUR MANUELL AKTIVIEREN
# ------------------------------------------------------------------------------


def update_db() -> None:
    """Führt manuelle Datenbankmigrationen aus.

    Muss in _init_db() nach state.db.create_all() einkommentiert werden.
    Nach erfolgreicher Migration wieder auskommentieren.
    """
    new_att = "raum"

    for cls in ["Berater"]:
        try:
            state.db.session.execute(text(f"ALTER TABLE {cls} ADD COLUMN {new_att} String"))
            state.db.session.commit()
            logger.info("update_db: Spalte '%s' zu '%s' hinzugefügt.", new_att, cls)
        except Exception as e:
            logger.warning("update_db: Fehler bei '%s': %s", cls, e)
