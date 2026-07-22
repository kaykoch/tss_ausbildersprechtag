# ------------------------------------------------------------------------------
#  FORMULARE
# ------------------------------------------------------------------------------

from datetime import datetime
import re

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    EmailField,
    Field,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)


# ------------------------------------------------------------------------------
# Konstanten
# ------------------------------------------------------------------------------

_EMAIL_VALIDATOR = Email(message="Bitte geben Sie eine gültige E-Mail-Adresse ein.")
_EMAIL_LENGTH = Length(max=100)
_NAME_LENGTH = Length(max=100)
_PASSWORD_LENGTH = Length(min=4, max=15)
_ID_VALIDATORS = [Optional(), Length(max=36), Regexp(r"^\d+$")]

_TIME_PLACEHOLDER = "z.B.: 16:00h"


# ------------------------------------------------------------------------------
# Filter
# ------------------------------------------------------------------------------


def normalize_whitespace(value: str | None) -> str:
    """Bereinigt einen String: trimmt Ränder und reduziert Leerzeichen auf eines.

    Args:
        value: Eingabewert aus dem Formularfeld.

    Returns:
        Bereinigter String, oder "" wenn der Eingabewert None war.
    """
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


# ------------------------------------------------------------------------------
# Validatoren
# ------------------------------------------------------------------------------


def validate_time_format(form: FlaskForm, field: Field) -> None:
    """Validiert, ob ein Feldwert dem Uhrzeitformat HH:MM entspricht.

    Args:
        form:  Das aufrufende FlaskForm.
        field: Das zu prüfende Formularfeld.

    Raises:
        ValidationError: Wenn der Wert kein gültiges HH:MM-Format hat.
    """
    try:
        datetime.strptime(field.data.strip(), "%H:%M")
    except ValueError as e:
        raise ValidationError(
            f"'{field.label.text}' enthält keine Uhrzeit. Bitte prüfe das Format (z. B.: 12:00)."
        ) from e


# ------------------------------------------------------------------------------
# Formulare
# ------------------------------------------------------------------------------


class ConfigForm(FlaskForm):
    """Konfigurationsformular für Admin-, Lehrkraft-, Mail- und Sprechtag-Einstellungen."""

    # Admin-Zugangsdaten
    admin_login = StringField("Admin Login", validators=[Optional(), _PASSWORD_LENGTH])
    admin_password = PasswordField("Admin Passwort", validators=[Optional(), _PASSWORD_LENGTH])

    # Lehrkraft-Zugangsdaten
    tss_login = StringField("Lehrkraft Login", validators=[Optional(), _PASSWORD_LENGTH])
    tss_password = PasswordField("Lehrkraft Passwort", validators=[Optional(), _PASSWORD_LENGTH])

    # Mail-Server
    mail_server = StringField("Mail Server", validators=[Optional(), Length(max=255)])
    mail_port = IntegerField("Mail Port", validators=[Optional(), NumberRange(min=1, max=65535)])
    mail_use_ssl = BooleanField("Nutze SSL", validators=[Optional()])
    mail_use_tls = BooleanField("Nutze TLS", validators=[Optional()])
    mail_username = StringField("Mail Benutzername", validators=[Optional(), Length(max=255)])
    mail_password = PasswordField("Mail Passwort", validators=[Optional(), Length(max=255)])
    mail_default_sender = StringField("Standard Absender (E-Mail)", validators=[Optional(), Length(max=320)])

    # Sprechtag
    sprechtag_termin = DateField(
        "Termin",
        format="%Y-%m-%d",
        validators=[DataRequired(message="Bitte den Termin des Ausbildersprechtages eingeben.")],
        render_kw={"title": "An welchem Tag findet der Ausbildersprechtag statt?"},
    )
    sprechtag_beginn = StringField(
        "Uhrzeit, Anfang",
        filters=[normalize_whitespace],
        validators=[Optional(), validate_time_format],
        render_kw={
            "placeholder": _TIME_PLACEHOLDER,
            "title": "Um welche Uhrzeit findet der erste Termin statt?",
        },
    )
    sprechtag_ende = StringField(
        "Uhrzeit, Ende",
        filters=[normalize_whitespace],
        validators=[Optional(), validate_time_format],
        render_kw={
            "placeholder": _TIME_PLACEHOLDER,
            "title": "Um welche Uhrzeit findet der letzte Termin statt?",
        },
    )
    sprechtag_wartezeit = IntegerField(
        "Wartezeit bis zum Löschen",
        validators=[Optional(), NumberRange(min=15, max=24 * 60)],
        render_kw={
            "placeholder": "z.B.: 90 (min: 15; max: 1440 → 24h)",
            "title": "Anzahl an Minuten, nach denen eine nicht bestätigte Anmeldung gelöscht wird.",
        },
    )
    submit = SubmitField("Einstellungen speichern")


