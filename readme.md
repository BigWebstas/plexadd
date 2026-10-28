# Plexadd

Telegram bot that adds movies to Radarr and TV shows to Sonarr. Python 3, no dependencies.

## Use

- `/movie <title>` – search Radarr, tap a result to add it (monitored, search starts)
- `/tv <title>` – search Sonarr, tap a result to add it (monitored, search starts)

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
