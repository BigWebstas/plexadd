# Plexadd

Telegram bot that adds movies to Radarr and TV shows to Sonarr. Python 3, no dependencies.

## Use

- `/movie <title>` – search Radarr, tap a result to add it (monitored, search starts)
- `/tv <title>` – search Sonarr, tap a result to add it (monitored, search starts)
- `/status` – check Radarr and Sonarr are reachable, the API keys work, health is clean, and a root folder and quality profile exist
- `/id` – show your Telegram user ID (works for anyone, to fill in `ALLOWED_USER_IDS`)

New items use the first root folder and first quality profile in the app.
✅ next to a result means it's already in the library.

## Run

Create a bot with @BotFather, then:

```sh
export TELEGRAM_TOKEN=...
export ALLOWED_USER_IDS=123456789,987654321   # only these Telegram users get a response
export RADARR_URL=http://localhost:7878 RADARR_API_KEY=...
export SONARR_URL=http://localhost:8989 SONARR_API_KEY=...
python3 bot.py
```

Needs Sonarr v4 and Radarr v5 (API v3).

## Docker

```sh
docker build -t plexadd .
docker run -d --restart unless-stopped --name plexadd \
  -e TELEGRAM_TOKEN=... -e ALLOWED_USER_IDS=... \
  -e RADARR_URL=... -e RADARR_API_KEY=... \
  -e SONARR_URL=... -e SONARR_API_KEY=... \
  plexadd
```

No ports or volumes needed. The bot only makes outbound connections.

## Unraid

1. Nothing to build: the image is published to `ghcr.io/bigwebstas/plexadd` by the GitHub Actions workflow on every push to `main`.
2. Copy the template to `/boot/config/plugins/dockerMan/templates-user/plexadd.xml` on the server.
3. In Docker → Add Container, pick **plexadd** from the template list and fill in the fields.

Use the server's LAN IP for the Radarr/Sonarr URLs (not `localhost`).
