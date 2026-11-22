"""Server-side rules for HIVE BREACH.

The browser only *reports* what happened in a run (rooms entered, kills,
bosses, waves, score). Nothing here trusts a claim on its own: every report is
checked against the run so far, the game's own numbers (spawn counts, boss
fight phases, minimum objective times, score per kill) and the server clock.
Progress (codex entries, skins, chapters, best score) is granted only when the
checks pass. If a report is impossible, the whole run is voided and grants
nothing more.

This module is pure Python with no I/O so it can be tested on its own.
"""
from collections import deque

# ---- game data (mirrors the numbers in game.js) -----------------------------

SKINS = ["standard", "crimson", "void", "swarm", "hazmat"]
CODEX = ["crawler", "runner", "brute", "spitter", "exploder", "flyer", "phantom",
         "bulwark", "splitter", "mite", "mender", "tunneler", "node", "husk",
         "trooper", "sapper", "blighter", "carrier", "amalgam", "queen", "queen2",
         "zero", "zero2"]
SKIN_BIT = {k: 1 << i for i, k in enumerate(SKINS)}
CODEX_BIT = {k: 1 << i for i, k in enumerate(CODEX)}

# credits value per enemy type; the game scores a kill as cr * 10 * combo * difficulty
CREDIT = {"crawler": 6, "runner": 5, "brute": 22, "spitter": 14, "exploder": 9,
          "flyer": 8, "phantom": 16, "bulwark": 24, "splitter": 18, "mite": 2,
          "mender": 20, "tunneler": 18, "node": 20, "husk": 8, "trooper": 13,
          "sapper": 13, "blighter": 14, "carrier": 260, "amalgam": 160,
          "queen": 400, "zero": 800}
DIFF_SCORE = [0.7, 1.0, 1.6]
MAX_COMBO = 5.0
BOSS_BONUS = {"queen": 5000, "zero": 15000}
BOSSES = ("queen", "zero")
CHAPTER_BOSS = {1: "queen", 2: "zero"}
BOSS_ROOM = 5                     # rooms 0-4 have objectives, room 5 is the lair

# which enemies can exist in each mode (spawn tables, boss summons, splits, fusions)
_SHARED = {"mite", "amalgam", "node"}
ALLOWED = {
    "story1": {"crawler", "runner", "spitter", "exploder", "flyer", "brute", "phantom",
               "mender", "bulwark", "splitter", "tunneler"} | _SHARED,
    "story2": {"crawler", "runner", "husk", "trooper", "sapper", "blighter", "spitter",
               "tunneler", "phantom", "carrier", "brute", "exploder"} | _SHARED,
    "endless": {"crawler", "runner", "spitter", "exploder", "flyer", "brute", "phantom",
                "bulwark", "splitter", "mender", "tunneler"} | _SHARED,
}

# ---- plausibility limits (generous on purpose: a real player must never trip them)

MIN_ROOM_SECONDS = 8.0
MIN_ROOM_SECONDS_FOR = {(1, 2): 22.0,   # cryo console: 24 s in the zone
                        (2, 2): 43.0}   # drill site: defend for 45 s
MIN_BOSS_STAGE1 = 1.0                   # spawn -> evolve (strong builds melt stage one)
MIN_BOSS_STAGE2 = 4.0                   # evolve -> death (the evolution alone takes 4.4 s)
MIN_BOSS_TOTAL = {"queen": 7.0, "zero": 9.0}
MIN_DONE_AFTER_BOSS = 4.0               # 6 s epilogue before the chapter ends
MIN_WAVE_SECONDS = 5.0
MAX_BATCH = 150                         # kills in one report
KILL_WINDOW = 10.0
MAX_KILLS_PER_WINDOW = 180
KILLS_BASE, KILLS_PER_SEC = 300, 10.0   # lifetime cap for a run: base + rate * seconds
STORY_FUSIONS_PER_ROOM = 2
MAX_WAVE = 500


def wave_size(n):
    """Enemies queued for endless wave n (buildWave in game.js)."""
    if n == 10:
        return 46
    if n == 20:
        return 50
    if n > 10:
        return min(96, 56 + (n - 10) * 4)
    return 10 + n * 6


def is_boss_wave(n):
    return n == 10 or n == 20 or (n > 20 and n % 5 == 0)


def boss_for_wave(n):
    if n == 10:
        return "queen"
    return "zero" if n % 10 == 0 else "queen"


class Invalid(Exception):
    """A report that cannot have come from a real run."""


