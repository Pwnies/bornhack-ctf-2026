import chess

from backend import sessions
from backend.games import game2_invisible as g2


def test_start_is_hidden_but_full_board_leaks():
    resp = g2.start()
    assert resp["hidden"] is True
    # The whole puzzle: the server still sends Black's pieces in the FEN.
    board = chess.Board(resp["fen"])
    black_pieces = [p for p in board.piece_map().values() if p.color == chess.BLACK]
    assert len(black_pieces) == 16


def test_black_back_rank_is_shuffled_same_material():
    ranks = set()
    for _ in range(30):
        board = chess.Board(g2.start()["fen"])
        # White is untouched (standard), Black pawns still on rank 7.
        assert board.piece_at(chess.E1) == chess.Piece(chess.KING, chess.WHITE)
        for f in range(8):
            assert board.piece_at(chess.square(f, 1)) == chess.Piece(chess.PAWN, chess.WHITE)
            assert board.piece_at(chess.square(f, 6)) == chess.Piece(chess.PAWN, chess.BLACK)
        back = "".join(chess.piece_symbol(board.piece_at(chess.square(f, 7)).piece_type)
                        for f in range(8))
        assert sorted(back) == sorted("rnbqkbnr")  # same material, rearranged
        assert back != "rnbqkbnr"                   # never the standard layout
        ranks.add(back)
    assert len(ranks) > 1  # actually random across games


def test_illegal_move_loses_and_locks():
    resp = g2.start()
    sess = sessions.get(resp["session"])
    out = g2.move(sess, "e2e5")  # illegal
    assert out["status"] == "failed"
    assert "illegal" in out["message"].lower()
    # Locked afterwards: further moves are refused, not silently applied.
    again = g2.move(sess, "e2e4")
    assert again["status"] == "failed"


def test_legal_move_keeps_leaking_black_reply():
    resp = g2.start()
    sess = sessions.get(resp["session"])
    out = g2.move(sess, "e2e4")
    assert out["status"] == "in_progress"
    assert out["hidden"] is True
    # Black's reply coordinate is present on the wire despite being hidden on the board.
    assert out["last_move"] is not None
    assert chess.Board(out["fen"]).turn == chess.WHITE
