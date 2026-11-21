#!/usr/bin/env bash
# End-to-end test of the AppImage self-update against a LOCAL fake channel, inside the same isolated headless session
# as e2e.sh (private kwin_wayland + D-Bus, temporary HOME; nothing on the user's screen).
#
#   shells/desktop/tests/update_e2e.sh [path/to/Madalean.AppImage]
#
# The fake channel (http://127.0.0.1:<port>/test.json + .sig) is signed with the release key through
# scripts/make_update_manifest.py --channel test (a "test" manifest is refused by real clients, which expect "stable").
# Scenarios, each on a fresh copy of the AppImage: good (installs, keeps .previous, relaunches the new file), tampered
# manifest, missing signature, downgrade, same version, manifest of another channel, SHA-256 mismatch, automatic
# updates switched off.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SRC="${1:-$(ls -t "$ROOT"/shells/desktop/dist/Madalean-*-x86_64.AppImage 2>/dev/null | head -1)}"
[ -f "$SRC" ] || { echo "no AppImage" >&2; exit 2; }
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
MK="$ROOT/scripts/make_update_manifest.py"
export MADALEAN_RELEASE_KEY="${MADALEAN_RELEASE_KEY:-$HOME/.config/madalean/release-keys/ed25519.pem}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/madalean-upd.XXXXXX")"
PORT=$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
WWW="$WORK/www"; mkdir -p "$WWW/files" "$WORK/run"; chmod 700 "$WORK/run"
# "New" release = the same AppImage with a marker appended (still runs: the runtime ignores trailing bytes).
cp "$SRC" "$WWW/files/Madalean-2.0.1-x86_64.AppImage"; printf '\nMADALEAN-TEST-RELEASE-2.0.1\n' >> "$WWW/files/Madalean-2.0.1-x86_64.AppImage"
NEW_SHA=$(sha256sum "$WWW/files/Madalean-2.0.1-x86_64.AppImage" | cut -d' ' -f1)
OLD_SHA=$(sha256sum "$SRC" | cut -d' ' -f1)
(cd "$WWW" && exec "$PY" -m http.server "$PORT" --bind 127.0.0.1) > "$WORK/http.log" 2>&1 &
HTTP=$!
trap 'kill $HTTP 2>/dev/null' EXIT
BASE="http://127.0.0.1:$PORT/files"

