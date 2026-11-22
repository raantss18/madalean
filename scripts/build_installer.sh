#!/usr/bin/env bash
# Build the self-extracting graphical installer `Madalean-installer.run` (DECISIONS D44, docs/INSTALL.md).
#
#   scripts/build_installer.sh [--tarball FILE] [--out DIR]
#     --tarball FILE   server archive to embed (default: `git archive HEAD` → DIR/madalean-server.tar.gz, which
#                      includes the committed web UI build madalean/static)
#     --out DIR        output directory (default dist/release)
# Output: DIR/Madalean-installer.run (+ DIR/madalean-server.tar.gz when built here). Release asset names are stable
# (no version): the site links to https://github.com/raantss18/madalean/releases/latest/download/<name>.
# Layout of the .run: packaging/installer/header.sh (with the payload's SHA-256 and byte offset filled in) followed
# by an uncompressed tar holding SHA256SUMS + madalean-server.tar.gz. The header verifies both before unpacking.
# Signing: scripts/sign_release.sh DIR signs every file of DIR (SHA256SUMS.sig), the .run included.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist/release"; TARBALL=""
while [ $# -gt 0 ]; do case "$1" in
  --tarball) shift; TARBALL="$(cd "$(dirname "${1:?}")" && pwd)/$(basename "$1")" ;;
  --out) shift; OUT="${1:?}" ;;
  -h|--help) sed -n 2,13p "$0"; exit 0 ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac; shift; done
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
if [ -z "$TARBALL" ]; then
  git -C "$ROOT" diff --quiet HEAD -- . ':!docs/manual/index.json' \
    || echo "warning: uncommitted changes are NOT in the archive (git archive HEAD)" >&2
  git -C "$ROOT" archive --format=tar.gz --prefix=madalean/ -o "$OUT/madalean-server.tar.gz" HEAD
  TARBALL="$OUT/madalean-server.tar.gz"
fi
LIST="$(tar -tzf "$TARBALL")"
grep -q '^[^/]*/install\.sh$' <<<"$LIST" || { echo "$TARBALL has no <top>/install.sh" >&2; exit 1; }
grep -q '^[^/]*/packaging/installer/server\.py$' <<<"$LIST" \
  || { echo "$TARBALL has no packaging/installer/server.py" >&2; exit 1; }
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
cp "$TARBALL" "$STAGE/madalean-server.tar.gz"
( cd "$STAGE" && sha256sum madalean-server.tar.gz > SHA256SUMS \
  && tar --owner=0 --group=0 --numeric-owner --mtime=@0 -cf payload.tar SHA256SUMS madalean-server.tar.gz )
SHA="$(sha256sum "$STAGE/payload.tar" | cut -d' ' -f1)"
python3 - "$ROOT/packaging/installer/header.sh" "$STAGE/header.sh" "$SHA" <<'EOF'
import sys
src, dst, sha = sys.argv[1:4]
h = open(src, encoding="utf-8").read().replace("@PAYLOAD_SHA256@", sha)
# fixed width so that the header length does not depend on the offset written into it
width = 12
h = h.replace("@PAYLOAD_OFFSET@", "0" * width)
size = len(h.encode("utf-8"))
h = h.replace("PAYLOAD_OFFSET=" + "0" * width, "PAYLOAD_OFFSET=" + str(size).ljust(width))
assert len(h.encode("utf-8")) == size
open(dst, "w", encoding="utf-8").write(h)
EOF
RUN="$OUT/Madalean-installer.run"
cat "$STAGE/header.sh" "$STAGE/payload.tar" > "$RUN.tmp"
chmod 755 "$RUN.tmp"; mv "$RUN.tmp" "$RUN"
"$RUN" --check >/dev/null
echo "installer: $RUN ($(du -h "$RUN" | cut -f1), payload sha256 $SHA)"
