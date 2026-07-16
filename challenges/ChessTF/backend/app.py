"""FastAPI app: one uniform JSON API over the game registry.

  POST /api/{game}/new              -> envelope (with intro message)
  POST /api/{game}/move {session,move} -> envelope
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import sessions
from .games import GAMES

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = FastAPI(title="Chess CTF")

# Dev convenience: the frontend runs on a different origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MoveReq(BaseModel):
    session: str
    move: str


@app.get("/api/games")
def list_games():
    return {"games": list(GAMES.keys())}


@app.post("/api/{game}/new")
def new_game(game: str):
    mod = GAMES.get(game)
    if mod is None:
        raise HTTPException(status_code=404, detail="No such game.")
    return mod.start()


@app.post("/api/{game}/move")
def make_move(game: str, req: MoveReq):
    mod = GAMES.get(game)
    if mod is None:
        raise HTTPException(status_code=404, detail="No such game.")
    sess = sessions.get(req.session)
    if sess is None or sess.game != game:
        raise HTTPException(status_code=404, detail="Unknown or expired session.")
    return mod.move(sess, req.move)


@app.get("/healthz")
def healthz():
    return {"ok": True}


# Serve the static frontend at "/". Mounted LAST so /api/* and /healthz win first.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
