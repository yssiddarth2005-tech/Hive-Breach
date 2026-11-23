"""HIVE BREACH progress server.

HTTP  (things that change rarely)
  POST   /api/players     create an anonymous player, returns its secret token once
  GET    /api/me          read your progress
  PUT    /api/me/skin     equip a skin you own
  DELETE /api/me          delete your save
  GET    /api/health      liveness check

WebSocket  /ws  (the live run)
  The game reports what happens while you play: rooms, kills (batched once a
  second), bosses, waves, score. game_rules.Run checks every report and the
  server grants codex entries, skins, chapters and best score itself. The
  browser never tells the server what you own.

Run with:  python app.py   (one process: runs are kept in memory)
"""
import asyncio
import ipaddress
import json
import os
import secrets
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect

import game_rules as rules
from store import Full, Store, hash_token, to_public

# Secrets (DATABASE_URL) come only from environment variables. Locally they can sit in
# hive-breach-server/.env (gitignored); on Render they are set in the dashboard.
# Variables that are already set always win over the .env file.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS",
    "https://yssiddarth2005-tech.github.io,http://localhost:8000,http://127.0.0.1:8000,"
    "http://localhost:10000,http://127.0.0.1:10000").split(",") if o.strip()]
_SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
if _SELF_URL and _SELF_URL not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(_SELF_URL)          # the game served by this server itself
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "players.db"))
MAX_PLAYERS = _env_int("MAX_PLAYERS", 20000)      # hard cap on rows in the database
NEW_PER_IP_HOUR = _env_int("NEW_PER_IP_HOUR", 5)  # new players per IP per hour
NEW_PER_HOUR = _env_int("NEW_PER_HOUR", 500)      # new players per hour, all IPs together
MAX_RUNS = _env_int("MAX_RUNS", 2000)             # runs held in memory at once
WS_PER_IP = _env_int("WS_PER_IP", 4)              # open sockets per IP
MSG_MAX_BYTES = 1024                              # largest report accepted
MSG_PER_10S = 80                                  # reports per socket per 10 s
BODY_MAX_BYTES = 512                              # largest HTTP body accepted
AUTH_SECONDS = 5                                  # time to send the token after connecting
IDLE_SECONDS = 90                                 # the game sends a ping every 25 s
RESUME_SECONDS = 120                              # a dropped run can be resumed for this long
RUN_MAX_SECONDS = 4 * 3600

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL and os.environ.get("RENDER"):
    # Render's disk is wiped on every deploy: refuse to start rather than lose saves.
    raise SystemExit("DATABASE_URL is not set. Add your Neon connection string in Render > Environment.")

store = Store(DB_PATH, MAX_PLAYERS, url=DATABASE_URL or None)
print("player storage: %s" % store.backend, flush=True)   # never print the URL itself


# ---- small helpers -----------------------------------------------------------------------

class RateLimiter:
    """Sliding-window counter per key. The number of keys tracked is capped too."""

    def __init__(self, limit, window, max_keys=20000):
        self.limit, self.window, self.max_keys = limit, window, max_keys
        self.hits = OrderedDict()

    def allow(self, key, now):
        q = self.hits.pop(key, None) or deque()
        while q and now - q[0] > self.window:
            q.popleft()
        ok = len(q) < self.limit
        if ok:
            q.append(now)
        self.hits[key] = q
        while len(self.hits) > self.max_keys:
            self.hits.popitem(last=False)
        return ok


new_per_ip = RateLimiter(NEW_PER_IP_HOUR, 3600)
new_global = RateLimiter(NEW_PER_HOUR, 3600, max_keys=1)
http_per_player = RateLimiter(60, 60)


def client_ip(headers, client):
    """Render sits behind proxies that append to X-Forwarded-For. Walk it from the
    right and take the first public address, so a client cannot pick its own IP
    by sending a fake header."""
    for part in reversed(headers.get("x-forwarded-for", "").split(",")):
        try:
            ip = ipaddress.ip_address(part.strip())
        except ValueError:
            continue
        if ip.is_global:
            return str(ip)
    return client[0] if client else "unknown"


def bearer(request):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if 20 <= len(token) <= 100:
            return hash_token(token)
    return None


async def read_json(request):
    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        return None
    if declared > BODY_MAX_BYTES:
        return None
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > BODY_MAX_BYTES:
            return None
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def err(status, why):
    return JSONResponse({"error": why}, status_code=status)


def player_or_401(request):
    th = bearer(request)
    row = store.get(th) if th else None
    if row is None:
        return None, None, err(401, "unknown player")
    if not http_per_player.allow(th, time.monotonic()):
        return None, None, err(429, "slow down")
    store.touch(th, row["last_seen"], time.time())
    return th, row, None


# ---- HTTP ---------------------------------------------------------------------------------

async def health(request):
    return JSONResponse({"status": "ok"})


async def create_player(request):
    now = time.monotonic()
    ip = client_ip(request.headers, request.client)
    if not new_per_ip.allow(ip, now) or not new_global.allow("all", now):
        return err(429, "too many new players, try later")
    token = secrets.token_urlsafe(32)
    try:
        store.create(hash_token(token), time.time())
    except Full:
        return err(503, "server is full")
    return JSONResponse({"token": token, "progress": to_public(store.get(hash_token(token)))}, status_code=201)


