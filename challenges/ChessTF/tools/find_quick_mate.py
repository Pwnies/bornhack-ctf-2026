"""Search for a line where White checkmates the seeded random bot within N moves.

Because the bot is deterministic given White's first move (seed = BASE + sha256(first move)),
the whole game tree is deterministic and searchable. This is:
  * a proof that the easy games are winnable, and
  * the foundation for Game 4 (find a <=5-move mate; tune SEED_BASE if none exists).

Run inside the container:
  docker compose run --rm --no-deps backend python tools/find_quick_mate.py --max 4
"""
from __future__ import annotations

import argparse

import chess

from backend import engine


def _search(board: chess.Board, rng, moves_used: int, maxw: int, line: list[str]):
    if moves_used >= maxw:
        return None
    for mv in sorted(board.legal_moves, key=lambda m: m.uci()):
        board.push(mv)
        if board.is_checkmate():
            board.pop()
            return line + [mv.uci()]
        if board.is_game_over():
            board.pop()
            continue
        st = rng.getstate()
        reply = engine.random_bot_move(board, rng)
        board.push(reply)
        if board.is_game_over():          # black's reply ended it (bad for us)
            board.pop(); board.pop(); rng.setstate(st)
            continue
        found = _search(board, rng, moves_used + 1, maxw, line + [mv.uci(), reply.uci()])
        board.pop(); board.pop(); rng.setstate(st)
        if found:
            return found
    return None


def find(maxw: int, base: int):
    """Return (line, first_move) for the first White first-move that admits a mate."""
    for first in sorted(chess.Board().legal_moves, key=lambda m: m.uci()):
        board = chess.Board()
        rng = engine.make_rng(first.uci(), base=base)
        board.push(first)
        if board.is_checkmate():
            return [first.uci()], first.uci()
        reply = engine.random_bot_move(board, rng)
        board.push(reply)
        line = _search(board, rng, 1, maxw, [first.uci(), reply.uci()])
        if line:
            return line, first.uci()
    return None, None


def shortest_mate_for_first(first: chess.Move, maxw: int, base: int):
    """Iterative deepening: shortest White-move count to mate after this first move."""
    for depth in range(1, maxw + 1):
        board = chess.Board()
        rng = engine.make_rng(first.uci(), base=base)
        board.push(first)
        if board.is_checkmate():
            return 1, [first.uci()]
        reply = engine.random_bot_move(board, rng)
        board.push(reply)
        line = _search(board, rng, 1, depth, [first.uci(), reply.uci()])
        if line:
            return len(line[0::2]), line
    return None, None


def report(maxw: int, base: int):
    print(f"Per-first-move shortest mate (base={base}, budget={maxw} White moves):")
    hist = {}
    best = None
    for first in sorted(chess.Board().legal_moves, key=lambda m: m.uci()):
        depth, line = shortest_mate_for_first(first, maxw, base)
        tag = f"{depth}" if depth else "-"
        hist[tag] = hist.get(tag, 0) + 1
        print(f"  {first.uci()}: {'mate in %d' % depth if depth else 'no mate'}"
              + (f"   {' '.join(line)}" if line else ""))
        if depth and (best is None or depth < best[0]):
            best = (depth, first.uci(), line)
    total = sum(v for k, v in hist.items() if k != "-")
    print(f"\nSummary: {total}/20 first moves admit a mate <= {maxw}.")
    print("  by depth:", {k: hist[k] for k in sorted(hist)})
    if best:
        print(f"  shortest overall: mate in {best[0]} via {best[1]}  ({' '.join(best[2])})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=4, help="max White moves to mate in")
    ap.add_argument("--base", type=int, default=0, help="SEED_BASE to test")
    ap.add_argument("--report", action="store_true", help="per-first-move breakdown")
    args = ap.parse_args()

    if args.report:
        report(args.max, args.base)
    else:
        line, first = find(args.max, args.base)
        if line:
            white = line[0::2]
            print(f"MATE FOUND in {len(white)} White moves (base={args.base}, first={first})")
            print("line (uci):", " ".join(line))
        else:
            print(f"No mate <= {args.max} White moves for base={args.base}.")
