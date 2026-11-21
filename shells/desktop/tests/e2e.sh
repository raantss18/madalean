#!/usr/bin/env bash
# End-to-end test of the desktop shell against shells/dev/mock_server.py, inside an ISOLATED headless
# compositor (kwin_wayland --virtual in its own D-Bus session, temporary HOME): nothing appears on the
# user's screen, no key is injected anywhere, the user's keyring / AppImageLauncher / browser are not used.
#
#   shells/desktop/tests/e2e.sh [path/to/Madalean.AppImage | path/to/binary]
#
# Scenarios: pairing by deep link (auto-submitted, test hook) → ticket → HttpOnly cookie → web UI + WebSocket;
# download (PDF); external link → system opener (fake xdg-open); restart → automatic reconnection with the stored
# token; wrong code; single instance + deep link forwarded to the running instance; revocation → pairing screen;
# host mode (local listener, no pairing). Screenshots in $OUT.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BIN="${1:-$(ls -t "$ROOT"/shells/desktop/dist/Madalean-*-x86_64.AppImage 2>/dev/null | head -1)}"
[ -x "$BIN" ] || { echo "no binary/AppImage: $BIN" >&2; exit 2; }
BIN="$(realpath "$BIN")"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
WORK="$(mktemp -d "${TMPDIR:-/tmp}/madalean-e2e.XXXXXX")"
OUT="${E2E_OUT:-$WORK/out}"; mkdir -p "$OUT"
LP=11630; RP=11631
export MADALEAN_E2E_WORK="$WORK" MADALEAN_E2E_BIN="$BIN" MADALEAN_E2E_OUT="$OUT" MADALEAN_E2E_LP=$LP MADALEAN_E2E_RP=$RP

"$PY" "$ROOT/shells/dev/mock_server.py" --local-port $LP --remote-port $RP > "$WORK/mock.log" 2>&1 &
MOCK=$!
mkdir -p "$WORK/run"; chmod 700 "$WORK/run"
trap 'kill $MOCK 2>/dev/null' EXIT
for _ in $(seq 50); do curl -fs "http://127.0.0.1:$RP/api/hello" >/dev/null && break; sleep 0.1; done

cat > "$WORK/inner.sh" <<'INNER'
#!/usr/bin/env bash
# Runs inside the private kwin_wayland session.
set -u
W="$MADALEAN_E2E_WORK"; OUT="$MADALEAN_E2E_OUT"; BIN="$MADALEAN_E2E_BIN"
export HOME="$W/home" XDG_CONFIG_HOME="$W/home/.config" XDG_DATA_HOME="$W/home/.local/share" XDG_CACHE_HOME="$W/home/.cache"
mkdir -p "$HOME/Downloads" "$W/fakebin"
export XDG_DOWNLOAD_DIR="$HOME/Downloads"
# Fake system opener: records what the shell sends to the browser / file manager.
printf '#!/bin/sh\necho "$@" >> "%s/opened.txt"\n' "$W" > "$W/fakebin/xdg-open"; chmod +x "$W/fakebin/xdg-open"
export PATH="$W/fakebin:$PATH"
export APPIMAGELAUNCHER_DISABLE=1 MADALEAN_TOKEN_STORE=file MADALEAN_SHELL_TEST_LOG="$W/shell.log"
# Rootful Xwayland inside the private compositor: its root window can be captured (ffmpeg x11grab).
Xwayland :57 -geometry 1280x860 -noreset > "$W/xwayland.log" 2>&1 & XW=$!
sleep 1.5
export DISPLAY=:57 GDK_BACKEND=x11 WEBKIT_DISABLE_DMABUF_RENDERER=1 NO_AT_BRIDGE=1
export MADALEAN_LOCAL_URL="http://127.0.0.1:9"   # no local server: remote scenarios first
LP=$MADALEAN_E2E_LP; RP=$MADALEAN_E2E_RP
shot() { ffmpeg -loglevel error -y -f x11grab -video_size 1280x860 -i "$DISPLAY" -frames:v 1 "$OUT/$1.png" 2>>"$W/shots.err"; }
events() { curl -fs "http://127.0.0.1:$LP/mock/events"; }
mark() { echo "=== $*" | tee -a "$W/steps.txt"; date +%s%3N >> "$W/steps.txt"; }

mark "A pair via deep link"
T0=$(date +%s%3N)
MADALEAN_SHELL_TEST_AUTOSUBMIT=1 MADALEAN_SHELL_TEST_CLICK=dl,ext,ext2 "$BIN" "madalean://pair?host=127.0.0.1:$RP&code=123456" &
APP=$!
sleep 3; shot A-remote-page; sleep 6; shot A-after-download
mark "F single instance: second launch forwards a deep link"
"$BIN" "madalean://pair?host=127.0.0.1:$RP&code=999999" & SECOND=$!
sleep 4; shot F-link-forwarded
kill -0 $SECOND 2>/dev/null && echo "second instance still running" >> "$W/steps.txt" || echo "second instance exited" >> "$W/steps.txt"
kill $APP; wait $APP 2>/dev/null

