#!/usr/bin/env bash
# Build the Madalean desktop shell as an AppImage (shells/desktop, Tauri 2 + system WebKitGTK).
#
#   scripts/build_appimage.sh          release AppImage → shells/desktop/dist/Madalean-<version>-x86_64.AppImage
#   scripts/build_appimage.sh --test   run the Rust unit tests only
#
# Requirements (Arch names): rust ≥ 1.80, webkit2gtk-4.1, gtk3, libsoup3, librsvg, patchelf, fuse2 (to run it),
# tauri-cli 2 (`cargo install tauri-cli --version "^2" --locked`). Pinned versions: shells/desktop/src-tauri/Cargo.lock.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/shells/desktop"
DIST="$APP/dist"
die() { echo "error: $*" >&2; exit 1; }

cd "$APP/src-tauri"
if [ "${1:-}" = "--test" ]; then exec cargo test --locked; fi
command -v cargo >/dev/null || die "cargo not found"
cargo tauri --version >/dev/null 2>&1 || die "tauri-cli missing: cargo install tauri-cli --version '^2' --locked"
pkg-config --exists webkit2gtk-4.1 || die "webkit2gtk-4.1 development files missing"

# Icons from the branding sources (kept in sync, never edited by hand).
B="$ROOT/shells/branding/madalean-icon.svg"
if command -v rsvg-convert >/dev/null; then
  rsvg-convert -w 32 -h 32 "$B" -o icons/32x32.png
  rsvg-convert -w 128 -h 128 "$B" -o icons/128x128.png
  rsvg-convert -w 256 -h 256 "$B" -o icons/128x128@2x.png
  rsvg-convert -w 512 -h 512 "$B" -o icons/icon.png
fi

# Ed25519 public key of the update channel, embedded by build.rs. Source of truth: PUBLIC_KEY in
# madalean/update_checkers/selfupdate.py (the private key file may be encrypted: never read, no passphrase asked).
if [ -z "${MADALEAN_UPDATE_PUBKEY:-}" ]; then
  MADALEAN_UPDATE_PUBKEY="$(python3 -c 'import re,sys,base64
m = re.search(r"PUBLIC_KEY\s*=\s*bytes\.fromhex\(\"([0-9a-fA-F]{64})\"\)", open(sys.argv[1]).read())
print(base64.b64encode(bytes.fromhex(m.group(1))).decode() if m else "")' "$ROOT/madalean/update_checkers/selfupdate.py")"
  export MADALEAN_UPDATE_PUBKEY
fi
[ -n "$MADALEAN_UPDATE_PUBKEY" ] || die "no update public key (PUBLIC_KEY in selfupdate.py or MADALEAN_UPDATE_PUBKEY)"
echo "update public key: $MADALEAN_UPDATE_PUBKEY"

cargo test --locked -q
# NO_STRIP: linuxdeploy's bundled strip is too old for current Arch libraries (.relr.dyn sections).
NO_STRIP=true APPIMAGE_EXTRACT_AND_RUN=1 cargo tauri build --bundles appimage -- --locked
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)"
SRC="$(ls -t target/release/bundle/appimage/*.AppImage | head -1)"
mkdir -p "$DIST"
OUT="$DIST/Madalean-$VERSION-x86_64.AppImage"
cp "$SRC" "$OUT"
chmod +x "$OUT"
(cd "$DIST" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256")
echo
echo "AppImage: $OUT"
echo "Size:     $(du -h "$OUT" | cut -f1)  ($(stat -c %s "$OUT") bytes)"
echo "SHA-256:  $(cut -d' ' -f1 "$OUT.sha256")"
echo "Binary:   $(du -h target/release/madalean | cut -f1) (target/release/madalean)"
