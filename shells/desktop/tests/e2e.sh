#!/usr/bin/env bash
# End-to-end test of the desktop shell inside an ISOLATED headless compositor (kwin_wayland --virtual in its own D-Bus
# session, temporary HOME, rootful Xwayland for screenshots): nothing appears on the user's screen, no key is injected
# anywhere, the user's keyring / AppImageLauncher / browser are not used.
#
#   shells/desktop/tests/e2e.sh [--server mock|real] [path/to/Madalean.AppImage | path/to/binary]
#
#   mock (default): shells/dev/mock_server.py (contract reference, with test helpers).
#   real:           bin/madalean serve --demo on free ports with a temporary --config-dir; the pairing code comes from
#                   the local listener's POST /api/pairing/start, revocation is DELETE /api/devices/{id}.
#
# Scenarios: pairing by deep link (auto-submitted, test hook) → ticket → HttpOnly cookie → web UI (+ WebSocket); restart
# → automatic reconnection with the stored token; wrong code; single instance + deep link forwarded to the running
# instance; revocation → pairing screen; unreachable server; host mode (local listener, no pairing). Mock mode adds
# download + external link (they need the mock's test page). Screenshots in $OUT.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SERVER=mock
if [ "${1:-}" = "--server" ]; then SERVER="$2"; shift 2; fi
case "$SERVER" in mock|real) ;; *) echo "--server mock|real" >&2; exit 2 ;; esac
BIN="${1:-$(ls -t "$ROOT"/shells/desktop/dist/Madalean-*-x86_64.AppImage 2>/dev/null | head -1)}"
[ -x "$BIN" ] || { echo "no binary/AppImage: $BIN" >&2; exit 2; }
BIN="$(realpath "$BIN")"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
WORK="$(mktemp -d "${TMPDIR:-/tmp}/madalean-e2e.XXXXXX")"
OUT="${E2E_OUT:-$WORK/out}"; mkdir -p "$OUT"
free_port() { "$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }
LP=$(free_port); RP=$(free_port)
export MADALEAN_E2E_WORK="$WORK" MADALEAN_E2E_BIN="$BIN" MADALEAN_E2E_OUT="$OUT" MADALEAN_E2E_LP=$LP MADALEAN_E2E_RP=$RP \
       MADALEAN_E2E_SERVER=$SERVER

if [ "$SERVER" = mock ]; then
  "$PY" "$ROOT/shells/dev/mock_server.py" --local-port $LP --remote-port $RP > "$WORK/server.log" 2>&1 &
else
  "$ROOT/bin/madalean" serve --demo --no-migrate --port $LP --remote-port $RP \
    --config-dir "$WORK/srv-config" --cache-dir "$WORK/srv-cache" > "$WORK/server.log" 2>&1 &
fi
SRV=$!
mkdir -p "$WORK/run"; chmod 700 "$WORK/run"
trap 'kill $SRV 2>/dev/null' EXIT
for _ in $(seq 120); do curl -fs "http://127.0.0.1:$RP/api/hello" >/dev/null && break; sleep 0.25; done
curl -fs "http://127.0.0.1:$RP/api/hello" >/dev/null || { echo "server did not start:"; tail -20 "$WORK/server.log"; exit 1; }

cat > "$WORK/inner.sh" <<'INNER'
#!/usr/bin/env bash
# Runs inside the private kwin_wayland session.
set -u
W="$MADALEAN_E2E_WORK"; OUT="$MADALEAN_E2E_OUT"; BIN="$MADALEAN_E2E_BIN"; MODE="$MADALEAN_E2E_SERVER"
export HOME="$W/home" XDG_CONFIG_HOME="$W/home/.config" XDG_DATA_HOME="$W/home/.local/share" XDG_CACHE_HOME="$W/home/.cache"
mkdir -p "$HOME/Downloads" "$W/fakebin"
export XDG_DOWNLOAD_DIR="$HOME/Downloads"
# Fake system opener: records what the shell sends to the browser / file manager.
printf '#!/bin/sh\necho "$@" >> "%s/opened.txt"\n' "$W" > "$W/fakebin/xdg-open"; chmod +x "$W/fakebin/xdg-open"
export PATH="$W/fakebin:$PATH"
export APPIMAGELAUNCHER_DISABLE=1 MADALEAN_TOKEN_STORE=file MADALEAN_SHELL_TEST_LOG="$W/shell.log"
export MADALEAN_UPDATE_CHANNEL="http://127.0.0.1:9/none.json" MADALEAN_UPDATE_DELAY_SECS=3600   # no update traffic here
[ "$MODE" = real ] && export MADALEAN_SHELL_TEST_PROBE=1
# Rootful Xwayland inside the private compositor: its root window can be captured (ffmpeg x11grab).
Xwayland :57 -geometry 1280x860 -noreset > "$W/xwayland.log" 2>&1 & XW=$!
sleep 1.5
export DISPLAY=:57 GDK_BACKEND=x11 WEBKIT_DISABLE_DMABUF_RENDERER=1 NO_AT_BRIDGE=1
export MADALEAN_LOCAL_URL="http://127.0.0.1:9"   # no local server: remote scenarios first
LP=$MADALEAN_E2E_LP; RP=$MADALEAN_E2E_RP
shot() { ffmpeg -loglevel error -y -f x11grab -video_size 1280x860 -i "$DISPLAY" -frames:v 1 "$OUT/$1.png" 2>>"$W/shots.err"; }
mark() { echo "=== $*" | tee -a "$W/steps.txt"; date +%s%3N >> "$W/steps.txt"; }
new_code() {  # prints a fresh valid pairing code
  if [ "$MODE" = mock ]; then curl -fs -X POST "http://127.0.0.1:$LP/mock/new_code" -d '{"code":"123456"}' >/dev/null; echo 123456
  else curl -fs -X POST "http://127.0.0.1:$LP/api/pairing/start" | python3 -c 'import json,sys; print(json.load(sys.stdin)["code"])'; fi
}
revoke_all() {
  if [ "$MODE" = mock ]; then curl -fs -X POST "http://127.0.0.1:$LP/mock/revoke_all" >/dev/null
  else
    for id in $(curl -fs "http://127.0.0.1:$LP/api/devices" | python3 -c 'import json,sys; print(" ".join(d["id"] for d in json.load(sys.stdin)["devices"]))'); do
      curl -fs -X DELETE "http://127.0.0.1:$LP/api/devices/$id" >/dev/null && echo "revoked $id" >> "$W/steps.txt"
    done
  fi
}
devices() { [ "$MODE" = real ] && curl -fs "http://127.0.0.1:$LP/api/devices" > "$W/devices-$1.json"; }

mark "A pair via deep link"
T0=$(date +%s%3N)
CODE=$(new_code)
CLICK=""; [ "$MODE" = mock ] && CLICK="dl,ext,ext2"
MADALEAN_SHELL_TEST_AUTOSUBMIT=1 MADALEAN_SHELL_TEST_CLICK=$CLICK "$BIN" "madalean://pair?host=127.0.0.1:$RP&code=$CODE" &
APP=$!
sleep 4; shot A-remote-page; sleep 7; shot A-after; devices A
mark "F single instance: second launch forwards a deep link"
"$BIN" "madalean://pair?host=127.0.0.1:$RP&code=999999" & SECOND=$!
sleep 4; shot F-link-forwarded
kill -0 $SECOND 2>/dev/null && echo "second instance still running" >> "$W/steps.txt" || echo "second instance exited" >> "$W/steps.txt"
kill $APP; wait $APP 2>/dev/null
stat -c '%a %n' "$XDG_DATA_HOME"/mg.madalean.desktop/*.json "$XDG_DATA_HOME"/mg.madalean.desktop > "$W/perms.txt" 2>&1

mark "B restart: automatic reconnection"
"$BIN" & APP=$!; sleep 9; shot B-reconnected; devices B; kill $APP; wait $APP 2>/dev/null

mark "D wrong code"
new_code >/dev/null
MADALEAN_SHELL_TEST_AUTOSUBMIT=1 "$BIN" "madalean://pair?host=127.0.0.1:$RP&code=000000" & APP=$!
sleep 6; shot D-wrong-code; kill $APP; wait $APP 2>/dev/null

mark "C revoked"
revoke_all
"$BIN" & APP=$!; sleep 6; shot C-revoked; kill $APP; wait $APP 2>/dev/null

mark "U unreachable"
printf '{"servers":[{"origin":"http://127.0.0.1:9","host_name":"gone","device_name":"x","last_used":9999999999}],"lang":"en"}' \
  > "$XDG_DATA_HOME/mg.madalean.desktop/settings.json"
printf '{"http://127.0.0.1:9":"%s"}' "$(head -c 32 /dev/urandom | base64 | tr -d '/+=')" > "$XDG_DATA_HOME/mg.madalean.desktop/tokens.json"
"$BIN" & APP=$!; sleep 6; shot U-unreachable-en; kill $APP; wait $APP 2>/dev/null

mark "E host mode (local listener)"
MADALEAN_LOCAL_URL="http://127.0.0.1:$LP" "$BIN" & APP=$!; sleep 9; shot E-local; kill $APP; wait $APP 2>/dev/null
ls -l "$HOME/Downloads" > "$W/downloads.txt"
[ "$MODE" = mock ] && curl -fs "http://127.0.0.1:$LP/mock/events" > "$W/events.json"
echo "$T0" > "$W/t0"
kill $XW 2>/dev/null
INNER
chmod +x "$WORK/inner.sh"

# Temporary HOME for the whole private session too, so D-Bus-activated helpers (portals, ksecretd…) never
# touch the user's real files.
mkdir -p "$WORK/home"
HOME="$WORK/home" XDG_CONFIG_HOME="$WORK/home/.config" XDG_DATA_HOME="$WORK/home/.local/share" \
XDG_CACHE_HOME="$WORK/home/.cache" XDG_RUNTIME_DIR="$WORK/run" setsid dbus-run-session -- kwin_wayland --virtual --no-lockscreen --width 1280 --height 860 \
  --socket "madalean-e2e-$$" --exit-with-session "$WORK/inner.sh" > "$WORK/kwin.log" 2>&1

# Reap helpers that D-Bus activated inside the private session (they outlive dbus-run-session otherwise).
for p in $(pgrep -f "xdg-desktop-portal|ksecretd|kwalletd|at-spi" || true); do
  tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -qx "HOME=$WORK/home" && kill "$p" 2>/dev/null
done
echo "server: $SERVER   work dir: $WORK"
"$PY" - "$WORK" "$SERVER" <<'PYEOF'
import json, sys, pathlib
w, mode = pathlib.Path(sys.argv[1]), sys.argv[2]
def load(name):
    p = w / name
    return json.loads(p.read_text()) if p.exists() else None
log = [json.loads(l) for l in (w / "shell.log").read_text().splitlines()] if (w / "shell.log").exists() else []
def shell(k, pred=lambda x: True): return any(l["kind"] == k and pred(l["extra"]) for l in log)
def count(k, pred=lambda x: True): return sum(1 for l in log if l["kind"] == k and pred(l["extra"]))
remote_root = lambda x: x.get("path") == "/" and x.get("origin", "").endswith(":" + str(load("rp") or ""))
checks = {}
if mode == "mock":
    ev = load("events.json") or []
    kinds = [e["kind"] for e in ev]
    def has(k, **kw): return any(e["kind"] == k and all(e.get(a) == b for a, b in kw.items()) for e in ev)
    checks.update({
      "A paired":                 has("paired"),
      "A ticket issued":          has("ticket_issued"),
      "A session cookie set":     has("session_opened"),
      "A page auth via cookie":   has("page", local=False, auth_ok=True, via="cookie"),
      "A websocket with cookie":  has("ws_open", local=False),
      "A download finished":      shell("download_finished", lambda x: x.get("success") is True),
      "A external link (same tab) → system opener": "leanprover-community.github.io" in ((w / "opened.txt").read_text() if (w / "opened.txt").exists() else ""),
      "B auto reconnect (2 tickets)": kinds.count("ticket_issued") >= 2,
      "D wrong code refused":     has("pair_bad_code"),
      "E local page, no pairing": has("page", local=True, auth_ok=True),
      "no unauthorized page hit": not has("unauthorized", path="/"),
    })
else:
    da, db = load("devices-A.json") or {"devices": []}, load("devices-B.json") or {"devices": []}
    checks.update({
      "A paired (device on the host)":      len(da["devices"]) == 1,
      "A session cookie issued":            bool(da["devices"]) and da["devices"][0]["sessions"] >= 1,
      "A web view API call authenticated (GET /api/state 200 with cookie)": shell("probe", lambda x: x.get("what") == "state" and x.get("status") == "200"),
      "A WebSocket accepted with cookie":   shell("probe", lambda x: x.get("what") == "ws" and x.get("status") == "open"),
      "A no unauthenticated state call":    not shell("probe", lambda x: x.get("what") == "state" and x.get("status") != "200"),
      "B auto reconnect (2nd session)":     bool(db["devices"]) and db["devices"][0]["sessions"] >= 2,
      "D wrong code refused":               shell("pair", lambda x: x.get("ok") is False),
      "E local page, no pairing":           count("open", lambda x: x.get("local") is True) >= 1,
    })
checks.update({
  "F deep link forwarded":    shell("deep_link"),
  "C revoked detected":       shell("connect_error", lambda x: x.get("code") == "revoked"),
  "U unreachable reported":   shell("connect_error", lambda x: x.get("code") == "unreachable"),
  "no re-auth loop":          not shell("connect_screen", lambda x: x.get("reason") == "session_failed"),
})
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
starts = [l["t_ms"] for l in log if l["kind"] == "start"]
loads = [l for l in log if l["kind"] == "page_loaded"]
if (w / "t0").exists() and starts:
    t0 = int((w / "t0").read_text())
    first_load = next((l["t_ms"] for l in loads if l["t_ms"] > t0), None)
    print(f"startup: process start→shell ready {starts[0]-t0} ms, →first page loaded {first_load - t0 if first_load else '?'} ms")
print("file perms:", (w / "perms.txt").read_text().strip() if (w / "perms.txt").exists() else "?")
sys.exit(0 if all(checks.values()) else 1)
PYEOF
RC=$?
echo "screenshots: $OUT"
exit $RC