stat -c '%a %n' "$XDG_DATA_HOME"/mg.madalean.desktop/*.json "$XDG_DATA_HOME"/mg.madalean.desktop > "$W/perms.txt" 2>&1
mark "B restart: automatic reconnection"
"$BIN" & APP=$!; sleep 8; shot B-reconnected; kill $APP; wait $APP 2>/dev/null

mark "D wrong code"
curl -fs -X POST "http://127.0.0.1:$LP/mock/new_code" -d '{"code":"123456"}' >/dev/null
MADALEAN_SHELL_TEST_AUTOSUBMIT=1 "$BIN" "madalean://pair?host=127.0.0.1:$RP&code=000000" & APP=$!
sleep 6; shot D-wrong-code; kill $APP; wait $APP 2>/dev/null

mark "C revoked"
curl -fs -X POST "http://127.0.0.1:$LP/mock/revoke_all" >/dev/null
"$BIN" & APP=$!; sleep 6; shot C-revoked; kill $APP; wait $APP 2>/dev/null

mark "U unreachable"
printf '{"servers":[{"origin":"http://127.0.0.1:9","host_name":"gone","device_name":"x","last_used":9999999999}],"lang":"en"}' \
  > "$XDG_DATA_HOME/mg.madalean.desktop/settings.json"
printf '{"http://127.0.0.1:9":"%s"}' "$(head -c 32 /dev/urandom | base64 | tr -d '/+=')" > "$XDG_DATA_HOME/mg.madalean.desktop/tokens.json"
"$BIN" & APP=$!; sleep 6; shot U-unreachable-en; kill $APP; wait $APP 2>/dev/null

mark "E host mode (local listener)"
MADALEAN_LOCAL_URL="http://127.0.0.1:$LP" "$BIN" & APP=$!; sleep 8; shot E-local; kill $APP; wait $APP 2>/dev/null
ls -l "$HOME/Downloads" > "$W/downloads.txt"
events > "$W/events.json"
echo "$T0" > "$W/t0"
kill $XW 2>/dev/null
INNER
chmod +x "$WORK/inner.sh"

# Temporary HOME for the whole private session too, so D-Bus-activated helpers (portals, ksecretd…) never
# touch the user's real files; everything started there is killed with the session's process group.
mkdir -p "$WORK/home"
HOME="$WORK/home" XDG_CONFIG_HOME="$WORK/home/.config" XDG_DATA_HOME="$WORK/home/.local/share" \
XDG_CACHE_HOME="$WORK/home/.cache" XDG_RUNTIME_DIR="$WORK/run" setsid dbus-run-session -- kwin_wayland --virtual --no-lockscreen --width 1280 --height 860 \
  --socket "madalean-e2e-$$" --exit-with-session "$WORK/inner.sh" > "$WORK/kwin.log" 2>&1

# Reap helpers that D-Bus activated inside the private session (they outlive dbus-run-session otherwise).
for p in $(pgrep -f "xdg-desktop-portal|ksecretd|kwalletd|at-spi" || true); do
  tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -qx "HOME=$WORK/home" && kill "$p" 2>/dev/null
done
echo "work dir: $WORK"
"$PY" - "$WORK" <<'PYEOF'
import json, sys, pathlib
w = pathlib.Path(sys.argv[1])
ev = json.loads((w / "events.json").read_text()) if (w / "events.json").exists() else []
log = [json.loads(l) for l in (w / "shell.log").read_text().splitlines()] if (w / "shell.log").exists() else []
kinds = [e["kind"] for e in ev]
def has(k, **kw): return any(e["kind"] == k and all(e.get(a) == b for a, b in kw.items()) for e in ev)
def shell(k, pred=lambda x: True): return any(l["kind"] == k and pred(l["extra"]) for l in log)
checks = {
  "A paired":                 has("paired"),
  "A ticket issued":          has("ticket_issued"),
  "A session cookie set":     has("session_opened"),
  "A page auth via cookie":   has("page", local=False, auth_ok=True, via="cookie"),
  "A websocket with cookie":  has("ws_open", local=False),
  "A download finished":      shell("download_finished", lambda x: x.get("success") is True),
  "A external link (same tab) → system opener": "leanprover-community.github.io" in ((w / "opened.txt").read_text() if (w / "opened.txt").exists() else ""),
  "F deep link forwarded":    any(l["kind"] == "deep_link" for l in log),
  "B auto reconnect (2 tickets)": kinds.count("ticket_issued") >= 2,
  "D wrong code refused":     has("pair_bad_code"),
  "C revoked detected":       shell("connect_error", lambda x: x.get("code") == "revoked"),
  "U unreachable reported":   shell("connect_error", lambda x: x.get("code") == "unreachable"),
  "E local page, no pairing": has("page", local=True, auth_ok=True),
  "no unauthorized page hit": not has("unauthorized", path="/"),
}
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
starts = [l["t_ms"] for l in log if l["kind"] == "start"]
loads = [l for l in log if l["kind"] == "page_loaded"]
if (w / "t0").exists() and starts:
    t0 = int((w / "t0").read_text())
    first_load = next((l["t_ms"] for l in loads if l["t_ms"] > t0), None)
    print(f"startup: process start→shell ready {starts[0]-t0} ms, →first page loaded {first_load - t0 if first_load else '?'} ms")
print("downloads:", (w / "downloads.txt").read_text().strip().splitlines()[1:] if (w / "downloads.txt").exists() else "?")
print("file perms:", (w / "perms.txt").read_text().strip() if (w / "perms.txt").exists() else "?")
sys.exit(0 if all(checks.values()) else 1)
PYEOF
RC=$?
echo "screenshots: $OUT"
exit $RC
