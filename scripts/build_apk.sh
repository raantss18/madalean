#!/usr/bin/env bash
# Build the signed release APK of the Madalean Android shell (shells/android).
#
#   scripts/build_apk.sh --new-key   create the release keystore once (outside the repository)
#   scripts/build_apk.sh             build release APKs (universal + one per ABI), verify the signature
#   scripts/build_apk.sh --debug     build the debug APK (cleartext allowed to 10.0.2.2 for the mock server)
#
# Update channel public key: derived at build time from the Ed25519 release key
# (~/.config/madalean/release-keys/ed25519.pem, or $MADALEAN_RELEASE_KEY; override with
# MADALEAN_UPDATE_PUBKEY=<base64 32 bytes>) and embedded with --dart-define. A release build refuses to run
# without it. Only the PUBLIC key enters the APK. Debug builds may also set MADALEAN_UPDATE_CHANNEL=<url of a
# test channel> (ignored by release builds) and BUILD_NAME / BUILD_NUMBER (version) for update tests.
#
# Signing material: ~/.config/madalean/release-keys/ (override with MADALEAN_KEYSTORE_PROPERTIES).
# BACK IT UP: without this keystore no update of the installed app can ever be published.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/shells/android"
KEYDIR="${MADALEAN_KEY_DIR:-$(cd "$(dirname "$0")/.." && pwd)/release-keys}"
export MADALEAN_KEYSTORE_PROPERTIES="${MADALEAN_KEYSTORE_PROPERTIES:-$KEYDIR/keystore.properties}"
FLUTTER="${FLUTTER:-$(command -v flutter || echo "$HOME/development/flutter/bin/flutter")}"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
BT="$(ls -d "$SDK"/build-tools/* 2>/dev/null | sort -V | tail -1)"
PINNED_FLUTTER="3.47.9"
DIST="$APP/dist"
RELEASE_ED25519="${MADALEAN_RELEASE_KEY:-$KEYDIR/ed25519.pem}"

die() { echo "error: $*" >&2; exit 1; }

