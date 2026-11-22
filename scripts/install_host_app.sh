#!/usr/bin/env bash
# « Madalean Server » menu entry on the HOST (DECISIONS D50): the host's own desktop app, with its own icon.
# Called by install.sh (step « Menu »), by the in-app self-update (--refresh) and by uninstall.sh (--uninstall).
# The client AppImage (other PCs) has its own entry, madalean.desktop (scripts/install_desktop_entry.sh); this script
# never installs it.
#
#   scripts/install_host_app.sh --prefix DIR [--port N] [--unit NAME] [--dry-run]   install / update the entry
#   scripts/install_host_app.sh --prefix DIR --refresh     after a self-update: only when an entry of THIS prefix exists
#                                                           (or the old xdg-open entry install.sh recorded); keeps its
#                                                           port and unit
#   scripts/install_host_app.sh --prefix DIR --uninstall   remove the entry and the icons
#   scripts/install_host_app.sh --detect [--binary PATH]   only print which launcher would be used (install.sh --dry-run)
#
# What the entry starts, best first:
#   1. native  — <prefix>/current/dist/host-app/madalean-server --host (Tauri, ≈ 7 MB, shipped in the server archive;
#                needs the system's webkit2gtk-4.1 + GTK 3, checked with ldd);
#   2. browser — a Chromium-family browser in app mode (--app=http://127.0.0.1:PORT/: own window, no tabs);
#   3. xdg-open http://127.0.0.1:PORT/ (the default browser).
# Installs (user level, honours XDG_DATA_HOME): applications/madalean-server.desktop,
# icons/hicolor/{16…512}/apps/madalean-server.png + scalable/apps/madalean-server.svg; removes the old
# « Madalean » xdg-open entry of install.sh ≤ 2.0.1 (<unit>.desktop whose Exec is `xdg-open http://127.0.0.1:…`).
# Records what it creates in <prefix>/installed-files.txt (read by uninstall.sh). Refreshes the desktop database and
# the icon caches (update-desktop-database, gtk-update-icon-cache, kbuildsycoca6/5) so the menu shows the icon at once.
# Last line of the output: `LAUNCHER=native|browser|xdg-open` (install / refresh) for the installer summary.
set -euo pipefail
PREFIX=""; PORT=""; UNIT=""; MODE=install; DRY=0; BIN=""
while [ $# -gt 0 ]; do case "$1" in
  --prefix) shift; PREFIX="${1:?}" ;;
  --port) shift; PORT="${1:?}" ;;
  --unit) shift; UNIT="${1:?}" ;;
  --refresh) MODE=refresh ;;
  --uninstall) MODE=uninstall ;;
  --detect) MODE=detect ;;
  --binary) shift; BIN="${1:?}" ;;
  --dry-run) DRY=1 ;;
  -h|--help) sed -n 2,25p "$0"; exit 0 ;;
  *) echo "Option inconnue : $1" >&2; exit 2 ;;
esac; shift; done
[ -n "$PREFIX" ] || [ $MODE = detect ] || { echo "--prefix est obligatoire" >&2; exit 2; }
PREFIX="${PREFIX%/}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"; ICONS="$DATA/icons/hicolor"
ENTRY="$APPS/madalean-server.desktop"
RECORD="$PREFIX/installed-files.txt"
SIZES="16 24 32 48 64 128 256 512"
have() { command -v "$1" >/dev/null 2>&1; }
run() { if [ $DRY = 1 ]; then printf '+ '; printf '%q ' "$@"; echo; else "$@"; fi; }
record() { [ $DRY = 1 ] || [ ! -d "$PREFIX" ] && return 0; grep -qxF -- "$1" "$RECORD" 2>/dev/null || echo "$1" >> "$RECORD"; }
entry_val() { sed -n "s/^$1=//p" "$2" 2>/dev/null | head -1; }

