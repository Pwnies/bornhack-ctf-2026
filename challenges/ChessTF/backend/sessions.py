"""In-memory session store keyed by an opaque token. Single-process, thread-safe."""
from __future__ import annotations

import secrets
import threading
import time
from typing import Optional

import chess

from .config import MAX_SESSIONS, SESSION_TTL
from .engine import GameSession

# sid -> (session, last_touched). The timestamp is refreshed on every get(), so it
# tracks recency of use, not creation.
_store: dict[str, tuple[GameSession, float]] = {}
_lock = threading.Lock()


def _prune_locked(now: float, incoming: int = 0) -> None:
    """Drop idle sessions, then enforce MAX_SESSIONS. Caller MUST hold _lock.

    `incoming` reserves room for sessions about to be inserted, so the store never
    exceeds the cap even momentarily.
    """
    dead = [sid for sid, (_, ts) in _store.items() if now - ts > SESSION_TTL]
    for sid in dead:
        _store.pop(sid, None)

    # Still over budget: evict least-recently-touched first. Only sorts on the rare
    # occasion the cap is actually hit, so the common path stays a single O(n) scan.
    over = len(_store) + incoming - MAX_SESSIONS
    if over > 0:
        for sid in sorted(_store, key=lambda s: _store[s][1])[:over]:
            _store.pop(sid, None)


def create(game: str, board: chess.Board, data: Optional[dict] = None) -> GameSession:
    now = time.time()
    sid = secrets.token_urlsafe(16)
    sess = GameSession(id=sid, game=game, board=board, data=data or {})
    with _lock:
        _prune_locked(now, incoming=1)
        _store[sid] = (sess, now)
    return sess


def get(sid: str) -> Optional[GameSession]:
    with _lock:
        item = _store.get(sid)
        if item is None:
            return None
        sess, _ = item
        _store[sid] = (sess, time.time())  # touch
    return sess


def delete(sid: str) -> None:
    with _lock:
        _store.pop(sid, None)
