#!/usr/bin/env bash
# Sign a Madalean release (ARCHITECTURE §16). Usage: scripts/sign_release.sh DIR
#   DIR contains the files to publish (madalean-<version>.tar.gz, AppImage, APK…).
# Writes DIR/SHA256SUMS (sha256 of every file of DIR) and DIR/SHA256SUMS.sig (base64 Ed25519 signature of SHA256SUMS)
# with the private key kept OUTSIDE git: ~/.config/madalean/release-keys/ed25519.pem (or $MADALEAN_RELEASE_KEY).
# Then checks the signature against the public key embedded in madalean/update_checkers/selfupdate.py, and writes
# the signed update channel (ARCHITECTURE §17): $SITE_DIR/updates/stable.json (+ .sig, Ed25519 over the exact bytes),
# SITE_DIR defaults to <repo>/site, written by scripts/make_update_manifest.py (single format). Env: MIN_VERSION
# (oldest version that may update directly), NOTES_URL, NOTES_FR, NOTES_EN, RELEASE_URL_BASE, APK_CERT_SHA256.
# Never publish a release without SHA256SUMS.sig: installed Madalean versions refuse it.
set -euo pipefail
DIR=${1:?usage: sign_release.sh DIR}
KEY=${MADALEAN_RELEASE_KEY:-$HOME/.config/madalean/release-keys/ed25519.pem}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$KEY" ] || { echo "missing private key $KEY" >&2; exit 1; }
# S-H review (docs/SECURITY.md F7): the key that every installed Madalean trusts must not sit unencrypted next to
# the running server (whose Jupyter kernels run arbitrary code as the same user). Keep it encrypted
# (openssl pkey -in ed25519.pem -aes256 -out ed25519.enc.pem) and/or off this machine.
case "$(realpath "$KEY")" in
  "$HOME"/.config/madalean/*) LOC_BAD=1 ;; *) LOC_BAD=0 ;;
esac
if ! grep -q "ENCRYPTED" "$KEY" || [ "$LOC_BAD" = 1 ]; then
  echo "WARNING: release key $KEY is $( grep -q ENCRYPTED "$KEY" && echo encrypted || echo NOT encrypted )" \
       "and $( [ "$LOC_BAD" = 1 ] && echo "inside Madalean's config dir" || echo "outside the config dir" )." >&2
  [ "${MADALEAN_ALLOW_WEAK_RELEASE_KEY:-0}" = 1 ] || {
    echo "refused: encrypt it and move it out of ~/.config/madalean (or set MADALEAN_ALLOW_WEAK_RELEASE_KEY=1)" >&2
    exit 2; }
fi
cd "$DIR"
rm -f SHA256SUMS SHA256SUMS.sig
files=$(find . -maxdepth 1 -type f ! -name 'SHA256SUMS*' -printf '%f\n' | sort)
[ -n "$files" ] || { echo "no file to sign in $DIR" >&2; exit 1; }
# shellcheck disable=SC2086
sha256sum $files > SHA256SUMS
openssl pkeyutl -sign -inkey "$KEY" -rawin -in SHA256SUMS | base64 -w0 > SHA256SUMS.sig
echo >> SHA256SUMS.sig
PY=${PYTHON:-$ROOT/.venv/bin/python}
[ -x "$PY" ] || PY=python3
PYTHONPATH="$ROOT" "$PY" -c '
import sys
from madalean.update_checkers.selfupdate import PUBLIC_KEY, signature_valid
ok = signature_valid(PUBLIC_KEY, open("SHA256SUMS", "rb").read(), open("SHA256SUMS.sig").read())
print("signature OK (embedded public key)" if ok else "signature does NOT match the embedded public key")
sys.exit(0 if ok else 1)'
VERSION=$(printf '%s\n' $files | sed -n 's/^madalean-\(.*\)\.tar\.gz$/\1/p' | head -1)
if [ -n "$VERSION" ]; then
  SITE=${SITE_DIR:-$ROOT/site}
  mkdir -p "$SITE/updates"
  # The ONE producer of the channel format (docs/SITE.md §3, docs/SHELLS.md "Updates"): signed `channel` field included.
  BASE=${RELEASE_URL_BASE:-https://github.com/raantss18/madalean/releases/download/v$VERSION}
  # shellcheck disable=SC2086
  "$PY" "$ROOT/scripts/make_update_manifest.py" --channel stable --version "$VERSION" --base-url "$BASE" \
    --notes-url "${NOTES_URL:-https://github.com/raantss18/madalean/releases/tag/v$VERSION}" \
    --min-version "${MIN_VERSION:-2.0.0}" --notes-fr "${NOTES_FR:-}" --notes-en "${NOTES_EN:-}" \
    --apk-cert "${APK_CERT_SHA256:-0d43426ba9682f791707ee3233361c369c8ebec3f1209c6e000d7322936fc544}" \
    --sums --key "$KEY" --out "$SITE/updates" $files >/dev/null
  echo "update channel written: $SITE/updates/stable.json (+ .sig)"
fi
cat SHA256SUMS
