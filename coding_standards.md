# Coding Standards für dieses Projekt

## 1. Service-Funktionen: Rückgabewert

Alle Service-Funktionen müssen folgende Struktur einhalten:

**Rückgabewert:**
```python
tuple[str, Literal["success", "warning", "danger"], <optional_daten>]
```

**Struktur:** `(Nachricht, Kategorie, optionale_Daten)`

**Kategorien:**
- `"success"`: Operation erfolgreich
- `"warning"`: Operation mit Warnung (z.B. keine Daten gefunden)
- `"danger"`: Fehler bei Operation

---

## 2. Try-Except-Else Struktur

> **Wichtig:** Der `try`-Block soll **NUR** Code enthalten, der tatsächlich Fehler werfen kann! Validierungen gehören vor den `try`-Block, und Rückgabewerte im Erfolgsfall in den `else`-Block.

```python
def service_funktion() -> tuple[str, Literal["success", "warning", "danger"], list]:
    """Beschreibung."""
    
    # Validierungen HIER (nicht im try-Block)
    if not valid_input:
        return ("Fehlermeldung", "danger", [])

    try:
        # NUR Code, der Fehler werfen kann
        ergebnis = state.db.session.execute(stmt).scalars().all()
    except SpecificError as e:
        state.db.session.rollback()
        logger.error("Fehler: %s", e)
        return ("Fehlermeldung", "danger", [])
    except Exception as e:
        state.db.session.rollback()
        logger.exception("Unerwarteter Fehler: %s", e)
        return ("Unerwarteter Fehler", "danger", [])
    else:
        # ✅ Rückgabewert HIER nach dem letzten except!
        if not ergebnis:
            return ("Keine Daten gefunden", "warning", [])
        return ("", "success", ergebnis)
```

---

## 3. Docstring-Format

```python
def funktion_name(param1: str, param2: int | None) -> tuple[str, Literal["success", "warning", "danger"], list]:
    """Kurze, prägnante Beschreibung.

    Args:
        param1: Beschreibung des Parameters
        param2: Beschreibung des Parameters oder None

    Returns:
        Tuple (message, category, daten).
        - "success": Beschreibung bei Erfolg
        - "warning": Beschreibung bei Warnung (falls relevant)
        - "danger": Beschreibung bei Fehler

    Raises:
        ExceptionType: Beschreibung (falls relevant)
    """
```

---

## 4. Logging-Richtlinien

**Info-Level:**
```python
logger.info("Lehrkraft %s erstellt.", lehrkraft.lehrkraft_id)
logger.info("Buchung gelöscht: %s", termin)
```

**Warning-Level:**
```python
logger.warning("Keine Buchung mit Token '%s' gefunden.", token)
logger.warning("Ungültige Wartezeit: %d Minuten", timetowait)
```

**Error-Level:**
```python
logger.error("DB-Fehler beim Löschen: %s", e)
logger.error("Unique Constraint verletzt: %s", e)
```

**Exception-Level (für unerwartete Fehler):**
```python
logger.exception("Unerwarteter Fehler beim Laden: %s", e)
```

---

## 5. Flash-Messages in Routes

```python
@app.route('/example', methods=['POST'])
def example_route():
    """Route-Beschreibung."""
    message, category, daten = service_funktion()
    flash(message, category)
    
    if category == "danger":
        return render_template('error.html')
        
    return render_template('success.html', daten=daten)
```

---

## 6. Fehlerbehandlung in Routes

### ❌ Nicht in Routes:
- Keine komplexe Fehlerbehandlung
- Keine DB-Operationen direkt
- Keine Validierungen

### ✅ In Routes:
- Service-Funktionen aufrufen
- Flash-Messages anzeigen
- Templates rendern

---

## 7. Type-Hints

Immer explizite Type-Hints verwenden:

```python
# ✅ Richtig
def funktion(param: str, optional: int | None = None) -> tuple[str, Literal["success", "danger"]]:
    """..."""

# ❌ Falsch
def funktion(param, optional=None):
    pass
```

