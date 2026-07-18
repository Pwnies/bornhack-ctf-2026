#!/usr/bin/env bash
# ===========================================================================
#  run-test.sh - headless end-to-end test of the VINDAASEN order flow.
#
#  Boots Windows 1.01 under dosbox-x (no display: dummy SDL video/audio),
#  auto-launches D:\VINDÅSEN.EXE, drives a full order over the COM2 BBS line,
#  and verifies the result: order total, order id, Giro +04 code line, and the
#  persisted ORDRER.TXT record. A status lookup and an unknown-id lookup are
#  checked too.
#
#  Both DOS drives are mounted through a dosbox-x OVERLAY, so the tracked repo
#  tree is NEVER modified:
#    * C:  base = WIN1.01/ , overlay carries a WIN.INI with run=D:\VINDÅSEN.EXE
#          (so Windows auto-launches the app) - no full-tree copy needed.
#    * D:  base = VINDAASEN/ , overlay captures the app's writes (ORDRER.TXT).
#  Everything transient lives in a mktemp dir that is removed on exit.
#
#  Usage:
#    ./run-test.sh              run the test against the current VINDÅSEN.EXE
#    ./run-test.sh --build      build first (WIN3.0 VM, BUILD.BAT), then test
#
#  Env overrides:
#    PORT=2399        TCP port dosbox-x bridges to COM2 (pick a free one)
#    BOOT_WAIT=35     seconds to wait for Win 1.01 to boot + load the app
# ===========================================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIN101="$REPO/WIN1.01"
WIN30="$REPO/WIN3.0"
VIND="$REPO/VINDAASEN"
PORT="${PORT:-2399}"
BOOT_WAIT="${BOOT_WAIT:-35}"
DO_BUILD=0
[ "${1:-}" = "--build" ] && DO_BUILD=1