refresh_caches() {
  [ $DRY = 1 ] && { echo "+ update-desktop-database / gtk-update-icon-cache / kbuildsycoca"; return 0; }
  touch "$ICONS" 2>/dev/null || true
  have update-desktop-database && update-desktop-database -q "$APPS" 2>/dev/null || true
  have gtk-update-icon-cache && gtk-update-icon-cache -q -t -f "$ICONS" 2>/dev/null || true
  if have kbuildsycoca6; then kbuildsycoca6 >/dev/null 2>&1 || true
  elif have kbuildsycoca5; then kbuildsycoca5 >/dev/null 2>&1 || true; fi
}

# Old entry of install.sh ≤ 2.0.1: « Madalean », Exec=xdg-open http://127.0.0.1:PORT/ (only that exact shape).
old_entry() { local f="$APPS/${1:-madalean}.desktop"; grep -q '^Exec=xdg-open http://127\.0\.0\.1:[0-9]*/\?$' "$f" 2>/dev/null && echo "$f"; }

if [ $MODE = uninstall ]; then
  run rm -f "$ENTRY" "$ICONS/scalable/apps/madalean-server.svg"
  for s in $SIZES; do run rm -f "$ICONS/${s}x${s}/apps/madalean-server.png"; done
  refresh_caches
  echo "Menu : « Madalean Server » retiré."
  exit 0
fi

if [ $MODE = refresh ]; then
  # Only an entry that belongs to this prefix (never someone else's, never a test prefix's).
  if [ -f "$ENTRY" ] && [ "$(entry_val X-Madalean-Prefix "$ENTRY")" = "$PREFIX" ]; then
    PORT="${PORT:-$(entry_val X-Madalean-Port "$ENTRY")}"; UNIT="${UNIT:-$(entry_val X-Madalean-Unit "$ENTRY")}"
  else
    OLD=""
    for u in madalean $(sed -n 's|.*/applications/\([A-Za-z0-9_.-]*\)\.desktop$|\1|p' "$RECORD" 2>/dev/null); do
      f="$(old_entry "$u" || true)"
      [ -n "$f" ] && grep -qxF -- "$f" "$RECORD" 2>/dev/null && { OLD="$f"; UNIT="${UNIT:-$u}"; break; }
    done
    [ -n "$OLD" ] || { echo "Menu : aucune entrée « Madalean Server » de $PREFIX à mettre à jour."; exit 0; }
    PORT="${PORT:-$(sed -n 's|^Exec=xdg-open http://127\.0\.0\.1:\([0-9]*\).*|\1|p' "$OLD" | head -1)}"
  fi
fi
PORT="${PORT:-11500}"; UNIT="${UNIT:-madalean}"
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] || { echo "Port invalide : $PORT" >&2; exit 2; }
[[ "$UNIT" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]] || { echo "Nom d'unité invalide : $UNIT" >&2; exit 2; }
URL="http://127.0.0.1:$PORT/"

# ---------------------------------------------------------------- choose the launcher
BIN="${BIN:-$PREFIX/current/dist/host-app/madalean-server}"
LAUNCHER=""; WHY=""
if [ -x "$BIN" ]; then
  if have ldd; then
    MISSING="$(ldd "$BIN" 2>/dev/null | sed -n 's/^[[:space:]]*\([^ ]*\) => not found.*/\1/p' | tr '\n' ' ')"
    if ldd "$BIN" >/dev/null 2>&1 && [ -z "$MISSING" ]; then LAUNCHER=native
    else WHY="bibliothèques absentes : ${MISSING:-illisibles} (paquet webkit2gtk-4.1 de votre distribution)"; fi
  else
    for d in /usr/lib /usr/lib64 /usr/lib/x86_64-linux-gnu /lib/x86_64-linux-gnu; do
      [ -e "$d/libwebkit2gtk-4.1.so.0" ] && { LAUNCHER=native; break; }
    done
    [ -n "$LAUNCHER" ] || WHY="webkit2gtk-4.1 introuvable"
  fi
else
  WHY="application de bureau absente de cette version ($BIN)"
fi
EXTRA=""
[ "$PORT" != 11500 ] && EXTRA="$EXTRA --port $PORT"
[ "$UNIT" != madalean ] && EXTRA="$EXTRA --unit $UNIT"
if [ "$LAUNCHER" = native ]; then
  EXEC="\"$BIN\" --host$EXTRA"
