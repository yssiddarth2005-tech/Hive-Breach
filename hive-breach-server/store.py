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
abandoned rows are pruned, so the file cannot grow without bound.
"""
import hashlib
import sqlite3
import threading

from game_rules import CODEX, CODEX_BIT, SKIN_BIT, SKINS

DAY = 86400
TOUCH_EVERY = 3600                 # update last_seen at most once an hour
EMPTY_TTL = 7 * DAY                # players with no progress are dropped after a week idle
IDLE_TTL = 180 * DAY               # everyone is dropped after six months idle


class Full(Exception):
    pass


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path, max_players):
        self.max_players = max_players
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS players ("
            " token_hash TEXT PRIMARY KEY,"
            " chapters INTEGER NOT NULL DEFAULT 0,"
            " skins INTEGER NOT NULL DEFAULT %d,"
            " codex INTEGER NOT NULL DEFAULT 0,"
            " skin INTEGER NOT NULL DEFAULT 0,"
            " best INTEGER NOT NULL DEFAULT 0,"
            " created INTEGER NOT NULL,"
            " last_seen INTEGER NOT NULL)" % SKIN_BIT["standard"])

    # -- reads ---------------------------------------------------------------------------
    def get(self, token_hash):
        with self.lock:
            row = self.db.execute(
                "SELECT chapters, skins, codex, skin, best, last_seen FROM players WHERE token_hash=?",
                (token_hash,)).fetchone()
        return None if row is None else dict(zip(("chapters", "skins", "codex", "skin", "best", "last_seen"), row))

    def count(self):
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0]

    # -- writes --------------------------------------------------------------------------
    def create(self, token_hash, now):
        with self.lock:
            n = self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            if n >= self.max_players:
                self._prune(now)
                n = self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
                if n >= self.max_players:
                    raise Full()
            self.db.execute("INSERT INTO players (token_hash, created, last_seen) VALUES (?, ?, ?)",
                            (token_hash, int(now), int(now)))

    def grant(self, token_hash, chapters=0, skins=0, codex=0, best=0):
        """Merge earned progress. Bits are OR-ed and best is MAX-ed in SQL, so two
        writers can never overwrite each other with an older copy."""
        with self.lock:
            self.db.execute(
                "UPDATE players SET chapters = chapters | ?, skins = skins | ?, codex = codex | ?,"
                " best = MAX(best, ?) WHERE token_hash=?",
                (chapters, skins, codex, best, token_hash))

    def set_skin(self, token_hash, index):
        with self.lock:
            self.db.execute("UPDATE players SET skin=? WHERE token_hash=?", (index, token_hash))

    def touch(self, token_hash, last_seen, now):
        if now - last_seen >= TOUCH_EVERY:
            with self.lock:
                self.db.execute("UPDATE players SET last_seen=? WHERE token_hash=?", (int(now), token_hash))

    def delete(self, token_hash):
        with self.lock:
            self.db.execute("DELETE FROM players WHERE token_hash=?", (token_hash,))

    def prune(self, now):
        with self.lock:
            return self._prune(now)

    def _prune(self, now):
        cur = self.db.execute(
            "DELETE FROM players WHERE last_seen < ? OR (last_seen < ? AND chapters = 0"
            " AND codex = 0 AND best = 0 AND skins = ?)",
            (int(now - IDLE_TTL), int(now - EMPTY_TTL), SKIN_BIT["standard"]))
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
