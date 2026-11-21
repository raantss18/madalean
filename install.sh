#!/usr/bin/env bash
# install.sh — Madalean 2.0, self-contained (ARCHITECTURE §18). One command, idempotent, resumable.
#
# Everything goes into ONE prefix (default ~/.local/share/madalean): Python + JupyterLab + poppler + tectonic + git
# (micromamba env from a conda-lock file, SHA-256 of every package checked), TeX bundle (offline after install),
# fonts, elan + Lean workspaces, llama.cpp (prebuilt, SHA-256), madalean-net (embedded Tailscale node), the web UI and
# Madalean itself. Outside the prefix: the systemd user unit, the desktop entry, ~/.config/madalean (settings) and
# ~/models (existing models are reused, never moved). Needs: Linux x86_64, bash, curl, tar, coreutils. Nothing else:
# no sudo, no system Python, no compiler. GPU: the NVIDIA driver only (no CUDA toolkit).
#
#   ./install.sh [options]
#     --prefix DIR        install prefix (default ~/.local/share/madalean = MADALEAN_HOME)
#     --config-dir DIR    settings/data directory (default ~/.config/madalean)
#     --cache-dir DIR     cache directory (default ~/.cache/madalean)
#     --unit-name NAME    systemd user unit name (default madalean) — tests use a throw-away name
#     --no-systemd        do not install/start the unit       --no-desktop   no menu entry
#     --cpu | --gpu       llama.cpp CPU build / CUDA build (default: CUDA when the driver supports it)
#     --offline DIR       install from an export made by export_offline.sh (no network)
#     --no-models         skip the model downloads (≈ 15 GB); existing ~/models files are always reused
#     --no-workspaces     skip the Lean workspaces             --build-workspace  build lean-current if none found
#     --build-net         build madalean-net from net/ with the local Go (must give the pinned SHA-256)
#     --port N --remote-port N   listeners written into the unit (default 11500 / 11501)
#     --serve-args "…"    extra arguments for `madalean serve` in the unit (e.g. "--demo" for tests)
set -euo pipefail
T0=$(date +%s)
SRC="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${MADALEAN_HOME:-$HOME/.local/share/madalean}"
CONFIG_DIR="$HOME/.config/madalean"; CACHE_DIR="$HOME/.cache/madalean"; UNIT=madalean
SYSTEMD=1; DESKTOP=1; VARIANT=auto; OFFLINE=""; MODELS=1; WORKSPACES=1; BUILD_WS=0; BUILD_NET=0
PORT=11500; RPORT=11501; SERVE_ARGS=""
while [ $# -gt 0 ]; do case "$1" in
  --prefix) shift; PREFIX="${1:?}" ;;
  --config-dir) shift; CONFIG_DIR="${1:?}" ;;
  --cache-dir) shift; CACHE_DIR="${1:?}" ;;
  --unit-name) shift; UNIT="${1:?}" ;;
  --no-systemd) SYSTEMD=0 ;;
  --no-desktop) DESKTOP=0 ;;
  --cpu) VARIANT=cpu ;;
  --gpu) VARIANT=auto ;;
  --offline) shift; OFFLINE="$(cd "${1:?}" && pwd)" ;;
  --no-models) MODELS=0 ;;
  --no-workspaces) WORKSPACES=0 ;;
  --build-workspace) BUILD_WS=1 ;;
  --build-net) BUILD_NET=1 ;;
  --port) shift; PORT="${1:?}" ;;
  --remote-port) shift; RPORT="${1:?}" ;;
  --serve-args) shift; SERVE_ARGS="${1:-}" ;;
  -h|--help) sed -n 2,25p "$0"; exit 0 ;;
  *) echo "Option inconnue : $1 (voir --help)"; exit 2 ;;
