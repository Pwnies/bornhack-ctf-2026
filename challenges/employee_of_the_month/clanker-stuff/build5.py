import json
from sim import run

FLAG="BHCTF{c0py_fr0m_th3_c0nv3y0r_b3lt}"
SEED=100
codes=[ord(c) for c in FLAG]; N=len(codes)

T=[]; p=SEED
for c in codes: T.append(c+p); p=c
assert all(-999<=t<=999 for t in T)

# ---- tile map ----------------------------------------------------------
# 0        PTR  -> current table entry (indirect target of `sub [0]`); also the
#                  loop counter -- it counts DOWN through the table to 0
# 1..N     the expected table, stored REVERSED: tile j holds T[N-j], so the
#          pointer walks tile N (=T[0]) down to tile 1 (=T[N-1])
# N+1      CUR  -> current char (also the bootstrap stash)
# N+2      PREV -> previous input / transform seed
# N+3..N+10 power-of-two "coins" 1,2,4,8,16,32,64,128 (tile N+3 == 1 == ONE, the
#          success value AND the anchor the table chains off -- no ZERO tile)
#
# The pointer doubles as the counter: it starts at N and each match decrements it
# with `bumpdn 0`; reaching 0 (a tile it never reads) means every entry matched.
# That merges the old PTR and CNT into a single tile.
TBL=1                                          # table occupies TBL..TBL+N-1 = 1..N
CUR=N+1; PREV=N+2; ONE=N+3; MAXCOIN=128
POW=[(ONE+i, 1<<i) for i in range(8)]          # (tile, value): ONE..ONE+7 = 1..128
VALT={v:t for t,v in POW}                      # value -> tile
COINVAL={str(t):v for t,v in POW}              # tile  -> value

def naf(v):
    "non-adjacent form: minimal-weight signed-binary digits of v (16-1 beats 8+4+2+1)"
    out=[]; n=v; k=1
    while n!=0:
        if n & 1:
            if n & 2: out.append(-k); n+=1
            else:     out.append(k)
        n>>=1; k<<=1
    return out

def delta(frm, to):
    "add/sub ops turning a hand holding `frm` into `to`, spending coin tiles"
    ops=[f"    {'add' if term>0 else 'sub'} {VALT[abs(term)]}"
         for term in sorted(naf(to-frm), key=lambda x:-abs(x))]
    assert frm + sum((1 if o[4:7]=='add' else -1)*COINVAL[o.split()[1]] for o in ops)==to
    return ops

def table_order(values, anchor):
    """Pick the *write order* for the table that minimises total add/sub ops.

    Building the table keeps the hand as a running accumulator, so the cost of
    writing value `b` right after value `a` is the signed-binary weight of a->b.
    Entries land in fixed tiles regardless of order, so we are free to choose the
    order -- a shortest Hamiltonian path from the `anchor` value the hand starts
    on through every entry. Edges needing a coin bigger than we built are forbidden
    (infinite cost). Deterministic nearest-neighbour + 2-opt + or-opt (no RNG, so
    the build is reproducible). Out-of-order writing roughly halves the table *and*
    hides T from a straight top-to-bottom read of the trace."""
    INF=10**9
    def edge(a,b):
        d=naf(a-b)
        return INF if d and max(abs(x) for x in d)>MAXCOIN else len(d)
    nodes=[anchor]+list(values); n=len(nodes)
    D=[[edge(nodes[i],nodes[j]) for j in range(n)] for i in range(n)]
    cost=lambda p: sum(D[p[i]][p[i+1]] for i in range(len(p)-1))
    def refine(path):
        better=True
        while better:
            better=False
            for i in range(1,n-1):
                for j in range(i+1,n):
                    q=path[:i]+path[i:j+1][::-1]+path[j+1:]
                    if cost(q)<cost(path): path=q; better=True
            for i in range(1,n):
                for j in range(1,n):
                    if i==j: continue
                    q=path[:i]+path[i+1:]; q=q[:j]+[path[i]]+q[j:]
                    if q[0]==0 and cost(q)<cost(path): path=q; better=True
        return path
    best=None
    for first in range(1,n):                     # try each entry as the first written
        unv=set(range(1,n))-{first}; path=[0,first]; cur=first
        while unv:
            nxt=min(unv,key=lambda j:D[cur][j]); path.append(nxt); unv.discard(nxt); cur=nxt
        path=refine(path)
        if best is None or cost(path)<cost(best): best=path
    return [i-1 for i in best[1:]]                # node index -> value index

# ---- coin ladder: bumpup seeds 1, each coin = the previous doubled in place ----
ladder=[f"    copyto {ONE}", f"    bumpup {ONE}"]    # tile ONE = 1, hand = 1
for t in range(ONE+1, ONE+8):
    ladder += [f"    add {t-1}", f"    copyto {t}"]   # hand doubles, then store
# hand now holds 128

