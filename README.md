Online-Portal zum Ausbilder- und Elternsprechtag
==============

### Einleitung
Der Ausbilder- und Elternsprechtag an Schulen ist ein zentrales Instrument zur För­derung des Dialogs zwischen der Schule und den dualen Ausbildungsbetrieben bzw. den Erziehungsberechtigten. Um die Orga­nisation dieses Austauschs – analog zum klassischen Elternsprechtag – effizient, transparent und zeitsparend zu gestalten, wird eine webbasierte Anwendung eingesetzt.

In folgenden wird für Ausbilder und Erziehungsberechtigte das Wort Partner genutzt.
___

# Inhaltsverzeichnis
- [Installation](#installation)
- [Webserver, Lokal](#lokal)
- [Webserver, Internet (startscript)](#server-variante-1)
- [Webserver, Internet (systemd)](#server-variante-2)
- [Ablauf für Lehrkräfte](#ablauf-für-lehrkräfte)
- [Ablauf für Ausbildungsbetriebe / Erziehungsberechtigte](#ablauf-für-partner)

# Installation
Die Installation erfolgt über setup.py. Das Programm installiert eine virtuelle Umgebung und alle notwendigen Bibliotheken.
Zusätzlich wird [Gunicorn](https://gunicorn.org) instaliert. Ein Web Server Gateway Interface (WSGI) HTTP Server 

## Voraussetzungen
Auf dem Server muss python3 (>= 3.11), python3-venv und git installiert sein
```bash 
apt install python3 python3-venv git
```

## Installation des Grundsystems
Wählen Sie die Zeilen entsprechend, ob sie Variante 1 (Lokal zum testen) oder Variante 2 
(auf einem Server als root !) einrichten wollen und wie sie das INSTALLATIONSVERZEICHNIS nennen wollen
```bash  
# Erstellen des INSTALLATIONSVERZEICHNIS
mkdir ~/www/ # Variante 1 Lokal
mkdir -p /var/www/ # Variante 2 Server

# In Ordner hineinspringen                            
cd ~/www # Variante 1 Lokal
cd /var/www/ # Variante 2 Server

# Herunterladen der App (git )                           
git https://github.com/kaykoch/tss_ausbildersprechtag.git

# Ins INSTALLATIONSVERZEICHNIS wechseln
 cd /var/www/ausbildersprechtag/

# Setup-Programm ausführbar machen und starten
chmod +x ./setup.sh 
./setup.sh                                
```

## Programmstart
### Lokal
Wenn das Programm zum Testen auf dem lokalen PC gestartet werden soll:
- virtuelle Umgebung .venv starten (im INSTALLATIONSVERZEICHNIS): 
```bash 
source .venv/bin/activate
```

- Programm ausführbar machen und starten:
```bash
chmod +x sprechtag.py
./sprechtag.py
```

Eventuelle Fehlermeldungen werden geloggt in:
  - INSTALLATIONSVERZEICHNIS/src/data/logfile.log

**sprechtag.py:** \
Man kann die App im Debug Mode laufen lassen. Das führt dazu, dass bei Änderungen am Code nicht neu gestartet werden muss. \
Im Quelltext:

```python
app.run(debug=False)  # (! ZWINGEND FÜR SERVEREINSATZ !)
```

```python
app.run(debug=True)  # App startet selbstständig neu (! NUR FÜR DEN LOKALEN EINSATZ !)
``` 

Der Aufruf erfolgt im Browser mit: 
   ```
  http://localhost:5000/
  ``` 

bzw. für die Administration:  (Login: admin | Password: admin)
  ```
  http://localhost:5000/admin
  ``` 
 

### Server-Variante 1
(mit startGunicorn.py) 

Wenn das Programm im produktiven Einsatz laufen, kommt GuniCorn ins Spiel. \
Hierfür gibt es das Startscript  **startGunicorn.py**, dass angepasst werden kann:

**startGunicorn.py:** \
Es gibt drei Parameter im script, die man ändern kann:\
Im Quelltext:
```python
# beliebiger Name für die Applikation. Dient nur zur Unterscheidung bei mehreren GuniCorn Anwendungen
APP_NAME = (
    "sprechtag"  
)
# Port auf dem der Server hört
PORT = "8083"
# Anzahl der gestarteten Dienste. Nur interessant bei zu erwartender hoher Last
WORKERS = 3  
```

Nach dem Anpassungen muss startGunicorn.py ausgeführt werden. 

```bash 
chmod +x startGunicorn.py
startGunicorn.py
```
Der Aufruf im Browser erfolgt im Browser: 
 - für die Partner:
```
http://<SERVER_URL>:PORT/
``` 

 - für die Lehrkräfte:
```
http://<SERVER_URL>:PORT/tss
``` 

 - für die Administration:
```
http://<SERVER_URL>:PORT/admin
``` 

### Server-Variante 2 
(mit systemd) 

Als Alternative kann man auch einen Dienst mit systemd einrichten. 
Hier sind einige Vorraussetzungen zu erfüllen, die hier nicht extra beschrieben werden, da es sich um Standard
Linux Befehle handelt
- Anlegen eines Benutzers, wenn es ihn nicht schon gibt ( www-data)

#### Erstellen einer Systemd Startdatei
Das folgende Startscript setzt folgenden Einstellungen  (Bei Bedarf ändern):
- **Name der Datei:** ausbildersprechtag.service
- **INSTALLATIONSVERZEICHNIS:** /var/www/ausbildersprechtag/
- **LogPfad:** /var/log/gunicorn/
- **Port:**  8083

Erstellen Sie eine Datei **/etc/systemd/system/ausbildersprechtag.service** mit folgendem, evtl.angepasstem Inhalt:
```
[Unit]
Description=Gunicorn Ausbildersprechtag (8083)
After=network.target

[Service]
# Benutzer und Gruppe
User=www-data
Group=www-data

# Arbeitsverzeichnis
WorkingDirectory=/var/www/ausbildersprechtag/

# Umgebungsvariablen (z. B. für Virtualenv)
Environment="PATH=/var/www/ausbildersprechtag/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"

# Gunicorn-Befehl
ExecStart=/var/www/ausbildersprechtag/.venv/bin/gunicorn \
    --workers 2 \
    --bind 0.0.0.0:8083 \
    --log-level info \
    --access-logfile /var/log/gunicorn/sprechtag_access.log \
    --error-logfile /var/log/gunicorn/sprechtag_error.log \
    --timeout 30 \
    --graceful-timeout 10 \
    sprechtag:app

# Automatischer Neustart
Restart=always
RestartSec=5

# Timeout für Stop-Vorgang
TimeoutStopSec=30

# Sauberes Beenden
ExecStop=/bin/kill -TERM $MAINPID

# Berechtigungen für Log-Dateien
PermissionsStartOnly=true
ExecStartPre=/bin/mkdir -p /var/log/gunicorn
ExecStartPre=/bin/chown www-data:www-data /var/log/gunicorn
ExecStartPre=/bin/chmod 755 /var/log/gunicorn

# Berechtigungen für App-Verzeichnis
ExecStartPre=/bin/chown www-data:www-data /var/www/ausbildersprechtag/ -R

[Install]
WantedBy=multi-user.target
```
Danach muss der Dienst registriert und gestartet werden
```
systemctl daemon-reload
systemctl enable ausbildersprechtag.service
```
und der Dienst gestartet werden:
```
systemctl restart ausbildersprechtag.service
```
Man kann den status des Dienstes überprüfen:
```
systemctl status ausbildersprechtag.service
```
Man sollte dann ganz unten Folgendes sehen:
```
systemd[1]: Started ausbildersprechtag.service - Gunicorn Ausbildersprechtag (8083).
```
#### Zugriff aus dem Internet
Damit der Dienst aus dem Internet erreicht werden kann, muss der Zugriff eingerichtet werden. Auch das sind Dinge, die nicht
primär mit der Applikation zu tun haben. Daher nur eine Liste meiner Empfehlungen, wenn mehr als eine Applikation geplant ist:
- Einrichten einer Firewall (Freigabe auf SSH und HTTPS)
- Einrichten von  [docker](https://github.com/docker/docker-install)
- Installation von  [Nginx Proxy Manager](https://nginxproxymanager.com)
- Konfiguration des Managers für den Gebrauch von Let's Encrypt mit DNS-Challenge (*.MEINE_SCHULE.DE)
- Weiterleitung des Proxy-Hosts auf die Applikation (spechtag.MEINE_SCHULE.DE -> http://<SERVER_URL>:PORT/)

___

# Ablauf für Lehrkräfte
Dieses Handbuch führt Sie Schritt für Schritt durch das System. Es deckt sowohl Ihre eigene Registrierung und Terminverwaltung als auch den Prozess aus Sicht der Partner ab, damit Sie bei Rückfragen Ihrer Schüler oder der Partner fundiert Auskunft geben können.

## Erstanmeldung und Registrierung
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

## Registrierungsbestätigung und Account-Zugriff

Unmittelbar nach der Speicherung generiert das System eine automatisierte E-Mail mit dem Betreff `Registrierung — Ausbildersprechtag TSS Bitburg`.

Diese enthält eine Zusammenfassung Ihrer hinterlegten Daten (Name, Raum, gewählte Termindauer und Mail-Benachrichtigungsstatus) sowie eine zentrale, blaue Schaltfläche mit der Aufschrift **\[Daten ändern / Termin einsehen\]**.

> ⚠️ **Wichtig:** Bewahren Sie diese E-Mail gut auf! Über den darin enthaltenen Link können Sie jederzeit – auch zu einem späteren Zeitpunkt – ohne erneute Passworteingabe auf Ihr Dashboard zugreifen, um Änderungen vorzunehmen.


## Einstellungen und Buchungen
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

# Ablauf für Partner  
Damit Sie genau wissen, wie der Prozess auf Seiten der Partner abläuft, ist nachfolgend das Anmeldeverfahren aus Sicht der Partner dargestellt.
## Verteilung der Zugangsdaten
Die Partner erhalten die spezifische Webadresse für die Anmeldung über die Schülerinnen und Schüler. Die Schüler leiten die URL direkt an ihre jeweiligen Partner im Betrieb oder zu Hause weiter. (Abbildung 4)

## Terminauswahl und Datenübermittlung
Wenn ein Partner die Anmeldeseite aufruft, führt er die Anmeldung in folgenden Schritten durch:
![Screenshot der Anwendung](./src/static/images/anmeldeseite_betrieb_2.png)
> *Abbildung 4: Startseite für Partner (mit ausgeklappter Zeitenliste)*


1. **Auswahl der Lehrkraft:** Auf der Startseite für Partner wählt der Partner aus dem Dropdown-Menü *„Mit wem möchten Sie sprechen?“* die gewünschte Lehrkraft aus.

2. ![]()**Zeitfenster wählen:** Im daneben stehenden Dropdown-Menü *„Wann möchten Sie mit der Lehrkraft sprechen?“* werden dynamisch alle noch freien Uhrzeiten der ausgewählten Lehrkraft angezeigt. Bereits belegte Zeiten sind automatisch ausgeblendet. (Abbildung 4)

3. **Partnerdaten angeben:** Der Partner trägt seinen Namen (und den des Betriebes, z. B. *„Apple Records Ltd (George Martin“*) sowie eine gültige E-Mail-Adresse in die dafür vorgesehenen Felder ein und klickt auf **\[Einstellungen speichern\]**.

4. ![]()**Sende-Bestätigung:** Direkt im Browser wird eine visuelle Bestätigung angezeigt (*„Termin gebucht für... um...“*), verbunden mit dem Hinweis, dass eine Verifizierungs-Mail an den Partner versendet wurde ().


## Zweistufiges Bestätigungsverfahren (Double-Opt-In)
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