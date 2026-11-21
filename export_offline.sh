#!/usr/bin/env bash
# export_offline.sh — pack an installed Madalean prefix for an OFFLINE install on another machine (Linux x86_64).
#
#   ./export_offline.sh DEST_DIR [--prefix DIR] [--with-models] [--with-workspaces]
#
# DEST_DIR receives: madalean/ (the installed version: code, web UI, locks, manifest, install.sh), downloads/ (every
# verified component file: micromamba, elan, llama.cpp, fonts, madalean-net), pkgs/ (the conda packages of the
# locked env), tectonic/ (the pinned TeX bundle cache), optionally models/ (~/models GGUF + .sha256) and
# workspaces/ + toolchains/ (built Lean workspaces). On the target:  DEST_DIR/madalean/install.sh --offline DEST_DIR
# Every file is checked again against the manifest SHA-256 / lock hashes during the offline install.
set -euo pipefail
DEST="${1:?usage: export_offline.sh DEST_DIR [--prefix DIR] [--with-models] [--with-workspaces]}"; shift
PREFIX="${MADALEAN_HOME:-$HOME/.local/share/madalean}"; MODELS=0; WS=0
while [ $# -gt 0 ]; do case "$1" in
  --prefix) shift; PREFIX="$1" ;;
  --with-models) MODELS=1 ;;
  --with-workspaces) WS=1 ;;
  *) echo "unknown option $1"; exit 2 ;;
esac; shift; done
[ -d "$PREFIX/current/madalean/deps" ] || { echo "no installed Madalean in $PREFIX"; exit 1; }
mkdir -p "$DEST"; DEST="$(cd "$DEST" && pwd)"
cp -a "$(readlink -f "$PREFIX/current")/." "$DEST/madalean/" 2>/dev/null || { mkdir -p "$DEST/madalean"; cp -a "$(readlink -f "$PREFIX/current")/." "$DEST/madalean/"; }
mkdir -p "$DEST/downloads"
find "$PREFIX/downloads" -maxdepth 1 -type f ! -name '*.part' -exec cp -a {} "$DEST/downloads/" \;
[ -f "$PREFIX/components/madalean-net/current/madalean-net" ] && \
  cp -a "$PREFIX/components/madalean-net/current/madalean-net" "$DEST/downloads/madalean-net-linux-amd64"
if [ -d "$PREFIX/downloads/pkgs" ]; then
  mkdir -p "$DEST/pkgs"
  (cd "$PREFIX/downloads/pkgs" && find . -type f \( -name '*.conda' -o -name '*.tar.bz2' \) -exec cp --parents -a {} "$DEST/pkgs/" \;)
fi
[ -d "$PREFIX/tectonic/bundles" ] && { mkdir -p "$DEST/tectonic"; cp -a "$PREFIX/tectonic/bundles" "$DEST/tectonic/"; }
if [ $MODELS = 1 ]; then
  mkdir -p "$DEST/models"; cp -a "$HOME"/models/*.gguf "$HOME"/models/*.gguf.sha256 "$DEST/models/" 2>/dev/null || true
fi
if [ $WS = 1 ] && [ -d "$PREFIX/workspaces" ]; then
  mkdir -p "$DEST/workspaces" "$DEST/toolchains"
  for w in "$PREFIX"/workspaces/*/; do
    w="${w%/}"; cp -a "$w" "$DEST/workspaces/"
    tcd=$(sed 's|/|--|; s|:|---|' "$w/lean-toolchain")
    [ -d "$PREFIX/elan/toolchains/$tcd" ] && cp -a "$PREFIX/elan/toolchains/$tcd" "$DEST/toolchains/"
  done
fi
{ echo "Madalean offline export — $(date -Is) — from $PREFIX"; du -sh "$DEST"/* ; du -sh "$DEST" | tail -1; } | tee "$DEST/SIZES.txt"
echo "Install on the target: $DEST/madalean/install.sh --offline $DEST"
