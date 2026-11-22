#!/bin/sh
# Madalean-installer.run — Madalean's self-extracting installer (built by scripts/build_installer.sh; DECISIONS D44).
#
#   ./Madalean-installer.run [options] [install.sh options]
#     (no option)     graphical install wizard in your web browser (local page, 127.0.0.1 only); without a graphical
#                     session: the terminal assistant; without a terminal either: the default install
#     --terminal      the terminal assistant of install.sh
#     --yes           no question, default install (install.sh --yes)
#     --check         verify the integrity of this file and exit
#     --extract DIR   verify, then unpack the Madalean sources into DIR and exit
#     --no-browser    graphical wizard without opening a browser (prints the address)
#     -h, --help      this help
# A file downloaded with a browser is not executable: right-click › Properties › Permissions › « Allow executing file
# as program », or `chmod +x Madalean-installer.run`. No sudo, ever.
# The payload (SHA256SUMS + madalean-server.tar.gz) follows this header; its SHA-256 is written below at build time
# and checked before anything is unpacked, then every file is checked against SHA256SUMS.
PAYLOAD_SHA256=@PAYLOAD_SHA256@
PAYLOAD_OFFSET=@PAYLOAD_OFFSET@
set -eu
umask 077
say() { printf '%s\n' "$*"; }
die() { say "$*" >&2; exit 1; }
MODE=auto; EXTRACT=""; NOBROWSER=""
while [ $# -gt 0 ]; do case "$1" in
  --terminal) MODE=terminal ;;
  --yes|-y) MODE=yes ;;
  --check) MODE=check ;;
  --extract) shift; EXTRACT="${1:?}"; MODE=extract ;;
  --no-browser) NOBROWSER=--no-browser ;;
  -h|--help) sed -n 2,15p "$0"; exit 0 ;;
  --) shift; break ;;
  *) break ;;
esac; shift; done
SELF="$0"
case "$SELF" in /*) ;; *) SELF="$(pwd)/$SELF" ;; esac
for c in tail tar sha256sum mktemp; do command -v "$c" >/dev/null 2>&1 || die "Commande manquante / missing command: $c"; done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/madalean-installer.XXXXXX")"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT INT TERM
tail -c +"$((PAYLOAD_OFFSET + 1))" "$SELF" > "$WORK/payload.tar"
GOT="$(sha256sum "$WORK/payload.tar" | cut -d' ' -f1)"
[ "$GOT" = "$PAYLOAD_SHA256" ] || die "Fichier abîmé ou modifié (empreinte SHA-256 incorrecte) : téléchargez-le à nouveau.
Damaged or modified file (wrong SHA-256): download it again."
mkdir "$WORK/p"
tar -xf "$WORK/payload.tar" -C "$WORK/p" SHA256SUMS madalean-server.tar.gz 2>/dev/null \
  || die "Contenu illisible / unreadable content."
( cd "$WORK/p" && sha256sum -c --quiet --strict SHA256SUMS ) >/dev/null 2>&1 \
  || die "Contenu abîmé (SHA256SUMS) : téléchargez le fichier à nouveau. / Damaged content (SHA256SUMS): download it again."
if [ "$MODE" = check ]; then say "OK : intégrité vérifiée / integrity verified ($PAYLOAD_SHA256)"; exit 0; fi
mkdir "$WORK/src"
tar -xzf "$WORK/p/madalean-server.tar.gz" -C "$WORK/src" --strip-components=1 --no-same-owner \
  || die "Archive illisible / unreadable archive."
SRC="$WORK/src"
[ -f "$SRC/install.sh" ] || die "install.sh absent de l'archive / missing from the archive."
if [ "$MODE" = extract ]; then
  mkdir -p "$EXTRACT" && cp -a "$SRC/." "$EXTRACT/" && say "Sources : $EXTRACT"; exit 0
fi

PY=""
for c in python3 python3.13 python3.12 python3.11 python3.10 python3.9 python3.8; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break; fi
done
rc=0
case "$MODE" in
  yes) bash "$SRC/install.sh" --yes "$@" || rc=$? ;;
  terminal) bash "$SRC/install.sh" "$@" || rc=$? ;;
  *)
    gui=0
    if [ -n "$PY" ] && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] || [ -n "$NOBROWSER" ]; } \
       && { command -v xdg-open >/dev/null 2>&1 || [ -n "$NOBROWSER" ]; }; then gui=1; fi
    if [ $gui = 1 ]; then
      "$PY" -I "$SRC/packaging/installer/server.py" --src "$SRC" $NOBROWSER -- "$@" || rc=$?
      if [ $rc = 3 ]; then gui=0; rc=0; say "(Pas de navigateur : assistant dans le terminal. / No browser: terminal assistant.)"; fi
    fi
    if [ $gui = 0 ]; then
      if [ -t 0 ] && [ -t 1 ]; then bash "$SRC/install.sh" "$@" || rc=$?
      else bash "$SRC/install.sh" --yes "$@" || rc=$?; fi
    fi ;;
esac
exit $rc
