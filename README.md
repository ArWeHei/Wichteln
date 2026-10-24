# Wichteln
App zum Wichtel verteilen: Vornamen eingeben, auslosen, jede Person bekommt einen
geheimen Link und sieht nur, wen sie selbst beschenkt. Keine Mailadressen, kein Login.

Der Projektplan steht in [PLAN.md](PLAN.md).

## Lokal starten

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
flask --app wsgi run --debug     # http://127.0.0.1:5000
pytest && ruff check .
```

Die Datenbank liegt standardmäßig in `instance/wichteln.db`
(anderer Ort: Umgebungsvariable `WICHTELN_DB`).

## Verwaltungslinks anzeigen

Falls ein Verwaltungslink verloren gegangen ist, zeigt der Server ihn an:

```bash
flask --app wsgi admin-links --base-url https://deine-seite.example
```

Das listet alle Wichteln mit ihrem Verwaltungslink. `--base-url` kann man weglassen (dann
steht nur der Pfad da) oder dauerhaft als Umgebungsvariable `WICHTELN_BASE_URL` setzen.
Bei Wichteln, die vor dieser Funktion angelegt wurden, ist der Link nicht gespeichert; dort
erzeugt `flask --app wsgi admin-links --reset <ID>` einen neuen (der alte wird ungültig).

## Deployment

- Prototyp auf PythonAnywhere: [deploy/PYTHONANYWHERE.md](deploy/PYTHONANYWHERE.md)
- Eigener Server mit Docker + Caddy: [deploy/VPS.md](deploy/VPS.md)
