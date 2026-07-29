Online-Portal zum Ausbilder- und Elternsprechtag
==================================================

### Einleitung

Der Ausbilder- und Elternsprechtag an Schulen ist ein zentrales Instrument zur Förderung des Dialogs zwischen der Schule und den dualen Ausbildungsbetrieben bzw. den Erziehungsberechtigten. Um die Organisation dieses Austauschs – analog zum klassischen Elternsprechtag – effizient, transparent und zeitsparend zu gestalten, wird eine webbasierte Anwendung eingesetzt.

**Sprechtag-Betriebsportal** digitalisiert und automatisiert den Prozess der Anmeldung.

Im Folgenden wird für Ausbilder und Erziehungsberechtigte das Wort Partner genutzt.

___

### Wie es funktioniert

Die Lehrkräfte der Schule registrieren sich einmalig über eine passwortgeschützte Weboberfläche und geben neben ihrem Namen den Raum und die Dauer eines Gesprächs an.
Die Partner wählen nach Start des Anmeldeprozesses ihren gewünschten Gesprächspartner und eine Uhrzeit aus. Sie erhalten eine Mail, die sie innerhalb eines durch die Schule festgelegten Zeitraums bestätigen müssen. Auf Wunsch der Lehrkräfte erhalten diese ebenfalls eine Benachrichtigung. Am Ende des Anmeldeprozesses können sich die Lehrkräfte ein PDF-Dokument mit ihren Terminen herunterladen.

___

### Was das Projekt löst

| Vorher (manuell)                              | Nachher (Sprechtag-Betriebsportal)              |
|-----------------------------------------------|-------------------------------------------------|
| Papierformulare, handschriftlich ausgefüllt   | Digitale Eingabe über Weboberfläche             |
| Keine Auswahl der Uhrzeit möglich             | Auswahl der Wunschzeit                          |
| Wartezeit auf dem Flur                        | Feste Termine                                   |
| Manuelle Benachrichtigung der Betriebe        | Automatischer Mailversand nach Anmeldung        |

___

### Für wen ist dieses Projekt gedacht?

Dieses Projekt richtet sich an **Schulen**, die Sprechtage organisieren und den
jährlichen Prozess der Anmeldung digitalisieren möchten. Es ist als
eigenständige Webanwendung konzipiert und kann auf einem schuleigenen Server
betrieben werden.

> ℹ️ Das Projekt wurde an der **Theobald-Simon-Schule Bitburg (TSS)** entwickelt
> und wird dort produktiv eingesetzt.

___