inside_repo() { case "$(realpath -m "$1")" in "$ROOT"/*) return 0;; *) return 1;; esac; }

new_key() {
  local jks="$KEYDIR/madalean-release.jks"
  inside_repo "$KEYDIR" && die "key directory $KEYDIR is inside the repository"
  [ -e "$jks" ] && die "$jks already exists; refusing to overwrite a release key"
  [ -e "$MADALEAN_KEYSTORE_PROPERTIES" ] && die "$MADALEAN_KEYSTORE_PROPERTIES already exists"
  command -v keytool >/dev/null || die "keytool (JDK 17) not found"
  umask 077
  mkdir -p "$KEYDIR"; chmod 700 "$KEYDIR"
  local pw
  pw="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40)"
  [ "${#pw}" -ge 32 ] || die "could not generate a password"
  # PKCS12: one password for store and key. Passed through the environment, not argv.
  MADALEAN_PW="$pw" keytool -genkeypair -v -storetype PKCS12 -keystore "$jks" \
    -storepass:env MADALEAN_PW -keypass:env MADALEAN_PW -alias madalean \
    -keyalg RSA -keysize 4096 -validity 10000 \
    -dname "CN=Madalean, O=Madalean, C=MG" >/dev/null 2>&1 || die "keytool failed"
  cat > "$MADALEAN_KEYSTORE_PROPERTIES" <<PROPS
# Madalean Android release signing — KEEP SECRET, BACK UP (with madalean-release.jks), NEVER COMMIT.
storeFile=$jks
storePassword=$pw
keyAlias=madalean
keyPassword=$pw
PROPS
  chmod 600 "$jks" "$MADALEAN_KEYSTORE_PROPERTIES"
  echo "Release key created:"
  echo "  $jks"
  echo "  $MADALEAN_KEYSTORE_PROPERTIES"
  MADALEAN_PW="$pw" keytool -list -v -keystore "$jks" -storepass:env MADALEAN_PW -alias madalean 2>/dev/null | grep -E "SHA256:|Valid"
  echo
  echo "BACK UP both files now (e.g. encrypted USB key / password manager)."
  echo "If they are lost, installed apps can no longer be updated (only uninstalled + reinstalled)."
}

update_pubkey() {
  if [ -n "${MADALEAN_UPDATE_PUBKEY:-}" ]; then echo "$MADALEAN_UPDATE_PUBKEY"; return; fi
  [ -f "$RELEASE_ED25519" ] || return 0
  openssl pkey -in "$RELEASE_ED25519" -pubout -outform DER 2>/dev/null | tail -c 32 | base64 -w0
}

define_args() { # $1 = release|debug
  local pk; pk="$(update_pubkey)"
  if [ -z "$pk" ] || [ "$(printf '%s' "$pk" | base64 -d 2>/dev/null | wc -c)" != 32 ]; then
    [ "$1" = release ] && die "no Ed25519 update public key (expected $RELEASE_ED25519 or MADALEAN_UPDATE_PUBKEY)"
    echo "warning: no update public key, updates disabled in this build" >&2
    return 0
  fi
  echo "--dart-define=MADALEAN_UPDATE_PUBKEY=$pk"
  [ "$1" = debug ] && [ -n "${MADALEAN_UPDATE_CHANNEL:-}" ] && echo "--dart-define=MADALEAN_UPDATE_CHANNEL=$MADALEAN_UPDATE_CHANNEL"
  [ -n "${BUILD_NAME:-}" ] && echo "--build-name=$BUILD_NAME"
  [ -n "${BUILD_NUMBER:-}" ] && echo "--build-number=$BUILD_NUMBER"
  return 0
}

check_flutter() {
  [ -x "$FLUTTER" ] || die "flutter not found (set FLUTTER=/path/to/flutter)"
  local v
  v="$("$FLUTTER" --version --machine 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["frameworkVersion"])' || true)"
  [ "$v" = "$PINNED_FLUTTER" ] || echo "warning: Flutter $v, pinned/tested version is $PINNED_FLUTTER" >&2
}

verify() {
  local apk="$1"
  "$BT/apksigner" verify --min-sdk-version 26 "$apk" || die "signature check failed: $apk"
  local certs
  certs="$("$BT/apksigner" verify --print-certs "$apk")"
  echo "$certs" | grep -q "CN=Android Debug" && die "$apk is signed with the DEBUG key"
  echo "$certs" | grep -E "certificate DN|SHA-256 digest"
}

build_release() {
  [ -f "$MADALEAN_KEYSTORE_PROPERTIES" ] || die "no release key at $MADALEAN_KEYSTORE_PROPERTIES (run: $0 --new-key)"
  check_flutter
  cd "$APP"
  "$FLUTTER" pub get >/dev/null
  local defs; mapfile -t defs < <(define_args release)
  [[ "${defs[0]:-}" == --dart-define=MADALEAN_UPDATE_PUBKEY=* ]] || die "no Ed25519 update public key (expected $RELEASE_ED25519)"
  echo "update public key: ${defs[0]#--dart-define=MADALEAN_UPDATE_PUBKEY=}"
  rm -rf "$DIST"; mkdir -p "$DIST"
  "$FLUTTER" build apk --release --split-per-abi "${defs[@]}"
  cp build/app/outputs/flutter-apk/app-*-release.apk "$DIST/"
  "$FLUTTER" build apk --release "${defs[@]}"
  cp build/app/outputs/flutter-apk/app-release.apk "$DIST/madalean-universal-release.apk"
  for f in "$DIST"/app-*-release.apk; do
    mv "$f" "$DIST/madalean-$(basename "$f" | sed 's/^app-//')"
  done
  echo
  echo "== Release APKs ($DIST)"
  for f in "$DIST"/*.apk; do
    printf '%-45s %8s KiB  sha256 %s\n' "$(basename "$f")" "$(( $(stat -c %s "$f") / 1024 ))" "$(sha256sum "$f" | cut -d' ' -f1)"
  done
  echo
  echo "== Signature ($DIST/madalean-universal-release.apk)"
  verify "$DIST/madalean-universal-release.apk"
  for f in "$DIST"/madalean-*-release.apk; do verify "$f" >/dev/null; done
  (cd "$DIST" && sha256sum ./*.apk > SHA256SUMS)
}

build_debug() {
  check_flutter
  cd "$APP"
  "$FLUTTER" pub get >/dev/null
  local defs; mapfile -t defs < <(define_args debug)
  "$FLUTTER" build apk --debug "${defs[@]}"
  ls -la build/app/outputs/flutter-apk/app-debug.apk
}

case "${1:-}" in
  --new-key) new_key ;;
  --debug) build_debug ;;
  ""|--release) build_release ;;
  -h|--help) sed -n '2,10p' "$0" ;;
  *) die "unknown option $1" ;;
esac
