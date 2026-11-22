# HIVE BREACH progress server

The game's progress (chapters, skins, Alien Codex, best score) lives here, not in
the browser. The browser only reports what happens while you play; this server
checks every report and decides what you have earned.

## Why

Up to v2.6 the game kept progress in `localStorage` (and later sent that same
self-reported progress to a server). Anyone could open the console and run

```js
localStorage.setItem('hivebreach_skins', JSON.stringify(['standard','crimson','void','swarm','hazmat']));
localStorage.setItem('hivebreach_skin', 'void');
location.reload();
```

and own every skin without playing. Now nothing the browser stores is read as
progress, and the server never accepts "I own X". It only accepts "this
happened", and only if it could really have happened.

## How it talks to the game

| What | Transport | Why |
|---|---|---|
| Create a player, read progress, equip a skin, delete a save | HTTP | rare, one request each |
| Rooms, kills, bosses, waves, score during a run | one WebSocket | many small reports, no per-request overhead |

Kills are counted in the game and sent once a second as one small message
(`{"t":"k","c":{"crawler":4,"brute":1}}`), so the socket carries roughly one
message per second during a fight.

### HTTP

| Method | Path | Notes |
|---|---|---|
| POST | `/api/players` | creates an anonymous player, returns its secret token once |
| GET | `/api/me` | `Authorization: Bearer <token>` |
| PUT | `/api/me/skin` | `{"skin":"crimson"}`, refused (403) unless the server granted that skin |
| DELETE | `/api/me` | deletes the save |
| GET | `/api/health` | liveness |

### WebSocket `/ws`

The first message must be `{"t":"auth","token":"..."}` within 5 seconds. Then:

| Game sends | Meaning |
|---|---|
| `start {mode, ch, diff}` | a new run (story chapter 1/2, or endless) |
| `room {i}` / `clear {i}` | entered / cleared story room i (0-4, 5 is the lair) |
| `wave {n}` | endless wave n started |
| `k {c:{type:count}}` | kills since the last report |
| `fuse` | an Amalgam formed |
| `boss {b}` / `evolve {b}` / `bosskill {b}` | the boss rose / reached stage 2 / died |
| `chdone {ch}` | the chapter epilogue finished |
| `score {s}` | the run's score at game over / chapter end |
| `end` | back to the menu |
| `resume {run}` | reconnect to a run after a dropped connection (2 min grace) |
| `ping` | heartbeat every 25 s |

The server answers with `ready`, `run`, `grant` (only what is new, plus the full
progress) or `void` (the run broke a rule and earns nothing more).

## What the server checks (`game_rules.py`)

- **Order**: rooms only in sequence (or a retry of the same room), waves only +1,
  a boss only in its lair or on a boss wave, stage 2 only after the boss rose,
  a boss kill only after stage 2, a chapter only after rooms 0-4 were cleared and
  its boss died in this run.
- **Time**, on the server's clock: a room takes at least 8 s (the cryo console 22 s,
  the drill 43 s), a wave at least 5 s, a boss fight at least 7 s (queen) / 9 s
  (Zero) including the 4.4 s evolution, the chapter epilogue at least 4 s.
- **Kills**: only enemy types that exist in that mode, at most 150 per report,
  180 per 10 s, 300 + 10/s over the whole run, and in endless no more than the
  wave can hold. An Amalgam kill needs an earlier fusion, and fusions are capped
  the same way the game caps them.
- **Score**: never above what the run's verified kills and boss kills could give
  at the maximum combo (x5) for the declared difficulty.

A run that breaks any rule is voided: it grants nothing more, and the game
tells the player. The limits are generous on purpose so honest players never
trip them.

## Storage limits (so the database cannot be filled up)

- One fixed-size row per player: progress is packed into a few integers.
  Runs, kills and events are never written to disk.
- Tokens are stored as SHA-256 hashes, never in plain text.
- At most `MAX_PLAYERS` rows (default 20,000, about 2 MB). New players are
  rate-limited per IP (5 per hour) and globally (500 per hour).
- Players who never earned anything are deleted after 7 days idle, everyone
  after 180 days idle.
- Memory is bounded too: at most `MAX_RUNS` live runs, 4 sockets per IP, one
  socket per player (a second tab takes over), 1 KB per message, 80 messages
  per 10 s, 512-byte HTTP bodies; the WebSocket frame limit is 4 KB.

## Settings (environment variables, all optional)

| Name | Default |
|---|---|
| `ALLOWED_ORIGINS` | `https://yssiddarth2005-tech.github.io,http://localhost:8000,http://127.0.0.1:8000` |
| `DB_PATH` | `players.db` next to `app.py` |
| `MAX_PLAYERS` | 20000 |
| `NEW_PER_IP_HOUR` / `NEW_PER_HOUR` | 5 / 500 |
| `MAX_RUNS` | 2000 |
| `WS_PER_IP` | 4 |

## Run and test

```
pip install -r requirements.txt
python app.py                  # listens on $PORT (default 10000)
pip install pytest && python -m pytest tests
```

It must run as **one process**: live runs are kept in memory.

## Deploy on Render

Build command `pip install -r requirements.txt`, start command `python app.py`.

On Render's free plan the disk is wiped on every redeploy, so saves reset when
you push a new version of the server. Attach a persistent disk and point
`DB_PATH` at it (a paid feature) if saves must survive redeploys.

## What this does not stop

The game itself still runs in the player's browser, so the server can only
judge whether a run's story is *possible*, not watch it being played. Someone
who studies the protocol and scripts a fake run that respects every order,
timing and kill limit, waiting out the real minutes it would take, could still
get through. Closing that last gap would mean running the whole simulation on
the server. What this does stop is the one-line console edit, replayed or
invented reports, skipped rooms and bosses, impossible kill counts and scores,
and equipping skins you don't own.
