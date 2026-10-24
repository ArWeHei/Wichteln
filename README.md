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

## Deployment

- Prototyp auf PythonAnywhere: [deploy/PYTHONANYWHERE.md](deploy/PYTHONANYWHERE.md)
- Eigener Server mit Docker + Caddy: [deploy/VPS.md](deploy/VPS.md)
