# ------------------------------------------------------------------------------
# Überprüft durch Claude 4
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
    AnyOf,
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
_EMAIL_LENGTH = Length(max=255)
_NAME_LENGTH = Length(max=100)
_PASSWORD_LENGTH_ADMIN = Length(min=4, max=15)
_PASSWORD_LENGTH_SMTP = Length(min=1, max=255)
_ID_VALIDATORS = [Optional(), Length(max=36), Regexp(r"^\d+$")]

_TIME_PLACEHOLDER = "z.B.: 16:00"


# ------------------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------------------
def email_validators() -> list:
    """Gibt eine neue Liste mit Standard-E-Mail-Validatoren zurück.

    Jeder Aufruf erzeugt eine eigene Instanz, um mutable shared state zu vermeiden.

    Returns:
        Liste mit DataRequired, Email und Length-Validator.
    """
    return [
        DataRequired(message="Bitte geben Sie eine E-Mail-Adresse ein."),
        Email(message="Bitte geben Sie eine gültige E-Mail-Adresse ein."),
        Length(max=255),
    ]


def normalize_whitespace(value: str | None) -> str | None:
    """Bereinigt einen String: trimmt Ränder und reduziert Leerzeichen auf eines.

    Args:
        value: Eingabewert aus dem Formularfeld.

    Returns:
        Bereinigter String oder None, wenn der Eingabewert None war.
    """
    if value is None:
        return None
    result = re.sub(r"\s+", " ", str(value).strip())
    return result or None  # "" → None → DataRequired() schlägt an


def validate_time_format(form: FlaskForm, field: Field) -> None:
    """Validiert, ob ein Feldwert dem Uhrzeitformat HH:MM entspricht.

    Args:
        form:  Das aufrufende FlaskForm.
        field: Das zu prüfende Formularfeld.

    Raises:
        ValidationError: Wenn der Wert kein gültiges HH:MM-Format hat.
    """
    if field.data in (None, ""):
        return  # von Optional() abgedeckt; ohne Optional nicht validieren
    try:
        datetime.strptime(str(field.data).strip(), "%H:%M")
    except ValueError as e:
        raise ValidationError(
            f"'{field.label.text}' enthält keine Uhrzeit. Bitte prüfe das Format (z. B.: 12:00)."
        ) from e


# ------------------------------------------------------------------------------
# Formulare
# ------------------------------------------------------------------------------


class ConfigForm(FlaskForm):
    """Konfigurationsformular für Admin-, Lehrkraft-, Mail- und Sprechtag-Einstellungen."""

    # Admin
    admin_login = StringField("Admin Login", validators=[Optional(), Length(min=3, max=100)])
    admin_password = PasswordField("Admin Passwort", validators=[Optional(), _PASSWORD_LENGTH_ADMIN])
    tss_password = PasswordField("Lehrkraft Passwort", validators=[Optional(), _PASSWORD_LENGTH_ADMIN])

    # Mail-Server (Variante mit mail_encryption)
    mail_server = StringField("Mail Server", validators=[Optional(), Length(max=255)])
    mail_port = IntegerField("Mail Port", validators=[Optional(), NumberRange(min=1, max=65535)])
    mail_encryption = SelectField(
        "Verschlüsselung",
        choices=[
            ("none", "Keine Verschlüsselung (Port 25)"),
            ("tls", "STARTTLS (Empfohlen, z. B. Port 587)"),
            ("ssl", "SSL / Implicit TLS (z. B. Port 465)"),
        ],
        validators=[DataRequired(), AnyOf(["none", "tls", "ssl"])],
        default="tls",
    )
    mail_username = StringField("Mail Benutzername", validators=[Optional(), _NAME_LENGTH])
    mail_password = PasswordField("Mail Passwort", validators=[Optional(), _PASSWORD_LENGTH_SMTP])
    mail_default_sender = StringField(
        "Standard Absender (E-Mail)",
        validators=[Optional(), Email(), _EMAIL_LENGTH],
        render_kw={"placeholder": "z.B.: schulserver@example.de"},
    )

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
        validators=email_validators(),
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
        validators=email_validators(),
        render_kw={"placeholder": "z.B.: john@beatles.de"},
    )
    submit = SubmitField("Termin buchen")


class BuchungShowForm(FlaskForm):
    """Formular für Aktionen auf der Buchungsübersicht (z. B. Bestätigen, Stornieren)."""

    buchung_token = HiddenField("buchung_token", validators=[Optional()], render_kw={"id": "buchung_token"})
    buchung_action = HiddenField("buchung_action", validators=[DataRequired()], render_kw={"id": "buchung_action"})
