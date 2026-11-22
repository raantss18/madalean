# Madalean 2.0 — installation (self-contained, ARCHITECTURE §18)

Session S-I, 2026-11-21. One command installs everything Madalean runs into **one prefix**; nothing is taken from
the system except the NVIDIA driver (for the GPU engine) and a few universal programs listed below.

```bash
./install.sh                 # GPU build of llama.cpp when the driver supports CUDA ≥ 12.8, else CPU
./install.sh --cpu           # CPU only
./install.sh --offline DIR   # from an export (export_offline.sh), no network
./uninstall.sh               # lists, asks, removes the prefix + the unit + the menu entry (keeps settings and models)
```

**Guided install (S-AL, DECISIONS D44).** In a terminal, `./install.sh` first checks the machine and shows a
recommended plan (one engine, `madalean/deps/assistant.py`, shared with the graphical installer and `GET /api/setup`):

```text
==> Assistant d'installation : vérification de la machine

Votre machine
  Processeur       AMD Ryzen 7 7735HS with Radeon Graphics (16 threads)
  Mémoire          31 Go
  Disque libre     924 Go (/home/me/.local/share/madalean)
  Carte graphique  aucune carte NVIDIA
  SageMath         10.10 compatible
  TeX Live         2026 compatible
  Python           3.14.10, 3.10
  elan / Lean      leanprover/lean4:v4.29.1, leanprover/lean4:v4.34.1
  Ollama           0.18.2
  Tailscale        1.104.7
  bubblewrap       présent

Plan conseillé pour cette machine
  • Modèles d'IA locaux : Aucun modèle local (modèles en ligne)
      Pas de modèle local conseillé : sans carte NVIDIA d'au moins 8 Go, un modèle local serait très lent. …
  • Moteur des modèles locaux (llama.cpp) : Processeur seulement (léger, 23 Mo)
  • SageMath (calcul) : Réutiliser le SageMath déjà installé
      SageMath 10.10 est déjà installé et compatible (version ≥ 10.0, noyau Jupyter présent) : le réutiliser
      économise 5 Go ; votre distribution le met à jour. Le même bac à sable s'applique.
  • LaTeX (export PDF, articles) : tectonic de Madalean (épinglé, hors ligne)
  • Espace Lean + Mathlib : Construire lean-current maintenant (≈ 5 Go, réseau)
  • Où travaillent les modèles : En ligne seulement
  ! Ollama est présent : il reste installé ; …

Plan retenu :
  1. Modèles d'IA locaux : Aucun modèle local (modèles en ligne) (conseillé)
  …
  Place nécessaire ≈ 11 Go
[Entrée] installer ce plan · numéro (1-6) pour changer un élément · q pour quitter : 3
    1) Copie de Madalean, installée au premier calcul (≈ 1,5 Go à télécharger, 5 Go)
    2) Copie de Madalean, installée maintenant (≈ 1,5 Go à télécharger, 5 Go)
    3) Réutiliser le SageMath déjà installé  ← conseillé
Choix : 3
…
[Entrée] installer ce plan · … :
==> 1/9 Vérifications
```

| | |
|---|---|
| When | interactive only when stdin and stdout are terminals (or `--assistant`) and neither `--yes` nor `--plan` is given |
| `--yes` / not a TTY | the 2.0.0 defaults, no question: models all, llama.cpp auto, Sage on first use, tectonic, import workspaces, mode auto |
| `--plan FILE` | a plan written by the assistant or the graphical installer (`{"plan": {...}}`) |
| `--dry-run` | machine check + recommended plan (or the defaults with `--yes`), installs and writes nothing |
| `--models all\|prover\|none`, `--sage later\|now\|system`, `--tex own\|system` | per-item choices (also `--cpu`, `--no-models`, `--no-workspaces`, `--build-workspace`) |
| needs | a `python3` ≥ 3.8 (the system's; else the assistant runs right after step 3 with Madalean's own Python) |
| records | `<config-dir>/setup.json` (`madalean-setup/1`): detected machine, recommended + chosen plan, result, settings to apply (`sage_source`, `tex_engine`, `mode`, applied **once** at first start), history |
| never | sudo, a package manager, or a system change: missing bubblewrap → the exact command is printed |

