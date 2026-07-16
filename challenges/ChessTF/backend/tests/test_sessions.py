import chess
import pytest

from backend import config, sessions


@pytest.fixture(autouse=True)
def _clean_store():
    """Each test gets an empty store (and restores the real cap afterwards)."""
    sessions._store.clear()
    cap = config.MAX_SESSIONS
    yield
    sessions._store.clear()
    config.MAX_SESSIONS = cap
    sessions.MAX_SESSIONS = cap


def _mk(n: int) -> list:
    return [sessions.create("game1", chess.Board()) for _ in range(n)]


def test_store_never_exceeds_cap():
    sessions.MAX_SESSIONS = 10
    _mk(50)  # a runaway client spamming /new
    assert len(sessions._store) <= 10


def test_cap_evicts_least_recently_used_not_the_active_player():
    sessions.MAX_SESSIONS = 5
    victim = sessions.create("game1", chess.Board())
    active = sessions.create("game1", chess.Board())

    # `active` keeps playing; `victim` goes idle. Touch ordering (not insertion
    # order) must decide who gets evicted.
    for _ in range(20):
        sessions.get(active.id)
        sessions.create("game1", chess.Board())

    assert sessions.get(active.id) is not None  # in-progress run survives the flood
    assert sessions.get(victim.id) is None      # idle one was evicted


def test_expired_session_is_swept():
    sess = sessions.create("game1", chess.Board())
    stale = sessions._store[sess.id][0]
    sessions._store[sess.id] = (stale, 0.0)  # last touched at the epoch
    sessions.create("game1", chess.Board())  # any create prunes
    assert sessions.get(sess.id) is None


def test_get_touches_and_delete_removes():
    sess = sessions.create("game1", chess.Board())
    before = sessions._store[sess.id][1]
    sessions.get(sess.id)
    assert sessions._store[sess.id][1] >= before
    sessions.delete(sess.id)
    assert sessions.get(sess.id) is None
