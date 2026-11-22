#!/usr/bin/env bash
# End-to-end test of « Madalean Server » (host mode of the desktop shell, DECISIONS D50) inside an ISOLATED headless
# compositor (kwin_wayland --virtual, own D-Bus session, temporary HOME, rootful Xwayland for screenshots), like e2e.sh:
# nothing appears on the user's screen and no input is injected (actions run through a test hook).
#
#   shells/desktop/tests/host_e2e.sh [binary]          scenarios with a demo server and a FAKE systemctl/journalctl
#   shells/desktop/tests/host_e2e.sh --live [binary]   read-only look at the REAL local Madalean (127.0.0.1:11500) and
#                                                      the real user service (systemctl --user show only): screenshots
#
# Default scenarios (fake systemctl in PATH, state in a file; `start` launches `bin/madalean serve --demo` on free
# ports, `stop` kills it): service inactive → panel « Arrêté »; start → web UI opens by itself; stop → panel; start
# again → web UI; « Ouvrir les journaux » → panel with logs; service not installed → panel with the fix; a second
# launch focuses the first window (single instance). The real `madalean` service is never touched.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LIVE=0
if [ "${1:-}" = "--live" ]; then LIVE=1; shift; fi
BIN="${1:-$ROOT/shells/desktop/src-tauri/target/release/madalean}"
[ -x "$BIN" ] || { echo "no binary: $BIN (cargo build --release in shells/desktop/src-tauri)" >&2; exit 2; }
BIN="$(realpath "$BIN")"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
WORK="$(mktemp -d "${TMPDIR:-/tmp}/madalean-host-e2e.XXXXXX")"
OUT="${E2E_OUT:-$WORK/out}"; mkdir -p "$OUT" "$WORK/run" "$WORK/home" "$WORK/fakebin"; chmod 700 "$WORK/run"
free_port() { "$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }
LP=$(free_port); RP=$(free_port)
# The app runs under its program name (the installed file is called madalean-server): copy, do not rename the build.
cp "$BIN" "$WORK/madalean-server"
export MADALEAN_E2E_WORK="$WORK" MADALEAN_E2E_OUT="$OUT" MADALEAN_E2E_LP=$LP MADALEAN_E2E_RP=$RP MADALEAN_E2E_ROOT="$ROOT" \
       MADALEAN_E2E_LIVE=$LIVE MADALEAN_E2E_REAL_RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# Fake systemctl / journalctl (default mode only): `show` reads $WORK/svc.state (active | inactive | notfound).
cat > "$WORK/fakebin/systemctl" <<'EOF'
#!/usr/bin/env bash
W="$MADALEAN_E2E_WORK"; echo "$*" >> "$W/systemctl.log"
[ "$1" = --user ] || { echo "only --user" >&2; exit 1; }
st=$(cat "$W/svc.state" 2>/dev/null || echo inactive)
start() {
  "$MADALEAN_E2E_ROOT/bin/madalean" serve --demo --no-migrate --port "$MADALEAN_E2E_LP" --remote-port "$MADALEAN_E2E_RP" \
    --config-dir "$W/srv-config" --cache-dir "$W/srv-cache" >> "$W/server.log" 2>&1 &
  echo $! > "$W/server.pid"; echo active > "$W/svc.state"; }
stop() { [ -f "$W/server.pid" ] && kill "$(cat "$W/server.pid")" 2>/dev/null; rm -f "$W/server.pid"; sleep 0.5; echo inactive > "$W/svc.state"; }
case "$2" in
  show) case "$st" in
          notfound) printf 'LoadState=not-found\nActiveState=inactive\nSubState=dead\nUnitFileState=\n' ;;
          *) printf 'LoadState=loaded\nActiveState=%s\nSubState=%s\nUnitFileState=enabled\n' "$st" "$([ "$st" = active ] && echo running || echo dead)" ;;
        esac ;;
  start) [ "$st" = notfound ] && { echo "Unit $3 not found." >&2; exit 5; }; [ "$st" = active ] || start ;;
  stop) stop ;;
  restart) stop; start ;;
  *) echo "unexpected: $*" >&2; exit 1 ;;
