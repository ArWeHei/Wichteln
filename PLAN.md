# Projektplan: Wichtel-App

## 1. Ziel

Eine kleine Web-App, mit der man ein Wichtel-Ereignis anlegt, die Vornamen der
Teilnehmenden einträgt und die Wichtel zufällig auslost. Jede Person bekommt
einen eigenen, geheimen Link zu einer Unterseite, auf der nur sie sieht, wen sie
beschenkt. Es werden keine E-Mail-Adressen, Konten oder Passwörter benötigt –
die Links werden z. B. per Messenger verteilt.

**Nicht-Ziele (vorerst):** kein Login, keine Benutzerkonten, kein E-Mail- oder
SMS-Versand.

## 2. Ablauf aus Sicht der Nutzer

1. Die Organisator:in öffnet die Startseite und gibt einen Titel ein
   (z. B. „Familienwichteln 2026“), optional Budget und Datum, sowie die
   Vornamen – eine Zeile pro Person.
2. Die App legt das Ereignis an und leitet zur **Verwaltungsseite** weiter. Ihr
   Link ist geheim und muss gespeichert werden (deutlicher Hinweis +
   Kopieren-Button).
3. Auf der Verwaltungsseite lassen sich die Namen noch korrigieren. Dann:
   **„Auslosen“**.
4. Danach zeigt die Verwaltungsseite pro Person einen **persönlichen Link**
   (Kopieren, Teilen per Messenger) – aber **nicht**, wer wen beschenkt. So kann
   die Orga selbst mitmachen.
5. Jede Person öffnet ihren Link, sieht „Hallo Anna!“ und klickt auf
   **„Aufdecken“** → „Du beschenkst: **Ben**“.
6. Die Verwaltungsseite zeigt, wer schon aufgedeckt hat (✔ / –), damit man weiß,
   wen man noch erinnern muss.

## 3. Kernentscheidungen

### 3.1 Geheime Links statt `/anna`

Unterseiten dürfen nicht erratbar sein, sonst schaut Anna einfach unter `/ben`
nach. Jede Person bekommt ein zufälliges Token mit mindestens 128 Bit
(`secrets.token_urlsafe(16)`, z. B. `/w/q3Zf8KxR…`). Dasselbe gilt für den
Verwaltungslink. Unbekannte Tokens liefern einfach 404.

### 3.2 Aufdecken per Klick (wegen Link-Vorschauen)

Messenger wie WhatsApp, Signal oder Telegram rufen geteilte Links automatisch ab,
um eine Vorschau zu erzeugen. Deshalb:

- Die Seite hinter dem Link (GET) enthält **nie** den Namen der beschenkten
  Person.
- Erst der Klick auf „Aufdecken“ (POST) zeigt das Ergebnis und speichert den
  Zeitpunkt des ersten Aufdeckens.
- Die Vorschau-Texte sind neutral (`og:title` = „Dein Wichtel wartet 🎁“).

Nebeneffekt: Der Aufgedeckt-Status wird nicht durch Vorschau-Bots verfälscht.

### 3.3 Schutz vor Schummeln durch die Orga

Die Orga kennt alle Links und könnte fremde Seiten öffnen. Einfache
Gegenmaßnahme ohne Login: Die persönliche Seite zeigt an, wann sie **zum ersten
Mal** aufgedeckt wurde. Sieht Anna beim ersten Öffnen „bereits aufgedeckt am
12.11. um 20:13“, weiß sie, dass jemand nachgeschaut hat – dann wird neu
ausgelost.

### 3.4 Auslosung

Gesucht ist eine zufällige Zuordnung „schenkt → beschenkt“, bei der

- jede Person genau eine Person beschenkt und genau einmal beschenkt wird,
- niemand sich selbst zieht,
- (später) Ausschlüsse eingehalten werden, z. B. Paare beschenken sich nicht.

Vorgehen: **zufällige Permutation erzeugen und verwerfen, bis alle Regeln
erfüllt sind.** Ohne Ausschlüsse braucht das im Mittel etwa 2,7 Versuche. Das
ist einfach und liefert jede gültige Zuordnung mit gleicher Wahrscheinlichkeit.
Als Zufallsquelle dient `secrets.SystemRandom()`.

```python
def draw(participants, exclusions=frozenset(), rng=None, max_attempts=10_000):
    rng = rng or secrets.SystemRandom()
    for _ in range(max_attempts):
        receivers = participants[:]
        rng.shuffle(receivers)
        pairs = list(zip(participants, receivers))
        if all(g != r and (g, r) not in exclusions for g, r in pairs):
            return dict(pairs)
    raise NoValidAssignment("Mit diesen Ausschlüssen ist keine Auslosung möglich.")
```