class BeraterForm(FlaskForm):
    """Formular zum Erstellen und Bearbeiten eines Beraters."""

    berater_id = HiddenField("ID", validators=_ID_VALIDATORS)

    berater_vorname = StringField(
        "Vorname",
        filters=[normalize_whitespace],
        validators=[DataRequired(), _NAME_LENGTH],
        render_kw={"placeholder": "z.B.: John"},
    )
    berater_nachname = StringField(
        "Nachname",
        filters=[normalize_whitespace],
        validators=[DataRequired(), _NAME_LENGTH],
        render_kw={"placeholder": "z.B.: Lennon"},
    )
    berater_raum = StringField(
        "Raum",
        filters=[normalize_whitespace],
        validators=[DataRequired(), Length(max=20)],
        render_kw={
            "placeholder": "z.B.: R109",
            "title": "Der Raum, in dem Sie den/die Ausbilder:in erwarten.",
        },
    )
    berater_mail = EmailField(
        "E-Mail",
        filters=[normalize_whitespace],
        validators=[Optional(), _EMAIL_VALIDATOR, _EMAIL_LENGTH],
        render_kw={"placeholder": "z.B.: john@beatles.de"},
    )
    berater_will_mail = BooleanField(
        "Benachrichtigung per Mail",
        default=False,
        render_kw={
            "title": (
                "Ich bin damit einverstanden, dass eine Benachrichtigung an mich "
                "gesendet wird, sobald eine Anmeldung erfolgt."
            )
        },
    )
    berater_dauer = IntegerField(
        "Dauer eines Termins",
        validators=[Optional(), NumberRange(min=10, max=45)],
        render_kw={
            "placeholder": "z.B.: 15 (min: 10 – max: 45)",
            "title": "Die Dauer in Minuten, für die ein Termin gebucht werden kann.",
        },
    )
    berater_token = HiddenField(
        "berater_token",
        validators=[Optional()],
        render_kw={"id": "berater_token"},
    )
    submit_berater = SubmitField("Lehrkraft erstellen / aktualisieren")

    def __repr__(self) -> str:
        return "<BeraterForm>"


class BeraterShowForm(FlaskForm):
    """Formular für Aktionen auf der Beraterliste (z. B. Löschen, Bearbeiten)."""

    action = HiddenField("Action", validators=[DataRequired()], render_kw={"id": "form_action"})
    token = HiddenField("token", validators=[DataRequired()], render_kw={"id": "form_token"})


class BuchungForm(FlaskForm):
    """Formular zur Buchung eines Sprechtag-Termins."""

    buchung_id = HiddenField("buchung_id", validators=_ID_VALIDATORS)

    berater_id = SelectField(
        "Mit wem möchten Sie sprechen?",
        choices=[("", "Bitte wählen...")],
        validators=[DataRequired()],
        render_kw={"title": "Bitte wählen Sie den Berater aus."},
    )
    uhrzeit_id = SelectField(
        "Wann möchten Sie mit der Lehrkraft sprechen?",
        validators=[DataRequired("Bitte wählen Sie eine Uhrzeit.")],
        render_kw={"title": "Bitte wählen Sie eine Uhrzeit aus."},
    )
    betrieb_name = StringField(
        "Betrieb (Ausbilder) / Erziehungsberechtigte",
        filters=[normalize_whitespace],
        validators=[DataRequired(), _NAME_LENGTH],
        render_kw={"placeholder": "z.B.: Apple Records Ltd. (George Martin)"},
    )
    betrieb_mail = EmailField(
        "E-Mail",
        filters=[normalize_whitespace],
        validators=[Optional(), _EMAIL_VALIDATOR, _EMAIL_LENGTH],
        render_kw={"placeholder": "z.B.: john@beatles.de"},
    )
    submit = SubmitField("Termin buchen")


class BuchungShowForm(FlaskForm):
    """Formular für Aktionen auf der Buchungsübersicht (z. B. Bestätigen, Stornieren)."""

    buchung_token = HiddenField("buchung_token", validators=[Optional()], render_kw={"id": "buchung_token"})
    buchung_action = HiddenField("buchung_action", validators=[DataRequired()], render_kw={"id": "buchung_action"})
