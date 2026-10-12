import logging
from typing import Literal

from src.extensions import state
from src.forms import ConfigForm
from src.models import ConfigSetting


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Konfiguriert das Logging für die Applikation."""
    logging.basicConfig(
        filename=state.logfile,
        format="%(asctime)s - [%(module)s.py -> %(funcName)s():%(lineno)d] - %(levelname)s - %(message)s",
        encoding="utf-8",
        level=logging.WARNING,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Werkzeug-Logger (Flask-Server) auf ERROR setzen
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("flask").setLevel(logging.WARNING)


def _set_logging_level(level_name: str) -> tuple[str, Literal["success", "warning", "danger"]]:
    """Ändert das Logging-Level zur Laufzeit.

    Args:
        level_name: Level-Name ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").

    Returns:
        Tuple (message, category).
        - "success": Level geändert
        - "danger": Ungültiges Level
    """
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    if level_name.upper() not in valid_levels:
        return (f"Ungültiges Log-Level: {level_name}", "danger")

    try:
        level = getattr(logging, level_name.upper())

        # Root-Logger
        logging.getLogger().setLevel(level)

        # Alle bestehenden Logger
        for logger_name in logging.Logger.manager.loggerDict:
            logging.getLogger(logger_name).setLevel(level)

        # ✅ Werkzeug-Logger immer auf ERROR halten (nicht beeinflussen)
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        logging.getLogger("flask").setLevel(logging.WARNING)

        logger = logging.getLogger(__name__)
        logger.warning("Logging-Level geändert auf: %s", level_name.upper())

        return (f"Logging-Level auf {level_name.upper()} gesetzt.", "success")

    except Exception as e:
        logger.exception("Fehler beim Ändern des Logging-Levels: %s", e)
        return ("Fehler beim Ändern des Logging-Levels.", "danger")


def load_logging_level() -> None:
    """Lädt das Logging-Level aus der DB und setzt es."""
    try:
        stmt = state.db.select(ConfigSetting)
        config = state.db.session.execute(stmt).scalars().first()

        if config and config.log_level:
            _set_logging_level(config.log_level)

    except Exception as e:
        logger.warning("Fehler beim Laden des Logging-Levels: %s", e)


def apply_logging_level_change(form: ConfigForm) -> None:
    """Wendet Logging-Level-Änderungen sofort an.

    Args:
        form: ConfigForm mit log_level-Feld.
    """
    if not form.log_level.data:
        return

    message, category = _set_logging_level(form.log_level.data)

    if category == "success":
        logger.info("Logging-Level geändert auf: %s", form.log_level.data)
    else:
        logger.warning("Fehler beim Ändern des Logging-Levels: %s", message)
