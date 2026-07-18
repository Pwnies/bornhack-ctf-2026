#!/usr/bin/env python3
# ===========================================================================
#  verify-vdlev-update.py - end-to-end test of the VDLEV remote self-update,
#  driven through BOTH services exactly as in production.
#
#      [ this script = admin terminal ]
#              | TCP BBS_PORT  (COM2 BBS line)
#              v
#      MAIN machine: VINDÅSEN.EXE  (headless dosbox-x, dummy video)
#              |  admin menu "O) Opdater" -> OPDATER + raw hex + EOT,
#              |  forwarded over COM3 (LINK.C direct-UART @0x3E8, 1200-8N1)
#              | TCP LINK_PORT  (main COM3 listener  <->  vdlev COM2 client)
#              v
#      VDLEV machine: VDLOVV.EXE + VDLEV.EXE  (headless dosbox-x)
#              VDLOVV decodes the hex -> stops VDLEV -> renames the scratch
#              over VDLEV.EXE -> relaunches it (LoadModule).
#
#  We push a *distinguishable* image: the freshly built VDLEV.EXE with its
#  window title "VinDaasen Leverance" byte-patched to "VinDaasen Leveran#7"
#  (same length, cosmetic).  After the push we check on the host that the
#  vdlev machine's D:\VDLEV.EXE is now byte-identical to that pushed image and
#  carries the marker, and that the VDLEVNEW.EXE scratch was renamed away.
#  That proves the whole chain: BBS admin -> COM3 forwarding -> receive +
#  hex-decode -> stop/swap on a mounted drive.
#
#  Neither tracked tree is modified: the main machine uses C:/D: dosbox
#  overlays; the vdlev machine's D: is a private scratch COPY of the two exes
#  (a real read-write mount, so the delete+rename swap actually runs).
#
#  Fully headless - no display, no Xvfb.  Requires: dosbox-x, python3, and a
#  built app tree (or pass --build to build both first in the WIN3.0 VM).
#
#  Usage:
#    ./verify-vdlev-update.py            test the current build
#    ./verify-vdlev-update.py --build    build VINDÅSEN + the VDLEV pair first
#
#  Env overrides:
#    BBS_PORT=2381   TCP port bridged to the main machine's COM2 (BBS)
#    LINK_PORT=2382  TCP port for the COM3<->COM2 fulfilment link
#    BOOT_WAIT=42    seconds to wait for both machines to boot + link
# ===========================================================================
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import shutil
import signal

REPO = os.path.dirname(os.path.abspath(__file__))
WIN101 = os.path.join(REPO, "WIN1.01")
WIN30 = os.path.join(REPO, "WIN3.0")
VIND = os.path.join(REPO, "VINDAASEN")
VDLEV = os.path.join(REPO, "VDLEV")

BBS_PORT = int(os.environ.get("BBS_PORT", "2381"))
LINK_PORT = int(os.environ.get("LINK_PORT", "2382"))
BOOT_WAIT = int(os.environ.get("BOOT_WAIT", "42"))

ADMIN_PW = "skiftmig"                       # [Admin] Kodeord in VINDÅSEN.INI
MARK_FROM = b"VinDaasen Leverance"          # VDLEV window title (unpatched)
MARK_TO = b"VinDaasen Leveran#7"            # same length, unique on-disk marker


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(2)


def headless_env():
    """Env for a no-display dosbox-x run (Windows 1.01 boots fine under the
    dummy SDL driver - no X/Wayland needed)."""
    env = dict(os.environ)
    for k in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY"):
        env.pop(k, None)
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"
    return env


