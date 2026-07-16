"""Static config: flags and tunables. Flags overridable via env for deployment."""
import os

FLAGS = {
    "game1": os.environ.get("FLAG_GAME1", "BHCTF{r4nd0m_b0t_1s_n0_m4tch}"),
    "game2": os.environ.get("FLAG_GAME2", "BHCTF{inv1sible_k1ng_1s_d3ad_GG}"),
    "game3": os.environ.get("FLAG_GAME3", "BHCTF{Exc3lent_r0yal_run}"),
    "game4": os.environ.get("FLAG_GAME4", "BHCTF{po0r_pr3dictable_bart_4lways_m0ves_th3_same}"),
}

# Seed base for the shared random bot. Tuned later (Game 4) so that at least one
# White first move yields a <=5-move mate line. Overridable via env.
SEED_BASE = int(os.environ.get("SEED_BASE", "0"))

# How long an idle session lives before it can be swept (seconds).
SESSION_TTL = int(os.environ.get("SESSION_TTL", str(60 * 60)))

# Hard cap on live sessions. Anyone can POST /{game}/new in a loop, and each session
# holds a board (+ attack sets for Game 3), so the TTL alone lets the store grow
# unbounded for an hour. Past the cap we evict least-recently-used sessions: a
# runaway client only ever evicts itself, while ~10 real players never come close.
MAX_SESSIONS = int(os.environ.get("MAX_SESSIONS", "5000"))
