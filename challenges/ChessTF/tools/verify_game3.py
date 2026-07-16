"""Author-side check: generate many mazes and assert every one is solvable.

  docker compose run --rm --no-deps -e PYTHONPATH=/app -v "$PWD/tools:/app/tools" \
    backend python tools/verify_game3.py --n 2000
"""
import argparse
import time

import chess

from backend.games.game3_maze import START, GOAL, generate_maze, bfs_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    t0 = time.time()
    piece_counts = []
    path_lens = []
    for i in range(args.n):
        board, unsafe, blocked = generate_maze()
        path = bfs_path(START, GOAL, unsafe, blocked)
        assert path is not None, f"maze {i} is UNSOLVABLE"
        assert path[0] == START and path[-1] == GOAL
        piece_counts.append(len(board.piece_map()))
        path_lens.append(len(path))

    dt = time.time() - t0
    n = args.n
    print(f"OK: {n} mazes, all solvable.")
    print(f"  gen+solve: {dt:.2f}s total, {dt / n * 1000:.2f} ms/maze")
    print(f"  black pieces/maze: min={min(piece_counts)} avg={sum(piece_counts)/n:.1f} max={max(piece_counts)}")
    print(f"  solution length: min={min(path_lens)} avg={sum(path_lens)/n:.1f} max={max(path_lens)}")


if __name__ == "__main__":
    main()