def run_dosbox_blocking(cfg, logpath, timeout):
    """Run dosbox-x to completion (used for builds, which `exit` on their own)."""
    with open(logpath, "wb") as log:
        try:
            subprocess.run(
                ["dosbox-x", "-conf", cfg, "-nolog", "-nogui", "-nomenu"],
                stdout=log, stderr=subprocess.STDOUT, env=headless_env(),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            pass


def launch_dosbox(cfg, logpath):
    """Launch dosbox-x in the background; return the Popen so we can kill it.
    stdout/stderr go to a file so the child never holds this script's stdout
    open (a backgrounded emulator on our stdout would wedge the caller)."""
    log = open(logpath, "wb")
    return subprocess.Popen(
        ["dosbox-x", "-conf", cfg, "-nolog", "-nogui", "-nomenu"],
        stdout=log, stderr=subprocess.STDOUT, env=headless_env(),
    )


def find_main_exe():
    for name in os.listdir(VIND):
        # host filename is UTF-8 "VINDÅSEN.EXE"; match tolerantly
        if name.upper().startswith("VIND") and name.upper().endswith("SEN.EXE"):
            return os.path.join(VIND, name)
    return None


# --------------------------------------------------------------------------
#  Optional build (WIN3.0 VM): main app, then the VDLEV pair.
# --------------------------------------------------------------------------
def build(work):
    if not os.path.isdir(WIN30):
        die("--build needs WIN3.0/")
    print(">> building VINDÅSEN.EXE...")
    old = find_main_exe()
    if old:
        os.remove(old)
    cfg = os.path.join(work, "build-main.dosbox")
    with open(cfg, "w") as f:
        f.write("[cpu]\ncycles=max\n[sdl]\nautolock=false\n[autoexec]\n"
                'mount c "%s"\nmount d "%s"\nd:\ncd \\\ncall BUILD.BAT\nexit\n'
                % (WIN30, VIND))
    run_dosbox_blocking(cfg, os.path.join(work, "build-main.log"), 240)
    if not find_main_exe():
        die("build failed: no VINDÅSEN.EXE produced")

    print(">> building the VDLEV pair (VDLOVV.EXE + VDLEV.EXE)...")
    for p in (os.path.join(VDLEV, "VDLOVV.EXE"), os.path.join(VDLEV, "VDLEV.EXE")):
        if os.path.exists(p):
            os.remove(p)
    cfg = os.path.join(work, "build-vdlev.dosbox")
    with open(cfg, "w") as f:
        f.write("[cpu]\ncycles=max\n[sdl]\nautolock=false\n[autoexec]\n"
                'mount c "%s"\nmount e "%s"\ne:\ncd \\\ncall BUILD.BAT\nexit\n'
                % (WIN30, VDLEV))
    run_dosbox_blocking(cfg, os.path.join(work, "build-vdlev.log"), 240)
    if not (os.path.exists(os.path.join(VDLEV, "VDLOVV.EXE")) and
            os.path.exists(os.path.join(VDLEV, "VDLEV.EXE"))):
        die("build failed: VDLEV pair not produced")
    print(">> build OK")


# --------------------------------------------------------------------------
#  BBS line helpers (CP865 wire text).
# --------------------------------------------------------------------------
def dec(b):
    return b.decode("cp865", "replace")


def read_until(s, tokens, timeout=15.0):
    if isinstance(tokens, str):
        tokens = [tokens]
    end = time.time() + timeout
    buf = b""
    while time.time() < end:
        try:
            d = s.recv(4096)
            if not d:
                break
            buf += d
            if any(t in dec(buf) for t in tokens):
                return dec(buf)
        except socket.timeout:
            pass
    return dec(buf)


def main():
    do_build = "--build" in sys.argv[1:]

    if not shutil.which("dosbox-x"):
        die("dosbox-x not found on PATH")
    if not (os.path.isdir(WIN101) and os.path.isdir(VIND) and os.path.isdir(VDLEV)):
        die("run from the repo (WIN1.01/, VINDAASEN/, VDLEV/ expected)")

    work = tempfile.mkdtemp(prefix="vdlev-verify.")
    procs = []

    def cleanup():
        for p in procs:
            try:
                p.kill()
            except Exception:
                pass
        time.sleep(1)
        # belt-and-suspenders: any dosbox-x still holding our workdir in argv,
        # plus the zenity child dosbox-x may spawn that keeps the TCP port.
        # Scoped to this run's workdir - never a blanket dosbox-x kill.
        subprocess.run(["pkill", "-f", work], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-x", "zenity"], stderr=subprocess.DEVNULL)
        shutil.rmtree(work, ignore_errors=True)

    try:
        if do_build:
            build(work)

        main_exe = find_main_exe()
        if not main_exe:
            die("VINDAASEN/VINDÅSEN.EXE not found - build first (--build)")
        if not (os.path.exists(os.path.join(VDLEV, "VDLOVV.EXE")) and
                os.path.exists(os.path.join(VDLEV, "VDLEV.EXE"))):
            die("VDLEV/VDLOVV.EXE + VDLEV.EXE not found - build first (--build)")

        # ---- lay out the transient drives --------------------------------
        mcovl = os.path.join(work, "mcovl", "WINDOWS")   # main C: overlay
        mdovl = os.path.join(work, "mdovl")              # main D: overlay
        vcovl = os.path.join(work, "vcovl")              # vdlev C: overlay
        vddir = os.path.join(work, "vd")                 # vdlev D: scratch
        os.makedirs(mcovl)
        os.makedirs(mdovl)
        os.makedirs(vddir)

        # main C: overlay WIN.INI -> auto-run the ring-named app.  The ring is
        # the CP865 byte 0x8F on the DOS side; write it byte-level.
        base_ini = open(os.path.join(WIN101, "WINDOWS", "WIN.INI"), "rb").read()
        out = []
        for ln in base_ini.split(b"\r\n"):
            out.append(b"run=D:\\VIND\x8fSEN.EXE" if ln.lower().startswith(b"run=") else ln)
        open(os.path.join(mcovl, "WIN.INI"), "wb").write(b"\r\n".join(out))

        # vdlev C: overlay = the tracked WINOVL (auto-runs VDLOVV + VDLEV)
        shutil.copytree(os.path.join(VDLEV, "WINOVL"), vcovl)
        # vdlev D: scratch = the two exes as they ship (title "VinDaasen Leverance")
        shutil.copy(os.path.join(VDLEV, "VDLOVV.EXE"), os.path.join(vddir, "VDLOVV.EXE"))
        shutil.copy(os.path.join(VDLEV, "VDLEV.EXE"), os.path.join(vddir, "VDLEV.EXE"))

        # the image to push: fresh VDLEV.EXE with the marker patched in
        img = open(os.path.join(VDLEV, "VDLEV.EXE"), "rb").read()
        if MARK_FROM not in img:
            die("cannot find %r in VDLEV.EXE to patch a marker" % MARK_FROM)
        push = img.replace(MARK_FROM, MARK_TO)

        # ---- dosbox configs ----------------------------------------------
        main_cfg = os.path.join(work, "main.dosbox")
        with open(main_cfg, "w") as f:
            f.write(
                "[dosbox]\nmachine=ega\n[cpu]\ncycles=max\n[sdl]\nautolock=false\n"
                "[serial]\nserial1=dummy\n"
                "serial2=nullmodem port:%d transparent:1\n"
                "serial3=nullmodem port:%d transparent:1\n"
                "[autoexec]\nkeyb dk\n"
                'mount c "%s"\nmount c "%s" -t overlay\n'
                'mount d "%s"\nmount d "%s" -t overlay\n'
                "c:\nPATH C:\\WINDOWS;Z:\\;C:\\;\nver set 3 30\ncd \\WINDOWS\nwin\n"
                % (BBS_PORT, LINK_PORT, WIN101, os.path.join(work, "mcovl"),
                   VIND, mdovl)
            )
        vdlev_cfg = os.path.join(work, "vdlev.dosbox")
        with open(vdlev_cfg, "w") as f:
            f.write(
                "[dosbox]\nmachine=ega\nquit warning=false\n[cpu]\ncycles=max\n"
                "[sdl]\nautolock=false\n[serial]\nserial1=dummy\n"
                "serial2=nullmodem server:localhost port:%d transparent:1\n"
                "[autoexec]\nkeyb dk\n"
                'mount c "%s"\nmount c "%s" -t overlay\n'
                'mount d "%s"\n'
                "c:\nPATH C:\\WINDOWS;Z:\\;C:\\;\nver set 3 30\ncd \\WINDOWS\nwin\n"
                % (LINK_PORT, WIN101, vcovl, vddir)
            )

        # ---- boot both machines ------------------------------------------
        print(">> starting MAIN machine (BBS %d, COM3 link listener %d)..."
              % (BBS_PORT, LINK_PORT))
        procs.append(launch_dosbox(main_cfg, os.path.join(work, "main.log")))
        time.sleep(4)   # let the COM3 nullmodem listener bind before the client connects
        print(">> starting VDLEV machine (COM2 link client -> %d)..." % LINK_PORT)
        procs.append(launch_dosbox(vdlev_cfg, os.path.join(work, "vdlev.log")))

        print(">> waiting %ds for both machines to boot + link..." % BOOT_WAIT)
        time.sleep(BOOT_WAIT)

        fails = []

        def check(name, cond, detail=""):
            print(("  PASS " if cond else "  FAIL ") + name +
                  (("  -- " + detail) if (detail and not cond) else ""))
            if not cond:
                fails.append(name)

        # ---- drive the BBS admin firmware push ---------------------------
        s = socket.socket()
        s.settimeout(2.5)
        try:
            s.connect(("127.0.0.1", BBS_PORT))
        except Exception as e:
            check("BBS connect", False, str(e))
            raise SystemExit(1)

        greet = read_until(s, ["Vælg"], 12)
        if "ORDRESYSTEM" not in greet:            # nudge if we predated OpenComm
            s.sendall(b"\r")
            greet = read_until(s, ["Vælg"], 12)
        check("BBS greeting/menu", "ORDRESYSTEM" in greet)

        s.sendall(b"******")
        pw = read_until(s, ["Kodeord"], 10)
        check("'*' x6 opens admin password prompt", "Kodeord" in pw)

        s.sendall(ADMIN_PW.encode("cp865") + b"\r")
        amenu = read_until(s, ["Vælg", "Tilbage"], 10)
        check("admin password accepted -> submenu",
              "Opdater leverance-tjeneste" in amenu and "Tilbage" in amenu,
              "got %r" % amenu[-160:])

        s.sendall(b"O")
        prompt = read_until(s, ["EOT", "Ctrl-D"], 10)
        check("O) opens update prompt (OPDATER sent on COM3)",
              "hex" in prompt and "EOT" in prompt, "got %r" % prompt[-160:])

        print(">> streaming %d bytes as hex over BBS -> COM3 (1200 baud, ~60-90s)..."
              % len(push))
        n = 0
        for i in range(0, len(push), 16):
            s.sendall(push[i:i + 16].hex().upper().encode() + b"\r\n")
            n += 1
            if n % 8 == 0:
                time.sleep(0.05)     # gentle pacing; the fixed sender also self-throttles
        s.sendall(bytes([0x04]))     # Ctrl-D -> BBS frames a clean EOT on COM3
        print(">> %d hex lines + Ctrl-D sent" % n)

        # the fixed COM3 sender is synchronous, so "Opdatering sendt." only
        # appears once the whole image + EOT has gone out on the wire (~80s)
        sent = read_until(s, ["Opdatering sendt", "Tryk en tast"], 160)
        check("BBS confirms 'Opdatering sendt.'", "Opdatering sendt" in sent,
              "got %r" % sent[-160:])
        s.close()

        print(">> waiting for the swap + relaunch on the vdlev machine...")
        time.sleep(20)

        # ---- host-side: the swap replaced the on-disk image --------------
        cur = os.path.join(vddir, "VDLEV.EXE")
        new = os.path.join(vddir, "VDLEVNEW.EXE")
        check("vdlev D:\\VDLEV.EXE present", os.path.exists(cur))
        if os.path.exists(cur):
            disk = open(cur, "rb").read()
            check("swapped VDLEV.EXE == pushed image (byte-identical)", disk == push,
                  "sizes %d vs %d" % (len(disk), len(push)))
            check("swapped VDLEV.EXE carries marker %r" % MARK_TO.decode(),
                  MARK_TO in disk)
        check("scratch VDLEVNEW.EXE consumed (renamed away)", not os.path.exists(new))

        print()
        if fails:
            print("RESULT: FAIL (%d) -- %s" % (len(fails), ", ".join(fails)))
            # surface the emulator logs to help diagnose
            for tag in ("main", "vdlev"):
                p = os.path.join(work, tag + ".log")
                if os.path.exists(p):
                    tail = open(p, "rb").read()[-600:].decode("latin-1", "replace")
                    if tail.strip():
                        print("--- %s.log tail ---\n%s" % (tag, tail), file=sys.stderr)
            return 1
        print("RESULT: PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
