#!/usr/bin/env python3
# "Modem" front-end for the VINDAASEN BBS ordering line.
#
# The public port is owned by this broker, NOT by DOSBox-X directly.  DOSBox-X's
# COM2 nullmodem now listens on loopback only; the broker fronts it and speaks
# Hayes-style result codes for the two failure paths:
#
#   * DOSBox-X not listening (down / mid-REBOOT VD) -> "NO CARRIER"
#   * a session already in progress                 -> "BUSY"
#
# Any accepted session is a raw byte bridge (transparent), so the binary
# ordering protocol and the flag-1 exploit are unaffected.
import socket, threading

LISTEN = ("0.0.0.0", 2323)          # public BBS line (mapped out by compose)
DOSBOX = ("127.0.0.1", 12323)       # DOSBox-X COM2 nullmodem, loopback only
busy = threading.Lock()             # single caller at a time


def pump(src, dst):
    try:
        while (b := src.recv(4096)):
            dst.sendall(b)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle(client):
    if not busy.acquire(blocking=False):        # someone's already on the line
        try:
            client.sendall(b"BUSY\r\n")
        finally:
            client.close()
        return
    try:
        try:
            dos = socket.create_connection(DOSBOX, timeout=3)
        except OSError:                          # DOSBox-X not listening
            client.sendall(b"NO CARRIER\r\n")
            return
        with dos:
            t = threading.Thread(target=pump, args=(client, dos), daemon=True)
            t.start()
            pump(dos, client)                   # returns when DOSBox hangs up
            try:
                client.sendall(b"\r\nNO CARRIER\r\n")
            except OSError:
                pass
    finally:
        try:
            client.close()
        except OSError:
            pass
        busy.release()


def main():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(LISTEN)
    srv.listen(8)
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
