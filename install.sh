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
#   Assistant (S-AL, docs/INSTALL.md): in a terminal, install.sh first checks the machine (hardware, SageMath, TeX Live,
#   Python, elan, Ollama, Tailscale…), shows a recommended plan and lets you accept it or change each item.
#     --yes | -y          no question: the defaults (also when stdin/stdout is not a terminal) — 2.0.0 behaviour
#     --assistant         ask even if stdin is not a terminal (reads /dev/tty)
#     --plan FILE         use a plan written by the assistant or the graphical installer (no question)
#     --dry-run           check the machine and show the plan; install nothing, write nothing
#     --models all|prover|none   local GGUF models (default all; --no-models = none)
#     --sage later|now|system    SageMath: Madalean's copy on first use (default) / now / reuse the system's
#     --tex own|system           LaTeX: tectonic first (default) / an existing TeX Live first
#   The choices are recorded in <config-dir>/setup.json (applied at first start, read by GET /api/setup).
set -euo pipefail
T0=$(date +%s)
SRC="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${MADALEAN_HOME:-$HOME/.local/share/madalean}"
CONFIG_DIR="$HOME/.config/madalean"; CACHE_DIR="$HOME/.cache/madalean"; UNIT=madalean
SYSTEMD=1; DESKTOP=1; VARIANT=auto; OFFLINE=""; MODELS=1; WORKSPACES=1; BUILD_WS=0; BUILD_NET=0
PORT=11500; RPORT=11501; SERVE_ARGS=""
YES=0; ASSIST=auto; PLAN_IN=""; DRY=0; SETS=()
while [ $# -gt 0 ]; do case "$1" in
  --prefix) shift; PREFIX="${1:?}" ;;
  --config-dir) shift; CONFIG_DIR="${1:?}" ;;
  --cache-dir) shift; CACHE_DIR="${1:?}" ;;
  --unit-name) shift; UNIT="${1:?}" ;;
  --no-systemd) SYSTEMD=0 ;;
  --no-desktop) DESKTOP=0 ;;
  --cpu) VARIANT=cpu; SETS+=(--set variant=cpu) ;;
  --gpu) VARIANT=auto; SETS+=(--set variant=auto) ;;
  --offline) shift; OFFLINE="$(cd "${1:?}" && pwd)" ;;
  --no-models) MODELS=0; SETS+=(--set models=none) ;;
  --no-workspaces) WORKSPACES=0; SETS+=(--set workspace=skip) ;;
  --build-workspace) BUILD_WS=1; SETS+=(--set workspace=build) ;;
  --build-net) BUILD_NET=1 ;;
  --port) shift; PORT="${1:?}" ;;
  --remote-port) shift; RPORT="${1:?}" ;;
  --serve-args) shift; SERVE_ARGS="${1:-}" ;;
  -y|--yes) YES=1 ;;
  --assistant) ASSIST=1 ;;
  --plan) shift; PLAN_IN="$(cd "$(dirname "${1:?}")" && pwd)/$(basename "$1")" ;;
  --dry-run) DRY=1 ;;
  --models) shift; SETS+=(--set "models=${1:?}") ;;
  --sage) shift; SETS+=(--set "sage=${1:?}") ;;
  --tex) shift; SETS+=(--set "tex=${1:?}") ;;
  -h|--help) sed -n 2,35p "$0"; exit 0 ;;
  *) echo "Option inconnue : $1 (voir --help)"; exit 2 ;;
