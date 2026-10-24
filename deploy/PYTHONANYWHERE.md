# Deployment auf PythonAnywhere (Prototyp)

Dauer: ca. 15 Minuten. Ein kostenloser Account reicht
(Adresse: `https://<benutzername>.pythonanywhere.com`, HTTPS ist dabei).

## 1. Code holen

Auf PythonAnywhere eine **Bash-Konsole** öffnen:

```bash
git clone https://github.com/ArWeHei/Wichteln.git
cd Wichteln
git checkout claude/wichtel-assignment-website-h89dw8   # bis der Branch in main ist
mkvirtualenv wichteln --python=python3.12              # oder eine andere angebotene Version ≥ 3.10
pip install -r requirements.txt
```

Ist das Repo privat, vorher ein GitHub-Token bzw. Deploy-Key einrichten.

## 2. Web-App anlegen

1. Tab **Web** → **Add a new web app** → **Manual configuration** (nicht „Flask“!) →
   gleiche Python-Version wie oben.
2. **Virtualenv**: `/home/<benutzername>/.virtualenvs/wichteln`
3. **Source code**: `/home/<benutzername>/Wichteln`
4. Auf **WSGI configuration file** klicken, den Inhalt komplett ersetzen durch:

   ```python
   import sys

   path = "/home/<benutzername>/Wichteln"
   if path not in sys.path:
       sys.path.insert(0, path)

   from wsgi import application  # noqa: E402,F401
   ```

5. Optional, aber empfohlen: unter **Static files** URL `/static/` →
   `/home/<benutzername>/Wichteln/wichteln/static` eintragen.
6. **Force HTTPS** einschalten und oben auf **Reload** klicken.

Die SQLite-Datenbank entsteht beim ersten Aufruf unter `~/Wichteln/instance/wichteln.db`
und bleibt bei Reloads erhalten.

## 3. Betrieb

- **Kostenloser Account:** die Web-App läuft nur 3 Monate, danach im Tab *Web* auf
  **„Run until 3 months from today“** klicken.
- **Update einspielen:** Bash-Konsole → `cd ~/Wichteln && git pull && pip install -r requirements.txt`,
  danach im Tab *Web* **Reload**.
- **Verwaltungslink vergessen:** Bash-Konsole →
  `cd ~/Wichteln && workon wichteln && flask --app wsgi admin-links --base-url https://<benutzername>.pythonanywhere.com`
- **Backup:** `instance/wichteln.db` herunterladen (Tab *Files*).
- **Löschen nach dem Fest:** Web-App im Tab *Web* löschen oder die Datenbankdatei entfernen.
- Zugriffs-Logs von PythonAnywhere enthalten die geheimen URLs; sie sind nur für dich
  einsehbar.
