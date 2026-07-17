#!/usr/bin/env python3
"""Forth-aware obfuscator for escargot.dev.fs -> escargot.fs.
Opaque-renames every word DEFINED in this file (via : / variable / create /
constant / value / ...) and every reference to them, then strips non-semantic
whitespace. String literals (." ..."  s" ..."  c" ..."  abort" ...") are kept
byte-for-byte (their spaces are program output / compare data). Words defined
elsewhere (chacha20-init, chacha20-xor) and all gforth built-ins are untouched.
"""
import sys

WS = " \t\r\n"
STRINGERS = {'."', 's"', 'c"', '.("', 'abort"'}
INTRODUCERS = {':', 'variable', '2variable', 'fvariable', 'create', 'constant',
               '2constant', 'fconstant', 'value', '2value', 'defer', 'buffer:'}

def scan(src):
    toks = []  # ('str', text) kept verbatim, or ('w', word)
    i, n = 0, len(src)
    while i < n:
        while i < n and src[i] in WS:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and src[j] not in WS:
            j += 1
        word = src[i:j]
        if word in STRINGERS:
            # src[j] is the delimiter (whitespace); content runs to next "
            k = src.index('"', j + 1)
            toks.append(('str', src[i:k + 1]))
            i = k + 1
        else:
            toks.append(('w', word))
            i = j
    return toks

def collect_names(toks):
    order, seen = [], set()
    prev = None
    for kind, tx in toks:
        if kind == 'w':
            low = tx.lower()
            if prev in INTRODUCERS and low not in seen:
                seen.add(low); order.append(low)
            prev = low
        else:
            prev = None
    return order

def opaque_names(count, reserved):
    """Generate `count` short opaque names avoiding gforth builtins + reserved."""
    out, k = [], 0
    while len(out) < count:
        cand = f'q{k}'
        k += 1
        if cand not in reserved:
            out.append(cand)
    return out

def gforth_builtins():
    import subprocess
    out = subprocess.run(['gforth', '-e', 'words bye'], capture_output=True,
                         text=True).stdout
    return set(w.lower() for w in out.split() if w)

def main():
    builtins = (set(w.strip().lower() for w in open(sys.argv[1]) if w.strip())
                if len(sys.argv) > 1 else gforth_builtins())
    src = open('escargot.dev.fs').read()
    toks = scan(src)
    names = collect_names(toks)
    reserved = builtins | set(names)
    opaque = opaque_names(len(names), reserved)
    rename = {nm: opaque[i] for i, nm in enumerate(names)}
    out = []
    for kind, tx in toks:
        if kind == 'w' and tx.lower() in rename:
            out.append(rename[tx.lower()])
        else:
            out.append(tx)
    # emit: single-space separation on one line (line breaks are just whitespace
    # in Forth). Wrap only as a safety net well under any input-line limit, never
    # splitting a string atom nor a definer from the name that must follow it.
    W, line, lines, glue = 100000, '', [], False
    for t in out:
        if line and not glue and len(line) + 1 + len(t) > W:
            lines.append(line); line = t
        else:
            line = t if not line else line + ' ' + t
        glue = t.lower() in INTRODUCERS
    if line:
        lines.append(line)
    open('escargot.fs', 'w').write('\n'.join(lines) + '\n')
    sys.stderr.write(f'obfuscated: {len(names)} names renamed, '
                     f'{len(lines)} lines, {sum(len(l) for l in lines)} bytes\n')

if __name__ == '__main__':
    main()