esac; shift; done
[[ "$UNIT" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "Nom d'unité invalide : $UNIT"; exit 2; }
mkdir -p "$PREFIX" "$CONFIG_DIR" "$CACHE_DIR"
PREFIX="$(cd "$PREFIX" && pwd)"; CONFIG_DIR="$(cd "$CONFIG_DIR" && pwd)"; CACHE_DIR="$(cd "$CACHE_DIR" && pwd)"
export MADALEAN_HOME="$PREFIX"
step() { printf '\n==> %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
LOG="$PREFIX/install.log"; : >> "$LOG"
RECORD="$PREFIX/installed-files.txt"       # files created OUTSIDE the prefix (read by uninstall.sh)
record() { grep -qxF -- "$1" "$RECORD" 2>/dev/null || echo "$1" >> "$RECORD"; }

step "1/9 Vérifications"
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || { echo "Madalean s'installe sur Linux x86_64."; exit 1; }
for c in tar sha256sum; do have "$c" || { echo "Commande manquante : $c"; exit 1; }; done
[ -n "$OFFLINE" ] || have curl || { echo "curl est nécessaire (ou --offline DIR)."; exit 1; }
echo "Préfixe : $PREFIX   (config : $CONFIG_DIR, unité : $UNIT.service)"
df -h "$PREFIX" | tail -1

# ------------------------------------------------------------------ Madalean itself (versions/<v> + current)
step "2/9 Madalean (code + interface web)"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SRC/madalean/__init__.py")
DEST="$PREFIX/versions/$VERSION"
if [ "$SRC" != "$(readlink -f "$DEST" 2>/dev/null)" ]; then
  rm -rf "$DEST.tmp"; mkdir -p "$DEST.tmp"
  ( cd "$SRC" && tar --exclude='__pycache__' --exclude='*.pyc' --exclude='site/_site' --exclude='site/_site_report.json' \
      -cf - madalean bin scripts packaging LICENSE NOTICE $( [ -d site ] && echo site ) \
      $( [ -d docs/manual ] && echo docs/manual ) \
      README.md README.en.md install.sh uninstall.sh export_offline.sh $( [ -d data ] && echo data ) \
      $( [ -d net ] && echo net ) $( [ -d dist/madalean-net ] && echo dist/madalean-net ) ) | tar -C "$DEST.tmp" -xf -
  [ -f "$DEST.tmp/madalean/static/index.html" ] || { echo "Interface web absente de madalean/static."; exit 1; }
  rm -rf "$DEST.old"; [ -d "$DEST" ] && mv "$DEST" "$DEST.old"
  mv "$DEST.tmp" "$DEST"; rm -rf "$DEST.old"
fi
ln -sfn "versions/$VERSION" "$PREFIX/.current.new" && mv -T "$PREFIX/.current.new" "$PREFIX/current"
APP="$PREFIX/current"
echo "Madalean $VERSION → $DEST"

# ------------------------------------------------------------------ micromamba + main env (bootstrap in bash)
toml() { # toml COMPONENT KEY  (flat keys of [components.X] in the manifest)
  awk -v sec="[components.$1]" -v key="$2" '
    $0==sec {on=1; next} /^\[/ {on=0}
    on && $1==key { sub(/^[^=]*= *"?/, ""); sub(/"? *(#.*)?$/, ""); print; exit }' "$APP/madalean/deps/manifest.toml"; }
fetch() { # fetch URL SHA256 NAME → $PREFIX/downloads/NAME (resumed, verified)
  local url=$1 sha=$2 name=$3 f="$PREFIX/downloads/$3"
  mkdir -p "$PREFIX/downloads"
  if [ -f "$f" ] && echo "$sha  $f" | sha256sum -c --status; then return 0; fi
  if [ -n "$OFFLINE" ] && [ -f "$OFFLINE/downloads/$name" ]; then cp "$OFFLINE/downloads/$name" "$f"
  elif [ -n "$OFFLINE" ]; then echo "Absent de l'export hors ligne : $name"; exit 1
  else curl -fsSL --retry 4 -C - -o "$f.part" "$url" && mv "$f.part" "$f"; fi
  echo "$sha  $f" | sha256sum -c --status || { rm -f "$f"; echo "Empreinte SHA-256 incorrecte : $name"; exit 1; }
}
step "3/9 Environnement (micromamba + paquets verrouillés)"
MM_URL=$(toml micromamba url); MM_SHA=$(toml micromamba sha256)
fetch "$MM_URL" "$MM_SHA" "micromamba-linux-64"
MM="$PREFIX/downloads/micromamba-linux-64"; chmod +x "$MM"
LOCK="$APP/madalean/deps/locks/main.conda-lock.yml"
H12=$(sha256sum "$LOCK" | cut -c1-12)
ENVDIR="$PREFIX/envs/main-$H12"
if [ ! -e "$ENVDIR/.madalean-complete" ]; then
  mkdir -p "$PREFIX/mamba" "$PREFIX/downloads/pkgs"
  cp "$LOCK" "$PREFIX/mamba/main.conda-lock.yml"
  [ -n "$OFFLINE" ] && [ -d "$OFFLINE/pkgs" ] && cp -a "$OFFLINE/pkgs/." "$PREFIX/downloads/pkgs/"
  [ -d "$ENVDIR/conda-meta" ] || rm -rf "$ENVDIR"
  env -u CONDA_PREFIX -u CONDA_DEFAULT_ENV -u CONDA_EXE -u CONDA_SHLVL -u MAMBA_EXE -u PYTHONPATH -u PYTHONHOME \
    MAMBA_ROOT_PREFIX="$PREFIX/mamba" CONDA_PKGS_DIRS="$PREFIX/downloads/pkgs" MAMBA_NO_BANNER=1 \
    "$MM" create -y --no-rc -p "$ENVDIR" -f "$PREFIX/mamba/main.conda-lock.yml" ${OFFLINE:+--offline} >>"$LOG" 2>&1 \
    || { echo "Échec de micromamba (voir $LOG)"; tail -20 "$LOG"; exit 1; }
fi
PY="$ENVDIR/bin/python"
DEPS() { env -u PYTHONHOME -u CONDA_PREFIX PYTHONNOUSERSITE=1 PYTHONPATH="$APP" MADALEAN_HOME="$PREFIX" \
           "$PY" -m madalean.deps "$@"; }
OFF=(); [ -n "$OFFLINE" ] && OFF=(--offline --offline-dir "$OFFLINE/downloads" --offline-dir "$OFFLINE")

step "4/9 Composants vérifiés (SHA-256) : micromamba, env, polices, TeX, elan, llama.cpp, madalean-net"
if [ -n "$OFFLINE" ] && [ -d "$OFFLINE/tectonic" ] && [ ! -d "$PREFIX/tectonic/bundles" ]; then
  mkdir -p "$PREFIX/tectonic" && cp -a "$OFFLINE/tectonic/." "$PREFIX/tectonic/"
fi
NETARGS=(); [ $BUILD_NET = 1 ] && NETARGS=(--build-net)
set +e
DEPS install micromamba env fonts tex-bundle elan llama.cpp madalean-net --variant "$VARIANT" "${OFF[@]}" \
  "${NETARGS[@]}" 2>&1 | grep --line-buffered -v ': download [0-9]' | tee -a "$LOG"
rc=${PIPESTATUS[0]}
set -e
[ "$rc" = 0 ] || { echo "Un composant n'a pas pu être installé (voir $LOG)."; exit 1; }

# ------------------------------------------------------------------ Lean workspaces
step "5/9 Espaces Lean"
if [ $WORKSPACES = 1 ]; then
  if [ -n "$OFFLINE" ] && [ -d "$OFFLINE/workspaces" ]; then
    DEPS import-workspaces --toolchains "$OFFLINE/toolchains" "$OFFLINE/workspaces" | tee -a "$LOG"
  else
    DEPS import-workspaces "$SRC/workspaces" | tee -a "$LOG"
  fi
  if [ ! -d "$PREFIX/workspaces/lean-current" ] && [ $BUILD_WS = 1 ]; then
    env PYTHONPATH="$APP" MADALEAN_HOME="$PREFIX" "$PY" "$APP/scripts/updater.py" install-mathlib v4.34.1 | tee -a "$LOG"
  elif [ ! -d "$PREFIX/workspaces/lean-current" ]; then
    echo "(Aucun espace Lean construit trouvé : relancez avec --build-workspace — ≈ 5 Go, réseau requis.)"
  fi
else
  echo "(ignoré : --no-workspaces)"
fi

# ------------------------------------------------------------------ models (~/models, reused, never moved)
step "6/9 Modèles d'IA (SHA-256)"
if [ $MODELS = 1 ]; then
  need=()
  for pair in "Q4_K_M:Goedel-Prover-V2-8B.Q4_K_M.gguf" "formalizer:Goedel-Formalizer-V2-8B.Q4_K_M.gguf" \
              "explainer:Qwen3-8B-Q4_K_M.gguf"; do
    f="$HOME/models/${pair#*:}"
    if [ -f "$f" ] && [ -f "$f.sha256" ]; then echo "Réutilisé : $f"; else need+=("${pair%%:*}"); fi
  done
  if ((${#need[@]})); then
    [ -n "$OFFLINE" ] && [ -d "$OFFLINE/models" ] && mkdir -p "$HOME/models" && cp -n "$OFFLINE"/models/* "$HOME/models/"
    PATH="$ENVDIR/bin:$PATH" "$APP/scripts/download_model.sh" "${need[@]}"
  fi
else
  echo "(ignoré : --no-models)"
fi

# ------------------------------------------------------------------ systemd user unit
step "7/9 Service ($UNIT.service)"
UNIT_FILE="$HOME/.config/systemd/user/$UNIT.service"
if [ $SYSTEMD = 1 ] && have systemctl; then
  mkdir -p "$(dirname "$UNIT_FILE")"
  sed -e "s|@PREFIX@|$PREFIX|g" -e "s|@CONFIG@|$CONFIG_DIR|g" -e "s|@CACHE@|$CACHE_DIR|g" \
      -e "s|@ARGS@|--port $PORT --remote-port $RPORT $SERVE_ARGS|g" "$APP/packaging/madalean.service" > "$UNIT_FILE"
  record "$UNIT_FILE"
  systemctl --user daemon-reload
  systemctl --user enable "$UNIT.service" >/dev/null 2>&1 || true
  systemctl --user restart "$UNIT.service" && echo "Service $UNIT actif." || echo "⚠️  systemctl --user indisponible."
else
  echo "(service non installé : lancez $APP/bin/madalean serve)"
fi

# ------------------------------------------------------------------ desktop entry
step "8/9 Menu"
if [ $DESKTOP = 1 ]; then
  APPIMG="$(ls -t "$SRC"/shells/desktop/dist/Madalean-*-x86_64.AppImage 2>/dev/null | head -1 || true)"
  DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
  if [ -n "$APPIMG" ] && [ -x "$SRC/scripts/install_desktop_entry.sh" ]; then
    OPT="${MADALEAN_OPT_DIR:-$HOME/.local/opt/madalean}"
    [ -d "$(dirname "$OPT")" ] || record "$(dirname "$OPT")/"     # directories we create: removed if empty
    [ -d "$OPT" ] || record "$OPT/"
    "$SRC/scripts/install_desktop_entry.sh" --appimage "$APPIMG" >/dev/null && {
      record "$DATA/applications/madalean.desktop"; record "${MADALEAN_OPT_DIR:-$HOME/.local/opt/madalean}/Madalean.AppImage"
      for s in 48 128 256 512; do record "$DATA/icons/hicolor/${s}x${s}/apps/madalean.png"; done
      record "$DATA/icons/hicolor/scalable/apps/madalean.svg"; echo "Menu : Madalean (client de bureau)."; }
  else
    D="$DATA/applications/$UNIT.desktop"; mkdir -p "$(dirname "$D")"
    printf '[Desktop Entry]\nType=Application\nName=Madalean\nComment=Lean 4 proving assistant\nExec=xdg-open http://127.0.0.1:%s/\nIcon=applications-science\nCategories=Education;Science;Math;\nTerminal=false\n' "$PORT" > "$D"
    record "$D"; echo "Menu : $D (ouvre http://127.0.0.1:$PORT/)"
  fi
fi

# ------------------------------------------------------------------ summary
step "9/9 Contrôle"
DEPS health | tee -a "$LOG" || true
if [ $SYSTEMD = 1 ] && have systemctl; then
  for _ in $(seq 1 100); do curl -fs "http://127.0.0.1:$PORT/api/hello" >/dev/null 2>&1 && break; sleep 0.2; done
  curl -fs "http://127.0.0.1:$PORT/api/hello" && echo || echo "⚠️  Le serveur ne répond pas encore : journalctl --user -u $UNIT"
fi
echo
echo "Installé en $(( $(date +%s) - T0 )) s — $(du -sh "$PREFIX" | cut -f1) dans $PREFIX"
echo "Étape suivante : ouvrez http://127.0.0.1:$PORT/ ; pour un téléphone ou un autre PC, suivez le lien de"
echo "connexion Tailscale affiché dans Système → Réseau, puis appairez l'appareil (madalean pair)."
