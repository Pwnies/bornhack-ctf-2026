"""Shared chess helpers over python-chess: session model, the seeded random bot,
and uniform API serialization. Rules correctness lives entirely in python-chess.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Optional

import chess

from .config import SEED_BASE


# --------------------------------------------------------------------------- #
# Session model
# --------------------------------------------------------------------------- #
@dataclass
class GameSession:
    id: str
    game: str
    board: chess.Board
    data: dict[str, Any] = field(default_factory=dict)
    last_move: Optional[str] = None  # UCI of most-recently applied move (either side)
    status: str = "in_progress"      # in_progress | victory | failed


# --------------------------------------------------------------------------- #
# The shared bot: a deterministic, seeded random mover.
#
# The seed is a stable function of White's FIRST move only, so Black's whole game
# is reproducible. We use sha256 (not builtin hash(), which is salted per process)
# so the mapping is identical across runs/machines.
# --------------------------------------------------------------------------- #
def stable_hash(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def make_rng(first_move_uci: str, base: int = SEED_BASE) -> random.Random:
    seed = (base + stable_hash(first_move_uci)) % (2 ** 32)
    return random.Random(seed)


def random_bot_move(board: chess.Board, rng: random.Random) -> chess.Move:
    """Pick a uniformly random legal move from a deterministically ordered list."""
    moves = sorted(board.legal_moves, key=lambda m: m.uci())
    return rng.choice(moves)


# --------------------------------------------------------------------------- #
# Serialization — the uniform API envelope every game returns.
# The server is always authoritative and always sends the TRUE board state
# --------------------------------------------------------------------------- #
def envelope(
    session: GameSession,
    *,
    message: Optional[str] = None,
    error: Optional[str] = None,
    **extra: Any,
) -> dict[str, Any]:
    board = session.board
    payload: dict[str, Any] = {
        "session": session.id,
        "fen": board.fen(),
        "turn": "w" if board.turn == chess.WHITE else "b",
        "last_move": session.last_move,
        "status": session.status,
        "message": message,
        "error": error,
    }
    payload.update(extra)
    return payload


def parse_move(uci: str) -> Optional[chess.Move]:
    """Return a Move for a well-formed UCI string, else None. Does not check legality."""
    try:
        return chess.Move.from_uci(uci)
    except (ValueError, TypeError):
        return None