else
  for b in chromium chromium-browser google-chrome-stable google-chrome brave brave-browser microsoft-edge-stable vivaldi-stable; do
    if have "$b"; then
      LAUNCHER=browser; BROWSER="$(command -v "$b")"
      EXEC="\"$BROWSER\" --app=$URL --class=madalean-server"
      break
    fi
  done
  if [ -z "$LAUNCHER" ]; then LAUNCHER=xdg-open; EXEC="xdg-open $URL"; fi
fi

if [ $MODE = detect ]; then
  [ -n "$WHY" ] && echo "($WHY)"
  echo "LAUNCHER=$LAUNCHER"
  exit 0
fi

# ---------------------------------------------------------------- icons + entry
SRC_ICONS="$PREFIX/current/shells/branding"
[ -f "$SRC_ICONS/madalean-server-icon.svg" ] || SRC_ICONS="$(cd "$(dirname "$0")/.." && pwd)/shells/branding"
run mkdir -p "$APPS" "$ICONS/scalable/apps"
if [ -f "$SRC_ICONS/madalean-server-icon.svg" ]; then
  run install -m 0644 "$SRC_ICONS/madalean-server-icon.svg" "$ICONS/scalable/apps/madalean-server.svg"
  record "$ICONS/scalable/apps/madalean-server.svg"
  for s in $SIZES; do
    [ -f "$SRC_ICONS/png/madalean-server-icon-$s.png" ] || continue
    run mkdir -p "$ICONS/${s}x${s}/apps"
    run install -m 0644 "$SRC_ICONS/png/madalean-server-icon-$s.png" "$ICONS/${s}x${s}/apps/madalean-server.png"
    record "$ICONS/${s}x${s}/apps/madalean-server.png"
  done
else
  echo "⚠️  Icône de Madalean Server introuvable ($SRC_ICONS) : le menu montrera une icône générique."
fi
CONTENT="[Desktop Entry]
Type=Application
Name=Madalean Server
GenericName=Serveur Madalean de cet ordinateur
GenericName[en]=Madalean server of this computer
Comment=Ouvrir Madalean sur cet ordinateur et piloter son serveur (démarrer, arrêter, journaux)
Comment[en]=Open Madalean on this computer and control its server (start, stop, logs)
Exec=$EXEC
Icon=madalean-server
Terminal=false
Categories=Education;Science;Math;
Keywords=Lean;Mathlib;preuve;proof;théorème;theorem;serveur;server;
StartupWMClass=madalean-server
StartupNotify=true
X-Madalean-Host=1
X-Madalean-Prefix=$PREFIX
X-Madalean-Port=$PORT
X-Madalean-Unit=$UNIT
X-Madalean-Launcher=$LAUNCHER
"
if [ $DRY = 1 ]; then
  echo "+ write $ENTRY:"; printf '%s' "$CONTENT" | sed 's/^/    /'
else
  printf '%s' "$CONTENT" > "$ENTRY.tmp" && chmod 0644 "$ENTRY.tmp" && mv -f "$ENTRY.tmp" "$ENTRY"
fi
record "$ENTRY"
OLD="$(old_entry "$UNIT" || true)"
[ -z "$OLD" ] && OLD="$(old_entry madalean || true)"
if [ -n "$OLD" ]; then run rm -f "$OLD"; echo "Ancienne entrée « Madalean » (navigateur) remplacée : $OLD"; fi
refresh_caches
case "$LAUNCHER" in
  native)   echo "Menu : « Madalean Server » (application de bureau) → $ENTRY" ;;
  browser)  echo "Menu : « Madalean Server » → fenêtre de $(basename "$BROWSER") ($WHY)" ;;
  xdg-open) echo "Menu : « Madalean Server » → navigateur par défaut ($WHY ; aucun navigateur Chromium pour une fenêtre dédiée)" ;;
esac
echo "LAUNCHER=$LAUNCHER"
