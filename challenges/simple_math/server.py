#!/usr/bin/env python3
import os
import random
import socketserver
import time

import numpy as np

np.seterr(all="ignore")

FLAG = os.environ.get("FLAG")
PORT = int(os.environ.get("PORT", "1337"))


def eml(a, b):
    return ("eml", a, b)


def ev(t, x):
    tag = t[0]
    if tag == "1":
        return np.complex128(1)
    if tag == "x":
        return np.complex128(x)
    return np.exp(ev(t[1], x)) - np.log(ev(t[2], x))


def gen(rng):
    n = rng.choice([3, 5])
    m = [rng.randint(-5, 5) for _ in range(n)] + [rng.choice([-3, -2, -1, 1, 2, 3])]

    ONE = ("1",)

    def foo(u):
        return eml(eml(ONE, eml(eml(ONE, eml(eml(ONE, eml(eml(ONE, eml(ONE, ONE)), ONE)), eml(u, ONE))), ONE)), eml(eml(ONE, ONE), ONE))

    def bar(n):
        if n == 0:
            return eml(eml(ONE, eml(eml(ONE, ONE), ONE)), eml(ONE, ONE))
        t = ONE
        for _ in range(abs(n) - 1):
            t = eml(eml(ONE, eml(eml(ONE, t), ONE)), eml(foo(ONE), ONE))
        return t if n > 0 else foo(t)

    e = bar(m[-1])
    for a in reversed(m[:-1]):
        b = eml(ONE, eml(eml(ONE, e), ONE))
        c = eml(ONE, eml(eml(ONE, ("x",)), ONE))
        d = eml(eml(eml(ONE, eml(eml(ONE, b), ONE)), eml(foo(c), ONE)), ONE)
        e = eml(eml(ONE, eml(eml(ONE, d), ONE)), eml(foo(bar(a)), ONE))
    return e


class Handler(socketserver.StreamRequestHandler):
    timeout = 20

    def send(self, text):
        self.wfile.write(text.encode())
        self.wfile.flush()

    def read_real(self):
        line = self.rfile.readline()
        if not line:
            raise EOFError
        return float(line.decode(errors="replace").strip())

    def handle(self):
        np.seterr(all="ignore")
        t = time.time()
        rng = random.Random(int(t))
        self.send(f"{t}\n")
        try:
            for i in range(1, 21):
                t = gen(rng)
                self.send(f"\n[round {i}/20] X = ")
                try:
                    x = self.read_real()
                except (ValueError, EOFError):
                    self.send("not a real number -- bye.\n")
                    return
                except (TimeoutError, OSError):
                    self.send("\ntoo slow -- bye.\n")
                    return
                val = abs(ev(t, float(x)))
                if val > 1e-6:
                    self.send(f"nope  (|f(X)| = {val:.2e})  -- bye.\n")
                    return
            self.send(f"{FLAG}\n")
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("0.0.0.0", PORT), Handler) as srv:
        print(f"listening on 0.0.0.0:{PORT}", flush=True)
        srv.serve_forever()
