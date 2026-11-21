#!/usr/bin/env bash
# uninstall.sh — removes exactly what install.sh installed (ARCHITECTURE §18). Lists first, then asks.
#
#   ./uninstall.sh [--prefix DIR] [--unit-name NAME] [--cache-dir DIR] [--config-dir DIR] [--yes] [--purge]
#
# Removed: the prefix (MADALEAN_HOME: env, components, Lean workspaces of the prefix, TeX bundle, Tailscale node
# state, Madalean versions), the systemd user unit, the desktop entry (files listed in <prefix>/installed-files.txt),
# the cache directory. Every process of the unit is stopped first (the whole cgroup).
# Kept unless --purge (asked separately): the config directory (settings, projects, dossiers, devices, keys),
# ~/models. Never touched: ~/.elan, ~/Documents/Madalean (notebooks), the old Lean AI Station, system packages,
# the host's tailscaled.
set -u
PREFIX="${MADALEAN_HOME:-$HOME/.local/share/madalean}"; UNIT=madalean
CONFIG_DIR="$HOME/.config/madalean"; CACHE_DIR="$HOME/.cache/madalean"; YES=0; PURGE=0
while [ $# -gt 0 ]; do case "$1" in
  --prefix) shift; PREFIX="$1" ;;
  --unit-name) shift; UNIT="$1" ;;
  --config-dir) shift; CONFIG_DIR="$1" ;;
  --cache-dir) shift; CACHE_DIR="$1" ;;
  --yes) YES=1 ;;
  --purge) PURGE=1 ;;
  -h|--help) sed -n 2,14p "$0"; exit 0 ;;
  *) echo "Option inconnue : $1"; exit 2 ;;
esac; shift; done
[[ "$UNIT" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "Nom d'unité invalide"; exit 2; }
case "$PREFIX" in ""|/|"$HOME"|"$HOME/"|/usr*|/etc*) echo "Préfixe refusé : $PREFIX"; exit 2 ;; esac
if [ -d "$PREFIX" ] && [ ! -e "$PREFIX/deps-state.json" ] && [ ! -d "$PREFIX/versions" ]; then
  echo "$PREFIX ne ressemble pas à une installation de Madalean : rien n'est supprimé."; exit 2
fi
UNIT_FILE="$HOME/.config/systemd/user/$UNIT.service"
ITEMS=("$PREFIX" "$CACHE_DIR")
[ -e "$UNIT_FILE" ] && ITEMS+=("$UNIT_FILE")
if [ -f "$PREFIX/installed-files.txt" ]; then
  while IFS= read -r f; do [ -n "$f" ] && [ "$f" != "$UNIT_FILE" ] && ITEMS+=("$f"); done < "$PREFIX/installed-files.txt"
fi
echo "Seront supprimés :"
for p in "${ITEMS[@]}"; do { [ -e "$p" ] || [ -L "$p" ]; } && printf "  %-80s %s\n" "$p" "$(du -sh "$p" 2>/dev/null | cut -f1)"; done
echo "Conservés : $CONFIG_DIR (réglages, projets, appareils), ~/models, ~/Documents/Madalean$( [ $PURGE = 1 ] && echo ' — sauf confirmation ci-dessous (--purge)')"
if [ $YES = 0 ]; then
  read -r -p "Confirmer la suppression ? [o/N] " a
  [[ "$a" =~ ^[oOyY]$ ]] || { echo "Annulé."; exit 0; }
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user stop "$UNIT.service" 2>/dev/null || true          # KillMode=control-group: the whole tree
  systemctl --user disable "$UNIT.service" 2>/dev/null || true
  systemctl --user reset-failed "$UNIT.service" 2>/dev/null || true
fi
# processes started from the prefix outside the unit (manual `madalean serve`): only binaries of this prefix
for pid in $(pgrep -u "$(id -u)" -f -- "^$PREFIX/" 2>/dev/null); do kill -TERM "$pid" 2>/dev/null || true; done
sleep 1
for pid in $(pgrep -u "$(id -u)" -f -- "^$PREFIX/" 2>/dev/null); do kill -KILL "$pid" 2>/dev/null || true; done
for p in "${ITEMS[@]}"; do case "$p" in */) ;; *) rm -rf -- "$p" ;; esac; done
# directories install.sh created (recorded with a trailing /): removed only when empty, deepest first
for p in $(printf '%s\n' "${ITEMS[@]}" | grep '/$' | sort -r); do rmdir -- "$p" 2>/dev/null || true; done
command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload 2>/dev/null
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" 2>/dev/null
if [ $PURGE = 1 ]; then
  for p in "$CONFIG_DIR" "$HOME/models"; do
    [ -e "$p" ] || continue
    read -r -p "Supprimer aussi $p ($(du -sh "$p" 2>/dev/null | cut -f1)) ? [o/N] " a
    [[ "$a" =~ ^[oOyY]$ ]] && rm -rf -- "$p" && echo "  supprimé : $p"
  done
fi
echo "Madalean a été désinstallé."
