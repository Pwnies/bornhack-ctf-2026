# Chess CTF Challenges — Plan

A misc-category CTF consisting of a website with a menu of **4 "chess" games**. Each
game is a self-contained puzzle with a different win condition. Players interact with a
minimal JS chessboard that speaks a simple JSON API to an authoritative server.

## Architecture Decision (settled)

**Pure Python. No Rust binaries, no self-written chess engine.**

- **Backend:** FastAPI (single process, one JSON API).
- **Rules engine:** [`python-chess`](https://python-chess.readthedocs.io/) — legal moves,
  check/checkmate, attack maps, FEN/SAN. Do **not** hand-roll chess rules.
- **State:** server-side, authoritative, keyed by an opaque per-game session token.
  The board never decides legality; the server does.
- **Frontend:** minimal React board (`react-chessboard`) — or vanilla `chessboard.js`
  if we want to skip a build step. The board only renders and relays the API.
- **Deployment:** one `Dockerfile`, one container.

Rationale: the challenges are API-inspection / logic-quirk puzzles, not reverse-engineering
of a binary, so separate Rust binaries add IPC + deployment cost for no CTF value. We still
get the "shared library + 4 games" separation via a shared `engine` module + one module per game.

### Shared bot (Games 1, 2, 4)

There is exactly **one** bot implementation: a random mover that picks a uniformly random
legal move from a deterministically ordered legal-move list, driven by `random.Random`.
It runs in two modes via the `seeded_bot` knob:

- **Unseeded** (Games 1 & 2): a fresh `random.Random()` per game, so Black is genuinely
  unpredictable game to game — no first-move-controls-everything shortcut. This keeps them
  **very easy** but not memorizable, which is intended (these are not "be good at chess"
  challenges).
- **Seeded** (Game 4): `random.Random(seed)` where `seed = BASE + hash(first White move)`,
  fixed per game — the whole point of Game 4 is that this determinism is discoverable.
- Game 4 is the same bot in **seeded** mode; the challenge is discovering that the seed (and
  thus Black's whole game) is controlled by White's first move, then finding a first move whose
  seed yields a <=5-move mate line.
- Game 3 has **no bot** — Black is static and never moves.

### Repo layout (target)

```
chess/
  plan.md
  backend/
    app.py                # FastAPI app, routes, session registry
    engine.py             # shared helpers over python-chess (session, legality, serialization)
    sessions.py           # in-memory session store (token -> game state)
    games/
      game1_random.py     # random-move bot, win in <=10 moves
      game2_invisible.py  # game1 + black hidden client-side (data still on the wire)
      game3_maze.py       # king-maze generator + solver-check + play loop
      game4_seed.py       # seeded "random" black; find quick-mate line, 100 in a row
    tests/
  frontend/
    (react-chessboard app, or a single static index.html + chessboard.js)
  tools/
    verify_game3.py       # generate N mazes, assert each is solvable
    verify_game4.py       # brute-force first move+line, assert a <=5-move mate exists; tune seed base
  Dockerfile
  README.md               # ops/run notes (NOT player-facing hints)
```

## Shared API shape (keep it dumb + uniform)

All games share one small vocabulary so the frontend stays generic.

- `POST /api/{game}/new` → `{ session, fen, turn, message, hidden? }`
  - `message` = the intro/how-to-play text shown when the game is opened.
- `POST /api/{game}/move` body `{ session, move: "e2e4" }` (UCI) →
  `{ fen, turn, last_move, status, message }`
  - `status` ∈ `in_progress | victory | failed`.
  - On victory the `message` carries the flag (or a token that unlocks it).
- Errors / illegal moves return a normal JSON body with `status: failed` (never a 500),
  so behavior is observable — important for Game 2's intended solve.

Design rule: **the server always sends the true game state** (including black's pieces).
Hiding is purely a frontend concern (Game 2). This is deliberate.

## The 4 Games

### Game 1 - Baby's first checkmate (trivial)
- Standard chess, player is White, bot is Black.
- Black plays a uniformly random legal move each turn.
- Win condition: checkmate Black within **10 White moves**, else `failed`.
- Intro message + Victory/Failed messages.
- Notes: straightforward; mostly validates the shared engine + session flow.

### Game 2 - Welcome to the jungle (easy)
- Mechanically identical to Game 1 (random bot, White to win).
- **Frontend never renders Black's pieces** — but the server response still contains the
  full FEN / black coordinates / `last_move`. Intended solve: inspect the API and read
  black's position off the wire.
- Extra failure rule: an **illegal White move loses immediately** (`failed`) — because a
  blind player who guesses wrong should be punished; a player who read the API won't.
- Implementation: reuse Game 1 logic; add a `hidden: true` flag so the client masks black.
  **Do not strip black data server-side** — that's the whole puzzle.

### Game 3 - Behind enemy lines (medium)
- Board full of **static** Black pieces + a single **White King** on `a1`.
- Goal: walk the king to `a8` (bottom-left → top-left). Only White moves; Black never moves.
- King may not move into an attacked square or an occupied square (standard king legality
  vs. the static black attack map).
- **Any illegal move resets the ENTIRE run** — back to maze 1.
- Win condition: solve **100** freshly generated mazes in **< ~2 min** (forces automation).
- Needs a **maze generator with a solvability guarantee**:
  1. Carve a random monotone-ish safe path a1 → a8 (sequence of king-adjacent squares).
  2. Place random black pieces only on non-path squares, rejecting any placement that
     attacks a path square (use python-chess attack maps). King start square also protected.
  3. Verify by running a BFS/king-move search a1→a8 over safe squares before serving.
- `tools/verify_game3.py`: generate a few thousand mazes, assert 100% solvable, measure gen time.
- Open question: board size (8x8 default; larger grid is possible but python-chess is 8x8 —
  if we want bigger we either stick to 8x8 or drop python-chess for Game 3's grid only).
  **Default: 8x8.**

### Game 4 - Chessmaster (hard)
- Standard chess, White = player, Black = bot. Win **100 games in a row**, each in **<=3 White
  moves**, and the whole run inside a **120s** clock (same limit as Game 3 — forces automation).
- Twist: **White's first move sets the RNG seed** that drives all of Black's "random" moves
  for that game (`seed = BASE + hash(first_move)`, deterministic thereafter).
- Consequence: for a fixed first move, Black's whole game is deterministic → a single
  5-move line wins every game identically. Intended aha: **"the randomness is fake."**
- We (authors) MUST guarantee at least one first-move + line delivers mate <=5 moves:
  - `tools/verify_game4.py`: for each legal first move, replay Black's deterministic responses,
    search White's follow-ups for a checkmate within 5 moves.
  - If none found, adjust `BASE` and re-run until a clean short mate (Scholar's-mate-like)
    exists. Lock `BASE` once verified.
- Intro message should hint at "randomness"; Victory after 100 → flag.
- Seeding must be a stable, documented scheme (e.g. Python `random.Random(seed)` with a
  fixed sequence of `.choice(legal_moves_sorted)`), so the author-found line stays valid at deploy.

## Messaging (all games)
- **Intro** message on `new` (how to play / flavor).
- **Victory** message (carries flag/unlock).
- **Failed** message (reason: illegal move / out of moves / reset).

## Build Steps (suggested order)

1. **[DONE] Scaffold + engine.** Dockerized FastAPI, `engine.py` (session model, seeded bot,
   uniform envelope), `sessions.py` store, `config.py` flags. Runs via `docker compose`.
2. **[DONE] Game 1.** Random bot + 10-move limit via reusable `RandomBotGame`. 7 passing tests;
   HTTP loop smoke-tested end to end.
3. **[DONE — MVP] Minimal frontend.** Self-contained vanilla-JS board (no build step, no CDN),
   served at `/` by FastAPI. 4-game menu (only Game 1 enabled; 2–4 "coming soon").
   Click-to-move, auto-queen, victory/failed messaging, honors `hidden` flag for Game 2.
   NOTE: react-chessboard swap deferred — API unchanged, so it's a drop-in later if desired.
4. **[DONE] Game 2.** Reuses `RandomBotGame` with `hidden=True` + `illegal_loses=True` +
   `shuffle_black=True`: Black's back rank is a random permutation of its normal material (same
   pieces, rearranged; White untouched), so players can't dodge illegal moves from memory — they
   must read Black's true squares off the API. Frontend masks Black; server still leaks the full
   FEN. Illegal move → `failed` (→ Restart). 4 game2 tests. Board CSS bug fixed.
5. **[DONE] Game 3.** King-maze **a1 -> h8 (corner to corner)** with a solvability guarantee
   (constructive O(n) path + king-transparent attack model so server/solver agree),
   full-reset-on-illegal, 100-maze/120s server-side clock. `tools/verify_game3.py` (all mazes
   solvable, ~0.5ms each) and a standalone stdlib-only solver `solvers/solve_game3.py`
   (solves 100 in ~2.6s over HTTP). 5 tests (15 total).
   Concurrency verified: sync endpoints run in Starlette's threadpool — 10 simultaneous players,
   300 requests, 366 req/s, p95 17ms, 0 errors. One worker on purpose (in-process session store;
   multi-worker would need Redis-backed sessions). Fixed a generator hang (pathological DFS).
6. **[DONE] Game 4.** Chessmaster — 100-in-a-row match vs the shared seeded bot, **3-move cap**
   (the tightest solvable: White can't force mate before move 3), streak resets on any
   loss/draw/over-budget/illegal move. Seed = f(first move). `tools/find_quick_mate.py --report`
   shows base=0 at budget 3 leaves **only 1/20 first moves winnable** (`g2g3 f5 e3 g5 Qh5#`), so
   the puzzle can't be hand-stumbled — it forces realising determinism + brute-forcing first moves.
   5 tests (20 total); verified 100-in-a-row over HTTP (flag in ~0.3s). SEED_BASE/budget tunable.
7. **[DONE] Flags + messages.** Per-game intro/victory/failed messages with flags on victory.
   Frontend message box is now fixed-height + centered (no layout jump). Final `BHCTF{...}`
   flag values set in `config.py` (env-overridable via `FLAG_GAME1..4`).
8. **[DONE] Hardening + deploy.** One self-contained production `docker-compose.yml` (no
   override file) so the service block can be pasted straight into the larger Bornhack CTF
   compose: image as built — no source mounts, no `--reload`, `restart: unless-stopped`,
   healthcheck on `/healthz`, 2 CPU / 512M limits. Dev mounts + `--reload` are kept as a
   commented block at the bottom. Service is named `chess-tf` (a generic `backend` would
   collide in a combined compose).
   - Deploy: `docker compose up -d --build`. Merge notes (build context, host port
     uniqueness, optional `FLAG_GAME*` env injection) are comments at the top of the file.
   - **Session cap** (`MAX_SESSIONS`, default 5000): `/{game}/new` is unauthenticated, so the
     store could grow unbounded for a whole TTL hour. `_prune_locked` now sweeps expired
     sessions then evicts least-recently-*touched* ones past the cap — a runaway client only
     evicts itself; active players are touched every move and survive. Sorts only when the cap
     is actually hit. 4 tests (27 total).
   - Still 1 worker on purpose (in-process sessions; multi-worker needs Redis). Reverse proxy
     with a per-request timeout still recommended so no request can wedge a thread.
   - `/docs`, `/openapi.json`, `/redoc` left ENABLED on purpose: Game 2's intended solve is
     "inspect the API", so a discoverable schema makes it a fair puzzle rather than guesswork.
   - Verified against the prod stack: Game 3 solver 100/100 mazes in 1.0s, Game 4 100-in-a-row
     in 0.3s (119.7s clock headroom), both returning the real flags.
   - **Deploy gotcha:** Game 4's only 3-move mate is calibrated to `SEED_BASE=0`. Changing it
     requires re-running `tools/find_quick_mate.py --report --base <new>` or Game 4 may become
     unsolvable.

