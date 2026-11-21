#!/usr/bin/env bash
# Builds the web UI into madalean/static/ (committed, so installing Madalean needs no Node).
# Usage: web/build.sh            (installs exact locked deps with `npm ci` when node_modules is missing)
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
if [ ! -d node_modules ]; then npm ci --no-audit --no-fund; fi
npx svelte-check --tsconfig ./tsconfig.json --threshold error
npx vite build
node scripts/compress.mjs ../madalean/static
echo "OK: built into $(cd ../madalean/static && pwd)"