command -v dosbox-x >/dev/null 2>&1 || { echo "ERROR: dosbox-x not found on PATH" >&2; exit 1; }
command -v python3  >/dev/null 2>&1 || { echo "ERROR: python3 not found on PATH" >&2; exit 1; }
[ -d "$WIN101" ] && [ -d "$VIND" ] || { echo "ERROR: run from the repo (WIN1.01/ + VINDAASEN/ expected)" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/vind-test.XXXXXX")"
COVL="$WORK/covl"; DOVL="$WORK/ovl"
mkdir -p "$COVL/WINDOWS" "$DOVL"

DOSBOX_PID=""
cleanup() {
    [ -n "$DOSBOX_PID" ] && kill "$DOSBOX_PID" 2>/dev/null || true
    sleep 1
    [ -n "$DOSBOX_PID" ] && kill -9 "$DOSBOX_PID" 2>/dev/null || true
    # belt-and-suspenders: any dosbox-x still holding our config (its argv
    # references $WORK even after the file is gone), plus the zenity child that
    # dosbox-x may spawn and that keeps holding the TCP port.
    pkill -f "$WORK" 2>/dev/null || true
    pkill -x zenity 2>/dev/null || true
    rm -rf "$WORK"
}
trap cleanup EXIT

# --------------------------------------------------------------------------
#  Optional: build VINDÅSEN.EXE in the WIN3.0 VM (plain mount - the build must
#  write the exe into VINDAASEN/; those outputs are gitignored).
# --------------------------------------------------------------------------
if [ "$DO_BUILD" = 1 ]; then
    [ -d "$WIN30" ] || { echo "ERROR: --build needs WIN3.0/" >&2; exit 1; }
    echo ">> building (WIN3.0 VM, BUILD.BAT)..."
    BCFG="$WORK/build.dosbox"
    cat > "$BCFG" <<EOF
[sdl]
autolock=false
[cpu]
cycles=max
[autoexec]
mount c "$WIN30"
mount d "$VIND"
d:
cd \\
call BUILD.BAT
exit
EOF
    rm -f "$VIND/VINDÅSEN.EXE"
    timeout 240 env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY \
        SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
        dosbox-x -conf "$BCFG" -nolog -nogui -nomenu >"$WORK/build.log" 2>&1 || true
    if [ ! -f "$VIND/VINDÅSEN.EXE" ]; then
        echo "BUILD FAILED: no VINDÅSEN.EXE produced (see build log below)" >&2
        tail -n 20 "$WORK/build.log" 2>/dev/null >&2 || true
        exit 1
    fi
    echo ">> build OK"
fi

[ -f "$VIND/VINDÅSEN.EXE" ] || {
    echo "ERROR: VINDAASEN/VINDÅSEN.EXE not found - build it first (./run-test.sh --build)" >&2
    exit 1
}

# --------------------------------------------------------------------------
#  Seed the C: overlay with a WIN.INI that auto-launches the app.
# --------------------------------------------------------------------------
python3 - "$WIN101/WINDOWS/WIN.INI" "$COVL/WINDOWS/WIN.INI" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
lines = open(src, 'rb').read().split(b'\r\n')          # preserve CRLF
out = [b'run=D:\\VIND\x8fSEN.EXE' if ln.lower().startswith(b'run=') else ln
       for ln in lines]
open(dst, 'wb').write(b'\r\n'.join(out))
PY

# --------------------------------------------------------------------------
#  Boot config: overlay on BOTH drives, COM2 -> TCP, dummy video.
# --------------------------------------------------------------------------
CFG="$WORK/run.dosbox"
cat > "$CFG" <<EOF
[dosbox]
machine=ega
[sdl]
autolock=false
[cpu]
cycles=max
[serial]
serial1=serialmouse
serial2=nullmodem port:$PORT transparent:1
serial3=nullmodem port:$((PORT+1)) transparent:1
[autoexec]
keyb dk
mount c "$WIN101"
mount c "$COVL" -t overlay
mount d "$VIND"
mount d "$DOVL" -t overlay
c:
PATH C:\\WINDOWS;Z:\\;C:\\;
ver set 3 30
cd \\WINDOWS
win
EOF

echo ">> booting Windows 1.01 headless (port $PORT, ~${BOOT_WAIT}s)..."
# env execs into dosbox-x (same PID), so $! is dosbox-x itself - the cleanup
# trap can kill it directly (no wrapper subshell to orphan it).
env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY \
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
    dosbox-x -conf "$CFG" -nolog -nogui -nomenu >"$WORK/dosbox.log" 2>&1 &
DOSBOX_PID=$!

# --------------------------------------------------------------------------
#  Drive the order flow and verify. Exit code: 0 = pass, 1 = fail.
# --------------------------------------------------------------------------
if python3 - "$PORT" "$BOOT_WAIT" "$VIND" "$DOVL" <<'PY'
import socket, time, sys, re, os

PORT      = int(sys.argv[1])
BOOT_WAIT = int(sys.argv[2])
VIND      = sys.argv[3]
DOVL      = sys.argv[4]

def dec(b): return b.decode('cp865', 'replace')

def read_until(s, tokens, timeout=15.0, quiet=1.5):
    end = time.time() + timeout; buf = b''; last = time.time()
    while time.time() < end:
        try:
            d = s.recv(4096)
            if d:
                buf += d; last = time.time()
                if any(t in dec(buf) for t in tokens):
                    time.sleep(0.25)
                    try:
                        d2 = s.recv(4096)
                        if d2: buf += d2
                    except socket.timeout: pass
                    return dec(buf)
            else:
                break
        except socket.timeout:
            if time.time() - last > quiet and buf:
                return dec(buf)
    return dec(buf)

def send(s, txt):
    s.sendall(txt.encode('cp865')); time.sleep(0.15)

# --- expected values, computed from the tracked data files ----------------
def catalog_price(path, art):
    for raw in open(path, 'rb').read().split(b'\r\n'):
        line = raw.decode('cp865', 'replace')
        if len(line) >= 6 and line[:3].strip() == art:
            m = re.search(r'(\d+)\s*$', line.rstrip())
            if m: return int(m.group(1))
    return None

def kreditor(path):
    if not os.path.exists(path): return None
    sect = None
    for raw in open(path, 'rb').read().split(b'\r\n'):
        ln = raw.decode('cp865', 'replace').strip()
        if ln.startswith('['): sect = ln.strip('[]').lower()
        elif sect == 'giro' and ln.lower().startswith('kreditornummer'):
            return ln.split('=', 1)[1].strip()
    return None

def admin_pw(path):
    if not path or not os.path.exists(path): return None
    sect = None
    for raw in open(path, 'rb').read().split(b'\r\n'):
        ln = raw.decode('cp865', 'replace').strip()
        if ln.startswith('['): sect = ln.strip('[]').lower()
        elif sect == 'admin' and ln.lower().startswith('kodeord'):
            return ln.split('=', 1)[1].strip()
    return None

def giro_line(oid, k8):
    pay = oid.rjust(15, '0')
    s = 0; w = 2
    for c in reversed(pay):
        p = (ord(c) - 48) * w
        if p >= 10: p = p // 10 + p % 10
        s += p; w = 1 if w == 2 else 2
    chk = (10 - s % 10) % 10
    return "+04<%s%d+%s<" % (pay, chk, k8)

VARER = os.path.join(VIND, "VARER.TXT")
INI   = None
for n in ("VINDÅSEN.INI", "VINDASEN.INI"):
    if os.path.exists(os.path.join(VIND, n)): INI = os.path.join(VIND, n); break

p101 = catalog_price(VARER, "101")
p110 = catalog_price(VARER, "110")
exp_total = 2 * p101 + 3 * p110
kred = kreditor(INI) if INI else None
k8   = (kred or "00000000").rjust(8, '0')
APW  = admin_pw(INI)

fails = []
def check(name, cond, detail=""):
    print(("  PASS " if cond else "  FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond: fails.append(name)

print(">> waiting %ds for boot + app load..." % BOOT_WAIT); sys.stdout.flush()
time.sleep(BOOT_WAIT)

s = socket.socket(); s.settimeout(2.5)
try:
    s.connect(('127.0.0.1', PORT))
except Exception as e:
    print("  FAIL connect  --", e); sys.exit(1)

greet = read_until(s, ["Vælg"], 12, 2.0)           # wait for the full menu ("Vælg: " is its last line)
if not greet.strip():                              # nothing arrived -> nudge once (client may predate OpenComm)
    send(s, "\r")
    greet = read_until(s, ["Vælg"], 12, 2.0)
check("greeting/menu", "ORDRESYSTEM" in greet)
# guard the static CP865 UI literals in BBS.C (a UTF-8 re-encode would replace
# these high-bit bytes and this would fail even though ASCII tokens survive)
check("banner 'VINDÅSEN' (Å byte intact)", "VINDÅSEN" in greet)
check("menu label 'Vælg' (æ byte intact)", "Vælg" in greet)
check("box-drawing intact", "╔" in greet and "═" in greet)
check("public menu hides 'Vis bestillinger'", "Vis bestillinger" not in greet)

# Use Danish high-bit letters (å=0x86 Å=0x8f æ=0x91 ø=0x9b in CP865) to guard
# against the signed-char input bug that silently dropped them.
NAME = "Søren Åbæk"
ADDR = "Nørregade 3"
CITY = "8700 Årup"
send(s, "N");            read_until(s, ["Navn:"])
send(s, NAME + "\r");    read_until(s, ["Adresse:"])
send(s, ADDR + "\r");    read_until(s, ["by:"])
send(s, CITY + "\r");    read_until(s, ["slut"])
send(s, "101\r");             read_until(s, ["Antal:"])
send(s, "2\r");               read_until(s, ["slut"])
send(s, "110\r");             read_until(s, ["Antal:"])
send(s, "3\r");               read_until(s, ["slut"])
send(s, "\r")
summary = read_until(s, ["Tryk en tast"], 15, 2.5)

m_tot  = re.search(r"I alt:\s*(\d+)\s*kr", summary)
m_id   = re.search(r"Ordrenr:\s*([0-9]+)", summary)
m_giro = re.search(r"(\+04<[0-9]+\+[0-9]+<)", summary)
tot = int(m_tot.group(1)) if m_tot else None
oid = m_id.group(1) if m_id else None
giro = m_giro.group(1) if m_giro else None

check("summary total = %d kr" % exp_total, tot == exp_total, "got %r" % tot)
check("order id present (11 digits)", bool(oid) and len(oid) == 11, "got %r" % oid)
check("Danish name echoed in summary (æøå)", NAME in summary, "want %r" % NAME)
check("Danish address echoed in summary", ADDR in summary and CITY in summary)
if oid:
    check("giro +04 line", giro == giro_line(oid, k8),
          "got %r want %r" % (giro, giro_line(oid, k8)))
    check("kreditor from INI (%s)" % k8, ("+%s<" % k8) in (giro or ""))

# --- status lookup --------------------------------------------------------
if oid:
    send(s, " ");        read_until(s, ["Vælg", "ORDRESYSTEM"])
    send(s, "S");        read_until(s, ["Ordrenr:"])
    send(s, oid + "\r"); st = read_until(s, ["Tryk en tast"], 12, 2.0)
    check("status shows NY", "Status" in st and "NY" in st)
    check("status shows total", ("I alt: %d kr" % exp_total) in st)

# --- unknown id -----------------------------------------------------------
send(s, " ");                  read_until(s, ["Vælg", "ORDRESYSTEM"])
send(s, "S");                  read_until(s, ["Ordrenr:"])
send(s, "99999999999\r"); bad = read_until(s, ["Tryk en tast", "Ukendt"], 12, 2.0)
check("unknown id -> 'Ukendt ordre'", "Ukendt" in bad)

# --- hidden admin area: *x6 -> masked password -> submenu -> list ----------
send(s, " "); read_until(s, ["Vælg"])              # back to main menu
# wrong password path
send(s, "******"); pw1 = read_until(s, ["Kodeord"], 12, 2.0)
check("'*' x6 opens password prompt", "Kodeord" in pw1)
send(s, "heltforkert\r"); wrong = read_until(s, ["Forkert", "Vælg"], 12, 2.0)
check("wrong password rejected", "Forkert" in wrong)
send(s, " "); read_until(s, ["Vælg"])              # ST_PAUSE -> main menu
# correct password path
if APW:
    send(s, "******"); read_until(s, ["Kodeord"], 12, 2.0)
    send(s, APW + "\r"); amenu = read_until(s, ["Tilbage", "Vælg"], 12, 2.0)
    check("correct password opens admin submenu",
          "Tilbage" in amenu and "Vis bestillinger" in amenu)
    send(s, "V"); lst = read_until(s, ["Tryk en tast"], 12, 2.0)
    check("admin list shows the order", bool(oid) and oid in lst, "id %r" % oid)
    send(s, " "); a2 = read_until(s, ["Tilbage", "Vælg"], 12, 2.0)
    check("list returns to admin submenu (still logged in)", "Tilbage" in a2)
    send(s, "T"); m2 = read_until(s, ["Vælg"], 12, 2.0)
    check("Tilbage logs out to main menu",
          "ORDRESYSTEM" in m2 and "Vis bestillinger" not in m2)
else:
    check("admin password present in INI", False, "no [Admin] Kodeord found")

s.close()

# --- persisted record (in the D: overlay, NOT the tracked tree) -----------
ordf = os.path.join(DOVL, "ORDRER.TXT")
if not os.path.exists(ordf):    # overlays store names as-is; be case-tolerant
    for root, _, files in os.walk(DOVL):
        for f in files:
            if f.lower() == "ordrer.txt": ordf = os.path.join(root, f)
check("ORDRER.TXT written to overlay (tree untouched)", os.path.exists(ordf))
if os.path.exists(ordf):
    rec = open(ordf, 'rb').read().decode('cp865').strip().split('\n')[0].strip()
    f = rec.split('|')
    check("record has 11 fields", len(f) == 11, "got %d" % len(f))
    if len(f) == 11:
        check("record id matches", f[0] == oid, "%r vs %r" % (f[0], oid))
        check("record status NY", f[1] == "NY")
        check("record navn round-trips (æøå)", f[6] == NAME, "%r vs %r" % (f[6], NAME))
        check("record adresse round-trips", f[7] == ADDR and f[8] == CITY,
              "%r/%r vs %r/%r" % (f[7], f[8], ADDR, CITY))
        check("record items 101*2;110*3", f[9] == "101*2;110*3", "got %r" % f[9])
        check("record total %d" % exp_total, f[10] == str(exp_total), "got %r" % f[10])
check("tracked VINDAASEN/ORDRER.TXT NOT created", not os.path.exists(os.path.join(VIND, "ORDRER.TXT")))

print()
if fails:
    print("RESULT: FAIL (%d) -- %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("RESULT: PASS")
sys.exit(0)
PY
then
    echo ">> TEST PASSED"
    exit 0
else
    echo ">> TEST FAILED (dosbox log tail:)" >&2
    tail -n 15 "$WORK/dosbox.log" 2>/dev/null >&2 || true
    exit 1
fi