esac
EOF
cat > "$WORK/fakebin/journalctl" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$MADALEAN_E2E_WORK/journalctl.log"
tail -n 40 "$MADALEAN_E2E_WORK/server.log" 2>/dev/null | sed 's/^/2026-11-22T12:00:00+0300 host madalean[1]: /'
EOF
printf '#!/bin/sh\necho "$@" >> "%s/opened.txt"\n' "$WORK" > "$WORK/fakebin/xdg-open"
chmod +x "$WORK/fakebin/"*
trap '[ -f "$WORK/server.pid" ] && kill "$(cat "$WORK/server.pid")" 2>/dev/null' EXIT

cat > "$WORK/inner.sh" <<'INNER'
#!/usr/bin/env bash
set -u
W="$MADALEAN_E2E_WORK"; OUT="$MADALEAN_E2E_OUT"; APP="$W/madalean-server"
export HOME="$W/home" XDG_CONFIG_HOME="$W/home/.config" XDG_DATA_HOME="$W/home/.local/share" XDG_CACHE_HOME="$W/home/.cache"
export NO_AT_BRIDGE=1 MADALEAN_SHELL_TEST_LOG="$W/shell.log"
Xwayland :58 -geometry 1280x860 -noreset > "$W/xwayland.log" 2>&1 & XW=$!
sleep 1.5
export DISPLAY=:58 GDK_BACKEND=x11 WEBKIT_DISABLE_DMABUF_RENDERER=1
shot() { ffmpeg -loglevel error -y -f x11grab -video_size 1280x860 -i "$DISPLAY" -frames:v 1 "$OUT/$1.png" 2>>"$W/shots.err"; }
mark() { echo "=== $*" >> "$W/steps.txt"; }
if [ "$MADALEAN_E2E_LIVE" = 1 ]; then
  # Real user manager for `systemctl --user show` (read-only); the window itself uses the private X server.
  export XDG_RUNTIME_DIR="$MADALEAN_E2E_REAL_RUNTIME"
  export PATH="$W/fakebin-live:$PATH"
  mark "live: web UI"
  "$APP" & A=$!; sleep 10; shot live-1-web-ui
  mark "live: server panel (menu « Panneau du serveur » through the test hook)"
  kill $A; wait $A 2>/dev/null
  MADALEAN_HOST_TEST_ACTIONS="panel@8,logs@10" "$APP" & A=$!; sleep 20; shot live-2-panel-logs
  kill $A; wait $A 2>/dev/null
  kill $XW; exit 0
fi
export PATH="$W/fakebin:$PATH" MADALEAN_HOST_NO_TRAY=1     # the tray is exercised by --live only
LP=$MADALEAN_E2E_LP
echo inactive > "$W/svc.state"
mark "S1 stopped → panel; start → web UI; stop → panel; start → web UI; logs"
MADALEAN_HOST_TEST_ACTIONS="start@6,stop@26,start@34,logs@54,panel@58" "$APP" --port "$LP" & A=$!
sleep 4; shot S1-a-stopped
sleep 4; shot S1-b-starting
sleep 16; shot S1-c-running-web-ui
sleep 6; shot S1-d-stopped-again
sleep 18; shot S1-e-running-again
sleep 7; shot S1-f-logs
mark "S2 single instance: a second launch exits and focuses the first"
"$APP" --port "$LP" & B=$!; sleep 4
kill -0 $B 2>/dev/null && echo "second instance still running" >> "$W/steps.txt" || echo "second instance exited" >> "$W/steps.txt"
kill $A; wait $A 2>/dev/null; kill $B 2>/dev/null
[ -f "$W/server.pid" ] && kill "$(cat "$W/server.pid")" 2>/dev/null; rm -f "$W/server.pid"
mark "S3 service not installed"
echo notfound > "$W/svc.state"
"$APP" --port "$LP" & A=$!; sleep 6; shot S3-not-installed; kill $A; wait $A 2>/dev/null
mark "S4 English, no systemctl at all"
printf '{"lang":"en"}' > "$XDG_DATA_HOME/mg.madalean.server/settings.json"
mkdir -p "$W/nosys"; for c in xdg-open; do ln -sf "$W/fakebin/$c" "$W/nosys/$c"; done
PATH="$W/nosys" "$APP" --port "$LP" & A=$!; sleep 6; shot S4-no-systemd-en; kill $A; wait $A 2>/dev/null
ls -la "$XDG_DATA_HOME" > "$W/datadirs.txt"
kill $XW 2>/dev/null
INNER
chmod +x "$WORK/inner.sh"
# Live mode: an empty xdg-open stub only (systemctl / journalctl are the real ones, used read-only).
mkdir -p "$WORK/fakebin-live"; cp "$WORK/fakebin/xdg-open" "$WORK/fakebin-live/"