async def get_me(request):
    th, row, bad = player_or_401(request)
    return bad or JSONResponse({"progress": to_public(row)})


async def equip_skin(request):
    th, row, bad = player_or_401(request)
    if bad:
        return bad
    data = await read_json(request)
    skin = data.get("skin") if data else None
    if skin not in rules.SKINS:
        return err(400, "unknown skin")
    if not row["skins"] & rules.SKIN_BIT[skin]:
        return err(403, "you have not unlocked that skin")
    store.set_skin(th, rules.SKINS.index(skin))
    return JSONResponse({"progress": to_public(store.get(th))})


async def delete_me(request):
    th, row, bad = player_or_401(request)
    if bad:
        return bad
    store.delete(th)
    hub.drop(th)
    return JSONResponse({"deleted": True})


# ---- live runs ----------------------------------------------------------------------------

class Slot:
    """What the server remembers about one player while they are connected."""

    def __init__(self):
        self.conn = None          # the socket currently speaking for this player
        self.run = None
        self.run_id = None
        self.detached_at = None   # set when the socket drops mid-run


class Hub:
    def __init__(self):
        self.slots = {}
        self.ip_conns = {}

    def slot(self, th):
        return self.slots.setdefault(th, Slot())

    def runs(self):
        return sum(1 for s in self.slots.values() if s.run is not None)

    def drop(self, th):
        s = self.slots.pop(th, None)
        if s and s.conn is not None:
            s.conn.kick()

    def sweep(self, now):
        for th in list(self.slots):
            s = self.slots[th]
            if s.run is not None and (now - s.run.t0 > RUN_MAX_SECONDS or
                                      (s.detached_at is not None and now - s.detached_at > RESUME_SECONDS)):
                s.run, s.run_id = None, None
            if s.conn is None and s.run is None:
                del self.slots[th]


hub = Hub()


def grant_bits(grants):
    bits = {"chapters": 0, "skins": 0, "codex": 0, "best": 0}
    for kind, value in grants:
        if kind == "codex":
            bits["codex"] |= rules.CODEX_BIT[value]
        elif kind == "skin":
            bits["skins"] |= rules.SKIN_BIT[value]
        elif kind == "chapter":
            bits["chapters"] |= 1 << (value - 1)
        elif kind == "best":
            bits["best"] = max(bits["best"], value)
    return bits


def what_is_new(before, after):
    return {
        "codex": [k for k in after["codex"] if k not in before["codex"]],
        "skins": [k for k in after["skins"] if k not in before["skins"]],
        "chapters": [c for c in after["chapters"] if c not in before["chapters"]],
        "best": after["best"] if after["best"] > before["best"] else None,
    }


class Conn:
    def __init__(self, ws):
        self.ws = ws
        self.replaced = False

    def kick(self):
        """Another tab took over this player, or the save was deleted."""
        self.replaced = True
        asyncio.get_running_loop().create_task(self._close())

    async def _close(self):
        try:
            await self.ws.close(code=4000)
        except Exception:
            pass


async def ws_endpoint(ws):
    origin = ws.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        await ws.close(code=1008)
        return
    ip = client_ip(ws.headers, ws.client)
    if hub.ip_conns.get(ip, 0) >= WS_PER_IP:
        await ws.close(code=1008)
        return
    hub.ip_conns[ip] = hub.ip_conns.get(ip, 0) + 1
    conn = Conn(ws)
    th = None
    try:
        await ws.accept()
        th = await authenticate(ws)
        if th is None:
            return
        slot = hub.slot(th)
        if slot.conn is not None:                 # same player opened the game twice
            slot.conn.kick()
        slot.conn, slot.detached_at = conn, None
        row = store.get(th)
        store.touch(th, row["last_seen"], time.time())
        await ws.send_json({"t": "ready", "progress": to_public(row),
                            "resumable": slot.run_id if slot.run is not None else None})
        await serve(ws, conn, th, slot)
    except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError, OSError):
        pass
    finally:
        left = hub.ip_conns.get(ip, 1) - 1
        if left > 0:
            hub.ip_conns[ip] = left
        else:
            hub.ip_conns.pop(ip, None)
        s = hub.slots.get(th) if th else None
        if s is not None and s.conn is conn:
            s.conn = None
            s.detached_at = time.monotonic()
        try:
            await ws.close()
        except Exception:                         # already closed by either side
            pass


async def recv_text(ws, timeout):
    """Next text frame, or None for a binary frame. Raises WebSocketDisconnect when
    the client leaves and asyncio.TimeoutError when it goes quiet."""
    message = await asyncio.wait_for(ws.receive(), timeout)
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    return message.get("text")


