#!/usr/bin/env bash
# Build « Madalean Server », the host's own desktop app (DECISIONS D50), for the server archive.
#
#   scripts/build_host_app.sh [--out DIR]      default dist/host-app → DIR/madalean-server + DIR/madalean-server.sha256
#
# It is the desktop shell's binary (shells/desktop, Tauri 2), built once by the release pipeline: users never need
# cargo. At run time it uses the system's webkit2gtk-4.1 + GTK 3 (install_host_app.sh checks them with ldd and falls
# back to a browser window). Same binary as the AppImage client; installed under the name `madalean-server`, it starts
# in host mode (--host). scripts/build_installer.sh puts DIR into madalean-server.tar.gz (madalean/dist/host-app/), so
# install.sh, the .run and the in-app self-update all install it. Build deps (Arch): rust, webkit2gtk-4.1, gtk3,
# libsoup3, librsvg (docs/SHELLS.md). The update public key is embedded as for the AppImage (unused in host mode).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist/host-app"
while [ $# -gt 0 ]; do case "$1" in
  --out) shift; OUT="${1:?}" ;;
  -h|--help) sed -n 2,11p "$0"; exit 0 ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac; shift; done
command -v cargo >/dev/null || { echo "cargo is needed to build the host app (release machine only)" >&2; exit 1; }
( cd "$ROOT/shells/desktop/src-tauri" && cargo build --release --locked --bin madalean )
BIN="$ROOT/shells/desktop/src-tauri/target/release/madalean"
mkdir -p "$OUT"
install -m 0755 "$BIN" "$OUT/madalean-server.tmp" && mv -f "$OUT/madalean-server.tmp" "$OUT/madalean-server"
( cd "$OUT" && sha256sum madalean-server > madalean-server.sha256 )
# Sanity (no window is opened here): every library it links against is present on the build machine.
if command -v ldd >/dev/null && ldd "$OUT/madalean-server" | grep -q 'not found'; then
  echo "warning: missing libraries on this machine:" >&2; ldd "$OUT/madalean-server" | grep 'not found' >&2
fi
echo "host app: $OUT/madalean-server ($(du -h "$OUT/madalean-server" | cut -f1), sha256 $(cut -d' ' -f1 "$OUT/madalean-server.sha256"))"