Regeln für die Eingabe:

- mindestens 3 Teilnehmende (bei 2 weiß jede:r sofort Bescheid),
- Namen je Ereignis eindeutig, Groß-/Kleinschreibung egal; bei gleichen
  Vornamen z. B. „Anna M.“ und „Anna K.“,
- Leerzeilen und überflüssige Leerzeichen werden ignoriert, Namenslänge und
  Teilnehmerzahl begrenzt (z. B. 50 Zeichen, 100 Personen).

### 3.5 Neu auslosen und Verlauf

- Die Orga kann jederzeit **neu auslosen**, z. B. bei Schummelverdacht oder nach geänderten
  Ausschlüssen. Das ist eine Aktion mit Bestätigung (aufklappbarer Bereich).
- Jede Auslosung hat einen **Namen** (optional beim Auslosen, sonst „Auslosung 1“,
  „Auslosung 2“ …) und lässt sich später umbenennen.
- Die persönlichen Links bleiben gleich, es muss also nichts neu verschickt werden. Die
  **neueste Auslosung ist die gültige**.
- Frühere Auslosungen werden nicht gelöscht, sondern bilden den **Verlauf**: Auf der
  persönlichen Seite stehen sie unter „Frühere Auslosungen“, markiert mit „gilt nicht mehr“,
  und müssen wie die aktuelle per Klick aufgedeckt werden. Der Aufgedeckt-Status wird je
  Auslosung gespeichert.
- Ausschlüsse sind jederzeit änderbar und gelten für die nächste Auslosung; bestehende
  Auslosungen bleiben unverändert. Schlägt eine Neuauslosung wegen zu strenger Ausschlüsse
  fehl, bleibt alles wie zuvor.
- Die Namen der Teilnehmenden sind nach dem Anlegen nicht änderbar (Phase 2).

## 4. Technik

Bewusst schlank, serverseitig gerendert, ohne JavaScript-Framework.

| Bereich           | Wahl                                                | Begründung                                              |
| ----------------- | --------------------------------------------------- | ------------------------------------------------------- |
| Sprache/Framework | Python 3.10+ mit Flask                              | wenig Code, ideal für Formulare und Templates           |
| Templates         | Jinja2                                              | in Flask enthalten                                      |
| Datenbank         | SQLite über das `sqlite3`-Modul der Standardbibliothek | eine Datei, kein DB-Server, keine Zusatz-Abhängigkeit |
| Styling           | kleines eigenes CSS (oder Pico.css, lokal)          | keine externen CDNs (Datenschutz, keine Token-Lecks)    |
| Tests / Linting   | pytest, ruff                                        |                                                         |
| Betrieb           | Prototyp: PythonAnywhere; später: Docker + gunicorn + Caddy auf einem VPS | beide Wege sind in `deploy/` beschrieben |
| CI                | GitHub Actions: ruff + pytest                       |                                                         |

Bei einer Vorliebe für JavaScript/TypeScript ginge dasselbe mit SvelteKit und
better-sqlite3; der restliche Plan bleibt gleich.

## 5. Datenmodell

**`events`**

| Spalte             | Typ           | Hinweis                                      |
| ------------------ | ------------- | -------------------------------------------- |
| `id`               | INTEGER PK    |                                              |
| `title`            | TEXT          | z. B. „Familienwichteln 2026“                |
| `budget`           | TEXT NULL     | Freitext, z. B. „ca. 20 €“                   |
| `gift_date`        | DATE NULL     | Tag der Bescherung                           |
| `note`             | TEXT NULL     | Hinweis für alle                             |
| `admin_token_hash` | TEXT UNIQUE   | SHA-256 des Verwaltungs-Tokens               |
| `organizer_sees`   | INTEGER       | 1 = Orga darf die Zuordnung sehen            |
| `created_at`       | DATETIME      |                                              |

**`participants`**

| Spalte              | Typ                      | Hinweis                                                    |
| ------------------- | ------------------------ | ---------------------------------------------------------- |
| `id`                | INTEGER PK               |                                                            |
| `event_id`          | FK → events, CASCADE     |                                                            |
| `name`              | TEXT                     | eindeutig je Ereignis                                      |
| `token`             | TEXT UNIQUE              | persönlicher Link; im Klartext, da die Orga ihn sehen muss |
| `wishes`            | TEXT NULL                | Wunschzettel (Phase 3)                                     |

**`exclusions`**: `event_id`, `giver_id`, `receiver_id` –
„giver darf receiver nicht ziehen“. Ein Paar sind zwei Einträge.