def _int(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise Invalid("bad " + what)
    return v


class Run:
    """One play session, from 'start' until 'end'. Lives in memory only."""

    def __init__(self, mode, chapter, diff, now):
        if mode == "story":
            self.key = "story%d" % _int(chapter, 1, 2, "chapter")
            self.chapter = chapter
        elif mode == "endless":
            self.key = "endless"
            self.chapter = None
        else:
            raise Invalid("bad mode")
        self.mode = mode
        self.diff = _int(diff, 0, 2, "difficulty")
        self.t0 = now
        self.voided = None
        self.ended = False
        # story
        self.room = -1
        self.room_t0 = now
        self.room_cleared = False
        self.room_kills = 0
        self.room_fuses = 0
        self.cleared = set()
        self.chapter_done = False
        # endless
        self.wave = 0
        self.wave_t0 = now
        self.wave_kills = 0
        self.wave_fuses = 0
        # both
        self.kills = {}
        self.total_kills = 0
        self.window = deque()            # (time, count) for the sliding kill window
        self.window_sum = 0
        self.fuses = 0
        self.boss = None                 # {"b", "t_spawn", "t_evolve", "t_kill"}
        self.boss_kills = []
        self.last_boss_kill_t = None

    # -- helpers ---------------------------------------------------------------
    def elapsed(self, now):
        return now - self.t0

    def score_cap(self):
        mult = 10 * MAX_COMBO * DIFF_SCORE[self.diff]
        cap = sum(CREDIT[t] * n for t, n in self.kills.items()) * mult
        for b in self.boss_kills:
            cap += CREDIT[b] * mult + BOSS_BONUS[b]
        return cap + 0.5 * (self.total_kills + len(self.boss_kills)) + 1

    def _void(self, why):
        self.voided = why
        raise Invalid(why)

    # -- the single entry point ---------------------------------------------------
    def apply(self, msg, now):
        """Check one report. Returns a list of (kind, value) grants.
        Raises Invalid (and voids the run) when the report is impossible."""
        if self.voided or self.ended:
            return []
        handler = self._handlers().get(msg.get("t"))
        if handler is None:
            self._void("unknown report")
        try:
            return handler(msg, now)
        except Invalid as e:
            self.voided = str(e)
            raise

    def _handlers(self):
        return {"room": self._on_room, "clear": self._on_clear, "chdone": self._on_chdone,
                "wave": self._on_wave, "k": self._on_k, "fuse": self._on_fuse,
                "boss": self._on_boss, "evolve": self._on_evolve,
                "bosskill": self._on_bosskill, "score": self._on_score, "end": self._on_end}

    # -- story ---------------------------------------------------------------------
    def _on_room(self, msg, now):
        if self.mode != "story":
            raise Invalid("room outside story")
        i = _int(msg.get("i"), 0, BOSS_ROOM, "room")
        if i == self.room:                       # died and retried the same room
            pass
        elif i == self.room + 1 and (self.room == -1 or self.room_cleared):
            pass
        else:
            raise Invalid("rooms out of order")
        self.room = i
        self.room_t0 = now
        self.room_cleared = False
        self.room_kills = 0
        self.room_fuses = 0
        if i == BOSS_ROOM:
            self.boss = None                     # a retry restarts the boss fight
        return []

    def _on_clear(self, msg, now):
        i = _int(msg.get("i"), 0, BOSS_ROOM - 1, "room")
        if self.mode != "story" or i != self.room or self.room_cleared:
            raise Invalid("clear for the wrong room")
        need = MIN_ROOM_SECONDS_FOR.get((self.chapter, i), MIN_ROOM_SECONDS)
        if now - self.room_t0 < need:
            raise Invalid("room cleared too fast")
        if self.room_kills < 1:
            raise Invalid("room cleared without a fight")
        self.room_cleared = True
        self.cleared.add(i)
        return []

    def _on_chdone(self, msg, now):
        ch = _int(msg.get("ch"), 1, 2, "chapter")
        if self.mode != "story" or ch != self.chapter or self.chapter_done:
            raise Invalid("wrong chapter")
        if self.cleared != set(range(BOSS_ROOM)) or self.room != BOSS_ROOM:
            raise Invalid("chapter finished without its rooms")
        b = self.boss
        if not b or b["b"] != CHAPTER_BOSS[ch] or b["t_kill"] is None:
            raise Invalid("chapter finished without its boss")
        if now - b["t_kill"] < MIN_DONE_AFTER_BOSS:
            raise Invalid("chapter finished too fast")
        self.chapter_done = True
        grants = [("chapter", ch)]
        if ch == 1:
            grants.append(("skin", "hazmat"))
        return grants

    # -- endless ---------------------------------------------------------------------
    def _on_wave(self, msg, now):
        n = _int(msg.get("n"), 1, MAX_WAVE, "wave")
        if self.mode != "endless" or n != self.wave + 1:
            raise Invalid("waves out of order")
        if self.wave >= 1:
            prev = self.wave
            if now - self.wave_t0 < MIN_WAVE_SECONDS:
                raise Invalid("wave cleared too fast")
            if is_boss_wave(prev):
                if not self.boss or self.boss["t_kill"] is None:
                    raise Invalid("boss wave skipped")
            elif self.wave_kills < int(wave_size(prev) * 0.3):
                raise Invalid("wave cleared without enough kills")
        self.wave = n
        self.wave_t0 = now
        self.wave_kills = 0
        self.wave_fuses = 0
        if is_boss_wave(n):
            self.boss = None
        return []

    # -- both ------------------------------------------------------------------------
    def _in_fight(self):
        return self.room >= 0 if self.mode == "story" else self.wave >= 1

    def _on_k(self, msg, now):
        c = msg.get("c")
        if not isinstance(c, dict) or not 0 < len(c) <= len(CREDIT):
            raise Invalid("bad kill report")
        if not self._in_fight():
            raise Invalid("kills outside a fight")
        allowed = ALLOWED[self.key]
        batch = 0
        for typ, n in c.items():
            if typ not in allowed:
                raise Invalid("enemy not in this mode")
            batch += _int(n, 1, MAX_BATCH, "kill count")
        if batch > MAX_BATCH:
            raise Invalid("too many kills at once")
        # sliding window and lifetime rate
        while self.window and now - self.window[0][0] > KILL_WINDOW:
            self.window_sum -= self.window.popleft()[1]
        if self.window_sum + batch > MAX_KILLS_PER_WINDOW:
            raise Invalid("kill rate too high")
        if self.total_kills + batch > KILLS_BASE + KILLS_PER_SEC * self.elapsed(now):
            raise Invalid("too many kills for the time played")
        amal = c.get("amalgam", 0)
        if amal and self.kills.get("amalgam", 0) + amal > self.fuses:
            raise Invalid("amalgam killed before it fused")
        if self.mode == "endless" and not is_boss_wave(self.wave):
            if self.wave_kills + batch > wave_size(self.wave) * 4 + 80:
                raise Invalid("more kills than the wave holds")
        self.window.append((now, batch))
        self.window_sum += batch
        grants = []
        for typ, n in c.items():
            if typ not in self.kills:
                grants.append(("codex", typ))
            self.kills[typ] = self.kills.get(typ, 0) + n
        if amal:
            grants.append(("skin", "swarm"))
        self.total_kills += batch
        self.room_kills += batch
        self.wave_kills += batch
        return grants

    def _on_fuse(self, msg, now):
        if self.mode == "story":
            if not 0 <= self.room < BOSS_ROOM or self.room_fuses >= STORY_FUSIONS_PER_ROOM:
                raise Invalid("fusion not possible here")
            self.room_fuses += 1
        else:
            limit = 3 if self.wave >= 12 else 2
            live_boss = self.boss is not None and self.boss["t_kill"] is None
            if self.wave <= 5 or self.wave_fuses >= limit or live_boss:
                raise Invalid("fusion not possible here")
            self.wave_fuses += 1
        self.fuses += 1
        return []

    def _boss_name(self, msg):
        b = msg.get("b")
        if b not in BOSSES:
            raise Invalid("bad boss")
        return b

    def _on_boss(self, msg, now):
        b = self._boss_name(msg)
        if self.mode == "story":
            if self.room != BOSS_ROOM or b != CHAPTER_BOSS[self.chapter]:
                raise Invalid("boss in the wrong place")
        elif not is_boss_wave(self.wave) or b != boss_for_wave(self.wave):
            raise Invalid("boss in the wrong wave")
        if self.boss is not None:
            raise Invalid("boss already up")
        self.boss = {"b": b, "t_spawn": now, "t_evolve": None, "t_kill": None}
        return []

    def _on_evolve(self, msg, now):
        b = self._boss_name(msg)
        s = self.boss
        if not s or s["b"] != b or s["t_evolve"] is not None:
            raise Invalid("evolve without a boss")
        if now - s["t_spawn"] < MIN_BOSS_STAGE1:
            raise Invalid("boss stage 1 too fast")
        s["t_evolve"] = now
        return [("codex", b)]

    def _on_bosskill(self, msg, now):
        b = self._boss_name(msg)
        s = self.boss
        if not s or s["b"] != b or s["t_evolve"] is None or s["t_kill"] is not None:
            raise Invalid("boss kill without the fight")
        if now - s["t_evolve"] < MIN_BOSS_STAGE2 or now - s["t_spawn"] < MIN_BOSS_TOTAL[b]:
            raise Invalid("boss killed too fast")
        s["t_kill"] = now
        self.boss_kills.append(b)
        return [("codex", b + "2"), ("skin", "crimson" if b == "queen" else "void")]

    def _on_score(self, msg, now):
        s = _int(msg.get("s"), 0, 2_000_000_000, "score")
        if s > self.score_cap():
            raise Invalid("score higher than the kills allow")
        return [("best", s)] if s > 0 else []

    def _on_end(self, msg, now):
        self.ended = True
        return []
