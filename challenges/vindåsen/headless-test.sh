#!/bin/sh
# headless-test.sh - boot Windows 1.01 with no visible window (under Xvfb),
# auto-run VINDÅSEN.EXE, then verify the BBS greeting over the COM2 TCP line
# and grab a screenshot of the GUI.
#
# Usage: ./headless-test.sh [port] [boot_wait_seconds] [screenshot_path]
#   port            TCP port to bridge to COM2   (default 2324)
#   boot_wait       seconds to let Win 1.01 boot (default 40)
#   screenshot_path PNG to write                 (default ./htest-screenshot.png)
#
# The app must already be built (run BUILD.BAT in the WIN3.0 VM first).
# Requires: dosbox-x, Xvfb, xwd/xwdtopnm/pnmtopng (or ImageMagick 'import'),
# fuser, python3.  Uses its own throwaway port so it won't clash with an
# interactive session on 2323.

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-2324}"
WAIT="${2:-40}"
SHOT="${3:-$ROOT/htest-screenshot.png}"
XDISP=":99"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/vindaasen-htest.XXXXXX")"
CDRIVE="$SCRATCH/C"
CONF="$SCRATCH/htest.dosbox"
DPID=""; XPID=""

cleanup() {
    # Graceful quit. The config sets `quit warning=false`, so dosbox-x exits
    # without popping its "Quit DOSBox-X warning" confirmation dialog (which
    # would otherwise leave it lingering and holding the port on SIGTERM).
    [ -n "$DPID" ] && kill "$DPID" 2>/dev/null
    fuser -k -9 "${PORT}/tcp" 2>/dev/null      # hard backstop: guarantee the port is freed
    [ -n "$XPID" ] && kill "$XPID" 2>/dev/null
    rm -f "/tmp/.X${XDISP#:}-lock" 2>/dev/null
    rm -rf "$SCRATCH"
}
trap cleanup EXIT INT TERM

# 1) scratchpad copy of the C: drive, with the app set to auto-run on Windows
#    start (Win 1.x mechanism; the tracked WIN.INI is never touched).
cp -a "$ROOT/WIN1.01" "$CDRIVE" || exit 3
python3 - "$CDRIVE/WINDOWS/WIN.INI" <<'PY'
import sys
p = sys.argv[1]
d = open(p, "rb").read()
d = d.replace(b"run=\r\n", b"run=D:\\VIND\x8fSEN.EXE\r\n", 1)
open(p, "wb").write(d)
PY

cat > "$CONF" <<CONF
[dosbox]
machine=ega
quit warning=false
[cpu]
cycles=max
[sdl]
autolock=false
[serial]
serial1=dummy
serial2=nullmodem port:$PORT transparent:1
[autoexec]
mount c "$CDRIVE"
mount d "$ROOT/VINDAASEN"
c:
ver set 3 30
cd \WINDOWS
win
CONF

# 2) virtual framebuffer (no visible window) + dosbox-x rendering onto it
rm -f "/tmp/.X${XDISP#:}-lock"
Xvfb "$XDISP" -screen 0 1024x768x24 -ac >/dev/null 2>&1 &
XPID=$!
sleep 1
DISPLAY="$XDISP" dosbox-x -conf "$CONF" -nolog -nomenu >"$SCRATCH/dosbox.log" 2>&1 &
DPID=$!

echo "Booting Windows 1.01 headlessly on port $PORT (waiting ${WAIT}s)..."
sleep "$WAIT"

# 3) screenshot of the GUI
if xwd -root -display "$XDISP" -silent 2>/dev/null | xwdtopnm 2>/dev/null | pnmtopng >"$SHOT" 2>/dev/null && [ -s "$SHOT" ]; then
    echo "Screenshot: $SHOT"
elif import -window root -display "$XDISP" "$SHOT" 2>/dev/null; then
    echo "Screenshot: $SHOT"
else
    echo "Screenshot: (failed)"
fi

# 4) COM2 verification: connect once, send a byte, read the greeting.
#    (With transparent:1 there is no carrier, so the app greets on first byte;
#    do not spray bytes during boot - those sent before OpenComm are lost.)
python3 - "$PORT" <<'PY'
import socket, sys
port = int(sys.argv[1])
try:
    s = socket.create_connection(("127.0.0.1", port), timeout=4)
except OSError as e:
    print("COM: connect failed:", e); sys.exit(2)
s.settimeout(4)
s.sendall(b"H\r")
data = b""
try:
    while len(data) < 512:
        c = s.recv(256)
        if not c:
            break
        data += c
except socket.timeout:
    pass
s.close()
if not data:
    print("COM: no response (try a longer boot wait)"); sys.exit(1)
print("COM OK:", len(data), "bytes")
print("  hex   :", data[:96].hex())
print("  cp865 :", repr(data.decode("cp865", "replace")))
PY
exit $?
