#!/usr/bin/env bash
# Reproducible build of madalean-net (static, no cgo). Output: dist/madalean-net/madalean-net-linux-amd64 (+ .sha256)
#   net/build.sh [OUT_DIR]
# Same Go version + same go.sum => same bytes (checked: two builds give the same SHA-256). The SHA-256 of the
# release binary is recorded in madalean/deps/manifest.toml ([components.madalean-net]).
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-../dist/madalean-net}"
mkdir -p "$OUT"
export CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOFLAGS="-mod=readonly -modcacherw" GOTOOLCHAIN="${GOTOOLCHAIN:-local}"
go build -trimpath -buildvcs=false -ldflags="-s -w -buildid=" -o "$OUT/madalean-net-linux-amd64" .
(cd "$OUT" && sha256sum madalean-net-linux-amd64 > madalean-net-linux-amd64.sha256 && cat madalean-net-linux-amd64.sha256)
echo "go: $(go env GOVERSION)"
