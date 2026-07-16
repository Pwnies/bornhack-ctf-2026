"""Game registry. Each game module exposes start() and move(session, uci)."""
from . import game1_random, game2_invisible, game3_maze, game4_seed

GAMES = {
    "game1": game1_random,
    "game2": game2_invisible,
    "game3": game3_maze,
    "game4": game4_seed,
}
