"""Game 1, Baby's first checkmate (trivial)

Beat a random-move bot in 10 moves or less.
"""
from ..config import FLAGS
from ._random_bot_game import RandomBotGame

INTRO = (
    "You are White. Win in 10 moves or less. Profit!"
)

GAME = RandomBotGame("game1", FLAGS["game1"], INTRO, max_white_moves=10, seeded_bot=False)


def start():
    return GAME.start()


def move(sess, uci):
    return GAME.move(sess, uci)