channel() {  # channel <scenario>: writes www/test.json(.sig)
  rm -f "$WWW"/*.json "$WWW"/*.sig
  local f="$WWW/files/Madalean-2.0.1-x86_64.AppImage"
  case "$1" in
    good|autooff) "$PY" "$MK" --channel test --version 2.0.1 --base-url "$BASE" --out "$WWW" "$f" ;;
    tampered)  "$PY" "$MK" --channel test --version 2.0.1 --base-url "$BASE" --out "$WWW" "$f"
               sed -i 's/"version": "2.0.1"/"version": "2.0.2"/' "$WWW/test.json" ;;
    unsigned)  "$PY" "$MK" --channel test --version 2.0.1 --base-url "$BASE" --out "$WWW" --no-sign "$f" ;;
    downgrade) "$PY" "$MK" --channel test --version 1.9.0 --base-url "$BASE" --out "$WWW" "$f" ;;
    same)      "$PY" "$MK" --channel test --version 2.0.0 --base-url "$BASE" --out "$WWW" "$f" ;;
    channel)   "$PY" "$MK" --channel stable --version 2.0.1 --base-url "$BASE" --out "$WWW" "$f"
               mv "$WWW/stable.json" "$WWW/test.json"; mv "$WWW/stable.json.sig" "$WWW/test.json.sig" ;;
    checksum)  cp "$SRC" "$WWW/files/other.AppImage"
               "$PY" "$MK" --channel test --version 2.0.1 --base-url "$BASE" --out "$WWW" "$WWW/files/other.AppImage"
               # signed manifest promises other.AppImage's hash, but its URL serves the 2.0.1 file
               "$PY" - "$WWW" <<'P'
import json, sys, pathlib, subprocess
w = pathlib.Path(sys.argv[1]); m = json.loads((w / "test.json").read_text())
m["files"][0]["url"] = m["files"][0]["url"].replace("other.AppImage", "Madalean-2.0.1-x86_64.AppImage")
m["files"][0]["size"] = (w / "files/Madalean-2.0.1-x86_64.AppImage").stat().st_size
(w / "test.json").write_text(json.dumps(m, indent=2) + "\n")
P
               openssl pkeyutl -sign -inkey "$MADALEAN_RELEASE_KEY" -rawin -in "$WWW/test.json" | base64 -w0 > "$WWW/test.json.sig" ;;
  esac
}

SCEN="good tampered unsigned downgrade same channel checksum autooff"
for s in $SCEN; do mkdir -p "$WORK/$s/app" "$WORK/$s/home"; cp "$SRC" "$WORK/$s/app/Madalean.AppImage"; chmod +x "$WORK/$s/app/Madalean.AppImage"; done
export MADALEAN_UPD_WORK="$WORK" MADALEAN_UPD_PORT="$PORT" MADALEAN_UPD_SCEN="$SCEN"
export -f channel; export PY MK WWW BASE SRC

cat > "$WORK/inner.sh" <<'INNER'
#!/usr/bin/env bash
set -u
W="$MADALEAN_UPD_WORK"
Xwayland :58 -geometry 1100x760 -noreset > "$W/xwayland.log" 2>&1 & XW=$!
sleep 1.5
export DISPLAY=:58 GDK_BACKEND=x11 WEBKIT_DISABLE_DMABUF_RENDERER=1 NO_AT_BRIDGE=1 APPIMAGELAUNCHER_DISABLE=1 MADALEAN_TOKEN_STORE=file
export MADALEAN_LOCAL_URL="http://127.0.0.1:9" MADALEAN_UPDATE_CHANNEL="http://127.0.0.1:$MADALEAN_UPD_PORT/test.json" MADALEAN_UPDATE_DELAY_SECS=1
for s in $MADALEAN_UPD_SCEN; do
  channel "$s" > /dev/null
  H="$W/$s/home"; mkdir -p "$H/.local/share/mg.madalean.desktop"
  [ "$s" = autooff ] && printf '{"servers":[],"auto_update":false}' > "$H/.local/share/mg.madalean.desktop/settings.json"
  RESTART=0; [ "$s" = good ] && RESTART=1
  HOME="$H" XDG_DATA_HOME="$H/.local/share" XDG_CONFIG_HOME="$H/.config" XDG_CACHE_HOME="$H/.cache" \
  MADALEAN_SHELL_TEST_LOG="$W/$s/shell.log" MADALEAN_SHELL_TEST_RESTART_AFTER_UPDATE=$RESTART \
    "$W/$s/app/Madalean.AppImage" & APP=$!
  sleep 14
  ffmpeg -loglevel error -y -f x11grab -video_size 1100x760 -i "$DISPLAY" -frames:v 1 "$W/$s/screen.png" 2>/dev/null
  kill $APP 2>/dev/null
  # the relaunched process (good scenario) is a new process group: stop every instance of this copy
  pkill -f "$W/$s/app/" 2>/dev/null; sleep 1
done
kill $XW
INNER
chmod +x "$WORK/inner.sh"
HOME="$WORK/home" XDG_CONFIG_HOME="$WORK/home/.config" XDG_DATA_HOME="$WORK/home/.local/share" XDG_CACHE_HOME="$WORK/home/.cache" \
XDG_RUNTIME_DIR="$WORK/run" setsid dbus-run-session -- kwin_wayland --virtual --no-lockscreen --width 1100 --height 760 \
  --socket "madalean-upd-$$" --exit-with-session "$WORK/inner.sh" > "$WORK/kwin.log" 2>&1
for p in $(pgrep -f "xdg-desktop-portal|ksecretd|kwalletd|at-spi" || true); do
  tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -q "^HOME=$WORK" && kill "$p" 2>/dev/null
done
echo "work dir: $WORK"
"$PY" - "$WORK" "$NEW_SHA" "$OLD_SHA" <<'PYEOF'
import json, sys, pathlib, hashlib
w, new, old = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def log(s):
    p = w / s / "shell.log"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
def err(s, code): return any(l["kind"] == "update_error" and l["extra"].get("error") == code for l in log(s))
def untouched(s): return sha(w / s / "app/Madalean.AppImage") == old and not (w / s / "app/Madalean.AppImage.previous").exists()
g = log("good")
checks = {
  "build has the update key": any(l["kind"] == "start" and l["extra"].get("update_key") for l in g),
  "good: installed (new SHA-256 in place)": sha(w / "good/app/Madalean.AppImage") == new,
  "good: previous kept for rollback": sha(w / "good/app/Madalean.AppImage.previous") == old,
  "good: relaunched from the new file": sum(1 for l in g if l["kind"] == "start") >= 2 and any(l["kind"] == "update_restart" for l in g),
  "good: no temp file left": not list((w / "good/app").glob(".*.download")),
  "tampered: refused (bad_signature), untouched": err("tampered", "bad_signature") and untouched("tampered"),
  "unsigned: refused (unsigned), untouched": err("unsigned", "unsigned") and untouched("unsigned"),
  "downgrade: nothing installed": any(l["kind"] == "update_none" for l in log("downgrade")) and untouched("downgrade"),
  "same version: nothing installed": any(l["kind"] == "update_none" for l in log("same")) and untouched("same"),
  "other channel: refused (bad_channel), untouched": err("channel", "bad_channel") and untouched("channel"),
  "checksum: refused (checksum), untouched, temp removed": err("checksum", "checksum") and untouched("checksum") and not list((w / "checksum/app").glob(".*.download")),
  "auto off: no check at all": not any(l["kind"].startswith("update_") for l in log("autooff")) and untouched("autooff"),
}
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
sys.exit(0 if all(checks.values()) else 1)
PYEOF
