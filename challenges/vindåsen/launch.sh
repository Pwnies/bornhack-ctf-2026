#!/bin/bash
# Launch both dosbox-x instances headlessly.
# VINDAASEN (main app) starts first because it owns the TCP listener on port 2324.
# VDLEV (fulfilment pair) starts 5 s later and connects to that listener.
# Port 2323 (COM2/BBS) is exposed to the outside world.

set -e

BASE=/challenge
DOSBOX=dosbox-x
export HOME=/tmp
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy

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
# COM2 = BBS ordering line, exposed as TCP 2323
serial2=nullmodem port:2323 transparent:1 nonlocal:1
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

cleanup() {
    [ -n "$VINDAASEN_PID" ] && kill "$VINDAASEN_PID" 2>/dev/null || true
    [ -n "$VDLEV_PID" ]     && kill "$VDLEV_PID"     2>/dev/null || true
    pkill -x zenity 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# VINDAASEN first — it owns the TCP server on 2324 that VDLEV connects to
$DOSBOX -conf /tmp/vindaasen.dosbox -nolog -nogui -nomenu &
VINDAASEN_PID=$!

# Wait for VINDAASEN's COM3 TCP listener to bind before VDLEV tries to connect
sleep 5

# VDLEV second — connects as client to VINDAASEN's COM3 on 2324
$DOSBOX -conf /tmp/vdlev.dosbox -nolog -nogui -nomenu &
VDLEV_PID=$!

wait "$VINDAASEN_PID" "$VDLEV_PID"
