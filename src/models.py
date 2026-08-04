# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations ------------------------------------------------------------------------------

from datetime import UTC, date, datetime
from secrets import token_urlsafe

from werkzeug.security import generate_password_hash

from src.extensions import db


# ------------------------------------------------------------------------------
# Konstanten
# ------------------------------------------------------------------------------

TOKEN_LENGTH = 12

# Admin / TSS
_DEFAULT_ADMIN_LOGIN = "admin"
_DEFAULT_ADMIN_PASSWORD = "admin"
_DEFAULT_TSS_PASSWORD = "tssbit"

# Mail Zugang
_DEFAULT_MAIL_SERVER = "smtp.office365.com"
_DEFAULT_MAIL_PORT = 587
_DEFAULT_MAIL_ENCRYPTION = "tls"
_DEFAULT_MAIL_SENDER = "paul@beatles.com"
_DEFAULT_MAIL_USER = "john@beatles.com"

# Sprechtag
_DEFAULT_SPRECHTAG_BEGINN = "16:00"
_DEFAULT_SPRECHTAG_ENDE = "19:00"
_DEFAULT_BERATER_DAUER = 15


def _make_token() -> str:
    """Erzeugt ein neues URL-sicheres Token. Als Callable für db.Column(default=) gedacht."""
    return token_urlsafe(TOKEN_LENGTH)


# ------------------------------------------------------------------------------
# Modelle
# ------------------------------------------------------------------------------


class ConfigSetting(db.Model):
    """Speichert alle zur Laufzeit änderbaren Anwendungseinstellungen."""

    __tablename__ = "config_setting"

    id = db.Column(db.Integer, primary_key=True)

    # Admin-Zugangsdaten
    admin_login = db.Column(db.String(100), nullable=False, default=_DEFAULT_ADMIN_LOGIN)
    admin_password = db.Column(
        db.String(255),  # vorher 100
        nullable=False,
        default=lambda: generate_password_hash(_DEFAULT_ADMIN_PASSWORD),
    )

    # TSS-Zugangsdaten
    tss_password = db.Column(
        db.String(255),  # vorher 100
        nullable=False,
        default=lambda: generate_password_hash(_DEFAULT_TSS_PASSWORD),
    )

    # Mail-Server-Einstellungen
    mail_server = db.Column(db.String(100), default=_DEFAULT_MAIL_SERVER)
    mail_port = db.Column(db.Integer, default=_DEFAULT_MAIL_PORT)
    mail_encryption = db.Column(db.String(10), default=_DEFAULT_MAIL_ENCRYPTION)
    mail_username = db.Column(db.String(100), default=_DEFAULT_MAIL_USER)
    # Fernet-Token sind >100 Zeichen → auf 255 erhöhen; None statt "" ist semantisch klarer
    mail_password = db.Column(db.String(255), nullable=True, default=None)
    mail_default_sender = db.Column(db.String(255), default=_DEFAULT_MAIL_SENDER)

    # Sprechtag-Einstellungen
    sprechtag_termin = db.Column(db.Date, default=date.today)
    sprechtag_beginn = db.Column(db.String(10), default=_DEFAULT_SPRECHTAG_BEGINN)
    sprechtag_ende = db.Column(db.String(10), default=_DEFAULT_SPRECHTAG_ENDE)


class Berater(db.Model):
    __tablename__ = "berater"

    berater_id = db.Column(db.Integer, primary_key=True)
    berater_nachname = db.Column(db.String(100), nullable=False)
    berater_vorname = db.Column(db.String(100), nullable=False)
    berater_mail = db.Column(db.String(255), nullable=False, index=True)  # Länge/Index optional erhöht
    berater_dauer = db.Column(db.Integer, default=_DEFAULT_BERATER_DAUER)
    berater_raum = db.Column(db.String(100), nullable=True)
    berater_will_mail = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(64), default=_make_token, unique=True, index=True)  # unique+index, Länge großzügiger

    buchungen = db.relationship("Buchung", backref="berater", lazy=True)

    def __repr__(self) -> str:
        return f"<Berater: {self.berater_nachname}, {self.berater_vorname}>"


class Buchung(db.Model):
    __tablename__ = "buchung"

    buchung_id = db.Column(db.Integer, primary_key=True)
    betrieb_name = db.Column(db.String(100), nullable=False)
    uhrzeit_id = db.Column(db.String(10), nullable=False)
    betrieb_mail = db.Column(db.String(255), nullable=True, index=True)  # Länge/Index optional erhöht
    bestaetigt = db.Column(db.Boolean, nullable=False, default=False)
    token = db.Column(db.String(64), default=_make_token, unique=True, index=True)
    erstellt_um = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    berater_id = db.Column(
        db.Integer,
        db.ForeignKey("berater.berater_id"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        db.UniqueConstraint("berater_id", "uhrzeit_id", name="_berater_zeit_uc"),
        # Optional: hilfreicher Kombi-Index für Aufräum-/Abfragejobs
        db.Index("ix_buchung_pending_cutoff", "bestaetigt", "erstellt_um"),
    )

    def __repr__(self) -> str:
        return f"<Buchung: {self.betrieb_name}, {self.uhrzeit_id}>"


def update_db() -> None:
    """Führt manuelle Datenbankmigrationen aus.

    Muss in _init_db() nach STATE.db.create_all() einkommentiert werden.
    Nach erfolgreicher Migration wieder auskommentieren.
    """
    from sqlalchemy import text

    from src.extensions import state

    new_att = "mail_encryption"

    for cls in ["ConfigSetting"]:
        try:
            state.db.session.execute(text(f"ALTER TABLE {cls} ADD COLUMN {new_att} String"))
            state.db.session.commit()
            print("update_db: Spalte '%s' zu '%s' hinzugefügt.", new_att, cls)
        except Exception as e:
            print("update_db: Fehler bei '%s': %s", cls, e)