esac; shift; done
[[ "$UNIT" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "Nom d'unité invalide : $UNIT"; exit 2; }
step() { printf '\n==> %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# ------------------------------------------------------------------ assistant: machine check + plan (S-AL, D44)
# ONE engine (madalean/deps/assistant.py, stdlib only) behind this terminal assistant, the graphical installer (.run)
# and GET /api/setup. It needs a python3 >= 3.8: the system's now, else Madalean's own right after step 3.
INTERACTIVE=0
if [ -z "$PLAN_IN" ] && [ $YES = 0 ] && [ $DRY = 0 ] && { [ "$ASSIST" = 1 ] || { [ -t 0 ] && [ -t 1 ]; }; }; then
  INTERACTIVE=1
fi
SYSPY=""
for c in python3 python3.13 python3.12 python3.11 python3.10 python3.9 python3.8; do
  if have "$c" && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    SYSPY="$(command -v "$c")"; break
  fi
done
PLAN_FILE="$(mktemp "${TMPDIR:-/tmp}/madalean-plan.XXXXXX")"; trap 'rm -f "$PLAN_FILE"' EXIT
PLANNED=0; PLAN_MODELS=all; PLAN_MODEL_LIST="Q4_K_M formalizer explainer"; PLAN_SAGE=later; PLAN_TEX=own
ENGINE() { local py=$1; shift
  env -u PYTHONHOME -u PYTHONSTARTUP PYTHONNOUSERSITE=1 PYTHONPATH="$SRC" MADALEAN_HOME="$PREFIX" \
    "$py" -m madalean.deps.assistant "$@"; }
plan_with() { # plan_with PYTHON: writes $PLAN_FILE, then sets the plan variables (fixed allow-lists, no eval)
  local py=$1 how=(--defaults) k v rc=0
  if [ -n "$PLAN_IN" ]; then how=(--from "$PLAN_IN")
  elif [ $INTERACTIVE = 1 ]; then how=(--interactive)
  elif [ $DRY = 1 ] && [ $YES = 0 ]; then how=(--recommended); fi
  ENGINE "$py" plan --out "$PLAN_FILE" --prefix "$PREFIX" "${how[@]}" "${SETS[@]}" || rc=$?
  [ $rc = 0 ] || exit $rc
  while IFS='=' read -r k v; do case "$k=$v" in
    PLAN_MODELS=all|PLAN_MODELS=prover|PLAN_MODELS=none) PLAN_MODELS=$v ;;
    PLAN_MODEL_LIST=*) [[ "$v" =~ ^[A-Za-z0-9_\ ]*$ ]] && PLAN_MODEL_LIST=$v ;;
    PLAN_VARIANT=auto|PLAN_VARIANT=cpu) VARIANT=$v ;;
    PLAN_SAGE=later|PLAN_SAGE=now|PLAN_SAGE=system) PLAN_SAGE=$v ;;
    PLAN_TEX=own|PLAN_TEX=system) PLAN_TEX=$v ;;
    PLAN_WORKSPACE=import) WORKSPACES=1; BUILD_WS=0 ;;
    PLAN_WORKSPACE=build) WORKSPACES=1; BUILD_WS=1 ;;
    PLAN_WORKSPACE=skip) WORKSPACES=0 ;;
    PLAN_MODE=auto|PLAN_MODE=online|PLAN_MODE=local) ;;
    *) echo "Plan illisible : $k"; exit 2 ;;
  esac; done < <(ENGINE "$py" vars "$PLAN_FILE")
  if [ "$PLAN_MODELS" = none ]; then MODELS=0; else MODELS=1; fi
  PLANNED=1
}
if [ -n "$SYSPY" ]; then
  [ $INTERACTIVE = 1 ] && step "Assistant d'installation : vérification de la machine"
  plan_with "$SYSPY"
elif [ $DRY = 1 ] || [ -n "$PLAN_IN" ]; then
  echo "python3 (>= 3.8) est nécessaire pour --dry-run et --plan."; exit 1
fi
if [ $DRY = 1 ]; then
  ENGINE "$SYSPY" detect
  echo "Plan (--dry-run : rien n'est installé ni écrit) :"
  ENGINE "$SYSPY" show "$PLAN_FILE"
  if [ $WORKSPACES = 0 ]; then WSTXT=ignorés; elif [ $BUILD_WS = 1 ]; then WSTXT=construire; else WSTXT=importer; fi
  echo "Étapes : 1 vérifications · 2 Madalean -> $PREFIX/versions · 3 environnement verrouillé ·"
  echo "  4 composants (llama.cpp : $VARIANT$([ "$PLAN_SAGE" = now ] && echo ', SageMath' || true)) ·" \
       "5 espaces Lean ($WSTXT) · 6 modèles (${PLAN_MODEL_LIST:-aucun}) · 7 service $UNIT · 8 menu · 9 contrôle"
  if [ $DESKTOP = 1 ]; then
    L=$(bash "$SRC/scripts/install_host_app.sh" --detect --port "$PORT" --binary "$SRC/dist/host-app/madalean-server" | sed -n 's/^LAUNCHER=//p')
    echo "Menu : « Madalean Server » ($L)"
    echo "DRY-RUN hostapp=$L"
  fi
  echo "DRY-RUN models=$PLAN_MODELS variant=$VARIANT sage=$PLAN_SAGE tex=$PLAN_TEX workspaces=$WORKSPACES build=$BUILD_WS"
  exit 0
fi

mkdir -p "$PREFIX" "$CONFIG_DIR" "$CACHE_DIR"
PREFIX="$(cd "$PREFIX" && pwd)"; CONFIG_DIR="$(cd "$CONFIG_DIR" && pwd)"; CACHE_DIR="$(cd "$CACHE_DIR" && pwd)"
export MADALEAN_HOME="$PREFIX"
LOG="$PREFIX/install.log"; : >> "$LOG"
RECORD="$PREFIX/installed-files.txt"       # files created OUTSIDE the prefix (read by uninstall.sh)
record() { grep -qxF -- "$1" "$RECORD" 2>/dev/null || echo "$1" >> "$RECORD"; }

