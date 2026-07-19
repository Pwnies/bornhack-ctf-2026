#!/bin/bash
# Launch both dosbox-x instances headlessly.
# VINDAASEN (main app) starts first because it owns the TCP listener on port 2324.
# VDLEV (fulfilment pair) starts 5 s later and connects to that listener.
# Port 2323 (COM2/BBS) is fronted by broker.py, which speaks Hayes-style result
# codes: "BUSY" when a caller is already connected, "NO CARRIER" when the
# VINDAASEN dosbox-x isn't listening (down / mid-REBOOT VD). DOSBox's COM2 itself
# now listens on loopback 12323; only the broker is exposed to the outside world.
# Port 1986 (control channel) accepts FACTORY RESET / REBOOT VD / REBOOT LEV commands.

BASE=/challenge
DOSBOX=dosbox-x
export HOME=/tmp
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy

VINDAASEN_PID=
VDLEV_PID=
SOCAT_PID=
BROKER_PID=

# ------------------------------------------------------------------ configs ---

cat > /tmp/vindaasen.dosbox << 'DBEOF'
[dosbox]
machine=ega

[sdl]
autolock=false

[cpu]
cycles=max

[serial]
serial1=serialmouse
# COM2 = BBS ordering line, loopback only; broker.py fronts it on TCP 2323
serial2=nullmodem port:12323 transparent:1
# COM3 = fulfilment link, TCP listener on 2324 (vdlev connects here)
serial3=nullmodem port:2324 transparent:1 nonlocal:1

[autoexec]
keyb dk
mount c /challenge/WIN1.01
mount c /challenge/VINDAASEN/WINOVL -t overlay
mount d /challenge/VINDAASEN
c:
PATH C:\WINDOWS;Z:\;C:\;
ver set 3 30
cd \WINDOWS
win
DBEOF

cat > /tmp/vdlev.dosbox << 'DBEOF'
[dosbox]
machine=ega

[sdl]
autolock=false

[cpu]
cycles=max

[serial]
serial1=serialmouse
# COM2 = fulfilment link, connects as TCP client to VINDAASEN's COM3 listener
serial2=nullmodem server:localhost port:2324 transparent:1

[autoexec]
keyb dk
mount c /challenge/WIN1.01
mount c /challenge/VDLEV/WINOVL -t overlay
mount d /challenge/VDLEV
c:
PATH C:\WINDOWS;Z:\;C:\;
ver set 3 30
cd \WINDOWS
win
DBEOF

# --------------------------------------------------------------- processes ---

echo $$ > /tmp/main.pid

cleanup() {
    [ -n "$VINDAASEN_PID" ] && kill "$VINDAASEN_PID" 2>/dev/null || true
    [ -n "$VDLEV_PID" ]     && kill "$VDLEV_PID"     2>/dev/null || true
    [ -n "$SOCAT_PID" ]     && kill "$SOCAT_PID"      2>/dev/null || true
    [ -n "$BROKER_PID" ]    && kill "$BROKER_PID"     2>/dev/null || true
    pkill -x zenity 2>/dev/null || true
}

start_vindaasen() {
    [ -n "$VINDAASEN_PID" ] && kill -9 "$VINDAASEN_PID" 2>/dev/null || true
    sleep 1
    $DOSBOX -conf /tmp/vindaasen.dosbox -nolog -nogui -nomenu &
    VINDAASEN_PID=$!
}

start_vdlev() {
    [ -n "$VDLEV_PID" ] && kill -9 "$VDLEV_PID" 2>/dev/null || true
    sleep 1
    $DOSBOX -conf /tmp/vdlev.dosbox -nolog -nogui -nomenu &
    VDLEV_PID=$!
}

trap start_vindaasen USR1
trap start_vdlev     USR2
trap 'cleanup; exit 0' TERM INT
trap cleanup EXIT

# VINDAASEN first — it owns the TCP server on 2324 that VDLEV connects to
$DOSBOX -conf /tmp/vindaasen.dosbox -nolog -nogui -nomenu &
VINDAASEN_PID=$!

# Wait for VINDAASEN's COM3 TCP listener to bind before VDLEV tries to connect
sleep 5

# VDLEV second — connects as client to VINDAASEN's COM3 on 2324
$DOSBOX -conf /tmp/vdlev.dosbox -nolog -nogui -nomenu &
VDLEV_PID=$!

# Control channel — one connection at a time (fork), persistent listener
socat TCP-LISTEN:1986,fork,reuseaddr EXEC:/challenge/control.sh &
SOCAT_PID=$!

# BBS "modem" — fronts the public port 2323 and brokers a single session to
# VINDAASEN's loopback COM2 (12323); answers BUSY / NO CARRIER otherwise.
# Independent of VINDAASEN reboots: while VD is down it just answers NO CARRIER.
python3 /challenge/broker.py &
BROKER_PID=$!

# Main loop: wait for any child; signals interrupt wait and run their handlers,
# then we loop back and wait again (covering any newly-started PID).
while true; do wait; done