# ---- run constants, chained straight off the hand (=128); no copyfrom ----
consts=[]; hand=MAXCOIN
for tile,val in ((PREV,SEED),(0,N)):           # PREV, then PTR (starts at N)
    consts += delta(hand,val); consts.append(f"    copyto {tile}"); hand=val

# ---- table: anchor on ONE once (copyfrom ONE -> hand = 1; no zero tile needed),
#      chained off the running hand, in cost-minimising write order. T[i] lands in
#      tile N-i so the pointer can walk the table downward to 0. ----
ORDER=table_order(T, 1)
table=[f"    copyfrom {ONE}"]; hand=1
for i in ORDER:
    table += delta(hand,T[i]); table.append(f"    copyto {TBL+(N-1-i)}"); hand=T[i]

L=["-- HUMAN RESOURCE MACHINE PROGRAM --",
   "-- fully self-contained flag checker: needs NO floor at all ({} works)",
   "-- one ASCII code of the flag per line in the INBOX -> prints 1 if correct",
   "",
   "-- ---- bootstrap 0 from the first INBOX box (no tile needed) ----",
   "    inbox",              # hand = f[0]
   f"    copyto {CUR}",      # CUR = f[0]   (stash the first char for the check)
   f"    sub {CUR}",         # hand = 0     (value-independent; PREV/PTR set by the chain)
   "",
   "-- ---- build the power-of-two coin ladder by doubling (first 1 from bumpup) ----",
   *ladder,
   "",
   "-- ---- build the run constants straight off the hand (still holds 128) ----",
   *consts,
   "",
   "-- ---- write the expected table into tiles %d..%d (reversed) ----"%(TBL,TBL+N-1),
   *table,
   "",
   "-- ---- check loop (char 0 is already waiting in CUR; PTR counts down to 0) ----",
   "    jump k",             # go straight to checking the stashed first char
   "a:",
   "    inbox", f"    copyto {CUR}",
   "k:",
   f"    copyfrom {CUR}", f"    add {PREV}", "    sub [0]",   # CUR + PREV - T[PTR]
   "    jumpz b",
   f"    copyfrom {CUR}", f"    sub {CUR}", "    outbox", "    jump z",  # mismatch -> 0
   "b:",
   f"    copyfrom {CUR}", f"    copyto {PREV}", "    bumpdn 0",  # PREV=CUR; PTR-- (hand=PTR)
   "    jumpz e", "    jump a",                                  # PTR hit 0 -> all matched
   "e:", f"    copyfrom {ONE}", "    outbox",                    # success -> output ONE
   "z:", ""]
program="\n".join(L)

def check(floor,inp):
    out,it=run(program,inp,floor); assert it<5000,("iters",it); return out
# empty floor and garbage floors must all behave identically
for floor in ({}, {"8":999}, {str(k):-7 for k in range(60)}):
    assert check(floor,codes)==[1], (floor,check(floor,codes))
    for bad in (codes[:5]+[88]+codes[6:], codes[:-1]+[33], codes[:8], [],
                [ord(x) for x in "BHCTF{completely_wrong_here!!!!!!}"]):
        assert check(floor,bad)!=[1], (floor,bad)

# solver trace: recover flag from the self-contained table-writing section only.
# The table is written OUT OF ORDER and REVERSED, so bucket each snapshot by its
# copyto tile, then read tiles back so tile N-i gives T[i] before inverting.
data=program.split("write the expected table")[1].split("check loop")[0]
tiles={}; acc=0
for line in data.splitlines():
    parts=line.split('--',1)[0].split()
    if not parts: continue
    if parts[0]=="copyfrom": acc=COINVAL.get(parts[1],0)   # anchor: ONE tile -> 1
    elif parts[0]=="copyto": tiles[int(parts[1])]=acc
    elif parts[0] in ("add","sub"):
        v=COINVAL[parts[1]]; acc+= v if parts[0]=="add" else -v
vals=[tiles[TBL+(N-1-i)] for i in range(N)]     # tile N-i -> T[i]
rec=""; p=SEED
for t in vals: f=t-p; rec+=chr(f); p=f
assert rec==FLAG, rec

addsub=program.count("\n    add ")+program.count("\n    sub ")
copyfrom=program.count("\n    copyfrom ")
FLOOR={}
open("checker.hrm","w").write(program)
open("floor.json","w").write(json.dumps(FLOOR)+"\n")
open("floor.min.json","w").write(json.dumps(FLOOR,separators=(',',':'))+"\n")
open("solution_inbox.txt","w").write("\n".join(map(str,codes))+"\n")
_,iters=run(program,codes,{})
print("VALIDATED  flag =",FLAG)
print("floor shipped:", json.dumps(FLOOR), "(empty; program reads no pre-existing tile)")
print("program lines:", program.count(chr(10))+1)
print("add/sub ops:", addsub, " copyfrom ops:", copyfrom, " runtime iters:", iters)
print("highest tile used:", ONE+7)