**Reuse of system tools.** `sage_source = system` uses the system SageMath through its `sagemath` Jupyter kernel
(≥ 10.0 recommended); `tex_engine = system` tries the system TeX Live (latexmk + XeLaTeX/LuaLaTeX, fontspec) before
tectonic. Both run in the same sandbox as Madalean's own copies (Sage launcher: environment allow-list, private home,
rlimits, bubblewrap with the file system read-only; TeX: `tex_confine`). `auto` (default) keeps the 2.0.0 order.

**Graphical installer** `Madalean-installer.run` (`scripts/build_installer.sh`, `packaging/installer/`): checks the
SHA-256 of its payload and the `SHA256SUMS` inside before unpacking; then, with a graphical session and `python3`, a
local wizard (127.0.0.1, random port, one-time token, Host/Origin checks, strict CSP) in the browser: welcome → machine
→ plan → live progress of `install.sh --plan` (« Réessayer », « Voir le détail ») → first configuration (« Ouvrir
Madalean ») → done; stops on « Fermer » or after 30 min idle. Options: `--terminal`, `--yes`, `--check`, `--extract
DIR`, `--no-browser`; other arguments go to install.sh. A browser-downloaded file must be made executable first
(Properties › Allow executing, or `chmod +x`).

`GET /api/setup` (host only, plugin `server/plugins/setup_api.py`): `{schema: "madalean-setup-status/1", setup
(setup.json or null), detected, prefs {sage_source, tex_engine, mode, wizard_done}, components (as /api/deps), reuse
{sage {preference, used: own|system|"", ok, system}, tex {preference, used: tectonic|system|"", ok, engines, system}},
keys [provider names], devices (count), next_steps [{id: keys|workspace|sandbox|sage|tex|components|pair, done, title
{fr, en}, help: manual page id}]}`; `?refresh=1` re-runs the machine check. S-AQ (D49) added `recommended`, `models`
and `wizard` for the in-app assistant « Premiers pas », plus `/api/setup/wizard`, `/api/setup/reuse` and
`/api/setup/models` (docs/API.md §6d); the assistant shows the same plan and reasons as the install assistant.

`install.sh --help` lists every option (`--prefix`, `--config-dir`, `--cache-dir`, `--unit-name`, `--no-systemd`,
`--no-desktop`, `--no-models`, `--no-workspaces`, `--build-workspace`, `--build-net`, `--port`, `--remote-port`,
`--serve-args`). It is idempotent and resumable: downloads resume (`curl -C -` / HTTP Range), a verified file is
never downloaded twice, an env that already matches its lock is adopted after verification, a component already at
the pinned version is only re-checked.

## 1. What is installed where

`MADALEAN_HOME` = `~/.local/share/madalean` (or `--prefix`):

