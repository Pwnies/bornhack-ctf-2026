"""Game 2, Welcome to the jungle (easy)

Identical to Game 1, but Black's pieces are shuffled and hidden (client-side).
The server STILL sends the full board (Black's coordinates and moves) in every
response — that's the whole puzzle: inspect the API to see what the board won't show.
An illegal White move (e.g. blindly stumbling into a hidden piece) loses immediately.
"""
from ..config import FLAGS
from ._random_bot_game import RandomBotGame

INTRO = (
    "How do you fight that which cannot be seen?\n"
    "Use 10 moves or less. An illegal move is an instant loss."
)

GAME = RandomBotGame(
    "game2", FLAGS["game2"], INTRO,
    max_white_moves=10, hidden=True, illegal_loses=True, shuffle_black=True,
    seeded_bot=False,
)


def start():
    return GAME.start()


def move(sess, uci):
    return GAME.move(sess, uci)
