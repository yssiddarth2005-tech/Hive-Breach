"""The rule engine on its own, with a fake clock."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_rules import Invalid, Run, wave_size  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self, dt=0.0):
        self.t += dt
        return self.t


def send(run, clock, msg, wait=0.0):
    return run.apply(msg, clock(wait))


def play_room(run, clock, i, seconds=30, kills=None):
    send(run, clock, {"t": "room", "i": i})
    for _ in range(int(seconds)):
        send(run, clock, {"t": "k", "c": kills or {"crawler": 2}}, wait=1)
    send(run, clock, {"t": "clear", "i": i}, wait=0.5)


def play_boss(run, clock, boss):
    send(run, clock, {"t": "room", "i": 5}, wait=1)
    grants = send(run, clock, {"t": "boss", "b": boss}, wait=4)
    grants += send(run, clock, {"t": "evolve", "b": boss}, wait=10)
    return grants + send(run, clock, {"t": "bosskill", "b": boss}, wait=12)


def honest_chapter(ch):
    clock = Clock()
    run = Run("story", ch, 1, clock())
    grants = []
    for i in range(5):
        send(run, clock, {"t": "room", "i": i}, wait=2)
        for _ in range(50):
            grants += send(run, clock, {"t": "k", "c": {"crawler": 2, "runner": 1}}, wait=1)
        grants += send(run, clock, {"t": "clear", "i": i}, wait=0.5)
    grants += play_boss(run, clock, "queen" if ch == 1 else "zero")
    grants += send(run, clock, {"t": "chdone", "ch": ch}, wait=6)
    return run, clock, grants


# ---- honest play is accepted ---------------------------------------------------------------

def test_honest_chapter_one_unlocks_everything_it_should():
    run, clock, grants = honest_chapter(1)
    assert ("chapter", 1) in grants
    assert ("skin", "hazmat") in grants
    assert ("skin", "crimson") in grants
    assert ("codex", "queen") in grants and ("codex", "queen2") in grants
    assert ("codex", "crawler") in grants and ("codex", "runner") in grants
    assert run.voided is None


def test_honest_chapter_two_unlocks_void_but_not_hazmat():
    run, clock, grants = honest_chapter(2)
    assert ("chapter", 2) in grants and ("skin", "void") in grants
    assert ("skin", "hazmat") not in grants


def test_retrying_a_room_after_dying_is_fine():
    clock = Clock()
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0})
    send(run, clock, {"t": "k", "c": {"crawler": 3}}, wait=5)
    send(run, clock, {"t": "room", "i": 0}, wait=5)          # died, checkpoint restored
    send(run, clock, {"t": "k", "c": {"crawler": 3}}, wait=5)
    send(run, clock, {"t": "clear", "i": 0}, wait=5)
    assert run.voided is None


def test_score_within_what_the_kills_allow_is_accepted():
    run, clock, _ = honest_chapter(1)
    assert send(run, clock, {"t": "score", "s": 40000}) == [("best", 40000)]


def test_honest_endless_waves():
    clock = Clock()
    run = Run("endless", None, 2, clock())
    for n in range(1, 11):
        send(run, clock, {"t": "wave", "n": n}, wait=1)
        send(run, clock, {"t": "k", "c": {"crawler": wave_size(n)}}, wait=20)
    send(run, clock, {"t": "boss", "b": "queen"}, wait=5)
    send(run, clock, {"t": "evolve", "b": "queen"}, wait=10)
    assert ("skin", "crimson") in send(run, clock, {"t": "bosskill", "b": "queen"}, wait=15)
    send(run, clock, {"t": "wave", "n": 11}, wait=3)
    assert run.voided is None


# ---- cheats are refused --------------------------------------------------------------------

@pytest.mark.parametrize("msg", [
    {"t": "chdone", "ch": 1},                       # finish the chapter straight away
    {"t": "bosskill", "b": "queen"},               # kill a boss that never appeared
    {"t": "room", "i": 3},                          # jump to room 4
    {"t": "room", "i": 5},                          # jump to the boss
    {"t": "clear", "i": 0},                         # clear a room never entered
    {"t": "unlock", "skin": "void"},                # ask for a skin
    {"t": "k", "c": {"queen": 1}},                  # report a boss as a normal kill
    {"t": "k", "c": {"crawler": 1}},                # kills before any room
    {"t": "score", "s": 999999},                    # score with no kills
    {"t": "wave", "n": 1},                          # endless report in story
])
def test_forged_reports_void_the_run(msg):
    clock = Clock()
    run = Run("story", 1, 1, clock())
    with pytest.raises(Invalid):
        run.apply(msg, clock(30))
    assert run.voided
    # and nothing is granted afterwards, even for honest-looking reports
    assert run.apply({"t": "room", "i": 0}, clock(1)) == []


def test_room_cleared_too_fast():
    clock = Clock()
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0})
    send(run, clock, {"t": "k", "c": {"crawler": 3}}, wait=1)
    with pytest.raises(Invalid, match="too fast"):
        send(run, clock, {"t": "clear", "i": 0}, wait=1)


def test_drill_room_needs_its_45_seconds():
    clock = Clock()
    run = Run("story", 2, 1, clock())
    for i in range(2):
        play_room(run, clock, i)
    send(run, clock, {"t": "room", "i": 2})
    send(run, clock, {"t": "k", "c": {"husk": 5}}, wait=20)
    with pytest.raises(Invalid, match="too fast"):
        send(run, clock, {"t": "clear", "i": 2}, wait=10)


def test_chapter_two_enemy_in_chapter_one():
    clock = Clock()
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0})
    with pytest.raises(Invalid, match="not in this mode"):
        send(run, clock, {"t": "k", "c": {"husk": 1}}, wait=2)


def test_kill_rate_limits():
    clock = Clock()
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0})
    with pytest.raises(Invalid, match="at once"):
        send(run, clock, {"t": "k", "c": {"crawler": 100, "runner": 100}}, wait=1)
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0}, wait=200)
    with pytest.raises(Invalid, match="kill rate"):
        for _ in range(5):
            send(run, clock, {"t": "k", "c": {"crawler": 50}}, wait=0.5)


def test_boss_killed_too_fast():
    clock = Clock()
    run = Run("story", 1, 1, clock())
    for i in range(5):
        play_room(run, clock, i)
    send(run, clock, {"t": "room", "i": 5}, wait=1)
    send(run, clock, {"t": "boss", "b": "queen"}, wait=4)
    send(run, clock, {"t": "evolve", "b": "queen"}, wait=2)
    with pytest.raises(Invalid, match="too fast"):
        send(run, clock, {"t": "bosskill", "b": "queen"}, wait=1)


def test_amalgam_needs_a_fusion_first():
    clock = Clock()
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0})
    with pytest.raises(Invalid, match="fused"):
        send(run, clock, {"t": "k", "c": {"amalgam": 1}}, wait=3)
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0})
    send(run, clock, {"t": "fuse"}, wait=3)
    assert ("skin", "swarm") in send(run, clock, {"t": "k", "c": {"amalgam": 1}}, wait=3)


def test_score_above_cap():
    clock = Clock()
    run = Run("story", 1, 0, clock())
    send(run, clock, {"t": "room", "i": 0})
    send(run, clock, {"t": "k", "c": {"crawler": 10}}, wait=5)
    cap = run.score_cap()
    send(run, clock, {"t": "score", "s": int(cap)})
    with pytest.raises(Invalid, match="score"):
        send(run, clock, {"t": "score", "s": int(cap) + 10})


def test_endless_wave_skipping():
    clock = Clock()
    run = Run("endless", None, 1, clock())
    send(run, clock, {"t": "wave", "n": 1})
    with pytest.raises(Invalid, match="out of order"):
        send(run, clock, {"t": "wave", "n": 9}, wait=30)


def test_endless_wave_with_no_kills():
    clock = Clock()
    run = Run("endless", None, 1, clock())
    send(run, clock, {"t": "wave", "n": 1})
    with pytest.raises(Invalid, match="enough kills"):
        send(run, clock, {"t": "wave", "n": 2}, wait=30)


@pytest.mark.parametrize("bad", [
    {"t": "k", "c": {"crawler": -5}},
    {"t": "k", "c": {"crawler": True}},
    {"t": "k", "c": {"crawler": 1.5}},
    {"t": "k", "c": []},
    {"t": "k", "c": {"__proto__": 1}},
    {"t": "room", "i": "0"},
    {"t": "score", "s": 10 ** 12},
    {"t": None},
    {"t": "_void"},
])
def test_malformed_reports(bad):
    clock = Clock()
    run = Run("story", 1, 1, clock())
    send(run, clock, {"t": "room", "i": 0})
    with pytest.raises(Invalid):
        send(run, clock, bad, wait=2)


def test_bad_run_settings():
    with pytest.raises(Invalid):
        Run("story", 3, 1, 0)
    with pytest.raises(Invalid):
        Run("god", None, 1, 0)
    with pytest.raises(Invalid):
        Run("endless", None, 7, 0)
