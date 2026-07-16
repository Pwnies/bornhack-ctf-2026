"""Game 3, Behind enemy lines (medium)

A board full of STATIC black pieces and a lone White King on a1 that must reach a8.
Only White moves. The King may step to an adjacent square that is empty and not
attacked by any black piece. An illegal move resets the whole run back to maze 1.
Solve `TOTAL_MAZES` within `TIME_LIMIT` seconds to win.

Safety model (must match the solver exactly): black attacks are computed with the
King removed from the board ("king-transparent"), so a slider's reach is maximal and
does not depend on where the King stands. The King can only ever block a black slider,
never open a new line — so a square that is safe stays safe for the entire maze.
"""
from __future__ import annotations

import random
import time
from typing import Any, Optional

import chess

from .. import engine, sessions
from ..config import FLAGS

START = chess.A1
GOAL = chess.H8  # opposite corner — a proper corner-to-corner maze

TOTAL_MAZES = 100
TIME_LIMIT = 120  # seconds for the whole run

INTRO = (
    "Move your King from A1 to H8 using safe/empty squares\n"
    f"Clear {TOTAL_MAZES} mazes in {TIME_LIMIT}s - Any illegal step resets the whole run!"
)

_PIECE_WEIGHTS = [
    (chess.PAWN, 35), (chess.KNIGHT, 25), (chess.BISHOP, 20),
    (chess.ROOK, 15), (chess.QUEEN, 5),
]
_PIECES = [p for p, w in _PIECE_WEIGHTS for _ in range(w)]


# --------------------------------------------------------------------------- #
# Geometry helpers (shared with generation + BFS verification)
# --------------------------------------------------------------------------- #
def king_neighbors(sq: int) -> list[int]:
    f, r = chess.square_file(sq), chess.square_rank(sq)
    out = []
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            nf, nr = f + df, r + dr
            if 0 <= nf < 8 and 0 <= nr < 8:
                out.append(chess.square(nf, nr))
    return out


def bfs_path(start: int, goal: int, unsafe: set[int], blocked: set[int]) -> Optional[list[int]]:
    """Shortest safe king path start -> goal, or None if unreachable."""
    prev: dict[int, Optional[int]] = {start: None}
    frontier = [start]
    while frontier:
        nxt = []
        for cur in frontier:
            if cur == goal:
                path, s = [], cur
                while s is not None:
                    path.append(s)
                    s = prev[s]
                return path[::-1]
            for n in king_neighbors(cur):
                if n in prev or n in blocked or n in unsafe:
                    continue
                prev[n] = cur
                nxt.append(n)
        frontier = nxt
    return None


def bfs_reachable(start: int, goal: int, unsafe: set[int], blocked: set[int]) -> bool:
    return bfs_path(start, goal, unsafe, blocked) is not None


# --------------------------------------------------------------------------- #
# Maze generation
# --------------------------------------------------------------------------- #
def _carve_path() -> list[int]:
    """A self-avoiding king path a1 -> h8, built constructively in O(n).

    Ascend one rank per step (file may drift +/-1 each step, so the path wanders),
    then slide right along the top rank to h8. Because rank strictly increases during
    the climb and the slide stays on rank 8 with strictly increasing file, the path
    is always self-avoiding and valid — no backtracking, so it can never blow up.
    """
    f, r = 0, 0  # a1
    path = [chess.square(f, r)]
    while r < 7:  # climb to rank 8, drifting in file
        r += 1
        f = random.choice([nf for nf in (f - 1, f, f + 1) if 0 <= nf < 8])
        path.append(chess.square(f, r))
    while f < 7:  # slide right to the h-file (h8)
        f += 1
        path.append(chess.square(f, r))
    return path


