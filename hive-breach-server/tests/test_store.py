"""Storage layer, run against SQLite always and against Postgres when
TEST_DATABASE_URL points at a throwaway database (it is wiped by these tests)."""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from game_rules import CODEX_BIT, SKIN_BIT  # noqa: E402
from store import Full, Store, hash_token, to_public  # noqa: E402

PG = os.environ.get("TEST_DATABASE_URL", "").strip()
BACKENDS = ["sqlite"] + (["postgres"] if PG else [])


@pytest.fixture(params=BACKENDS)
def store(request):
    if request.param == "sqlite":
        s = Store(os.path.join(tempfile.mkdtemp(), "t.db"), 5)
    else:
        s = Store(None, 5, url=PG)
        s.db.execute("DELETE FROM players")
    yield s


def test_backend_is_what_was_asked(store):
    assert store.backend in BACKENDS


def test_create_get_and_hash_only(store):
    th = hash_token("a" * 40)
    store.create(th, 1000)
    row = store.get(th)
    assert to_public(row) == {"chapters": [], "skins": ["standard"], "codex": [], "skin": "standard", "best": 0}
    assert store.get(hash_token("b" * 40)) is None
    assert store.db.execute("SELECT COUNT(*) FROM players WHERE token_hash=%s", ("a" * 40,)).fetchone()[0] == 0


def test_grant_merges_bits_and_keeps_best_max(store):
    th = hash_token("c" * 40)
    store.create(th, 1000)
    store.grant(th, skins=SKIN_BIT["crimson"], codex=CODEX_BIT["queen"], best=500)
    store.grant(th, skins=SKIN_BIT["void"], codex=CODEX_BIT["zero2"], chapters=1, best=200)
    store.grant(th, best=1_999_999_999)
    p = to_public(store.get(th))
    assert set(p["skins"]) == {"standard", "crimson", "void"}
    assert set(p["codex"]) == {"queen", "zero2"}
    assert p["chapters"] == [1] and p["best"] == 1_999_999_999


def test_skin_touch_delete(store):
    th = hash_token("d" * 40)
    store.create(th, 1000)
    store.set_skin(th, 2)
    assert store.get(th)["skin"] == 2
    store.touch(th, 1000, 1000 + 10)          # too soon: unchanged
    assert store.get(th)["last_seen"] == 1000
    store.touch(th, 1000, 1000 + 4000)
    assert store.get(th)["last_seen"] == 5000
    store.delete(th)
    assert store.get(th) is None


def test_cap_and_prune(store):
    day = 86400
    for i in range(5):
        store.create(hash_token("p%038d" % i), 0)
    with pytest.raises(Full):
        store.create(hash_token("x" * 40), 1 * day)  # nobody is idle long enough yet
    keep = hash_token("p%038d" % 0)
    store.grant(keep, best=10)                       # has progress: survives the 7-day prune
    store.create(hash_token("y" * 40), 8 * day)      # full -> prunes the empty idle players
    assert store.count() == 2 and store.get(keep) is not None


def test_create_is_safe_to_repeat(store):
    th = hash_token("e" * 40)
    store.create(th, 1000)
    store.create(th, 1000)                           # a retried insert must not crash
    assert store.count() == 1


def test_injection_strings_are_just_data(store):
    evil = "x'); DROP TABLE players; --"
    assert store.get(evil) is None
    store.create(evil, 1000)
    assert store.get(evil) is not None and store.count() == 1
