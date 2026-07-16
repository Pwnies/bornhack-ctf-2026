import chess

from backend import sessions
from backend.games import game3_maze as g3
from backend.games.game3_maze import START, GOAL, bfs_path


def _drive_to_goal(sess, game):
    """Solve exactly one maze by walking the BFS path; return the completing response."""
    start_solved = sess.data["solved"]
    while True:
        d = sess.data
        path = bfs_path(d["king_sq"], GOAL, d["unsafe"], d["blocked"])
        assert path is not None, "maze served was unsolvable"
        uci = chess.square_name(d["king_sq"]) + chess.square_name(path[1])
        resp = game.move(sess, uci)
        # Completing a maze increments `solved` (and either advances or wins).
        if sess.status != "in_progress" or sess.data["solved"] != start_solved:
            return resp


def test_generated_mazes_are_solvable():
    for _ in range(50):
        board, unsafe, blocked = g3.generate_maze()
        assert START not in blocked and START not in unsafe
        assert GOAL not in blocked and GOAL not in unsafe
        assert bfs_path(START, GOAL, unsafe, blocked) is not None


def test_start_envelope():
    game = g3.MazeGame("FLAG{x}", total=5, time_limit=999)
    resp = game.start()
    assert resp["turn"] == "w"
    assert resp["solved"] == 0
    assert resp["total"] == 5
    assert resp["goal"] == "h8"
    assert resp["message"] == g3.INTRO
    # The lone White king is on a1.
    assert chess.Board(resp["fen"]).piece_at(chess.A1) == chess.Piece(chess.KING, chess.WHITE)


def test_illegal_step_resets_progress():
    game = g3.MazeGame("FLAG{x}", total=5, time_limit=999)
    resp = game.start()
    sess = sessions.get(resp["session"])
    # Solve one maze so solved > 0, then make an illegal move.
    _drive_to_goal(sess, game)
    assert sess.data["solved"] == 1
    out = game.move(sess, "a1a8")  # not a king step -> illegal -> reset
    assert out["error"] and "reset" in out["error"].lower()
    assert out["solved"] == 0
    assert sess.data["king_sq"] == START
    assert sess.status == "in_progress"


def test_full_run_wins_and_returns_flag():
    game = g3.MazeGame("FLAG{maze}", total=3, time_limit=999)
    resp = game.start()
    sess = sessions.get(resp["session"])
    last = None
    for _ in range(3):
        last = _drive_to_goal(sess, game)
    assert sess.status == "victory"
    assert "FLAG{maze}" in last["message"]
    assert last["solved"] == 3


def test_time_up_fails():
    game = g3.MazeGame("FLAG{x}", total=5, time_limit=0)  # already expired
    resp = game.start()
    sess = sessions.get(resp["session"])
    d = sess.data
    path = bfs_path(d["king_sq"], GOAL, d["unsafe"], d["blocked"])
    uci = chess.square_name(d["king_sq"]) + chess.square_name(path[1])
    out = game.move(sess, uci)
    assert out["status"] == "failed"
    assert "Time up" in out["message"]
