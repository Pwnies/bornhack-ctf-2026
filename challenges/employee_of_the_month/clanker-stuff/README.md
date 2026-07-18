# HRM Reversing Challenge — "Self-Writing Checker"

A flag-checker reversing challenge for the **Human Resource Machine** sandbox:
<https://s3.amazonaws.com/christopherwatford-com/hrm/hrmfiddle.html>

## Files
- `checker.hrm` — the program (paste into the code editor)
- `floor.json` / `floor.min.json` — the memory floor: **empty `{}`**
- `solution_inbox.txt` — the winning INBOX (author copy; don't ship to players)
- `build5.py` — regenerator/tuner; `sim.py` — faithful engine simulator used to verify

## Run it
1. Paste `checker.hrm` into the editor. Put `{}` in the **Floor (JSON)** box
   (or anything — the program ignores it).
2. Put one integer per line in the **Inbox** — the ASCII code of each flag char.
3. **Run.** Output `1` (green) = correct flag; `0` = wrong.

## Player brief
> You recovered a worker's program. The floor is empty — no answer key, no hints.
> It reads the ASCII code of each flag character from the INBOX and prints `1` if
> the flag is correct. The program builds everything it needs itself. Recover the
> flag. Format: `BHCTF{...}`

Players get **`checker.hrm`** only (floor is empty).

---

## Fully self-contained (design note)

HRM has **no immediate operands** — `sub 6` means "subtract *tile* 6", never the
literal 6 — and `bumpup`/`copyfrom`/`add`/`sub` all require the tile to already be
*defined*. So a program can't just conjure a constant from nothing… except that
**`inbox` yields a value without touching any tile.** The program uses that to
bootstrap from an empty floor:

The whole builder keeps a **running accumulator in the hand** — it almost never
`copyfrom`s a tile, it just keeps add/sub-ing the current hand onward:

1. **Bootstrap 0:** `inbox` → hand holds flag char 0; `copyto` stashes it into
   `CUR` (and defines a tile); `sub CUR` gives **0**, independent of any value.
   (PREV/PTR need no pre-zeroing — the chain `copyto`s straight over them, and
   there is no dedicated zero tile at all.)
2. **First 1 from `bumpup`:** seed the first coin tile with that 0 and `bumpup`
   it → `1` (`ONE`).
3. **Build a power-of-two coin ladder by doubling *in place*:** each coin is the
   previous one added to itself — `copyto d` stores the hand, `add d` doubles it —
   giving `1,2,4,8,…,128` with no `copyfrom`. This is the cheapest ladder to
   construct *and* lets every later value be a minimal signed-binary
   (add/subtract-powers-of-two) sum.
4. **Build constants and write the table:** the constants — seed/PREV (100) and the
   table pointer (= flag length `N`) — are reached by add/sub-ing coins *straight
   off the last coin (128)*, never resetting. The table then anchors on `ONE`
   **once** (`copyfrom ONE`, so the accumulator starts at 1 — no zero tile required)
   and chains every entry off the hand as a signed-binary delta. It is written into
   tiles `1..N` **reversed** — entry `T[i]` lands in tile `N-i` — so the pointer
   can later walk it *downward*. Only that one anchoring `copyfrom` appears in the
   whole build. Crucially the entries are also written **out of address order** —
   the builder solves a shortest-path problem so each value is a cheap delta from
   the one written just before it (equal entries even cost nothing). That roughly
   halves the table *and* means reading the trace top-to-bottom no longer hands you
   `T` in order — you must bucket each snapshot by its `copyto` tile first. The
   table is *not* the flag — it's the chained transform

   ```
   T[i] = f[i] + f[i-1]        with f[-1] = SEED = 100
   ```

5. **Check loop:** char 0 is already stashed in `CUR`, so it jumps straight into
   the check; later chars come from `inbox`. Each char: add `PREV`, then `sub [0]`
   (indirect) subtracts the table entry the pointer is on. Zero ⇒ match → set
   `PREV` to this char and `bumpdn 0` the pointer. **The pointer is also the
   counter:** it starts at `N` and walks tile `N` (`=T[0]`) down to tile `1`
   (`=T[N-1]`); when `bumpdn` takes it to **0** — a tile it never reads — every
   entry matched, so output `ONE`. Any mismatch ⇒ output `0`, produced
   value-independently as `CUR - CUR` — the same trick as the bootstrap, so no zero
   tile is needed here either.

Runtime tiles (all constructed at run time, nothing pre-seeded):

| tile | role |
|------|------|
| 0 | `PTR` → current table entry, **and** the down-counter (0 ⇒ done) |
| 1..N | the expected table, stored **reversed**: tile `j` holds `T[N-j]` |
| N+1 | `CUR` — current char (also the bootstrap stash) |
| N+2 | `PREV` — previous input / transform seed |
| N+3..N+10 | power-of-two coins `1,2,4,8,16,32,64,128` (tile `N+3` = `1` = `ONE`, the success value and the table anchor) |

Merging the pointer and counter into one down-counting tile removes the old
separate counter. There is likewise no zero tile: the two spots that needed `0` —
the table anchor and the fail output — get it for free (the table starts from
`ONE`; the fail output is `CUR - CUR`).

### Solve
The coins are powers of two: tile `ONE` = `1`, and each higher coin tile doubles it
(read the ladder off the top of the program to fix `ONE` and the mapping). The
table section opens with `copyfrom ONE`, so the accumulator starts at `1`. Because
the table is written **out of order** *and* **reversed**, snapshot the accumulator
at every `copyto` and store it under that tile number; the table lives in tiles
`1..N`, and tile `N-i` holds `T[i]`, so read them back accordingly and invert the
chain (`f[0]=T[0]-SEED`, `f[i]=T[i]-f[i-1]`):

```python
N = 34                                               # = number of copyto's into 1..N
ONE = N + 3                                           # first coin tile (from the ladder)
coin = {ONE + i: 1 << i for i in range(8)}           # tile -> power of two
tbl, acc = {}, 0
for op, arg in table_section_ops:                    # the "write the expected table" block
    if op == "copyfrom": acc = coin.get(arg, 0)      # anchor: copyfrom ONE -> 1
    elif op == "copyto": tbl[arg] = acc              # arg in 1..N
    elif op == "add":    acc += coin[arg]
    elif op == "sub":    acc -= coin[arg]
T = [tbl[N - i] for i in range(N)]                   # tile N-i -> T[i]; undoes the reversal
                                                     # == [166,138,139,151,154,193,222,147,
                                                     #     160,233,216,197,216,162,157,204,211,
                                                     #     220,155,146,194,147,158,228,169,172,
                                                     #     169,162,209,193,149,159,224,241]
prev, flag = 100, ""
for t in T:
    f = t - prev          # f[i] = T[i] - f[i-1]
    flag += chr(f)
    prev = f
print(flag)               # BHCTF{c0py_fr0m_th3_c0nv3y0r_b3lt}
```

### Winning INBOX (one per line)
```
66 72 67 84 70 123 99 48 112 121 95 102 114 48 109 95 116 104 51 95 99 48 110 118 51 121 48 114 95 98 51 108 116 125
```

**Flag: `BHCTF{c0py_fr0m_th3_c0nv3y0r_b3lt}`**

## Tuning
Edit `FLAG` / `SEED` in `build5.py` and rerun `python3 build5.py`. It regenerates
`checker.hrm` and re-verifies (via `sim.py`, capped at the engine's 5000-iteration
limit) that: the correct flag outputs `1` under an **empty floor** (and under
garbage floors); wrong/truncated/empty inputs output non-`1`; and the builder's
table inverts back to the flag.