HOME="$WORK/home" XDG_CONFIG_HOME="$WORK/home/.config" XDG_DATA_HOME="$WORK/home/.local/share" \
XDG_CACHE_HOME="$WORK/home/.cache" XDG_RUNTIME_DIR="$WORK/run" setsid dbus-run-session -- kwin_wayland --virtual --no-lockscreen \
  --width 1280 --height 860 --socket "madalean-host-e2e-$$" --exit-with-session "$WORK/inner.sh" > "$WORK/kwin.log" 2>&1
for p in $(pgrep -f "xdg-desktop-portal|ksecretd|kwalletd|at-spi" || true); do
  tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -qx "HOME=$WORK/home" && kill "$p" 2>/dev/null
done
echo "work dir: $WORK"
echo "screenshots: $OUT"
[ "$LIVE" = 1 ] && { grep -h '"kind":"host_state"\|"kind":"open"\|"kind":"host_tray"' "$WORK/shell.log" | head; exit 0; }
"$PY" - "$WORK" <<'PYEOF'
import json, sys, pathlib
w = pathlib.Path(sys.argv[1])
log = [json.loads(l) for l in (w / "shell.log").read_text().splitlines()] if (w / "shell.log").exists() else []
sysctl = (w / "systemctl.log").read_text().splitlines() if (w / "systemctl.log").exists() else []
steps = (w / "steps.txt").read_text() if (w / "steps.txt").exists() else ""
def ev(k, pred=lambda x: True): return [l for l in log if l["kind"] == k and pred(l["extra"])]
phases = [e["extra"]["phase"] for e in ev("host_state")]
opens = ev("open", lambda x: x.get("local") is True)
checks = {
    "start in host mode": bool(ev("start", lambda x: x.get("host_mode") is True)),
    "stopped service seen first": phases[:1] == ["stopped"],
    "start → starting → running": "starting" in phases and "running" in phases
        and phases.index("starting") < phases.index("running"),
    "web UI opened by itself after start (twice: start, start again)": len(opens) >= 2,
    "stop → panel": bool(ev("connect_screen", lambda x: x.get("reason") == "stopped")),
    "systemctl used with --user and the unit only": all(l.split()[0] == "--user" and
        (l.split()[1] == "show" or l.split()[1:] in (["start", "madalean.service"], ["stop", "madalean.service"],
                                                     ["restart", "madalean.service"])) for l in sysctl),
    "start and stop really run": any(l.startswith("--user start ") for l in sysctl) and any(l.startswith("--user stop ") for l in sysctl),
    "logs read with journalctl --user -u": "--user -u madalean.service" in ((w / "journalctl.log").read_text() if (w / "journalctl.log").exists() else ""),
    "not installed detected": "not_installed" in phases,
    "no systemd detected": "no_systemd" in phases,
    "single instance (second launch exited)": "second instance exited" in steps,
    "own data dir mg.madalean.server": "mg.madalean.server" in ((w / "datadirs.txt").read_text() if (w / "datadirs.txt").exists() else ""),
}
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
print("phases:", " → ".join(phases))
sys.exit(0 if all(checks.values()) else 1)
PYEOF
