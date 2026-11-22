#!/usr/bin/env bash
# Collect the release assets under their STABLE names (DECISIONS D44) into one directory, ready for
# scripts/sign_release.sh DIR and the GitHub release upload. The site never shows a version: it links to
#   https://github.com/raantss18/madalean/releases/latest/download/<name>
# so every release must publish exactly these names:
#   madalean-server.tar.gz        the server (git archive HEAD, web UI build included)       ← host, from source
#   Madalean-installer.run        graphical installer of the host (scripts/build_installer.sh) ← host, recommended
#   Madalean-x86_64.AppImage      desktop client (scripts/build_appimage.sh)                  ← client, Linux PC
#   Madalean-android.apk          Android client, universal (scripts/build_apk.sh)            ← client, phone/tablet
#   Madalean-android-<abi>.apk    per-ABI APKs (arm64-v8a, armeabi-v7a, x86_64), smaller
# (The signed channel stable.json carries the version; updaters never rely on file names.)
#
#   scripts/stage_release.sh [DIR]     default dist/release; missing client builds are reported, not fatal
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="${1:-$ROOT/dist/release}"
mkdir -p "$DIR"
"$ROOT/scripts/build_installer.sh" --out "$DIR"          # also writes madalean-server.tar.gz
APPIMG="$(ls -t "$ROOT"/shells/desktop/dist/Madalean-*x86_64.AppImage 2>/dev/null | grep -v '/Madalean-x86_64.AppImage$' | head -1 || true)"
if [ -n "$APPIMG" ]; then cp "$APPIMG" "$DIR/Madalean-x86_64.AppImage"; else echo "note: no AppImage (scripts/build_appimage.sh)"; fi
APKS="$ROOT/shells/android/dist"
if [ -f "$APKS/madalean-universal-release.apk" ]; then
  cp "$APKS/madalean-universal-release.apk" "$DIR/Madalean-android.apk"
  for abi in arm64-v8a armeabi-v7a x86_64; do
    [ -f "$APKS/madalean-$abi-release.apk" ] && cp "$APKS/madalean-$abi-release.apk" "$DIR/Madalean-android-$abi.apk"
  done
else
  echo "note: no APK (scripts/build_apk.sh)"
fi
ls -la "$DIR"
echo "next: scripts/sign_release.sh $DIR   (then upload every file of $DIR to the GitHub release)"