step "1/9 Vérifications"
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || { echo "Madalean s'installe sur Linux x86_64."; exit 1; }
for c in tar sha256sum; do have "$c" || { echo "Commande manquante : $c"; exit 1; }; done
[ -n "$OFFLINE" ] || have curl || { echo "curl est nécessaire (ou --offline DIR)."; exit 1; }
echo "Préfixe : $PREFIX   (config : $CONFIG_DIR, unité : $UNIT.service)"
df -h "$PREFIX" | tail -1
if ! have bwrap; then
  echo "Conseil : bubblewrap (bac à sable de Lean, LaTeX et des calculs) n'est pas installé. À lancer vous-même :"
  case " $(. /etc/os-release 2>/dev/null; echo "${ID:-} ${ID_LIKE:-}") " in
    *" arch "*|*manjaro*|*endeavouros*|*cachyos*) echo "    sudo pacman -S --needed bubblewrap" ;;
    *debian*|*ubuntu*) echo "    sudo apt install bubblewrap" ;;
    *fedora*|*rhel*) echo "    sudo dnf install bubblewrap" ;;
    *suse*) echo "    sudo zypper install bubblewrap" ;;
    *) echo "    (paquet « bubblewrap » de votre distribution)" ;;
  esac
fi

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
      $( [ -d net ] && echo net ) $( [ -d dist/madalean-net ] && echo dist/madalean-net ) \
      $( [ -d dist/host-app ] && echo dist/host-app ) $( [ -d shells/branding ] && echo shells/branding ) ) \
    | tar -C "$DEST.tmp" -xf -
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
[ $PLANNED = 1 ] || plan_with "$PY"          # no system python3: the assistant runs now, with Madalean's own
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
if [ "$PLAN_SAGE" = now ]; then           # optional: a failure is reported, the install goes on (repair from the app)
  set +e
  DEPS install sage "${OFF[@]}" 2>&1 | grep --line-buffered -v ': download [0-9]' | tee -a "$LOG"
  [ "${PIPESTATUS[0]}" = 0 ] || echo "⚠️  SageMath n'a pas pu être installé maintenant ; il le sera au premier calcul (voir $LOG)."
  set -e
elif [ "$PLAN_SAGE" = system ]; then
  echo "SageMath : celui du système sera utilisé (choix enregistré, appliqué au premier démarrage)."
fi

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
    [[ " $PLAN_MODEL_LIST " == *" ${pair%%:*} "* ]] || continue        # not in the plan (--models prover)
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
# ONE entry on the host: « Madalean Server » (D50), the host's own desktop app (shipped prebuilt in the server
# archive, dist/host-app/madalean-server) — else a Chromium-family app window, else the default browser. It replaces
# the old « Madalean » xdg-open entry. The client AppImage is for the OTHER computers: never installed here (the user
# can still add it with scripts/install_desktop_entry.sh).
HOSTAPP_SUMMARY=""
if [ $DESKTOP = 1 ]; then
  HOSTAPP_OUT="$(bash "$APP/scripts/install_host_app.sh" --prefix "$PREFIX" --port "$PORT" --unit "$UNIT" 2>&1)" \
    || echo "⚠️  Entrée de menu non installée."
  printf '%s\n' "$HOSTAPP_OUT" | grep -v '^LAUNCHER=' || true
  case "$(printf '%s\n' "$HOSTAPP_OUT" | sed -n 's/^LAUNCHER=//p')" in
    native)   HOSTAPP_SUMMARY="Ouvrez « Madalean Server » dans le menu des applications." ;;
    browser)  HOSTAPP_SUMMARY="Ouvrez « Madalean Server » dans le menu (fenêtre du navigateur : webkit2gtk-4.1 manque)." ;;
    xdg-open) HOSTAPP_SUMMARY="« Madalean Server » ouvre votre navigateur (webkit2gtk-4.1 et Chromium absents)." ;;
  esac
else
  echo "(ignoré : --no-desktop)"
fi

# ------------------------------------------------------------------ summary
step "9/9 Contrôle"
DEPS health | tee -a "$LOG" || true
if [ $SYSTEMD = 1 ] && have systemctl; then
  for _ in $(seq 1 100); do curl -fs "http://127.0.0.1:$PORT/api/hello" >/dev/null 2>&1 && break; sleep 0.2; done
  curl -fs "http://127.0.0.1:$PORT/api/hello" && echo || echo "⚠️  Le serveur ne répond pas encore : journalctl --user -u $UNIT"
fi
SRC_TAG="install.sh"
[ $INTERACTIVE = 1 ] && SRC_TAG="install.sh (assistant)"
[ $YES = 1 ] && SRC_TAG="install.sh --yes"
[ -n "$PLAN_IN" ] && SRC_TAG="${MADALEAN_INSTALL_SOURCE:-install.sh --plan}"
if ENGINE "$PY" record --config-dir "$CONFIG_DIR" --plan "$PLAN_FILE" --rc 0 --source "$SRC_TAG" --version "$VERSION"; then
  echo "Choix enregistrés : $CONFIG_DIR/setup.json"
else
  echo "⚠️  $CONFIG_DIR/setup.json n'a pas pu être écrit."
fi
echo
echo "Installé en $(( $(date +%s) - T0 )) s — $(du -sh "$PREFIX" | cut -f1) dans $PREFIX"
[ -n "$HOSTAPP_SUMMARY" ] && echo "$HOSTAPP_SUMMARY"
echo "Étape suivante : ouvrez Madalean (http://127.0.0.1:$PORT/) ; pour un téléphone ou un autre PC, suivez le lien de"
echo "connexion Tailscale affiché dans Système → Réseau, puis appairez l'appareil (madalean pair)."
