#!/usr/bin/env python3
"""Reference solver for "One Operator to Root Them All".

The server prints the time.time() it used, seeds random.Random(int(t)), and
generates each polynomial with the handout's own code. So we reproduce every
polynomial exactly and find a real root of each. Two ways are shown:

  * roots   -- reproduce the coefficients and use numpy.roots (the "reverse the
               EML representation" path); default.
  * numeric -- reconstruct the pure-EML tree and bisect for a real zero,
               treating eml() as a black box (--numeric).

Usage: python solve.py [host] [port] [--numeric]
"""
import random
import socket
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 2)[0])
import server as S  # noqa: E402

NUMERIC = "--numeric" in sys.argv
pos = [a for a in sys.argv[1:] if not a.startswith("--")]
HOST = pos[0] if pos else "127.0.0.1"
PORT = int(pos[1]) if len(pos) > 1 else 1337


def coeffs_of(rng):
    deg = rng.choice([3, 5])
    return [rng.randint(-5, 5) for _ in range(deg)] + [rng.choice([-3, -2, -1, 1, 2, 3])]


def root_via_roots(rng):
    coeffs = coeffs_of(rng)
    roots = np.roots(coeffs[::-1])
    return float(sorted(roots, key=lambda z: abs(z.imag))[0].real)


def root_via_bisection(rng):
    t = S.gen(rng)
    f = lambda x: S.ev(t, float(x)).real
    lo, hi, n = -8.0, 8.0, 400
    xs = [lo + (hi - lo) * i / n for i in range(n + 1)]
    ys = [f(x) for x in xs]
    for i in range(1, n + 1):
        if ys[i - 1] * ys[i] <= 0 and ys[i - 1] != ys[i]:
            a, b, fa = xs[i - 1], xs[i], ys[i - 1]
            for _ in range(60):
                m = (a + b) / 2
                fm = f(m)
                if fa * fm <= 0:
                    b = m
                else:
                    a, fa = m, fm
            return (a + b) / 2
    raise RuntimeError("no real root bracketed")


def main():
    s = socket.create_connection((HOST, PORT), timeout=30)
    s.settimeout(30)
    buf = b""

    def fill():
        nonlocal buf
        d = s.recv(4096)
        if not d:
            raise EOFError("connection closed")
        buf += d

    while b"\n" not in buf:
        fill()
    line, buf = buf.split(b"\n", 1)
    seed = int(float(line.decode().strip()))
    rng = random.Random(seed)
    print(f"[*] seed = {seed}")

    while True:
        while not any(m in buf for m in (b"X = ", b"BHCTF{", b"bye.")):
            fill()
        if b"BHCTF{" in buf:
            print("[+] " + buf.decode(errors="replace").strip())
            print(f"[+] solved via {'numeric' if NUMERIC else 'roots'} path.")
            return
        if b"bye." in buf:
            print("[-] rejected: " + buf.decode(errors="replace").strip())
            return
        buf = buf[buf.index(b"X = ") + 4:]
        root = root_via_bisection(rng) if NUMERIC else root_via_roots(rng)
        s.sendall(f"{root!r}\n".encode())


if __name__ == "__main__":
    main()
