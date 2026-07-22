# ------------------------------------------------------------------------------
#  DATENBANK-MODELLE
# ------------------------------------------------------------------------------

from datetime import date, datetime
from secrets import token_urlsafe

from werkzeug.security import generate_password_hash

from src.extensions import db
from src.forms import BeraterForm


# ------------------------------------------------------------------------------
# Konstanten
# ------------------------------------------------------------------------------

TOKEN_LENGTH = 12

# Admin / TSS
DEFAULT_ADMIN_LOGIN = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
DEFAULT_TSS_LOGIN = "tssbit"
DEFAULT_TSS_PASSWORD = "tssbit"

# Mail-Server
DEFAULT_MAIL_SERVER = "smtp.office365.com"
DEFAULT_MAIL_PORT = 587
DEFAULT_MAIL_USER = "john@beatles.com"
DEFAULT_MAIL_SENDER = "paul@beatles.com"

# Sprechtag
DEFAULT_SPRECHTAG_BEGINN = "16:00"
DEFAULT_SPRECHTAG_ENDE = "19:00"
DEFAULT_SPRECHTAG_WARTEZEIT = 90
DEFAULT_BERATER_DAUER = 15


def _make_token() -> str:
    """Erzeugt ein neues URL-sicheres Token. Als Callable für db.Column(default=) gedacht."""
    return token_urlsafe(TOKEN_LENGTH)


# ------------------------------------------------------------------------------
# Modelle
# ------------------------------------------------------------------------------


class ConfigSetting(db.Model):
    """Speichert alle zur Laufzeit änderbaren Anwendungseinstellungen."""

    __tablename__ = "ConfigSetting"

    id = db.Column(db.Integer, primary_key=True)

    # Admin-Zugangsdaten
    admin_login = db.Column(db.String(100), nullable=False, default=DEFAULT_ADMIN_LOGIN)
    admin_password = db.Column(
        db.String(255),
        nullable=False,
        default=lambda: generate_password_hash(DEFAULT_ADMIN_PASSWORD),
    )

    # TSS-Zugangsdaten
    tss_login = db.Column(db.String(100), nullable=False, default=DEFAULT_TSS_LOGIN)
    tss_password = db.Column(
        db.String(255),
        nullable=False,
        default=lambda: generate_password_hash(DEFAULT_TSS_PASSWORD),
    )

    # Mail-Server-Einstellungen
    mail_server = db.Column(db.String(255), default=DEFAULT_MAIL_SERVER)
    mail_port = db.Column(db.Integer, default=DEFAULT_MAIL_PORT)
    mail_use_tls = db.Column(db.Boolean, default=True)
    mail_use_ssl = db.Column(db.Boolean, default=False)
    mail_default_sender = db.Column(db.String(255), default=DEFAULT_MAIL_SENDER)
    mail_username = db.Column(db.String(255), default=DEFAULT_MAIL_USER)
    # muss für neue DB Null sein und erst später über Admin-Menü belegt werden
    mail_password = db.Column(db.String(255), nullable=True)

    # Sprechtag-Einstellungen
    sprechtag_termin = db.Column(db.Date, default=date.today)
    sprechtag_beginn = db.Column(db.String(6), default=DEFAULT_SPRECHTAG_BEGINN)
    sprechtag_ende = db.Column(db.String(6), default=DEFAULT_SPRECHTAG_ENDE)
    sprechtag_wartezeit = db.Column(db.Integer, default=DEFAULT_SPRECHTAG_WARTEZEIT)


class Berater(db.Model):
    """Repräsentiert eine Person, mit der ein Termin gebucht werden kann."""

    __tablename__ = "berater"

    berater_id = db.Column(db.Integer, primary_key=True)
    berater_nachname = db.Column(db.String(100), nullable=False)
    berater_vorname = db.Column(db.String(100), nullable=False)
    berater_mail = db.Column(db.String(100), nullable=False)
    berater_dauer = db.Column(db.Integer, default=DEFAULT_BERATER_DAUER)
    berater_raum = db.Column(db.String(100), nullable=True)
    berater_will_mail = db.Column(db.Boolean, default=False)
    # WICHTIG: Callable (ohne Klammern) übergeben, damit es bei jedem Insert neu berechnet wird
    token = db.Column(db.String(32), default=_make_token)

    # Verknüpfung zur Buchungstabelle (Eins-zu-Viele)
    buchungen = db.relationship("Buchung", backref="berater", lazy=True)

    def __repr__(self) -> str:
        return f"<Berater: {self.berater_nachname}, {self.berater_vorname}>"


class Buchung(db.Model):
    """Repräsentiert einen gebuchten Termin beim Sprechtag."""

    __tablename__ = "buchung"

    buchung_id = db.Column(db.Integer, primary_key=True)
    betrieb_name = db.Column(db.String(100), nullable=False)
    uhrzeit_id = db.Column(db.String(5), nullable=False)
    betrieb_mail = db.Column(db.String(100), nullable=True)
    bestaetigt = db.Column(db.Boolean, nullable=False, default=False)
    # WICHTIG: Callable (ohne Klammern) übergeben, damit es bei jedem Insert neu berechnet wird
    token = db.Column(db.String(32), default=_make_token)
    erstellt_um = db.Column(db.DateTime, default=datetime.now)

    # Fremdschlüssel: Welcher Berater wurde gebucht?
    berater_id = db.Column(
        db.Integer,
        db.ForeignKey("berater.berater_id"),
        nullable=False,
    )

    # Verhindert Doppelbuchung desselben Beraters zur selben Zeit
    __table_args__ = (db.UniqueConstraint("berater_id", "uhrzeit_id", name="_berater_zeit_uc"),)

    def __repr__(self) -> str:
        return f"<Buchung: {self.betrieb_name}>"


# ------------------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------------------


def _get_berater_liste() -> list[Berater]:
    """Lädt alle Berater aus der DB und rendert die Übersichtsseite."""

    stmt = db.select(Berater).order_by(
        Berater.berater_nachname,
        Berater.berater_vorname,
    )

    return db.session.execute(stmt).scalars().all()


def _create_berater(form: BeraterForm) -> Berater:
    berater = Berater()
    form.populate_obj(berater)
    db.session.add(berater)
    db.session.commit()
    return berater


def _update_berater(form: BeraterForm, berater: Berater) -> None:
    form.populate_obj(berater)
    db.session.commit()


def _get_buchung_by_token(token: str) -> Buchung | None:
    stmt = db.select(Buchung).where(Buchung.token == token)
    return db.session.execute(stmt).scalars().first()


def _delete_buchung(buchung: Buchung) -> None:
    db.session.delete(buchung)
    db.session.commit()