**`draws`** (eine Zeile je Auslosung; die mit der größten `id` ist die aktuelle)

| Spalte       | Typ                  | Hinweis                        |
| ------------ | -------------------- | ------------------------------ |
| `id`         | INTEGER PK           |                                |
| `event_id`   | FK → events, CASCADE |                                |
| `name`       | TEXT                 | z. B. „Heiligabend“            |
| `created_at` | DATETIME             | Zeitpunkt der Auslosung        |

**`assignments`** (eine Zeile je Person und Auslosung)

| Spalte              | Typ                        | Hinweis                                             |
| ------------------- | -------------------------- | --------------------------------------------------- |
| `draw_id`           | FK → draws, CASCADE        | PK zusammen mit `giver_id`                          |
| `giver_id`          | FK → participants, CASCADE |                                                     |
| `receiver_id`       | FK → participants, CASCADE | UNIQUE zusammen mit `draw_id`                       |
| `first_revealed_at` | DATETIME NULL              | Zeitpunkt des ersten Aufdeckens in dieser Auslosung |

Datenbanken aus früheren Versionen (Zuordnung direkt an `participants`) werden beim Start
automatisch in eine „Auslosung 1“ überführt.

## 6. Seiten und Routen

| Methode | Pfad                                          | Zweck                                          |
| ------- | --------------------------------------------- | ---------------------------------------------- |
| GET     | `/`                                           | Startseite mit Formular „Neues Wichteln“       |
| POST    | `/events`                                     | Ereignis anlegen → Weiterleitung zur Verwaltung |
| GET     | `/admin/<admin_token>`                        | Verwaltung: Namen, Status, persönliche Links   |
| POST    | `/admin/<admin_token>/exclusions`             | Ausschluss hinzufügen (einseitig/gegenseitig)  |
| POST    | `/admin/<admin_token>/exclusions/<id>/delete` | Ausschluss entfernen                           |
| POST    | `/admin/<admin_token>/draw`                   | Auslosen bzw. neu auslosen (Feld `name` optional) |
| POST    | `/admin/<admin_token>/draws/<id>/rename`      | Auslosung umbenennen                           |
| POST    | `/admin/<admin_token>/delete`                 | Ereignis löschen                               |
| GET     | `/w/<token>`                                  | persönliche Seite mit Verlauf, ohne Ergebnisse |
| POST    | `/w/<token>/reveal/<draw_id>`                 | eine Auslosung aufdecken, Ergebnis anzeigen    |
| POST    | `/w/<token>/wishes`                           | Wunschzettel speichern (Phase 3)               |

## 7. Sicherheit und Datenschutz

- Es werden nur Vornamen gespeichert, keine Kontaktdaten.
- Tokens mit mindestens 128 Bit. Das Verwaltungs-Token wird zusätzlich zum Hash im Klartext
  gespeichert, damit der Betreiber verlorene Links per Kommandozeile
  (`flask --app wsgi admin-links`) wieder anzeigen kann. Das ist unkritisch, weil die
  persönlichen Tokens ohnehin im Klartext liegen; die Datenbank muss also so oder so
  geschützt sein.
- HTTPS ist Pflicht.
- Auf allen Token-Seiten: `Referrer-Policy: no-referrer`,
  `X-Robots-Tag: noindex`, `Cache-Control: no-store`.
- Keine externen Skripte, Schriften oder CDNs.
- Tokens möglichst nicht in Access-Logs schreiben (Log-Format von Caddy und
  gunicorn anpassen).
- Alte Ereignisse automatisch löschen, z. B. 30 Tage nach der Bescherung bzw.
  180 Tage nach dem Anlegen.
- Optional: Rate-Limit auf `POST /events` gegen Spam.

### Risiken und Gegenmaßnahmen

| Risiko                                     | Gegenmaßnahme                                                           |
| ------------------------------------------ | ----------------------------------------------------------------------- |
| Link-Vorschau verrät das Ergebnis          | Ergebnis nur nach Klick (POST), neutrale Vorschau-Texte                 |
| Orga schaut bei anderen nach               | „zuerst aufgedeckt am …“ sichtbar; Zuordnung nie auf der Verwaltungsseite |
| Verwaltungslink geht verloren              | deutlicher Hinweis, Kopieren-Button; ohne Konto gibt es keine Wiederherstellung |
| Person verliert ihren Link                 | Orga kann ihn jederzeit erneut von der Verwaltungsseite schicken        |
| Unmögliche Ausschlüsse                     | klare Fehlermeldung statt Endlosschleife                                |

## 8. Projektstruktur

