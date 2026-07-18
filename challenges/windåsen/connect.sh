#!/bin/sh
# Connect to the VINDAASEN BBS line (COM2 -> TCP, default 127.0.0.1:2323) with
# on-the-fly CP865<->UTF-8 conversion and char-at-a-time I/O.
#
# Usage: ./connect.sh [host] [port]
#
# Why not `iconv | nc | iconv`?  iconv block-buffers in a pipe (stdbuf does not
# override it), so keystrokes never reach the app.  This Python bridge converts
# in-process and flushes every byte, and puts the tty in cbreak mode (no local
# echo -- the BBS echoes; Ctrl-C still quits).
#
# NB: the script is passed via -c, NOT a heredoc on stdin -- with `python3 -`
# the heredoc *becomes* stdin, leaving the program unable to read the terminal.
exec python3 -c "$(cat <<'PY'
import sys, os, socket, select, codecs

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.create_connection((host, port))
sock.setblocking(False)

fd = sys.stdin.fileno()
istty = os.isatty(fd)
if istty:
    import termios, tty
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)                       # char-at-a-time, no echo, Ctrl-C works

dec = codecs.getincrementaldecoder("utf-8")()   # terminal UTF-8 -> unicode
try:
    while True:
        r, _, _ = select.select([fd, sock], [], [])
        if fd in r:                          # keystrokes -> CP865 -> line
            b = os.read(fd, 4096)
            if not b:
                break
            sock.sendall(dec.decode(b).encode("cp865", "replace"))
        if sock in r:                        # line CP865 -> UTF-8 -> terminal
            try:
                b = sock.recv(4096)
            except BlockingIOError:
                continue
            if not b:
                break
            os.write(1, b.decode("cp865").encode("utf-8"))
except (KeyboardInterrupt, OSError):
    pass
finally:
    if istty:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sock.close()
PY
)" "${1:-127.0.0.1}" "${2:-2323}"
