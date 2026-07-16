"""Game 4, Chessmaster (hard)

Normal chess, player is White vs the shared seeded bot. Win TARGET games in a row,
each within MAX_WHITE moves. The twist: Black's RNG seed is a function of White's
FIRST move only (seed = SEED_BASE + sha256(first move)). So for a fixed first move,
Black's entire game is deterministic — one short mating line, discovered once, wins
every game identically. The "aha" is realising the randomness is fake and hunting for
a first move whose seed lets a Fool's/Scholar's-style mate land inside the move budget.

Any lost/drawn/over-budget game (or an illegal move) resets the streak to 0.
"""
from __future__ import annotations

import time
from typing import Any

import chess

from .. import engine, sessions
from ..config import FLAGS

MAX_WHITE = 3  # tightest solvable budget: White cannot force mate faster than move 3
TARGET = 100
TIME_LIMIT = 120  # seconds for the whole 100-in-a-row run (same as Game 3)

INTRO = (
    "So you're good at chess? Prove it!\n"
    "Win 100 games in a row (max 3 moves each) within 120 seconds."
)


class SeedMatch:
    def __init__(self, flag: str, target: int = TARGET, max_white: int = MAX_WHITE,
                 time_limit: int = TIME_LIMIT):
        self.flag = flag
        self.target = target
        self.max_white = max_white
        self.time_limit = time_limit

    def _new_subgame(self, sess: engine.GameSession) -> None:
        sess.board = chess.Board()
        sess.last_move = None
        sess.data.update(rng=None, white_moves=0)

    def start(self) -> dict[str, Any]:
        sess = sessions.create(
            "game4", chess.Board(),
            {"streak": 0, "rng": None, "white_moves": 0, "run_start": time.time()},
        )
        return self._view(sess, message=INTRO)

    def _time_left(self, sess: engine.GameSession) -> float:
        return max(0.0, self.time_limit - (time.time() - sess.data["run_start"]))

    def _view(self, sess, *, message=None, error=None) -> dict[str, Any]:
        left = max(0, self.max_white - sess.data["white_moves"])
        return engine.envelope(
            sess, message=message, error=error,
            streak=sess.data["streak"], target=self.target, moves_left=left,
            time_left=round(self._time_left(sess), 1),
        )

    def _win_game(self, sess) -> dict[str, Any]:
        sess.data["streak"] += 1
        if sess.data["streak"] >= self.target:
            sess.status = "victory"
            return self._view(sess, message=f"{self.target} in a row! Flag: {self.flag}")
        streak = sess.data["streak"]
        self._new_subgame(sess)
        return self._view(sess, message=f"Checkmate! Streak {streak}/{self.target}. Next game.")

    def _lose_game(self, sess, reason: str) -> dict[str, Any]:
        sess.data["streak"] = 0
        self._new_subgame(sess)
        return self._view(sess, message=f"{reason} Streak reset to 0. Next game.")

    def move(self, sess: engine.GameSession, uci: str) -> dict[str, Any]:
        if sess.status != "in_progress":
            return self._view(sess, error="Match already over. Start a new one.")

        if self._time_left(sess) <= 0:
            sess.status = "failed"
            return self._view(
                sess, message=f"Time up — {sess.data['streak']}/{self.target} won.")

        board = sess.board
        mv = engine.parse_move(uci)
        if mv is None or mv not in board.legal_moves or board.turn != chess.WHITE:
            return self._lose_game(sess, "Illegal move.")

        # White's first move seeds the bot for the rest of THIS game.
        if sess.data["rng"] is None:
            sess.data["rng"] = engine.make_rng(uci)

        board.push(mv)
        sess.last_move = uci
        sess.data["white_moves"] += 1

        if board.is_checkmate():
            return self._win_game(sess)
        if board.is_game_over():
            return self._lose_game(sess, f"Game drawn ({board.result()}).")

        reply = engine.random_bot_move(board, sess.data["rng"])
        board.push(reply)
        sess.last_move = reply.uci()

        if board.is_checkmate():
            return self._lose_game(sess, "Black checkmated you.")
        if board.is_game_over():
            return self._lose_game(sess, f"Game drawn ({board.result()}).")
        if sess.data["white_moves"] >= self.max_white:
            return self._lose_game(sess, f"No mate in {self.max_white} moves.")

        return self._view(sess)


GAME = SeedMatch(FLAGS["game4"])


def start():
    return GAME.start()


def move(sess, uci):
    return GAME.move(sess, uci)