| Path | Content | Size (measured) |
|---|---|---|
| `current -> versions/<v>/` | Madalean itself: `madalean/` (server, web UI `madalean/static`, `deps/` manifest + locks), `bin/`, `scripts/`, `packaging/`, `site/` (publication templates), `net/` sources | 35 MB |
| `env -> envs/main-<lock hash>/` | micromamba env from `madalean/deps/locks/main.conda-lock.yml` (220 conda-forge packages): Python 3.13.18, aiohttp 3.14.5, cryptography, pillow, fonttools, JupyterLab 4.6.6, ipykernel 7.4.0, poppler 26.11 (pdftotext/pdfinfo/pdftoppm), tesseract 5.5.4, **tectonic 0.17.0**, fontconfig, git 2.56.1, fonts | 1.2 GB on disk (362 MB downloaded) |
| `envs/sage -> envs/sage-<hash>/` | **on demand**: SageMath 10.10 (386 packages, `locks/sage.conda-lock.yml`) + its kernelspec registered in the main env | ≈ 4.7 GB on disk (1.45 GB downloaded) |
| `components/micromamba/<v>/` | micromamba 2.10.0-0 (static) | 19 MB |
| `components/fonts/<v>/` | DejaVu Sans Mono 2.37, Noto Sans Math 3.000 (+ `fontconfig/fonts.conf`: prefix fonts only) | 2.2 MB |
| `tectonic/` | TECTONIC_CACHE_DIR: the pinned TeX bundle (v33, digest `6ffe0558…`), only the files Madalean's exports use; `tectonic/files/` = font files read by the export | 48 MB |
| `components/elan/<v>/` + `elan/` | elan 4.2.4; `elan/` = ELAN_HOME (toolchains of the managed workspaces). `~/.elan` is never touched | 13.5 MB + toolchains |
| `workspaces/` | `lean-current`, `lean-prover49`: imported by **hard links** from an existing built workspace (dev checkout, Lean AI Station 1.x) — no extra space, no runtime dependency on the source — or built with `--build-workspace` | 12 GB apparent + 3.9 GB toolchains, **0 extra** (hard links) (shared inodes) |
| `components/llama.cpp/b12608-<variant>/` | llama.cpp b12608 (commit 93cb37ea7; ≥ b12556 required: CVE-2026-133710, CVE-2026-107183 in older builds), prebuilt release asset; `cuda13`/`cuda12` variants also carry the CUDA runtime (cudart, cuBLAS) — no CUDA toolkit | 44 MB (cpu); cuda13 = 224 + 444 MB downloaded |
| `components/madalean-net/<v>/` | embedded Tailscale node (Go, tsnet 1.104.7, static) | 22 MB |
| `tailscale/` | state of the Tailscale node (0700), `net.sock` status socket, `tsnet.log` (capped 4 MB) | < 1 MB |
| `downloads/` | verified downloads + micromamba package cache (`pkgs/`) — reused by repairs and `export_offline.sh` | package archives (main 362 MB, Sage 1.45 GB) + 48 MB of component files |
| `deps-state.json` | installed version, path, SHA-256 and *previous* version of each component (rollback) | |
| `installed-files.txt` | files install.sh created outside the prefix (unit, menu entry) — read by uninstall.sh | |

Outside the prefix: `~/.config/systemd/user/madalean.service`, the menu entry **« Madalean Server »**
(`madalean-server.desktop` + `madalean-server` icons in the user hicolor theme, by `scripts/install_host_app.sh`,
D50: the host's own desktop app `<prefix>/current/dist/host-app/madalean-server --host`, shipped prebuilt in the server
archive; without webkit2gtk-4.1 a Chromium-family `--app=` window, else `xdg-open`; it replaces the 2.0.1
`madalean.desktop` xdg-open entry; the client AppImage is never installed on the host),
`~/.config/madalean` (settings, projects, devices — kept by uninstall), `~/.cache/madalean`, `~/models` (existing
models are **reused, never moved**; missing ones are downloaded by `scripts/download_model.sh` with SHA-256).

