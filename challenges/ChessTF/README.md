# Chess CTF

Four "chess" misc challenges behind one simple JSON API. See [`plan.md`](plan.md) for design.

**Everything runs in Docker — no host Python needed.**

## Run (dev, hot-reload)

```bash
docker compose up --build        # API on http://localhost:8000
docker compose down
```

## Tests

```bash
docker compose run --rm --no-deps backend python -m pytest backend/tests -q
```

## API

| Method | Path                | Body                      | Returns |
|--------|---------------------|---------------------------|---------|
| GET    | `/api/games`        | —                         | list of game ids |
| POST   | `/api/{game}/new`   | —                         | envelope (with intro `message`) |
| POST   | `/api/{game}/move`  | `{"session","move"}` (UCI)| envelope |
| GET    | `/healthz`          | —                         | `{"ok":true}` |

Envelope: `{ session, fen, turn, last_move, status, message, error, ... }`
where `status` ∈ `in_progress | victory | failed`. The server always sends the true
board; Game 2's hiding is frontend-only.

> Note: `curl ... | echo` mangles JSON under **zsh** (its `echo` expands `\n`). Use
> `printf '%s'` or pipe straight into `python3 -m json.tool`.
