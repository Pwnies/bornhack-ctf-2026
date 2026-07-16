import pytest

from backend import config, sessions
from backend.games import game4_seed as g4
from backend.games.game4_seed import SeedMatch

# The known base=0 mate-in-3 line: g2g3 f7f5 e2e3 g7g5 Qh5#.
WIN_LINE = ["g2g3", "e2e3", "d1h5"]

pytestmark = pytest.mark.skipif(
    config.SEED_BASE != 0, reason="WIN_LINE is calibrated for SEED_BASE=0"
)


def _play_game(game, sess, moves=WIN_LINE):
    out = None
    for mv in moves:
        out = game.move(sess, mv)
    return out


def test_start_envelope():
    resp = g4.start()
    assert resp["streak"] == 0
    assert resp["target"] == 100
    assert resp["moves_left"] == 3
    assert resp["time_left"] <= 120
    assert resp["message"] == g4.INTRO


def test_run_times_out():
    game = SeedMatch("FLAG{x}", target=100, time_limit=120)
    sess = sessions.get(game.start()["session"])
    sess.data["run_start"] -= 121  # pretend the clock already ran out
    out = game.move(sess, "g2g3")  # otherwise-legal move
    assert out["status"] == "failed"
    assert "Time up" in out["message"]
    assert out["time_left"] == 0


def test_single_win_increments_streak():
    game = SeedMatch("FLAG{x}", target=100)
    sess = sessions.get(game.start()["session"])
    out = _play_game(game, sess)
    assert sess.data["streak"] == 1
    assert "Streak 1/100" in out["message"]
    # A fresh sub-game is dealt (standard start position, White to move).
    assert out["moves_left"] == 3


def test_illegal_move_resets_streak():
    game = SeedMatch("FLAG{x}", target=100)
    sess = sessions.get(game.start()["session"])
    _play_game(game, sess)
    assert sess.data["streak"] == 1
    out = game.move(sess, "e2e5")  # illegal on the fresh board
    assert sess.data["streak"] == 0
    assert "Illegal" in out["message"]


def test_full_match_victory_returns_flag():
    game = SeedMatch("FLAG{seed}", target=3)
    sess = sessions.get(game.start()["session"])
    last = None
    for _ in range(3):
        last = _play_game(game, sess)
    assert sess.status == "victory"
    assert "FLAG{seed}" in last["message"]


def test_determinism_same_first_move_same_reply():
    # Two independent matches: the same first move must yield the same Black reply.
    g_a = SeedMatch("A", target=100)
    g_b = SeedMatch("B", target=100)
    sa = sessions.get(g_a.start()["session"])
    sb = sessions.get(g_b.start()["session"])
    ra = g_a.move(sa, "g2g3")
    rb = g_b.move(sb, "g2g3")
    assert ra["last_move"] == rb["last_move"] == "f7f5"
