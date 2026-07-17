# Simple Math

Category: misc / math
Type: dynamic (TCP service)

## Description
Simple math can be quite complex

## Flag
BHCTF{eml_tr33s_4r3_fuN}

## Walkthrough/Solution
The server seeds `random.Random(int(time.time()))`, sends that `time.time()`,
and for each of 20 rounds builds an odd-degree polynomial with `gen()` and
asks for a real `X` with `|f(X)| < 1e-6`. Odd degree guarantees a real root.

Reproduce the polynomials from the sent seed (the generator is in the handout),
then find a real root. Two paths:
1. **Numeric** — reconstruct the pure-EML tree and treat it as a black-box
   `f(x)`: scan the real axis for a sign change and bisect / Newton. You don't
   even need to know it's a polynomial.
2. **Reverse the EML** — recognise (via the paper) that each tree is a
   polynomial, recover its integer coefficients, and use `numpy.roots`.

Two subtleties, both from the paper:
- `eml` uses **complex** `exp`/`ln`, so evaluate over ℂ. Evaluate only on the
  real axis — off it, the branch cuts make the eml reconstruction unreliable.
- Pure Python traps the `ln(0)`/`inf` cases eml relies on; **numpy** follows
  IEEE and sails through them (`np.log(0) = -inf`, no exception).

Reference solver: [`solve/solve.py`](solve/solve.py) — `roots` path by default,
`--numeric` for the bisection path:
```bash
python3 solve/solve.py <host> 9004
python3 solve/solve.py <host> 9004 --numeric
```

## How-to-run (Dynamic Challenges only)
```bash
docker compose up --build one-operator     # from the repo root
# or standalone:
docker build -t one-operator challenges/math && docker run -p 9004:1337 one-operator
```
