#!/usr/bin/env python3
from Cryptodome.Cipher import AES
from os import urandom

encrypt_real = lambda key, pt: AES.new(key, AES.MODE_ECB).encrypt(pt)

circut = {}
while (gate := input("NAND> ").strip()):
    o, a, b = gate.split(" ")
    circut[o] = (a, b)

def eval(wire, memo):
    if wire not in memo:
        memo[wire] = not (eval(circut[wire][0], memo) and eval(circut[wire][1], memo))
    return memo[wire]

def encrypt_circut(key, pt):
    memo = {}
    for i in range(128): memo[f"pt_{i}"] = (int.from_bytes(pt, "big") >> i) & 1
    for i in range(128): memo[f"key_{i}"] = (int.from_bytes(key, "big") >> i) & 1
    return sum(eval(f"ct_{i}", memo) << i for i in range(128)).to_bytes(16, "big")

for i in range(100):
    key, pt = urandom(16), urandom(16)
    assert encrypt_real(key, pt) == encrypt_circut(key, pt)

with open("flag", "rb") as flag:
    while pt := flag.read(16):
        pt += b"\x00" * (16 - len(pt))
        print(encrypt_circut(urandom(16), pt).hex())