# Chess CTF

# Flags:
* Game 1, Baby's first checkmate: BHCTF{r4nd0m_b0t_1s_n0_m4tch}
* Game 2, Welcome to the jungle:  BHCTF{inv1sible_k1ng_1s_d3ad_GG}
* Game 3, Behind enemy lines:     BHCTF{Exc3lent_r0yal_run}
* Game 4, Chessmaster:            BHCTF{po0r_pr3dictable_bart_4lways_m0ves_th3_same}

# Solution(s)
* Game 1: Play the game, the bot is random...
* Game 2: Same dummy bot as Game 1, but bot is "invisible". Proxy the traffic and view their location via the API (note: location is scrambled as well as "invisible")
* Game 3: 100 mazes. Create a maze solver that interacts with the API
* Gmae 4: Note the new bot sets its random-seed based on the users movement. Find a Fool's Mate-like move, repeat it 100 times (automated), win

## Run
```bash
docker compose up --build
docker compose down
```

## Run Tests
```bash
docker compose run --rm --no-deps backend python -m pytest backend/tests -q
```