async def authenticate(ws):
    text = await recv_text(ws, AUTH_SECONDS)
    if text is None:
        await ws.close(code=1003)
        return None
    try:
        msg = json.loads(text) if len(text) <= MSG_MAX_BYTES else None
    except ValueError:
        msg = None
    token = msg.get("token") if isinstance(msg, dict) and msg.get("t") == "auth" else None
    th = hash_token(token) if isinstance(token, str) and 20 <= len(token) <= 100 else None
    if th is None or store.get(th) is None:
        await ws.send_json({"t": "error", "why": "unknown player"})
        return None
    return th


async def serve(ws, conn, th, slot):
    limiter = deque()
    while not conn.replaced:
        text = await recv_text(ws, IDLE_SECONDS)
        now = time.monotonic()
        if conn.replaced:
            break
        if text is None:                          # the game only sends JSON text
            await ws.close(code=1003)
            return
        if len(text) > MSG_MAX_BYTES:
            await ws.close(code=1009)
            return
        while limiter and now - limiter[0] > 10:
            limiter.popleft()
        limiter.append(now)
        if len(limiter) > MSG_PER_10S:
            await ws.close(code=1008)
            return
        try:
            msg = json.loads(text)
        except ValueError:
            msg = None
        if not isinstance(msg, dict):
            await ws.close(code=1003)
            return
        t = msg.get("t")
        if t == "ping":
            await ws.send_json({"t": "pong"})
        elif t == "start":
            await start_run(ws, slot, msg, now)
        elif t == "resume":
            if slot.run is not None and msg.get("run") == slot.run_id:
                await ws.send_json({"t": "run", "id": slot.run_id, "resumed": True})
            else:
                await ws.send_json({"t": "void", "why": "run expired"})
        elif slot.run is None:
            await ws.send_json({"t": "void", "why": "no run"})
        else:
            await report(ws, th, slot, msg, now)


async def start_run(ws, slot, msg, now):
    if slot.run is None and hub.runs() >= MAX_RUNS:
        hub.sweep(now)
        if hub.runs() >= MAX_RUNS:
            await ws.send_json({"t": "void", "why": "server busy"})
            return
    try:
        slot.run = rules.Run(msg.get("mode"), msg.get("ch"), msg.get("diff", 1), now)
    except rules.Invalid as e:
        slot.run, slot.run_id = None, None
        await ws.send_json({"t": "void", "why": str(e)})
        return
    slot.run_id = secrets.token_hex(8)
    await ws.send_json({"t": "run", "id": slot.run_id})


async def report(ws, th, slot, msg, now):
    run = slot.run
    if now - run.t0 > RUN_MAX_SECONDS:
        run.voided = "run too long"
    was_voided = run.voided
    try:
        grants = run.apply(msg, now)
    except rules.Invalid as e:
        if not was_voided:
            print("void run: %s (%s)" % (e, run.key), flush=True)
            await ws.send_json({"t": "void", "why": str(e)})
        return
    if run.ended:
        slot.run, slot.run_id = None, None
    if not grants:
        return
    row = store.get(th)
    if row is None:                               # save deleted mid-run
        slot.run, slot.run_id = None, None
        return
    before = to_public(row)
    store.grant(th, **grant_bits(grants))
    after = to_public(store.get(th))
    new = what_is_new(before, after)
    if new["codex"] or new["skins"] or new["chapters"] or new["best"] is not None:
        await ws.send_json({"t": "grant", "new": new, "progress": after})


# ---- the game's own files ------------------------------------------------------------------
# The server also hands out the game, so one Render URL is both the game and its API.
# Only these three files are served (the game draws and synthesizes everything else) -
# never the repo root, which also holds .git, the server code and .env.
GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_FILES = {"index.html": "text/html", "game.js": "text/javascript", "style.css": "text/css"}
NO_SNIFF = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"}


def game_file(name):
    path = os.path.join(GAME_DIR, name)

    async def serve_file(request):
        if not os.path.isfile(path):
            return err(404, "not found")
        return FileResponse(path, media_type=GAME_FILES[name], headers=NO_SNIFF)
    return serve_file


def game_routes():
    routes = [Route("/", game_file("index.html"))]
    routes += [Route("/" + n, game_file(n)) for n in GAME_FILES]
    return routes


# ---- app --------------------------------------------------------------------------------

async def housekeeping():
    while True:
        await asyncio.sleep(60)
        hub.sweep(time.monotonic())
        store.prune(time.time())


@asynccontextmanager
async def lifespan(app):
    store.prune(time.time())
    task = asyncio.create_task(housekeeping())
    yield
    task.cancel()


app = Starlette(
    routes=[
        Route("/api/health", health),
        Route("/api/players", create_player, methods=["POST"]),
        Route("/api/me", get_me, methods=["GET"]),
        Route("/api/me", delete_me, methods=["DELETE"]),
        Route("/api/me/skin", equip_skin, methods=["PUT"]),
        WebSocketRoute("/ws", ws_endpoint),
    ] + game_routes(),
    middleware=[Middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                           allow_methods=["GET", "POST", "PUT", "DELETE"],
                           allow_headers=["Authorization", "Content-Type"], max_age=600)],
    lifespan=lifespan,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=_env_int("PORT", 10000), workers=1,
                ws_max_size=4096, ws_ping_interval=20, ws_ping_timeout=20,
                proxy_headers=False, log_level="info")
