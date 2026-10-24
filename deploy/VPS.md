# Deployment auf einem VPS (Docker + Caddy)

Voraussetzungen: ein kleiner Linux-Server (z. B. Hetzner CX-Klasse) mit Docker und dem
Compose-Plugin sowie eine Domain, deren A-/AAAA-Eintrag auf den Server zeigt.
Ports 80 und 443 müssen offen sein.

```bash
git clone https://github.com/ArWeHei/Wichteln.git
cd Wichteln
cp .env.example .env        # SITE_ADDRESS=wichteln.example.org eintragen
docker compose up -d --build
```

Caddy holt das HTTPS-Zertifikat automatisch. Die Datenbank liegt im Docker-Volume
`wichteln-data`.

- **Update:** `git pull && docker compose up -d --build`
- **Backup:** `docker compose cp app:/data/wichteln.db ./wichteln-backup.db`
- **Verwaltungslinks anzeigen:**
  `docker compose exec app flask --app wsgi admin-links --base-url https://wichteln.example.org`
- **Logs:** `docker compose logs -f app` – es gibt bewusst kein Access-Log, weil die
  URLs geheime Tokens enthalten.
