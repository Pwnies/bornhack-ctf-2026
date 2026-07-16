"""Reusable engine for the random-bot games (Game 1, Game 2, and the base of Game 4).

Player is White; Black is the shared seeded random bot (seeded by White's first move).
Win = checkmate Black within `max_white_moves`. Configurable knobs let Game 2 reuse this
verbatim while masking Black client-side and punishing illegal moves.
"""
from __future__ import annotations

import random
from typing import Any

import chess

from .. import engine, sessions

_STANDARD_BACK_RANK = "rnbqkbnr"


def shuffled_black_board() -> chess.Board:
    """Standard position, but Black's back rank is a random permutation of its pieces.

    Same material, only rearranged — so a player can't dodge illegal moves from memory
    of the standard layout; they must read Black's real squares off the API. White is
    left standard (keeps its castling); Black castling is dropped (its king has moved).
    """
    letters = list(_STANDARD_BACK_RANK)
    while True:
        random.shuffle(letters)
        rank8 = "".join(letters)
        if rank8 != _STANDARD_BACK_RANK:  # never (coincidentally) deal the standard setup
            break
    return chess.Board(f"{rank8}/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1")


class RandomBotGame:
    def __init__(
        self,
        name: str,
        flag: str,
        intro: str,
        *,
        max_white_moves: int = 10,
        hidden: bool = False,       # frontend-only: hide Black's pieces (Game 2)
        illegal_loses: bool = False,  # an illegal White move loses outright (Game 2)
        shuffle_black: bool = False,  # randomize Black's back rank (Game 2)
        seeded_bot: bool = True,      # seed Black's RNG from White's first move (Game 4-style)
    ) -> None:
        self.name = name
        self.flag = flag
        self.intro = intro
        self.max_white_moves = max_white_moves
        self.hidden = hidden
        self.illegal_loses = illegal_loses
        self.shuffle_black = shuffle_black
        self.seeded_bot = seeded_bot

    # -- lifecycle ---------------------------------------------------------- #
    def start(self) -> dict[str, Any]:
        board = shuffled_black_board() if self.shuffle_black else chess.Board()
        # Seeded bot (Game 4-style): RNG is derived from White's first move, so the
        # whole game is reproducible. Unseeded (Games 1 & 2): a fresh, process-random
        # RNG per game, so Black is genuinely unpredictable game to game.
        rng = None if self.seeded_bot else random.Random()
        sess = sessions.create(
            self.name, board, {"white_moves": 0, "rng": rng, "hidden": self.hidden}
        )
        return engine.envelope(
            sess,
            message=self.intro,
            hidden=self.hidden,
            moves_left=self.max_white_moves,
        )

    # -- helpers ------------------------------------------------------------ #
    def _view(self, sess: engine.GameSession, **kw: Any) -> dict[str, Any]:
        left = max(0, self.max_white_moves - sess.data["white_moves"])
        return engine.envelope(sess, hidden=self.hidden, moves_left=left, **kw)

    def _win(self, sess: engine.GameSession) -> dict[str, Any]:
        sess.status = "victory"
        return self._view(sess, message=f"Checkmate! You win. Flag: {self.flag}")

    def _lose(self, sess: engine.GameSession, reason: str) -> dict[str, Any]:
        sess.status = "failed"
        return self._view(sess, message=f"Defeat: {reason}")

    # -- move --------------------------------------------------------------- #
    def move(self, sess: engine.GameSession, uci: str) -> dict[str, Any]:
        if sess.status != "in_progress":
            return self._view(sess, error="Game already over. Start a new one.")

        board = sess.board
        mv = engine.parse_move(uci)
        legal = mv is not None and mv in board.legal_moves and board.turn == chess.WHITE
        if not legal:
            if self.illegal_loses:
                return self._lose(sess, "illegal move.")
            return self._view(sess, error="Illegal move; try another.")

        # Seeded variant: White's first move seeds the bot for the rest of the game.
        # (Unseeded games already hold a fresh RNG from start().)
        if sess.data["rng"] is None:
            sess.data["rng"] = engine.make_rng(uci)

        board.push(mv)
        sess.last_move = uci
        sess.data["white_moves"] += 1

        if board.is_checkmate():
            return self._win(sess)
        if board.is_game_over():
            return self._lose(sess, f"game drawn ({board.result()}).")

        # Black replies with a seeded-random legal move.
        reply = engine.random_bot_move(board, sess.data["rng"])
        board.push(reply)
        sess.last_move = reply.uci()

        if board.is_checkmate():
            return self._lose(sess, "Black checkmated you.")
        if board.is_game_over():
            return self._lose(sess, f"game drawn ({board.result()}).")
        if sess.data["white_moves"] >= self.max_white_moves:
            return self._lose(sess, f"out of moves (limit {self.max_white_moves}).")

        return self._view(sess)
