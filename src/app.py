import logging
from pathlib import Path

from flask import Flask

from src.config import BaseConfig
from src.extensions import state  # state ist Objekt der Klasse AppState und beinhaltet db)
from src.helpies import _init_db, _update_app


logger = logging.getLogger(__name__)

# Logging definieren
logging.basicConfig(
    filename=Path(__file__).resolve().parent / "data/logfile.log",
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    encoding="utf-8",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app(config_object=BaseConfig):
    app = Flask(__name__)

    # Basiskonfiguration laden
    app.config.from_object(config_object)

    # Extensions an App binden (db ist Eigenschaft von state )
    state.db.init_app(app)

    with app.app_context():
        try:
            logger.info(50 * "_")

            # States setzen (app)
            state.set_data(app)

            # Wenn die Datenbank nicht existiert, wird sie mit den default Config Werten erstellt
            # state wird als globale Variable in helpies verankert
            _init_db(state)

            # Weitere Configdaten aus der Datenbank laden
            _update_app()

            # mail an app binden
            state.mail.init_app(app)

        except Exception as e:
            logger.exception(f"Fehler bei der App-Initialisierung: {e}")

    # Blueprints/Routes registrieren
    from src.routes import bp as main_bp  # nur den Blueprint importieren
    from src.routes_admin import bp as admin_bp  # nur den Blueprint importieren
    from src.routes_lehrkraft import bp as tss_bp  # nur den Blueprint importieren

    app.register_blueprint(main_bp, url_prefix="")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(tss_bp, url_prefix="/tss")

    logger.info("  --> !! App: Erfassungsbogen wurde erfolgreich gestartet !!")
    logger.info(50 * "_")

    return app


app = create_app(BaseConfig)


if __name__ == "__main__":
    app.run(debug=True)
