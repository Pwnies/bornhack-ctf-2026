import chess

from backend import engine, sessions
from backend.games import game1_random
from backend.games._random_bot_game import RandomBotGame


def test_seeded_bot_is_deterministic():
    rng1 = engine.make_rng("e2e4")
    rng2 = engine.make_rng("e2e4")
    b1, b2 = chess.Board(), chess.Board()
    b1.push_uci("e2e4")
    b2.push_uci("e2e4")
    assert engine.random_bot_move(b1, rng1) == engine.random_bot_move(b2, rng2)


def test_stable_hash_matches_across_calls():
    assert engine.stable_hash("e2e4") == engine.stable_hash("e2e4")


def test_start_envelope():
    resp = game1_random.start()
    assert resp["turn"] == "w"
    assert resp["status"] == "in_progress"
    assert resp["moves_left"] == 10
    assert resp["hidden"] is False
    assert resp["message"] == game1_random.INTRO
    assert chess.Board().fen() == resp["fen"]


def test_illegal_move_rejected_but_not_fatal():
    resp = game1_random.start()
    sess = sessions.get(resp["session"])
    out = game1_random.move(sess, "e2e5")  # illegal from start
    assert out["status"] == "in_progress"
    assert out["error"]
    assert sess.data["white_moves"] == 0


def test_victory_on_checkmate():
    resp = game1_random.start()
    sess = sessions.get(resp["session"])
    # Back-rank mate in 1 for White: Ra1-a8#.
    sess.board = chess.Board("6k1/5ppp/8/8/8/8/8/R6K w - - 0 1")
    out = game1_random.move(sess, "a1a8")
    assert out["status"] == "victory"
    assert game1_random.GAME.flag in out["message"]


def test_out_of_moves_is_a_loss():
    game = RandomBotGame("t_oom", "FLAG{x}", "intro", max_white_moves=1)
    start = game.start()
    sess = sessions.get(start["session"])
    out = game.move(sess, "e2e4")  # legal, not mate; hits the 1-move cap
    assert out["status"] == "failed"
    assert "out of moves" in out["message"]


def test_game1_bot_is_unseeded_and_unpredictable():
    # Games 1 & 2 use a fresh RNG per game (seeded_bot=False), so the SAME White
    # first move can draw different Black replies across games — unlike Game 4.
    replies = set()
    for _ in range(40):
        resp = game1_random.start()
        sess = sessions.get(resp["session"])
        out = game1_random.move(sess, "e2e4")
        replies.add(out["last_move"])  # Black's reply
    assert len(replies) > 1  # not locked to White's first move


def test_illegal_loses_variant():
    game = RandomBotGame("t_il", "FLAG{x}", "intro", illegal_loses=True)
    start = game.start()
    sess = sessions.get(start["session"])
    out = game.move(sess, "e2e5")  # illegal -> immediate loss
    assert out["status"] == "failed"
    assert "illegal" in out["message"].lower()