```
Wichteln/
├── wichteln/
│   ├── __init__.py         # create_app(), Sicherheits-Header
│   ├── db.py               # SQLite-Schema und Verbindung
│   ├── draw.py             # Auslosung als reine Funktion
│   ├── tokens.py           # Tokens erzeugen und hashen
│   ├── views.py            # alle Routen
│   ├── templates/
│   └── static/
├── tests/
├── deploy/                 # PYTHONANYWHERE.md, VPS.md, Caddyfile
├── wsgi.py                 # Einstiegspunkt für PythonAnywhere und gunicorn
├── requirements.txt
├── Dockerfile
├── compose.yaml
└── .github/workflows/ci.yml
```

## 9. Meilensteine

### Phase 0 – Grundgerüst

- [x] `pyproject.toml`, Flask-App-Factory, SQLite-Anbindung
- [x] ruff und pytest einrichten, GitHub-Actions-CI
- [x] Basis-Layout (Template, CSS, mobilfreundlich)

### Phase 1 – MVP (ab hier ist das Wichteln benutzbar)

- [x] Formular: Ereignis und Namensliste anlegen, inkl. Validierung
- [x] Verwaltungsseite mit geheimem Link und Hinweis „Link speichern“
- [x] Auslosung (`draw.py`) mit Tests
- [x] Liste der persönlichen Links mit Kopieren-Button
- [x] Persönliche Seite mit „Aufdecken“, Speichern von `first_revealed_at`
- [x] Aufgedeckt-Status auf der Verwaltungsseite
- [x] Sicherheits-Header, `noindex`, neutrale Link-Vorschau
- [x] Dockerfile und `compose.yaml` (VPS) sowie Anleitung für PythonAnywhere
- [ ] Erstes Deployment auf PythonAnywhere (Prototyp)

### Phase 2 – Komfort

- [x] „Neu auslosen“ mit Bestätigung, benannte Auslosungen und Verlauf – bereits im Prototyp umgesetzt
- [ ] Namen vor der ersten Auslosung bearbeiten (Person hinzufügen/entfernen)
- [ ] Teilen-Buttons (WhatsApp-Link `https://wa.me/?text=…`, Web Share API auf
      dem Handy)
- [ ] Budget, Datum und Hinweistext auf allen Seiten anzeigen
- [ ] Festliches Design

### Phase 3 – Extras nach Bedarf

- [x] Ausschlüsse (Paare, „letztes Jahr schon gezogen“) – bereits im Prototyp umgesetzt
- [ ] Wunschzettel: Jede Person trägt auf ihrer Seite Wünsche ein, ihr Wichtel
      sieht sie auf seiner Seite
- [ ] Druckansicht mit QR-Codes zum Ausschneiden, für Wichteln vor Ort
- [ ] Automatisches Löschen alter Ereignisse
- [ ] Mehrsprachigkeit (DE/EN)

## 10. Tests

- **Auslosung** (wichtigster Teil): jede Person schenkt und wird beschenkt genau
  einmal; nie sich selbst; Ausschlüsse werden eingehalten; unmögliche
  Ausschlüsse ergeben eine klare Fehlermeldung; grobe Gleichverteilung (bei
  3 Personen kommen beide möglichen Zuordnungen je etwa zur Hälfte vor).
- **Routen**: Anlegen inkl. Validierungsfehlern, Auslosen nur mit
  Verwaltungs-Token, falsches Token → 404, Bearbeiten nach der Auslosung
  gesperrt.
- **Geheimhaltung**: Der GET-Aufruf der persönlichen Seite enthält den Namen der
  beschenkten Person nicht; die Verwaltungsseite enthält keine Zuordnung.

## 11. Offene Fragen

1. Wo soll die App laufen (eigener Server oder Raspberry Pi, VPS, Fly.io …) und
   unter welcher Domain?
2. Passt Python/Flask, oder gibt es eine Vorliebe, z. B. für TypeScript?
3. Persönliche Links, die die Orga einzeln verschickt – oder lieber **ein**
   Gruppenlink, auf dem sich jede:r den eigenen Namen auswählt? Letzteres ist
   bequemer, aber man kann versehentlich oder absichtlich den falschen Namen
   anklicken. Empfehlung: persönliche Links.
4. Werden Ausschlüsse oder Wunschzettel schon fürs erste Wichteln gebraucht?
   Dann wandern sie in Phase 1.
5. ~~Soll die Orga optional die komplette Zuordnung sehen dürfen?~~ Entschieden: Ja, als
   Option beim Anlegen (Standard: nein). Sie ist danach nicht mehr änderbar, und die
   Teilnehmenden sehen auf ihrer Seite einen Hinweis, wenn die Orga die Zuordnung sieht.