Every pin (version, URL, SHA-256, size, licence, required / optional / on-demand) is in
`madalean/deps/manifest.toml`; conda packages are pinned with URL + SHA-256 + MD5 in the conda-lock files (generated
with conda-lock from `locks/*.environment.yml`; conda-lock is a **generation** tool only — installs use micromamba,
and every installed package is checked against the lock's SHA-256 through `conda-meta` before the switch).

### System requirements (what is still taken from the host)

| Needed | Why | Without it |
|---|---|---|
| Linux x86_64, glibc ≥ 2.28 (conda-forge baseline), bash, coreutils, tar, curl | install.sh | — |
| NVIDIA driver (CUDA ≥ 12.8 for `cuda12`, ≥ 13.5 for `cuda13`) | GPU engine | CPU build (slow) |
| `setpriv` (util-linux) | children die with the server (`PR_SET_PDEATHSIG`) | Python trampoline (same effect) |
| systemd user session | `madalean.service` | run `$MADALEAN_HOME/current/bin/madalean serve` |
| `bwrap` (optional) | sandbox of Sage/Python experiments (S-G) | rlimits only |
| `secret-tool` (optional) | API keys in the keyring | `keys.json` 0600 |
| system XeLaTeX (optional) | export fallback only, if tectonic failed | HTML export |

**Not needed any more**: system Python, pip, a C/C++ compiler, CMake, the CUDA toolkit, git, TeX Live, poppler,
JupyterLab, SageMath, fonts, the system `tailscaled` / `tailscale serve`.

## 2. For other sessions: how to locate a tool

**Rule: `from madalean import deps; deps.tool("<name>")`** — one choke point. It returns an absolute path or None:

1. the prefix first (`env/bin`, `elan/bin`, `components/*/current`, `envs/sage/bin`);
2. a system program only for the names in `deps.SYSTEM_ALLOWED` (nvidia-smi, setpriv, bwrap, secret-tool,
   systemctl, systemd-run, xdg-open, and the system TeX programs as export fallback) — `deps.tool_info(name)` says
   `source: "system"` and the health page lists them;
3. in a development checkout **without** an installed prefix env, PATH is used for everything (`source:
   "system-dev"`), so code and tests behave as before.

Once the prefix env is installed, a managed tool missing from the prefix resolves to **None** (never the system's):
report it as a missing component (repair button) instead of silently using another version.

Known names: `python`, `python3`, `jupyter-lab`, `jupyter`, `pdftotext`, `pdfinfo`, `pdftoppm`, `tesseract`,
`tectonic`, `fc-match`, `fc-list`, `fc-query`, `git`, `micromamba`, `elan`, `lake`, `lean`, `llama-server`,
`madalean-net`, `sage`, `sage-python` (+ the system-allowed ones). Other helpers: `deps.home()`, `deps.env_dir()`,
`deps.elan_home()` (ELAN_HOME of the prefix), `deps.workspaces_dir()`, `deps.tectonic_cache()`,
`deps.tex_files_dir()`, `deps.installed()`.

`madalean serve` calls `deps.activate()` first: the prefix's bin directories are put first in `PATH`, and
`ELAN_HOME`, `TECTONIC_CACHE_DIR`, `FONTCONFIG_FILE` are set — so children and code that still calls
`shutil.which` see the prefix first. Please still move to `deps.tool()`; remaining direct lookups found in other
sessions' code (2026-11-21):

| File (owner) | Lookup | Should become |
|---|---|---|
| `research/fulltext.py`, `research/sources.py` (S-E) | `shutil.which("tesseract"/"pdftoppm")`, bare `pdftotext`/`pdfinfo` | `deps.tool(...)` |
| `research/sagebridge.py` (S-G) | `system_python()` prefers `/usr/bin/python3`; `KERNEL_DIRS` | `deps.tool("python")`; the Sage kernelspec is registered in `sys.prefix/share/jupyter/kernels/sagemath` (found already) |
| `update_checkers/system.py` (S-G) | `shutil.which("sage"/"jupyter-lab"/"tex"/"pdftotext")`, `/usr/bin/python3` | these are prefix components now: the `deps` checker covers them (§4); keep the system checks only in dev mode (`not deps.installed()`) |
| `update_checkers/lean.py` (S-G) | default `~/.elan` | `config.ELAN_HOME` |
| `update_checkers/common.py` (S-G) | `git` with PATH `/usr/bin:/bin` | `deps.tool("git")` |
| `update_checkers/selfupdate.py` (S-G) | root `~/.local/share/madalean` | `deps.home()` (same default, honours `MADALEAN_HOME`); layout `versions/<v>` + `current` is the one install.sh uses |
| `keys.py` (S-A) | `shutil.which("secret-tool")` | `deps.tool("secret-tool")` (system-allowed) |

On-demand components: `await madalean.deps.service.ensure("sage", ctx.publish)` installs Sage the first time (the
UI receives `deps.progress` events) and returns when it is ready.

## 3. HTTP API and events (plugin `server/plugins/deps_net.py`)

| Route | |
|---|---|
| `GET /api/deps` | `{home, installed, components:[{component, title, need, version, pinned, variant, path, source, ok, state: ok\|missing\|outdated\|on_demand\|dev, license, repair}], system:[{tool, path, why}], jobs}` |
| `POST /api/deps/{component}/install` (host) | 202; background install/repair; WS `deps.progress {component, phase, done, total, message}` (phases: start, download, verify, extract, create, check, switch, done, error) |
| `POST /api/deps/{component}/rollback` (host) | switch back to the previous version |
| `POST /api/system/repair/dep_<component>` (host) | same as install (the health checks carry `repair: "dep_<component>"`) |
| `GET /api/system` | `checks` now include one `dep_<component>` line per component |
| `GET /api/net` (host) | `{state: starting\|needs_login\|needs_machine_auth\|running\|stopped\|restarting\|error\|unavailable, auth_url, dns_name, url, tailnet, ips, cert_ok, cert_error, hostname, version, tailscale_version, running, settings:{enabled, hostname}}` |
| `POST /api/net/start`, `POST /api/net/stop`, `PATCH /api/net {enabled?, hostname?}` (host) | settings in `<config>/net.json` |
| WS `net.status {net}` | every state change (the UI shows `auth_url` as « Connecter à Tailscale ») |

## 4. Updates of the components (interface with S-G's update system)

`madalean/deps/checker.py` registers the checker « Composants » (`updates.register_checker`) and the installer kind
`deps` (`updates.INSTALL_ARGS["deps"]` → `scripts/updater.py deps-install <component>`):
- installed version ≠ manifest pin (a Madalean update brought a new manifest) → candidate `deps:<component>`,
  **installable**, applied automatically at a quiet moment when « automatique » is on (verify SHA-256 → new
  versioned directory → check it runs → atomic switch → previous kept; `rollback` available);
- upstream newer than the pin (micromamba / elan / llama.cpp releases, tailscale.com, conda-forge latest of the
  watched packages: python, aiohttp, jupyterlab, ipykernel, poppler, tectonic, git, tesseract, cryptography, sage)
  → candidate `deps-upstream:<component>:<item>`, **notify only**: a new pin needs new hashes, so it ships with a
  signed Madalean release (regenerate the lock: `conda-lock -f locks/main.environment.yml -p linux-64 --lockfile
  locks/main.conda-lock.yml`, update `sha256` of the lock in the manifest; `tests/test_deps.py` fails if they
  differ).
In `mode = local` the checker makes no network request.

## 5. The embedded Tailscale node (madalean-net)

`net/` (Go module, `go.mod` + `go.sum` committed, tailscale.com v1.104.7, Go 1.27.4), built with `net/build.sh`
(`CGO_ENABLED=0 -trimpath -buildvcs=false -ldflags="-s -w -buildid="`; two builds → same SHA-256 `446ba511…`).
The server starts it (not in `--demo`) when it is installed and `net.json` does not disable it:
- joins the tailnet as `madalean` (configurable), state in `$MADALEAN_HOME/tailscale/state` (0700);
- first start: `state = needs_login` + `auth_url` (shown in the UI) — the user approves the device in their
  Tailscale admin; Madalean never approves anything and never passes an auth key (the server strips every `TS_*`
  variable from the sidecar's environment);
- serves HTTPS on `:443` of the tailnet address with the certificate Tailscale issues for
  `madalean.<tailnet>.ts.net` (`ListenTLS`; the tailnet must have « HTTPS certificates » enabled — `cert_ok` /
  `cert_error` say so), `:80` only redirects to HTTPS;
- reverse-proxies everything (WebSocket upgrades included, streaming unbuffered) to the remote listener
  `127.0.0.1:11501` with the original `Host`, `X-Forwarded-Proto: https`, `X-Forwarded-Host`, `X-Forwarded-For`
  (client-supplied `X-Forwarded-*` are dropped); the remote listener still requires a device token;
- **no Funnel**: the code never calls `ListenFunnel` nor changes serve/funnel configuration (`go test` checks it);
- **no telemetry**: `TS_NO_LOGS_NO_SUPPORT=true` and `logtail.Disable()` (tsnet would otherwise upload its logs);
- exits when the server dies (`PR_SET_PDEATHSIG` + parent polling) or on SIGTERM;
- the host's `tailscaled`, if any, is neither required nor touched; both coexist. `scripts/tailscale_setup.sh`
  (system tailscaled + `tailscale serve --https=10500`) stays as the documented alternative, not the default.

Server side: the remote listener stays bound to 127.0.0.1; its `Host` allow-list = loopback names, `*.ts.net`
(the node's name and the `tailscale serve` alternative) and the node's current DNS name; any other Host → `403
bad_host` (DNS rebinding). Origin checks are unchanged (same-origin with Host / X-Forwarded-Host).

## 6. Processes

One tree under `madalean.service`: the server and its children (llama-server, lean, jupyter-lab and its kernels,
madalean-net, updater). Every child is started through `runtime.guarded` (`setpriv --pdeathsig KILL`, else a
Python `prctl` trampoline). Jupyter kernels are started by jupyter-lab in their own session, so Madalean's
`JUPYTER_PATH` overrides the `python3` kernelspec with a guarded one (and the Sage kernelspec too): kernel dies
with jupyter-lab, which dies with the server. The unit has `KillMode=control-group`: stopping it — or the server
dying — kills the whole cgroup.

## 7. Offline install

```bash
./export_offline.sh /media/usb/madalean-export [--with-models] [--with-workspaces]
# on the target (no network):
/media/usb/madalean-export/madalean/install.sh --offline /media/usb/madalean-export
```
The export holds the installed version, every verified download, the conda package archives, the TeX bundle
cache, optionally the models and the built workspaces with their toolchains. Everything is verified again on the
target (manifest SHA-256, lock SHA-256 per package, bundle digest).

## 8. Troubleshooting

- `python -m madalean.deps health` (with `PYTHONPATH=$MADALEAN_HOME/current`, run with `$MADALEAN_HOME/env/bin/python`)
  lists every component, its state and path; `install <component>` repairs one; `rollback <component>` goes back.
- `install.log` in the prefix has the micromamba output. `journalctl --user -u madalean`.
- PDF export: tectonic runs with `--only-cached`; a document needing a TeX package outside the warmed set fails
  and the export falls back to the system XeLaTeX (if any), then to HTML. Re-run `install tex-bundle` after a
  template change (it compiles Madalean's real export documents to fill the cache).
- Bibliography with tectonic uses BibTeX + `amsalpha` (built into tectonic). biblatex + biber is used only with a
  system TeX that has biber.
- The Tailscale login URL expires: `POST /api/net/stop` then `start` gives a new one.

## 9. Verified / not verified (2026-11-21)

Measured on this machine (Arch Linux, RTX 4060 laptop, driver 620.70, ~3 MB/s from GitHub), 2026-11-21:

**Totals**: base prefix (everything except Sage, workspaces shared by hard links) **1.9 GB**; with Sage **≈ 6.6 GB**.
Fresh online install (`install.sh --cpu`, temp prefix + temp config + temp unit `madalean-sitest`, Sage excluded)
**359 s** (micromamba env ≈ 1 min, TeX bundle warm-up ≈ 4 min, the rest < 1 min); re-run (idempotent) **16 s**;
offline install from an export in a network-less namespace (`unshare -rn`) **26 s**; Sage on demand through the
API **381 s** download + 15 s link/verify.

Verified for real (temp prefix, not the dev checkout, nothing of the user's system changed):
- install.sh end to end → server started by the temp systemd unit **from the prefix** (python of `env/`, code of
  `versions/2.0.0.dev0`), `/api/hello` 200, `/api/system`: every check green incl. `tex` = « tectonic de Madalean »
  and one `dep_*` line per component;
- PDF export of the demo dossier through the API: produced by the prefix's tectonic (`Producer: xdvipdfmx (0.1)`,
  tectonic's own), fonts embedded DejaVuSansMono + LatinModernMath + LMRoman; the same with **no network**
  (offline prefix in `unshare -rn`). The warm-up compiles Madalean's real export documents (FR + EN, fontspec,
  unicode-math, fvextra, tcolorbox, babel, hyperref, bibliography through tectonic's BibTeX + amsalpha) and then
  checks them again with `--only-cached`;
- Python kernel through the prefix's JupyterLab (proxy + WebSocket): `sys.executable` is the prefix's python, 42;
- Sage installed on demand (`POST /api/deps/sage/install`, progress events), kernel `sagemath`:
  `factor(2^64+1)` = `274177 * 67280421310721`, SageMath 10.10;
- process hygiene: under systemd, `kill -9` of the server with jupyter-lab + a Python kernel + a Sage kernel
  running → all 4 PIDs of the cgroup gone, unit restarted (NRestarts=1); outside systemd (server started by hand
  from the prefix), `kill -9` of the server → jupyter-lab **and its kernel (own session)** died within 0.25 s —
  the survivor S-A had noted is fixed (guarded kernelspecs);
- madalean-net (real binary): started by the server through `POST /api/net/start` → `needs_login` with a
  `https://login.tailscale.com/a/…` URL in ≈ 2 s, then stopped; **no device was authorised** (needs the user);
  state dir 0700, no log upload;
- uninstall.sh: lists, removes the prefix, the cache, the unit (stopped + disabled + reset), the menu entry and
  icons, the AppImage copy and the directories install.sh had created; afterwards no process from the prefix, no
  unit, no file left except the kept config dir (and the desktop/icon caches regenerated by
  `update-desktop-database` / `gtk-update-icon-cache`). The source workspaces and `~/.elan` were intact;
- security: `pip-audit` on the main env (110 Python distributions): **0** known vulnerabilities; `govulncheck` on
  madalean-net: **0** affecting the code (klauspost/compress 1.20.0 → 1.20.2 and x/net 0.60 → 0.62 bumped for
  that); SBOM `dist/sbom/madalean-prefix.cdx.json` (CycloneDX 1.5, 658 components: 220 main-env packages, 386
  Sage packages, 44 Go modules, 8 manifest components) + the audit reports next to it.

Security review F11 (2026-11-21 evening): llama.cpp re-pinned from b11375 (CVE-2026-133710, CVE-2026-107183) to
**b12608**. cpu + cuda13 (+ cudart) downloaded and their SHA-256 checked against the GitHub digests; every flag of
`runtime/llama.py` still accepted (`--help`); `--list-devices` shows the RTX 4060 with the cuda13 build; Goedel-Prover
Q4_K_M loaded with `-c 4096` and the exact Madalean flags: `-ngl 99` and `-ngl 20` did not fit (Ollama held 5.5 of
8 GB; cudaMalloc OOM), **`-ngl 12` → "offloaded 12/37 layers to GPU", one completion (8 tok/s), stopped**, VRAM
back to its previous level. nvidia-smi 620 prints `CUDA UMD Version:`; the variant detection reads both banners.

## 10. Accepted findings, NOT verified, risks

Accepted (with reason):
- **Sage env: pillow 12.3.0** (42 advisories, fixed in 13.0.0): sage 10.10 on conda-forge requires `pillow <13`
  (the solver refuses `pillow >=13`). Pillow there is only reachable from Sage kernels (experiments, sandboxed by
  S-G's bridge); the server itself uses the main env's pillow 13.0.0. Re-lock when conda-forge's sage allows 13.
- **golang.org/x/crypto 0.58.0 (GO-2026-5932)**: module-level only (govulncheck: not called); the fix exists only
  as a pseudo-version; bump with the next tailscale.com release.
- `pip-audit` covers Python distributions only: native conda packages (openssl 3.6.5, git, poppler, libxml2…)
  are pinned + hashed but not scanned (no CVE scanner understands conda packages); the `deps` checker notifies
  newer upstream versions of the watched ones.

Not verified:
- a real tailnet login: authorising the node, HTTPS with the Tailscale certificate, the reverse proxy over the
  tailnet and WebSocket through it (the proxy itself is unit-tested with httptest, incl. the WebSocket upgrade);
- the CUDA variants of llama.cpp (`cuda13`, `cuda12`; SHA-256 taken from GitHub's asset digests, not downloaded
  here) and any GPU model load (GPU reserved); GPUs/drivers other than this one;
- other distributions (only Arch here; the conda-forge baseline needs glibc ≥ 2.28);
- `--build-workspace` (Mathlib download + build into the prefix) — the hard-link import path was used;
- building madalean-net from source on another Go version (the pinned SHA-256 is for Go 1.27.4; the release asset
  `madalean-net-linux-amd64` must be attached to the GitHub release, or install.sh needs `--build-net` + the same Go);
- the update path end to end through the UpdatesManager (the `deps` checker and `updater.py deps-install` are
  unit-tested; the install itself is the same code the installer ran).

Risks:
- The TeX cache only holds what the warm-up documents use: a future template needing a new package fails offline
  until `install tex-bundle` runs again (the export then falls back to system XeLaTeX or HTML).
- conda-forge / GitHub URLs may disappear; `downloads/` + `export_offline.sh` are the mitigation.
- The export's math sanitiser lets `\blacksquare` through, which is undefined with unicode-math (found while
  writing the warm-up; owner of `texio`/`export` should map it to `\mdlgblksquare` or `\blacksquare` from amssymb).
