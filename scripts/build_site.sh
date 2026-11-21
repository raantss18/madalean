#!/usr/bin/env bash
# Build the GitHub Pages site (manual FR/EN, install page, signed update channel) into site/_site and refresh
# docs/manual/index.json (in-app help). Stdlib Python 3.10+; node (any recent version) pre-renders the maths.
#
#   scripts/build_site.sh              build + checks (links, anchors, external URLs, HTML basics, QR codes)
#   scripts/build_site.sh --preview    also the sample publication and the install page with SAMPLE release data,
#                                      then serve on a free localhost port (Ctrl+C to stop)
#   scripts/build_site.sh --ci         as in .github/workflows/pages.yml: fails if docs/manual/index.json was stale
#   scripts/build_site.sh -- ARGS      pass ARGS to site/build.py (see python3 site/build.py --help)
# Format of the manual, the index, the update channel and the publication input: docs/SITE.md.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Python >= 3.10 required" >&2; exit 1; }
command -v node >/dev/null || echo "warning: node not found, maths will be shown as TeX source" >&2
MODE=build; EXTRA=()
while [ $# -gt 0 ]; do case "$1" in
  --preview) MODE=preview ;;
  --ci) MODE=ci ;;
  --) shift; EXTRA=("$@"); break ;;
  -h|--help) sed -n 2,12p "$0"; exit 0 ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac; shift; done
case "$MODE" in
  build) "$PY" "$ROOT/site/build.py" "${EXTRA[@]}" ;;
  ci)
    "$PY" "$ROOT/site/build.py" --report "$ROOT/site/_site_report.json" "${EXTRA[@]}"
    if command -v git >/dev/null && git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
      git -C "$ROOT" diff --exit-code -- docs/manual/index.json \
        || { echo "docs/manual/index.json is stale: run scripts/build_site.sh and commit it" >&2; exit 1; }
    fi ;;
  preview)
    "$PY" "$ROOT/site/build.py" --sample-release --with-sample-publication "${EXTRA[@]}"
    PORT=$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
    echo "serving http://127.0.0.1:$PORT/  (sample publication: /publication-sample/)"
    exec "$PY" -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT/site/_site" ;;
esac
