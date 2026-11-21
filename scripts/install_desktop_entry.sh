#!/usr/bin/env bash
# Install the Madalean desktop launcher for the current user (menu entry, icon, madalean:// links).
#
#   scripts/install_desktop_entry.sh [--appimage PATH]   install (default: newest shells/desktop/dist/*.AppImage)
#   scripts/install_desktop_entry.sh --replace-old       also remove the old "Lean AI Station" menu entry
#                                                        (a backup copy is kept, see below)
#   scripts/install_desktop_entry.sh --uninstall         remove what this script installed
#   scripts/install_desktop_entry.sh --dry-run ...       print what would be done
#
# Installs (user-level only, no sudo):
#   ~/.local/opt/madalean/Madalean.AppImage                     (copy of the AppImage)
#   ~/.local/share/applications/madalean.desktop                (menu entry + x-scheme-handler/madalean)
#   ~/.local/share/icons/hicolor/{48,128,256,512}x…/apps/madalean.png and scalable/apps/madalean.svg
# The old entry lean-ai-station.desktop is only touched with --replace-old (backup: ~/.local/share/madalean/backup/).
# Honors XDG_DATA_HOME (useful to test into a temporary directory).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
OPT="${MADALEAN_OPT_DIR:-$HOME/.local/opt/madalean}"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor"
BRAND="$ROOT/shells/branding"
APPIMAGE=""
REPLACE_OLD=0
UNINSTALL=0
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --appimage) APPIMAGE="$2"; shift 2 ;;
    --replace-old) REPLACE_OLD=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --dry-run|--print) DRY=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }
run() { if [ "$DRY" = 1 ]; then printf '+ '; printf '%q ' "$@"; echo; else "$@"; fi; }
write() { # write <file> (content on stdin)
  if [ "$DRY" = 1 ]; then echo "+ write $1:"; sed 's/^/    /'; else cat > "$1"; fi
}

refresh() {
  command -v update-desktop-database >/dev/null && run update-desktop-database "$APPS" 2>/dev/null || true
  command -v gtk-update-icon-cache >/dev/null && run gtk-update-icon-cache -q -t "$ICONS" 2>/dev/null || true
}

if [ "$UNINSTALL" = 1 ]; then
  run rm -f "$APPS/madalean.desktop" "$OPT/Madalean.AppImage"
  for s in 48 128 256 512; do run rm -f "$ICONS/${s}x${s}/apps/madalean.png"; done
  run rm -f "$ICONS/scalable/apps/madalean.svg"
  refresh
  echo "Madalean launcher removed (the old Lean AI Station entry, if any, was not touched)."
  exit 0
fi

if [ -z "$APPIMAGE" ]; then
  APPIMAGE="$(ls -t "$ROOT"/shells/desktop/dist/Madalean-*-x86_64.AppImage 2>/dev/null | head -1 || true)"
  [ -n "$APPIMAGE" ] || die "no AppImage found; build it with scripts/build_appimage.sh or pass --appimage PATH"
fi
[ -f "$APPIMAGE" ] || die "$APPIMAGE does not exist"
[ -f "$BRAND/madalean-icon.svg" ] || die "branding missing: $BRAND"

run mkdir -p "$OPT" "$APPS" "$ICONS/scalable/apps"
run install -m 0755 "$APPIMAGE" "$OPT/Madalean.AppImage.new"
run mv -f "$OPT/Madalean.AppImage.new" "$OPT/Madalean.AppImage"
for s in 48 128 256 512; do
  run mkdir -p "$ICONS/${s}x${s}/apps"
  if [ -f "$BRAND/png/madalean-icon-$s.png" ]; then
    run install -m 0644 "$BRAND/png/madalean-icon-$s.png" "$ICONS/${s}x${s}/apps/madalean.png"
  fi
done
run install -m 0644 "$BRAND/madalean-icon.svg" "$ICONS/scalable/apps/madalean.svg"

write "$APPS/madalean.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Madalean
GenericName=Assistant de preuve Lean 4
GenericName[en]=Lean 4 proving assistant
Comment=Prouver, formaliser et expliquer des théorèmes avec Lean 4
Comment[en]=Prove, formalise and explain theorems with Lean 4
Exec=env APPIMAGELAUNCHER_DISABLE=1 "$OPT/Madalean.AppImage" %u
Icon=madalean
Terminal=false
Categories=Education;Science;Math;
Keywords=Lean;Mathlib;preuve;proof;théorème;theorem;
MimeType=x-scheme-handler/madalean;
StartupWMClass=madalean
StartupNotify=true
DESKTOP

# madalean:// links (QR / pair links) open the shell.
command -v xdg-mime >/dev/null && run xdg-mime default madalean.desktop x-scheme-handler/madalean || true

if [ "$REPLACE_OLD" = 1 ] && [ -f "$APPS/lean-ai-station.desktop" ]; then
  BK="$DATA/madalean/backup"
  run mkdir -p "$BK"
  run mv -f "$APPS/lean-ai-station.desktop" "$BK/lean-ai-station.desktop"
  echo "Old 'Lean AI Station' menu entry moved to $BK/ (restore it by moving it back)."
fi
refresh
echo "Madalean launcher installed: $APPS/madalean.desktop -> $OPT/Madalean.AppImage"
