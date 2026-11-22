# HIVE BREACH save server

A tiny Flask API that stores player progress (chapter progress, best score,
codex entries, unlocked skins, options) so it survives clearing the browser.

## Endpoints
- `POST /api/new` — mint a new anonymous save token
- `GET /api/save/<token>` — fetch that token's save data
- `POST /api/save/<token>` — update it (send any subset of the save fields as JSON)

## Run locally
```
pip install -r requirements.txt
python app.py
```

## Deploy to Render (free tier)
1. Push this folder to its own GitHub repo (e.g. `hive-breach-server`).
2. On render.com, click **New > Web Service**, connect that repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Click **Create Web Service**. Render gives you a URL like
   `https://hive-breach-server.onrender.com`.
6. Paste that URL into `BACKEND_URL` near the top of the game's `game.js` /
   `hive-breach.html`, replacing the placeholder.

**Note on persistence:** this uses a SQLite file on disk. Render's free tier
does not guarantee that disk survives a redeploy or a long sleep cycle — fine
for a personal project, but if you want data to survive forever, move to an
external database (e.g. a free Postgres instance) later.