# Inhaltsverzeichnis
- [Voraussetzungen](#voraussetzungen)
- [Installation](#installation)
- [Programmstart](#programmstart)
  - [Variante 1 – Direkt mit Python (Lokal)](#variante-1--direkt-mit-python-lokal)
  - [Variante 2 – Gunicorn (Servertest)](#variante-2--gunicorn-servertest)
  - [Variante 3 – systemd (Produktion)](#variante-3--systemd-produktion)
- [Stoppen der Anwendung](#stoppen-der-anwendung)
- [Hinweise zur Sicherheit](#hinweise-zur-sicherheit)
- [Verzeichnisstruktur](#verzeichnisstruktur)

___

# Voraussetzungen

Auf dem Server muss Python 3 (>= 3.11), python3-venv und git installiert sein:

    apt install python3 python3-venv git

___

# Installation

> Im Beispiel: INSTALLATIONSVERZEICHNIS := /var/www/tss_ausbildersprechtag/

    # Basisverzeichnis erstellen
    mkdir ~/www/                        # Variante 1 – Lokal
    mkdir -p /var/www/                  # Variante 2/3 – Server

    # In das Verzeichnis wechseln
    cd ~/www/                           # Variante 1 – Lokal
    cd /var/www/                        # Variante 2/3 – Server

    # Projekt herunterladen
    git clone https://github.com/kaykoch/tss_ausbildersprechtag.git

    # In das Projektverzeichnis wechseln
    cd tss_ausbildersprechtag/

    # Setup-Skript ausführbar machen und starten
    chmod +x ./setup.py
    ./setup.py

## Was setup.py macht

- Prüft die Python-Version (>= 3.11)
- Prüft, ob der Systembenutzer `www-data` existiert (nur Linux, Warnung bei Fehlen)
- Erstellt eine virtuelle Umgebung unter `.venv/`
- Generiert eine `.env`-Datei mit kryptografischen Schlüsseln
- Installiert alle Abhängigkeiten aus `requirements.txt`
- Setzt die Verzeichnisberechtigungen auf `www-data:www-data` (nur Linux, benötigt sudo)

> Für Variante 2/3 (Server) muss setup.py mit sudo ausgeführt werden,
> damit die Berechtigungen korrekt gesetzt werden können:
>
>     sudo ./setup.py

___

## Weitere Anpassungen

### Texte auf der Webseite
- Seiten, die den Ausbildern angezeigt werden, beinhalten Informationen, die in einer speziellen Datei angepasst werden können. → `texts.toml`
- Texte auf den Adminseiten müssen in den entsprechenden Templates geändert werden → `src/templates/admin`
- Texte in den Mails müssen in den entsprechenden Templates geändert werden → `src/templates/mail`

### Logo und favicon
- Das Logo und das favicon.ico können im static-Ordner geändert werden → `src/static`
- Eine Dokumentation kann im static-Ordner abgelegt werden → `src/static`

___

# Programmstart

## Variante 1 – Direkt mit Python (Lokal)

Geeignet für: Lokale Entwicklung und schnelle Tests.

    source .venv/bin/activate
    python sprec.py

Risiken:
- Läuft im Flask-Entwicklungsserver — nicht produktionstauglich
- debug=True gibt Stacktraces im Browser aus
- Kein automatischer Neustart bei Absturz
- Kein Load-Balancing / mehrere Worker

___

## Variante 2 – Gunicorn (Servertest)

Geeignet für: Tests auf dem Server ohne systemd.

    # Starten
    python deploy/startGunicorn.py

    # Stoppen
    python deploy/startGunicorn.py kill

Risiken:
- Läuft auf Port 8081 und ist unter 0.0.0.0 von außen erreichbar
- Kein automatischer Neustart bei Absturz oder Serverneustart
- Logs landen unter /tmp/ — gehen bei Serverneustart verloren
- Nur für Tests gedacht — nicht für den Dauerbetrieb

___

## Variante 3 – systemd (Produktion)

Geeignet für: Dauerhafter Betrieb auf einem Linux-Server.

### Einmalige Einrichtung

    sudo cp deploy/tss_ausbildersprechtag.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable tss_ausbildersprechtag

### Starten / Stoppen / Status

    sudo systemctl start tss_ausbildersprechtag
    sudo systemctl stop tss_ausbildersprechtag
    sudo systemctl status tss_ausbildersprechtag

### Logs anzeigen

    sudo journalctl -u tss_ausbildersprechtag -f

Hinweise:
- Läuft auf Port 8083 unter Benutzer www-data
- Startet automatisch nach einem Serverneustart
- Automatischer Neustart bei Absturz
- Pfade in der .service-Datei ggf. anpassen

___

# Stoppen der Anwendung

| Variante                   | Befehl                                         |
|----------------------------|------------------------------------------------|
| Variante 1 (Python direkt) | STRG + C im Terminal                           |
| Variante 2 (Gunicorn)      | python deploy/startGunicorn.py kill            |
| Variante 3 (systemd)       | sudo systemctl stop tss_ausbildersprechtag     |

___

# Hinweise zur Sicherheit

- Die .env-Datei enthält kryptografische Schlüssel — niemals in git einchecken
- .env ist in .gitignore eingetragen und wird nicht hochgeladen
- Für den Produktiveinsatz ausschließlich Variante 3 (systemd) verwenden
- Der Gunicorn-Start (Variante 2) ist nur im lokalen Netz für Testzwecke gedacht
- Stelle sicher, dass Port 8083 durch eine Firewall oder einen Reverse Proxy (z.B. nginx) abgesichert ist

___

# Verzeichnisstruktur

    tss_ausbildersprechtag/
    ├── deploy/
    │   ├── startGunicorn.py               # Manueller Gunicorn-Start/-Stop
    │   ├── tss_ausbildersprechtag.service # systemd-Unit für Produktionsbetrieb
    │   └── README.md                      # Infodatei (Startmöglichkeiten)
    ├── logs/                              # Logdateien
    ├── src/                               # Anwendungsquellcode
    ├── .env                               # Generierte Schlüssel
    ├── texts.toml                         # Konfigurationsdatei (Schulname, Domain etc.)
    ├── requirements.txt                   # Abhängigkeiten für .venv
    ├── README.md                          # Infodatei (Allgemein)
    ├── ruff.toml                          # Editor-Einstellungen für VSCodium (nicht nötig für Betrieb)
    ├── setup.py                           # Einrichtungsskript
    └── sprechtag.py                       # Einstiegspunkt der Anwendung

___

# Dokumentation
___

## Ablauf für Lehrkräfte
Dieses Handbuch führt Sie Schritt für Schritt durch das System. Es deckt sowohl Ihre eigene Registrierung und Terminverwaltung als auch den Prozess aus Sicht der Partner ab, damit Sie bei Rückfragen Ihrer Schüler oder der Partner fundiert Auskunft geben können.

### Erstanmeldung und Registrierung
![Screenshot der Anwendung](./src/static/images/anmeldeseite_lehrkraft_1.png)
>*Abbildung 1: Registrierungsseite*

Für die initiale Anmeldung der Lehrkräfte stellt das System ein übersichtliches Online-Formular zur Verfügung. Gehen Sie hierfür wie folgt vor:

1. Rufen Sie die Anmeldeadresse im Webbrowser auf. Die URL sowie das erforderliche Zugangspasswort entnehmen Sie bitte dem offiziellen Aushang im Lehrerzimmer.

2. Füllen Sie die Pflichtfelder auf der Registrierungsseite aus:

   - **Vorname & Nachname:** Tragen Sie hier Ihre vollständigen Namensdaten ein. (Abbildung 1)

   - **E-Mail:** Nutzen Sie vorzugsweise Ihre dienstliche E-Mail-Adresse (`@tssbit.de`).

   - **Dauer eines Termins:** Wählen Sie die gewünschte Taktung pro Gespräch in Minuten (Standardvorgabe: 15, konfigurierbar zwischen 10 und 45 Minuten).

   - **Raum:** Geben Sie den Raum an, in dem Sie während des Sprechtags physisch erreichbar sind (z. B. *R109*).

   - **Benachrichtigung per Mail:** Setzen Sie hier ein Häkchen, falls Sie bei jeder neuen Terminbuchung eines Partners automatisch eine Benachrichtigung per E-Mail erhalten möchten.

   - Klicken Sie abschließend auf die blaue Schaltfläche **\[Lehrkraft speichern\]**, um Ihr Profil im System anzulegen.

### Registrierungsbestätigung und Account-Zugriff

Unmittelbar nach der Speicherung generiert das System eine automatisierte E-Mail mit dem Betreff `Registrierung — Ausbildersprechtag TSS Bitburg`.

Diese enthält eine Zusammenfassung Ihrer hinterlegten Daten (Name, Raum, gewählte Termindauer und Mail-Benachrichtigungsstatus) sowie eine zentrale, blaue Schaltfläche mit der Aufschrift **\[Daten ändern / Termin einsehen\]**.

> ⚠️ **Wichtig:** Bewahren Sie diese E-Mail gut auf! Über den darin enthaltenen Link können Sie jederzeit – auch zu einem späteren Zeitpunkt – ohne erneute Passworteingabe auf Ihr Dashboard zugreifen, um Änderungen vorzunehmen.


### Einstellungen und Buchungen
![Screenshot der Anwendung](./src/static/images/anmeldeseite_lehrkraft_4.png)
>*Abbildung 2:  Buchungen*



Sobald Sie Ihr Dashboard über den Link aus der Bestätigungs-E-Mail aufrufen, erhalten Sie vollen Zugriff auf Ihre persönlichen Daten und ihren aktuellen Buchungsstatus **\[Einstellungen\] \[Buchungen\]**.:

- **Einstellungen:** Sie können Ihre Profildaten (Raum, Mail-Präferenz etc.) bei Bedarf durch die Schaltfläche Einstellungen ändern. Sie werden dann auf die Eingabemaske () weitergeleitet. Dort finden Sie ihre aktuellen Daten eingetragen und können sie bei Bedarf ändern.

- **Buchungen: Einsicht in alle Buchungen erhalten sie mit der Schaltfläche Buchungen. (Abbildung 2)**

- **💡 Hinweis zu Tooltips: Wenn Sie mit der Maus über die einzelnen Eingabefelder fahren, erscheinen hilfreiche Tooltips mit zusätzlichen Erläuterungen und Formatvorgaben.**

- ![]()**Termine löschen:** Sollte unvorhergesehen ein Termin aus organisatorischen Gründen gelöscht werden müssen, befindet sich in der Spalte *Buchung* neben dem jeweiligen Eintrag eine rote Schaltfläche **\[löschen\]**. Ein Klick entfernt die Buchung und gibt das Zeitfenster sofort wieder für andere Partner frei.

- ![]()**PDF-Export der Terminliste:** Um am Sprechtag selbst eine ausgedruckte oder digitale Übersicht parat zu haben, klicken Sie unterhalb der Tabelle auf die blaue Schaltfläche **\[pdf - Download\]**. Das System erzeugt daraufhin eine übersichtliche PDF-Terminliste, welche Ihren Namen, den zugewiesenen Raum sowie die chronologische Tabelle der angemeldeten Partner enthält.(Abbildung 3)
![Screenshot der Anwendung](./src/static/images/lehrkraft_PDF.png)
> *Abbildung 3: PDF-Terminliste*
___

## Ablauf für Partner  
Damit Sie genau wissen, wie der Prozess auf Seiten der Partner abläuft, ist nachfolgend das Anmeldeverfahren aus Sicht der Partner dargestellt.
### Verteilung der Zugangsdaten
Die Partner erhalten die spezifische Webadresse für die Anmeldung über die Schülerinnen und Schüler. Die Schüler leiten die URL direkt an ihre jeweiligen Partner im Betrieb oder zu Hause weiter. (Abbildung 4)

### Terminauswahl und Datenübermittlung
Wenn ein Partner die Anmeldeseite aufruft, führt er die Anmeldung in folgenden Schritten durch:
![Screenshot der Anwendung](./src/static/images/anmeldeseite_betrieb_2.png)
> *Abbildung 4: Startseite für Partner (mit ausgeklappter Zeitenliste)*


1. **Auswahl der Lehrkraft:** Auf der Startseite für Partner wählt der Partner aus dem Dropdown-Menü *„Mit wem möchten Sie sprechen?“* die gewünschte Lehrkraft aus.

2. ![]()**Zeitfenster wählen:** Im daneben stehenden Dropdown-Menü *„Wann möchten Sie mit der Lehrkraft sprechen?“* werden dynamisch alle noch freien Uhrzeiten der ausgewählten Lehrkraft angezeigt. Bereits belegte Zeiten sind automatisch ausgeblendet. (Abbildung 4)

3. **Partnerdaten angeben:** Der Partner trägt seinen Namen (und den des Betriebes, z. B. *„Apple Records Ltd (George Martin“*) sowie eine gültige E-Mail-Adresse in die dafür vorgesehenen Felder ein und klickt auf **\[Einstellungen speichern\]**.

4. ![]()**Sende-Bestätigung:** Direkt im Browser wird eine visuelle Bestätigung angezeigt (*„Termin gebucht für... um...“*), verbunden mit dem Hinweis, dass eine Verifizierungs-Mail an den Partner versendet wurde ().


### Zweistufiges Bestätigungsverfahren (Double-Opt-In)
Zum Schutz vor Fehlbuchungen und Blockaden nutzt die Anwendung ein striktes Bestätigungsverfahren per E-Mail
![Screenshot der Anwendung](./src/static/images/anmeldeseite_betrieb_4.png)
> *Abbildung 6: Verifizierungs-E-Mail*


- **E-Mail-Eingang:** Der Partner erhält eine Nachricht mit dem Betreff `Terminbestätigung — Ausbildersprechtag TSS Bitburg`.

- ⏱️ **2-STUNDEN-FRIST:** Der Termin muss zwingend **innerhalb von 2 Stunden** vom Partner bestätigt werden. Erfolgt dies nicht, löscht das System die Reservierung automatisch und gibt das Zeitfenster wieder frei.

- **Interaktionsmöglichkeiten in der E-Mail:** Die Nachricht enthält zwei markante Buttons:

  - **\[Grünes Häkchen - Termin bestätigen\]:** Schließt die Buchung verbindlich ab.

  - **\[Rotes X - Termin Löschen\]:** Gibt den Termin sofort wieder für andere Partner frei, falls er irrtümlich ausgewählt wurd![]()e.

- **Erfolgreicher Abschluss:** Sobald der Partner in der E-Mail auf den Bestätigungsbutton geklickt hat, öffnet sich die finale Bestätigungsseite im Portal. Sie signalisiert *„Der Termin wurde bestätigt“* und fasst alle Daten (Partner, Uhrzeit, Raum und Name der Lehrkraft) in einer übersichtlichen Übersichtskarte zusammen.
![Screenshot der Anwendung](./src/static/images/anmeldeseite_betrieb_5.png)
> *Abbildung 7: Finale Bestätigungsansicht*