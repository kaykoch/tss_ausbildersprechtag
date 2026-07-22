#!/usr/bin/python3
import os
import signal
import subprocess
import sys
import time


# --- Konfiguration ---
APP_NAME = "sprechtag"  # beliebiger Name für die Applikation
PORT = "8083"  # Port auf dem der Server hört
WORKERS = 1  # Anzahl der gestarteten Dienste
# ---------------------

BIND_ADDRESS = f"0.0.0.0:{PORT}"
APP_DIR = os.path.abspath(os.path.dirname(__file__))
VENV_DIR = os.path.join(APP_DIR, ".venv")

# Pfad zum Gunicorn-Executable im venv
GUNICORN_BIN = os.path.join(VENV_DIR, "bin", "gunicorn")

print(f"--- Deployment-Tool für {APP_NAME} ---")

# Wechsel ins Projektverzeichnis
os.chdir(APP_DIR)


def find_gunicorn_pids(app_name: str = None) -> list:
    """Gibt eine Liste von PIDs zurück, die zu laufenden gunicorn-Prozessen passen.
    Wenn app_name gesetzt ist, wird nach 'gunicorn' und dem app_name im Kommando gesucht.

    Args:
        app_name (str, optional): Name der Application. Defaults to None.

    Returns:
        list: Liste mit PIDs
    """
    try:
        if app_name:
            pgrep_output = subprocess.check_output(["pgrep", "-f", f"gunicorn.*{app_name}"])
        else:
            pgrep_output = subprocess.check_output(["pgrep", "-f", "gunicorn"])
        pids = [int(p) for p in pgrep_output.decode().strip().splitlines() if p.strip()]
        return pids
    except subprocess.CalledProcessError:
        # pgrep gibt einen Fehlercode zurück, wenn nichts gefunden wird
        return []


def kill_pids(pids: list, sig=signal.SIGTERM) -> list:
    """Versucht die PIDs mit sig zu beenden. Gibt zurück, welche PIDs noch existieren.

    Args:
        pids (list): Liste ,it PIDs, die beendet werden sollen
        sig (_type_, optional): signal, mit dem beendet weerden soll. Defaults to signal.SIGTERM.

    Returns:
        list: Liste mit PIDs, die nicht beendet werden konnten
    """
    for pid in pids:
        try:
            print(f"Versuche, PID {pid} mit Signal {sig.name} zu beenden...")
            os.kill(pid, sig)
        except ProcessLookupError:
            print(f"PID {pid} existiert nicht mehr.")
        except PermissionError:
            print(f"Keine Berechtigung, PID {pid} zu beenden.")
        except Exception as e:
            print(f"Fehler beim Beenden von PID {pid}: {e}")

    # Kurze Pause, dann prüfen welche noch laufen
    time.sleep(1)
    remaining = []
    for pid in pids:
        try:
            os.kill(pid, 0)
            remaining.append(pid)
        except OSError:
            pass
    return remaining


def main():
    # Prüfe CLI-Parameter
    action_kill_only = False
    if len(sys.argv) > 1 and sys.argv[1].lower() == "kill":
        action_kill_only = True
        print("Parameter 'kill' erkannt: Beende alle Gunicorn-Instanzen und starte nichts neu.")

    # 1) Alle relevanten Gunicorn-PIDs finden
    pids = find_gunicorn_pids(APP_NAME)
    if not pids:
        print("Kein laufender Gunicorn-Prozess gefunden.")
    else:
        print(f"Gefundene Gunicorn-PIDs: {pids}")
        # Zuerst versuchen, ordentlich zu beenden (SIGTERM)
        remaining = kill_pids(pids, sig=signal.SIGTERM)
        if remaining:
            print(f"PIDs {remaining} reagieren nicht auf SIGTERM, sende SIGKILL...")
            remaining = kill_pids(remaining, sig=signal.SIGKILL)
            if remaining:
                print(f"Folgende PIDs konnten nicht beendet werden: {remaining}")
            else:
                print("Alle gefundenen PIDs wurden beendet.")
        else:
            print("Alle gefundenen PIDs wurden mit SIGTERM beendet.")

    # Wenn nur kill gefordert war, beenden wir hier
    if action_kill_only:
        print("Beenden nach 'kill' Aktion — kein Neustart wird durchgeführt.")
        return

    # 2) Gunicorn neu starten (wie bisher)
    print("Starte Gunicorn neu...")

    if not os.path.isfile(GUNICORN_BIN):
        print(
            f"Warnung: Gunicorn-Binary nicht gefunden unter '{GUNICORN_BIN}'."
            " Versuche, 'gunicorn' aus PATH zu verwenden."
        )
        gunicorn_cmd = "gunicorn"
    else:
        gunicorn_cmd = GUNICORN_BIN

    cmd = [gunicorn_cmd, "--workers", str(WORKERS), "--bind", BIND_ADDRESS, "--daemon", f"{APP_NAME}:app"]

    try:
        subprocess.run(cmd, check=True)
        print("--- Neustart erfolgreich! ---")
        time.sleep(1)
        pids = find_gunicorn_pids(APP_NAME)
        if not pids:
            print("Kein laufender Gunicorn-Prozess gefunden.")
        else:
            print(f"Gefundene Gunicorn-PIDs: {pids}")
    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Starten von Gunicorn: {e}")
    except FileNotFoundError:
        print("Gunicorn ist nicht installiert oder das Binary ist nicht auffindbar. Bitte (virtuelle) Umgebung prüfen.")


if __name__ == "__main__":
    main()