---

## 8. Naming Conventions

- **Funktionen:** `snake_case` (z. B. `create_lehrkraft()`)
- **Private Funktionen:** `_snake_case` (z. B. `_generiere_zeiten()`)
- **Klassen:** `PascalCase` (z. B. `LehrkraftForm`)
- **Konstanten:** `UPPER_SNAKE_CASE` (z. B. `DEFAULT_TIMETOWAIT`)
- **Variablen:** `snake_case` (z. B. `lehrkraft_id`)

---

## 9. Datenbank-Operationen

Datenbank-Transaktionen immer absichern und mit explizitem Rollback im Fehlerfall versehen:

```python
try:
    state.db.session.add(objekt)
    state.db.session.commit()
except SQLAlchemyError as e:
    state.db.session.rollback()
    logger.error("DB-Fehler: %s", e)
    return ("Fehler", "danger", None)
```

---

## 10. Helper-Funktionen (interne Funktionen)

Nutzen einfache Rückgabewerte (kein Flash-/UI-Format):

```python
def get_gebuchte_zeiten(lehrkraft_id: int) -> list[str]:
    """Gibt gebuchte Zeiten zurück.

    Returns:
        Liste gebuchter Uhrzeiten oder leere Liste bei Fehler.
    """
    try:
        result = state.db.session.execute(stmt).scalars().all()
        return result
    except Exception as e:
        logger.error("Fehler: %s", e)
        return []
```

---

## 11. Wichtige Regeln

- ✅ Validierungen gehören in Services, nicht in Routes
- ✅ Logging in jeder Funktion (Info, Warning, Error)
- ✅ Rollback bei DB-Fehlern
- ✅ Aussagekräftige Fehlermeldungen für Benutzer
- ✅ Type-Hints überall
- ✅ Docstrings für alle Funktionen
- ✅ `_external=True` in `url_for()` für Mail-Links
- ✅ HTTPS erzwingen (Flask-Talisman)

---

## 12. Technologie-Stack

- **Python:** `>= 3.11`
- **Framework:** Flask
- **ORM:** SQLAlchemy 2.0
- **Forms:** Flask-WTF
- **Security:** Flask-Talisman

---

## 13. Häufige Fehler (vermeiden!)

| Fehler | ❌ Falsch | ✅ Richtig |
| :--- | :--- | :--- |
| **Validierung im try-Block** | `try:`<br>`    if not x:` | `if not x:`<br>`    return` |
| **Rückgabewert im try-Block** | `try:`<br>`    return ...` | `else:`<br>`    return ...` |
| **Keine Type-Hints** | `def func(x):` | `def func(x: str) -> str:` |
| **f-String in Logging** | `logger.info(f"...")` | `logger.info("...", var)` |
| **Kein Rollback** | `except:`<br>`    pass` | `except:`<br>`    rollback()` |
| **Flash-Status ignorieren** | `message, cat, data = func()` | `if cat != "danger":` |
| **Relative URLs in Mails** | `url_for('route')` | `url_for('route', _external=True)` |
| **Token-Feld in Form** | `form.populate_obj()` | `if not token:`<br>`    token = _make_token()` |

---

## 14. Code-Review Checkliste

Vor dem Commit immer prüfen:

- [ ] Type-Hints vorhanden?
- [ ] Docstring vollständig (`Args`, `Returns`, `Raises`)?
- [ ] `try-except-else`-Struktur korrekt aufgebaut?
- [ ] Logging auf allen Ebenen (Info, Warning, Error) implementiert?
- [ ] Rollback bei DB-Fehlern gesetzt?
- [ ] Flash-Status in Routes abgefragt/geprüft?
- [ ] keine Validierungen in Routes durchgeführt?
- [ ] Naming Conventions eingehalten?
- [ ] keine f-Strings im Logging verwendet?
- [ ] `_external=True` in Mail-URLs vorhanden?