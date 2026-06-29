from dataclasses import dataclass
import logging
from pathlib import Path

from flask import Flask
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()  # noch ohne App
mail = Mail()  # noch ohne App
logger = logging.getLogger(__name__)


@dataclass
class Sprechtagdata:
    """
    Repräsentiert eine Datenstruktur aus drei Strings mit dataclasses.
    """

    tag: str
    beginn: str
    ende: str


class AppState:
    """verkörpert Zustände, die während der Laufzeit gespeichert werden müssen"""

    def __init__(self):
        # Die Wichtigsten

        self.db: SQLAlchemy = db
        self.mail = mail
        self.app: Flask = None

        # Pfade zu den verschiedenen Dateien
        self.datafolder: Path = Path(__file__).resolve().parent / "data/"
        self.staticfolder: Path = Path(__file__).resolve().parent / "static/"
        self.sprechtag: dataclass | None = None
        self.logfile = self.__ensure_file_exists(self.datafolder, "logfile.log")

    def set_sprechtag(self, tag: str, beginn: str, ende: str):
        self.sprechtag = Sprechtagdata(
            tag,
            beginn,
            ende,
        )

    def set_data(self, app, **kwargs):
        """setzt die Pfade der Dateien und initialisiert die Schulformen

        Args:
            datafolder (path): absoluter Pfad zum Ordner der Dateien

            **kwargs: mehrere Dateinamen

                erlaubte keys sind:
                klassenfile (str): Name der CSV-Datei mit den Klassennamen für den Upload
                prototype_klassen (str): Name der CSV-Datei im korrekten Format für den Upload
        """

        self.app: Flask = app
        """
        for attr_name, filename in kwargs.items():
            # Alle übergebenden Werte
            if hasattr(self, attr_name):
                # Es gibt den Schlüssel hier in der Class
                file_path = self.__ensure_file_exists(self.datafolder, filename)
                setattr(self, attr_name, file_path)
                logger.info(f"Datei: {attr_name} vorhanden")
        """

    def __ensure_file_exists(self, directory: str, filename: str) -> Path:
        # 1. Sicherstellen, dass directory ein String ist (falls None übergeben wurde)
        directory_str = directory or "."

        # 2. Pfad-Objekt erstellen
        filepath = Path(directory_str) / filename

        try:
            # 3. Elternverzeichnis erstellen, falls es nicht existiert
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # 4. Datei erstellen (tut nichts, wenn sie schon existiert)
            filepath.touch(exist_ok=True)

            # 5. Absoluten Pfad zurückgeben
            return filepath.resolve()

        except Exception as e:
            logger.exception(f"Kann Datei nicht anlegen: {filepath}: ({e})")
            # 6. Im Fehlerfall ein leeres Pfad-Objekt zurückgeben
            return Path()


# 2) App-weiter Zustand (State) vorbereiten
state = AppState()
