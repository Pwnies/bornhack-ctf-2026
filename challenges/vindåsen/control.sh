#!/bin/sh
# Per-connection handler for the control channel (port 1986).
# socat runs this script once per TCP connection.
# Reads one command from stdin (LF, CRLF, or EOF-terminated), then signals the main script.
IFS= read -r CMD || true
CMD="${CMD%"$(printf '\r')"}"
MAIN=$(cat /tmp/main.pid 2>/dev/null) || exit 1
case "$CMD" in
    "FACTORY RESET") kill -TERM "$MAIN" ;;
    "REBOOT VD")     kill -USR1 "$MAIN" ;;
    "REBOOT LEV")    kill -USR2 "$MAIN" ;;
esac
