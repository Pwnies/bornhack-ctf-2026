#!/usr/bin/env python3
"""Standalone solver for Chess CTF — Game 3 (Behind enemy lines).

No third-party dependencies (Python 3 stdlib only). Point it at a running instance:

    python3 solve_game3.py --url http://localhost:8000

It walks the King from a1 to h8 in every maze by reproducing the server's safety
model: black attacks are computed with the King treated as transparent (it never
blocks a slider), then a breadth-first search finds a safe, empty path.
"""
import argparse
import json
import sys
import time
import urllib.request

GOAL = 63  # h8, using square = rank*8 + file  (a1 = 0)


# --------------------------------------------------------------------------- #
# Tiny HTTP helper
# --------------------------------------------------------------------------- #
def post(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


# --------------------------------------------------------------------------- #
# Board model (mirrors the server exactly)
# --------------------------------------------------------------------------- #
def parse_fen(fen):
    """Return {square: piece_char} for the placement field of a FEN."""
    board = {}
    for row, line in enumerate(fen.split()[0].split("/")):
        rank = 7 - row
        file = 0
        for ch in line:
            if ch.isdigit():
                file += int(ch)
            else:
                board[rank * 8 + file] = ch
                file += 1
    return board


def sq_name(sq):
    return "abcdefgh"[sq % 8] + str(sq // 8 + 1)


def _attacks(sq, piece, occ):
    """Squares a black `piece` on `sq` attacks; sliders stop at `occ` (inclusive).
    `occ` is the set of black-piece squares only — the White King is transparent."""
    f, r = sq % 8, sq // 8
    kind = piece.lower()
    out = set()

    def on(nf, nr):
        return 0 <= nf < 8 and 0 <= nr < 8

    if kind == "p":  # black pawn captures diagonally toward rank 1
        for df in (-1, 1):
            if on(f + df, r - 1):
                out.add((r - 1) * 8 + (f + df))
    elif kind == "n":
        for df, dr in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
            if on(f + df, r + dr):
                out.add((r + dr) * 8 + (f + df))
    elif kind == "k":
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if (df or dr) and on(f + df, r + dr):
                    out.add((r + dr) * 8 + (f + df))
    else:
        dirs = []
        if kind in ("b", "q"):
            dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        if kind in ("r", "q"):
            dirs += [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for df, dr in dirs:
            nf, nr = f + df, r + dr
            while on(nf, nr):
                s = nr * 8 + nf
                out.add(s)
                if s in occ:
                    break
                nf += df
                nr += dr
    return out


def unsafe_and_blocked(board):
    black = {sq: p for sq, p in board.items() if p.islower()}
    occ = set(black)
    unsafe = set()
    for sq, p in black.items():
        unsafe |= _attacks(sq, p, occ)
    return unsafe, occ  # (attacked squares, occupied squares)


def king_neighbors(sq):
    f, r = sq % 8, sq // 8
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if (df or dr) and 0 <= f + df < 8 and 0 <= r + dr < 8:
                yield (r + dr) * 8 + (f + df)


def bfs_path(start, unsafe, blocked):
    """Shortest safe king path start -> GOAL, or None."""
    prev = {start: None}
    queue = [start]
    while queue:
        nxt = []
        for cur in queue:
            if cur == GOAL:
                path = []
                s = cur
                while s is not None:
                    path.append(s)
                    s = prev[s]
                return path[::-1]
            for n in king_neighbors(cur):
                if n in prev or n in blocked or n in unsafe:
                    continue
                prev[n] = cur
                nxt.append(n)
        queue = nxt
    return None


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def solve(base_url, verbose=False):
    base = base_url.rstrip("/")
    data = post(f"{base}/api/game3/new")
    total = data.get("total", "?")
    print(f"Run started: {total} mazes, {data.get('time_left')}s on the clock.")

    t0 = time.time()
    requests = 0
    last_solved = 0

    while True:
        status = data["status"]
        if status == "victory":
            print(f"\nVICTORY in {time.time() - t0:.1f}s ({requests} moves).")
            print(data["message"])
            return 0
        if status == "failed":
            print(f"\nFAILED: {data.get('message')}")
            return 1

        board = parse_fen(data["fen"])
        king = next((sq for sq, p in board.items() if p == "K"), None)
        if king is None:
            print("No King on the board?!", data["fen"], file=sys.stderr)
            return 2

        unsafe, blocked = unsafe_and_blocked(board)
        path = bfs_path(king, unsafe, blocked)
        if not path or len(path) < 2:
            print("No safe path found — solver and server disagree.", file=sys.stderr)
            print("FEN:", data["fen"], file=sys.stderr)
            return 3

        uci = sq_name(king) + sq_name(path[1])
        data = post(f"{base}/api/game3/move", {"session": data["session"], "move": uci})
        requests += 1

        if data.get("error"):
            # An illegal step would reset the run — should never happen if models match.
            print("Server rejected a move (run reset):", data["error"], file=sys.stderr)
            return 4

        solved = data.get("solved", last_solved)
        if solved != last_solved:
            last_solved = solved
            if verbose or solved % 10 == 0 or solved == total:
                print(f"  solved {solved}/{total}  ({data.get('time_left')}s left)")


def main():
    ap = argparse.ArgumentParser(description="Solve Chess CTF Game 3 (Behind enemy lines).")
    ap.add_argument("--url", default="http://localhost:8000", help="base URL of the server")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    sys.exit(solve(args.url, args.verbose))


if __name__ == "__main__":
    main()
