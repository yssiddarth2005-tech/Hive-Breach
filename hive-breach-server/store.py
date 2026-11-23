"""Player storage: one small fixed-size row per player, nothing else.

Runs, kill counts and event history are never written to disk; they live in
memory for the length of a run. The database only holds what a player has
earned, packed into integers:

    token_hash  sha256 of the player's secret token (the token itself is never stored)
    chapters    bit 0 = chapter 1 done, bit 1 = chapter 2 done
    skins       one bit per skin in game_rules.SKINS
    codex       one bit per entry in game_rules.CODEX
    skin        index of the equipped skin
    best        best verified score
    created / last_seen   unix seconds

Every row is the same size, the number of rows is capped (MAX_PLAYERS) and
abandoned rows are pruned, so the database cannot grow without bound.

Two backends, same behaviour:
  * Postgres (Neon) when a DATABASE_URL is given - used in production.
  * a local SQLite file otherwise - for development without any setup.
All SQL is written once with %s placeholders; values are always passed as
parameters, never formatted into the query text.
"""
import hashlib
import sqlite3
import threading
from urllib.parse import urlsplit

from game_rules import CODEX, CODEX_BIT, SKIN_BIT, SKINS

DAY = 86400
TOUCH_EVERY = 3600                 # update last_seen at most once an hour
EMPTY_TTL = 7 * DAY                # players with no progress are dropped after a week idle
IDLE_TTL = 180 * DAY               # everyone is dropped after six months idle

COLUMNS = ("chapters", "skins", "codex", "skin", "best", "last_seen")
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS players ("
    " token_hash TEXT PRIMARY KEY,"
    " chapters BIGINT NOT NULL DEFAULT 0,"
    " skins BIGINT NOT NULL DEFAULT {standard},"
    " codex BIGINT NOT NULL DEFAULT 0,"
    " skin BIGINT NOT NULL DEFAULT 0,"
    " best BIGINT NOT NULL DEFAULT 0,"
    " created BIGINT NOT NULL,"
    " last_seen BIGINT NOT NULL)").format(standard=int(SKIN_BIT["standard"]))


class Full(Exception):
    pass


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class _Sqlite:
    """Local development backend: a single file next to app.py."""
    name = "sqlite"

    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(SCHEMA)

    def execute(self, sql, params=()):
        return self.db.execute(sql.replace("%s", "?").replace("GREATEST(", "MAX("), params)


class _Postgres:
    """Production backend: one connection to Postgres (Neon), reopened if it drops.
    Neon closes idle connections when its compute sleeps, so a dead connection is
    expected now and then; each query is retried once on a fresh connection."""
    name = "postgres"

    def __init__(self, url):
        import psycopg                     # only needed when Postgres is used
        self.psycopg = psycopg
        self.url = url
        host = (urlsplit(url).hostname or "").lower()
        self.local = host in ("", "localhost", "127.0.0.1", "::1")
        self.conn = None
        self._connect()
        self.execute(SCHEMA)

    def _connect(self):
        extra = {} if self.local or "sslmode=" in self.url else {"sslmode": "require"}
        try:
            self.conn = self.psycopg.connect(self.url, autocommit=True, connect_timeout=10,
                                             prepare_threshold=None, **extra)
        except self.psycopg.Error as e:
            # never echo the connection string: it contains the password
            raise RuntimeError("could not connect to the database (%s) - check DATABASE_URL" % type(e).__name__) from None

    def execute(self, sql, params=()):
        for attempt in (1, 2):
            try:
                if self.conn is None or self.conn.closed:
                    self._connect()
                return self.conn.execute(sql, params)
            except self.psycopg.OperationalError:
                try:
                    if self.conn is not None:
                        self.conn.close()
                except Exception:
                    pass
                self.conn = None
                if attempt == 2:
                    raise


class Store:
    def __init__(self, path, max_players, url=None):
        self.max_players = max_players
        self.lock = threading.Lock()
        self.db = _Postgres(url) if url else _Sqlite(path)
        self.backend = self.db.name

    # -- reads ---------------------------------------------------------------------------
    def get(self, token_hash):
        with self.lock:
            row = self.db.execute(
                "SELECT chapters, skins, codex, skin, best, last_seen FROM players WHERE token_hash=%s",
                (token_hash,)).fetchone()
        return None if row is None else dict(zip(COLUMNS, (int(v) for v in row)))

    def count(self):
        with self.lock:
            return int(self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0])

    # -- writes --------------------------------------------------------------------------
    def create(self, token_hash, now):
        with self.lock:
            n = self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            if n >= self.max_players:
                self._prune(now)
                n = self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
                if n >= self.max_players:
                    raise Full()
            self.db.execute("INSERT INTO players (token_hash, created, last_seen) VALUES (%s, %s, %s)"
                            " ON CONFLICT (token_hash) DO NOTHING",
                            (token_hash, int(now), int(now)))

    def grant(self, token_hash, chapters=0, skins=0, codex=0, best=0):
        """Merge earned progress. Bits are OR-ed and best is MAX-ed in SQL, so two
        writers can never overwrite each other with an older copy."""
        with self.lock:
            self.db.execute(
                "UPDATE players SET chapters = chapters | %s, skins = skins | %s, codex = codex | %s,"
                " best = GREATEST(best, %s) WHERE token_hash=%s",
                (int(chapters), int(skins), int(codex), int(best), token_hash))

    def set_skin(self, token_hash, index):
        with self.lock:
            self.db.execute("UPDATE players SET skin=%s WHERE token_hash=%s", (int(index), token_hash))

    def touch(self, token_hash, last_seen, now):
        if now - last_seen >= TOUCH_EVERY:
            with self.lock:
                self.db.execute("UPDATE players SET last_seen=%s WHERE token_hash=%s", (int(now), token_hash))

    def delete(self, token_hash):
        with self.lock:
            self.db.execute("DELETE FROM players WHERE token_hash=%s", (token_hash,))

    def prune(self, now):
        with self.lock:
            return self._prune(now)

    def _prune(self, now):
        cur = self.db.execute(
            "DELETE FROM players WHERE last_seen < %s OR (last_seen < %s AND chapters = 0"
            " AND codex = 0 AND best = 0 AND skins = %s)",
            (int(now - IDLE_TTL), int(now - EMPTY_TTL), int(SKIN_BIT["standard"])))
        return cur.rowcount


def to_public(row):
    """The progress a client is allowed to see, as plain lists."""
    return {
        "chapters": [c for c in (1, 2) if row["chapters"] & (1 << (c - 1))],
        "skins": [k for k in SKINS if row["skins"] & SKIN_BIT[k]],
        "codex": [k for k in CODEX if row["codex"] & CODEX_BIT[k]],
        "skin": SKINS[row["skin"]] if 0 <= row["skin"] < len(SKINS) else "standard",
        "best": row["best"],
    }