def generate_maze() -> tuple[chess.Board, set[int], set[int]]:
    """Return (black-only board, unsafe squares, blocked squares) for a solvable maze.

    The carved path is always safe and empty, so the first attempt essentially always
    succeeds; the retry cap + empty-board fallback make a hang impossible regardless.
    """
    for _ in range(20):
        path = _carve_path()
        path_set = set(path)
        board = chess.Board.empty()

        candidates = [sq for sq in chess.SQUARES if sq not in path_set]
        random.shuffle(candidates)
        for sq in candidates:
            ptype = random.choice(_PIECES)
            if ptype == chess.PAWN and chess.square_rank(sq) in (0, 7):
                continue  # pawns never on rank 1/8 (keeps the FEN legal)
            board.set_piece_at(sq, chess.Piece(ptype, chess.BLACK))
            # A newly placed piece may only reduce other sliders' reach, so it is
            # enough to check that THIS piece does not hit a path square.
            if any(p in board.attacks(sq) for p in path):
                board.remove_piece_at(sq)

        unsafe = {sq for sq in chess.SQUARES if board.is_attacked_by(chess.BLACK, sq)}
        blocked = set(board.piece_map().keys())
        if bfs_reachable(START, GOAL, unsafe, blocked):
            return board, unsafe, blocked

    # Unreachable in practice (the invariant guarantees success): serve an empty board.
    empty = chess.Board.empty()
    return empty, set(), set()


def _fen_with_king(board: chess.Board, king_sq: int) -> str:
    view = board.copy()
    view.set_piece_at(king_sq, chess.Piece(chess.KING, chess.WHITE))
    view.turn = chess.WHITE
    return view.fen()


# --------------------------------------------------------------------------- #
# Game
# --------------------------------------------------------------------------- #
class MazeGame:
    def __init__(self, flag: str, total: int = TOTAL_MAZES, time_limit: int = TIME_LIMIT):
        self.flag = flag
        self.total = total
        self.time_limit = time_limit

    def _new_maze(self, sess: engine.GameSession) -> None:
        board, unsafe, blocked = generate_maze()
        sess.data.update(board=board, unsafe=unsafe, blocked=blocked, king_sq=START)

    def start(self) -> dict[str, Any]:
        board = chess.Board.empty()  # placeholder; real board set by _new_maze
        sess = sessions.create("game3", board, {"solved": 0, "run_start": time.time()})
        self._new_maze(sess)
        return self._view(sess, message=INTRO)

    def _time_left(self, sess: engine.GameSession) -> float:
        return max(0.0, self.time_limit - (time.time() - sess.data["run_start"]))

    def _view(self, sess, *, message=None, error=None) -> dict[str, Any]:
        d = sess.data
        sess.board = d["board"]  # keep session.board coherent for any generic code
        fen = _fen_with_king(d["board"], d["king_sq"])
        return {
            "session": sess.id, "fen": fen, "turn": "w",
            "last_move": sess.last_move, "status": sess.status,
            "message": message, "error": error,
            "solved": d["solved"], "total": self.total,
            "time_left": round(self._time_left(sess), 1),
            "goal": chess.square_name(GOAL),
        }

    def move(self, sess: engine.GameSession, uci: str) -> dict[str, Any]:
        if sess.status != "in_progress":
            return self._view(sess, error="Run already over. Start a new one.")

        if self._time_left(sess) <= 0:
            sess.status = "failed"
            return self._view(sess, message=f"Time up — {sess.data['solved']}/{self.total} solved.")

        d = sess.data
        cur = d["king_sq"]
        mv = engine.parse_move(uci)
        legal = (
            mv is not None
            and mv.from_square == cur
            and chess.square_distance(cur, mv.to_square) == 1
            and mv.to_square not in d["blocked"]
            and mv.to_square not in d["unsafe"]
        )

        if not legal:
            # Any illegal step wipes progress back to maze 1 (the clock keeps running).
            d["solved"] = 0
            sess.last_move = None
            self._new_maze(sess)
            return self._view(sess, error="Illegal step! Run reset to maze 1.")

        d["king_sq"] = mv.to_square
        sess.last_move = uci

        if mv.to_square == GOAL:
            d["solved"] += 1
            if d["solved"] >= self.total:
                sess.status = "victory"
                return self._view(sess, message=f"All {self.total} mazes cleared! Flag: {self.flag}")
            self._new_maze(sess)
            return self._view(sess, message=f"Maze solved ({d['solved']}/{self.total}).")

        return self._view(sess)


GAME = MazeGame(FLAGS["game3"])


def start():
    return GAME.start()


def move(sess, uci):
    return GAME.move(sess, uci)
