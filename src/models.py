# ------------------------------------------------------------------------------
# Überprüft durch  Claude Haiku
# ------------------------------------------------------------------------------

from __future__ import annotations

from datetime import UTC, date, datetime
from secrets import token_urlsafe

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
_DEFAULT_SPRECHTAG_STORNO = 30


def _make_token() -> str:
    """Erzeugt ein neues URL-sicheres Token.

    Wird als Callable für `mapped_column(default=_make_token)` verwendet,
    um bei jeder neuen Instanz ein eindeutiges Token zu generieren.

    Returns:
        URL-sicheres Token (Base64-kodiert, Länge: TOKEN_LENGTH).
    """
    return token_urlsafe(TOKEN_LENGTH)


# ------------------------------------------------------------------------------
# Modelle
# ------------------------------------------------------------------------------


class ConfigSetting(db.Model):
    """Speichert alle zur Laufzeit änderbaren Anwendungseinstellungen."""

    __tablename__ = "config_setting"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Admin-Zugangsdaten
    admin_login: Mapped[str] = mapped_column(String(100), nullable=False, default=_DEFAULT_ADMIN_LOGIN)
    admin_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default=lambda: generate_password_hash(_DEFAULT_ADMIN_PASSWORD),
    )

    # TSS-Zugangsdaten
    tss_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default=lambda: generate_password_hash(_DEFAULT_TSS_PASSWORD),
    )

    # Mail-Server-Einstellungen
    mail_server: Mapped[str] = mapped_column(String(100), default=_DEFAULT_MAIL_SERVER)
    mail_port: Mapped[int] = mapped_column(Integer, default=_DEFAULT_MAIL_PORT)
    mail_encryption: Mapped[str] = mapped_column(String(10), default=_DEFAULT_MAIL_ENCRYPTION)
    mail_username: Mapped[str] = mapped_column(String(100), default=_DEFAULT_MAIL_USER)
    mail_password: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    mail_default_sender: Mapped[str] = mapped_column(String(255), default=_DEFAULT_MAIL_SENDER)

    # Sprechtag-Einstellungen
    sprechtag_termin: Mapped[date] = mapped_column(Date, default=date.today)
    sprechtag_beginn: Mapped[str] = mapped_column(String(10), default=_DEFAULT_SPRECHTAG_BEGINN)
    sprechtag_ende: Mapped[str] = mapped_column(String(10), default=_DEFAULT_SPRECHTAG_ENDE)
    sprechtag_storno: Mapped[int] = mapped_column(Integer, default=_DEFAULT_SPRECHTAG_STORNO)

    # Sonstiges
    log_level: Mapped[str] = mapped_column(String(10), default="WARNING")

    def __repr__(self) -> str:
        return f"<ConfigSetting: id={self.id}>"


class Lehrkraft(db.Model):
    """Speichert Informationen über Lehrkräfte/Lehrkraft."""

    __tablename__ = "lehrkraft"

    # Primary Key
    lehrkraft_id: Mapped[int] = mapped_column(primary_key=True)

    # Required String Fields
    lehrkraft_nachname: Mapped[str] = mapped_column(String(100), nullable=False)
    lehrkraft_vorname: Mapped[str] = mapped_column(String(100), nullable=False)
    lehrkraft_mail: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Optional Fields with Defaults
    lehrkraft_dauer: Mapped[int] = mapped_column(Integer, default=_DEFAULT_BERATER_DAUER)
    lehrkraft_raum: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lehrkraft_will_mail: Mapped[bool] = mapped_column(Boolean, default=False)

    # Token Field
    lehrkraft_token: Mapped[str] = mapped_column(String(64), default=_make_token, unique=True, index=True)

    # Relationship (mit Cascade-Delete)
    buchungen: Mapped[list[Buchung]] = relationship(
        "Buchung",
        back_populates="lehrkraft",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Lehrkraft: {self.lehrkraft_nachname}, {self.lehrkraft_vorname}>"

    @property
    def full_name(self) -> str:
        """Gibt den vollständigen Namen des Lehrkrafts zurück.

        Returns:
            Formatierter Name (z.B. "Lennon, John").
        """
        return f"{self.lehrkraft_nachname}, {self.lehrkraft_vorname}"


class Buchung(db.Model):
    """Speichert Buchungen für Sprechtag-Termine.

    Attributes:
        buchung_id: Eindeutige ID der Buchung.
        betrieb_name: Name des Betriebs/der Schule.
        uhrzeit_id: Zeitslot als String (z.B. "15:30").
        betrieb_mail: E-Mail-Adresse des Betriebs (optional).
        bestaetigt: Bestätigungsstatus der Buchung.
        token: Eindeutiges Token für externe Zugriffe.
        created_at: Zeitstempel der Erstellung (mit Timezone).
        lehrkraft_id: Fremdschlüssel zum Lehrkraft.
        lehrkraft: Beziehung zum Lehrkraft-Objekt.
    """

    __tablename__ = "buchung"

    # Primary Key
    buchung_id: Mapped[int] = mapped_column(primary_key=True)

    # Required String Fields
    betrieb_name: Mapped[str] = mapped_column(String(100), nullable=False)
    uhrzeit_id: Mapped[str] = mapped_column(String(10), nullable=False)  # Format: "HH:MM"

    # Optional Fields
    betrieb_mail: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Boolean with Default
    bestaetigt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Token Field
    buchung_token: Mapped[str] = mapped_column(String(64), default=_make_token, unique=True, index=True)

    # DateTime with Timezone
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )

    # Foreign Key (mit Cascade-Delete)
    lehrkraft_id: Mapped[int] = mapped_column(
        ForeignKey("lehrkraft.lehrkraft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship (bidirektional mit Lehrkraft)
    lehrkraft: Mapped[Lehrkraft] = relationship("Lehrkraft", back_populates="buchungen")

    # Table Arguments: Constraints und Indices
    __table_args__ = (
        UniqueConstraint("lehrkraft_id", "uhrzeit_id", name="_lehrkraft_zeit_uc"),
        Index("ix_buchung_pending_cutoff", "bestaetigt", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Buchung: {self.betrieb_name}, {self.uhrzeit_id}>"

    def is_pending(self) -> bool:
        """Prüft, ob die Buchung noch nicht bestätigt ist.

        Returns:
            True, wenn bestaetigt=False, sonst False.
        """
        return not self.bestaetigt

    @property
    def full_name(self) -> str:
        """Gibt den vollständigen Namen des Lehrkrafts zurück.

        Returns:
            Formatierter Name (z.B. "Lennon, John").
        """
        return f"{self.betrieb_name}, {self.betrieb_mail}"


def update_db() -> None:
    """Führt manuelle Datenbankmigrationen aus.

    Muss in _init_db() nach state.db.create_all() einkommentiert werden.
    Nach erfolgreicher Migration wieder auskommentieren.

    Example:
        # In app.py _init_db():
        # state.db.create_all()
        # update_db()  # ← Einkommentieren
    """
    from sqlalchemy import text

    from src.extensions import state

    new_att = "mail_encryption"

    for cls in ["ConfigSetting"]:
        try:
            state.db.session.execute(text(f"ALTER TABLE {cls} ADD COLUMN {new_att} String"))
            state.db.session.commit()
            print(f"update_db: Spalte '{new_att}' zu '{cls}' hinzugefügt.")
        except Exception as e:
            print(f"update_db: Fehler bei '{cls}': {e}")
