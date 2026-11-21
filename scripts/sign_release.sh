#!/usr/bin/env bash
# Sign a Madalean release (ARCHITECTURE §16). Usage: scripts/sign_release.sh DIR
#   DIR contains the files to publish (madalean-<version>.tar.gz, AppImage, APK…).
# Writes DIR/SHA256SUMS (sha256 of every file of DIR) and DIR/SHA256SUMS.sig (base64 Ed25519 signature of SHA256SUMS)
# with the private key kept OUTSIDE git: ~/.config/madalean/release-keys/ed25519.pem (or $MADALEAN_RELEASE_KEY).
# Then checks the signature against the public key embedded in madalean/update_checkers/selfupdate.py, and writes
# the signed update channel (ARCHITECTURE §17): $SITE_DIR/updates/stable.json (+ .sig, Ed25519 over the exact bytes),
# SITE_DIR defaults to <repo>/site. Env: MIN_VERSION (oldest version that may update directly), NOTES_URL.
# Never publish a release without SHA256SUMS.sig: installed Madalean versions refuse it.
set -euo pipefail
DIR=${1:?usage: sign_release.sh DIR}
KEY=${MADALEAN_RELEASE_KEY:-$HOME/.config/madalean/release-keys/ed25519.pem}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$KEY" ] || { echo "missing private key $KEY" >&2; exit 1; }
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
  # shellcheck disable=SC2086
  "$PY" - "$VERSION" "$SITE/updates/stable.json" $files <<'PYEOF'
import datetime, hashlib, json, os, sys
version, out, names = sys.argv[1], sys.argv[2], sys.argv[3:]
base = os.environ.get("RELEASE_URL_BASE", f"https://github.com/raantss18/madalean/releases/download/v{version}")
def kind(n):
    return "server" if n.endswith(".tar.gz") else "appimage" if n.endswith(".AppImage") else "apk" if n.endswith(".apk") else "other"
files = [{"name": n, "url": f"{base}/{n}", "sha256": hashlib.sha256(open(n, "rb").read()).hexdigest(),
          "size": os.path.getsize(n), "kind": kind(n)} for n in names]
m = {"version": version, "published": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
     "notes_url": os.environ.get("NOTES_URL", f"https://github.com/raantss18/madalean/releases/tag/v{version}"),
     "files": files, "min_version": os.environ.get("MIN_VERSION", "2.0.0")}
open(out, "w").write(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
PYEOF
  openssl pkeyutl -sign -inkey "$KEY" -rawin -in "$SITE/updates/stable.json" | base64 -w0 > "$SITE/updates/stable.json.sig"
  echo >> "$SITE/updates/stable.json.sig"
  echo "update channel written: $SITE/updates/stable.json (+ .sig)"
fi
cat SHA256SUMS
