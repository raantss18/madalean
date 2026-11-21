# Madalean 2.0 — sécurité / security

Revue indépendante S-H (2026-11-21), avant la première publication. Les auteurs du code n'ont pas fait cette revue.

## Résumé (FR)

**Ce qui est protégé.** Vos fichiers et vos clés (clés d'API, jetons des appareils, clé de signature des versions), le
contrôle de l'ordinateur hôte (exécuter du code, installer, changer les réglages), l'intégrité des preuves (« prouvé »
veut dire « Lean l'a accepté ») et celle des mises à jour.

**Contre qui.** Une page web malveillante ouverte dans le navigateur de l'hôte. Un appareil appairé volé ou piraté.
Un PDF, un .tex, un BibTeX, un carnet ou une archive piégés. Un texte qui donne des ordres cachés au modèle (sources,
résultats web, réponses de modèles). Une version publiée piégée. Un attaquant sur le réseau local. Les autres comptes de
la machine.

**Ce que la revue a trouvé et corrigé.**
- **Critique.** Un texte Lean pouvait exécuter du code sur l'hôte malgré le filtre D28, via `attribute [command_elab …]`
  puis `#check`. Il suffisait d'une réponse de modèle, d'un indice tiré d'un article ou d'un appareil appairé.
  - Le filtre est étendu.
  - Surtout, **chaque processus `lean` tourne maintenant dans un bac à sable** (bubblewrap) : pas de réseau, pas de
    dossier personnel, tout en lecture seule.
- **Élevé.** N'importe quel autre site web servi sur la machine (`http://127.0.0.1:<autre port>`) était accepté comme
  « même origine » par le guichet local de confiance.
  - L'origine doit maintenant être exactement `127.0.0.1:11500`.
  - Les requêtes inter-sites sont refusées (en-têtes Fetch Metadata), sauf l'ouverture de l'interface.
- **Élevé.** Le LaTeX produit par les modèles pouvait lire `/etc/…` (et l'imprimer dans le PDF) et écrire des fichiers
  n'importe où.
  - L'astuce était `^^5c`, l'écriture hexadécimale de l'antislash en TeX.
  - Tectonic ne respecte pas `openin_any`/`openout_any`.
  - Le filtre refuse maintenant ces textes, et chaque compilation TeX tourne dans un bac à sable.
- **Élevé.** Le code d'expérience Sage/Python, pourtant « en bac à sable », pouvait piloter Madalean par
  `127.0.0.1:11500`, lire le jeton de JupyterLab et joindre le bus D-Bus.
  - Les noyaux d'expérience n'ont plus de réseau (`--unshare-net`, avec un relais TCP → socket Unix pour Jupyter).
  - `/run` et `/tmp` sont vides, et le dossier de JupyterLab est caché.
- **Élevé.** La règle D29 (pas de mise à jour automatique depuis une copie de développement ou un dossier de
  configuration temporaire, jamais dans `~/.elan`) n'était pas codée. Elle l'est maintenant, avec des tests.
- **Moyen.** Un appareil appairé pouvait faire charger n'importe quel fichier par llama.cpp, via le réglage
  `model_path`. Seuls les modèles détectés sont acceptés désormais.
- **Faible.** Un lien Markdown `/\site` sortait du site. La somme SHA-256 de Gradle n'était pas épinglée. Il n'y avait
  pas de configuration Dependabot.

**À faire avant la publication (bloquant).** La revue laisse deux points ouverts (détail dans § 9) :
- la clé de signature des versions est en clair dans `~/.config/madalean/release-keys/`, sur la machine qui exécute des
  carnets ;
- llama.cpp b11375 a une CVE critique dans la lecture des fichiers GGUF.

**Risques acceptés.** Voir § 8 et `ACCEPTANCE.md`. Exemples : tout programme local du même utilisateur a la confiance
de l'hôte ; JupyterLab exécute du code par nature.

---

## 1. Assets

| Asset | Where | Why it matters |
|---|---|---|
| Provider API keys | keyring (`secret-tool`) or `~/.config/madalean/keys.json` 0600 | money, account abuse |
| Device tokens | client side (keyring / Android Keystore); server keeps SHA-256 only (`devices.json` 0600) | full remote access |
| **Release signing key** (Ed25519) + APK keystore | `~/.config/madalean/release-keys/` (0700) — **see F7** | every installed Madalean, AppImage and APK trusts it |
| Host control | `127.0.0.1:11500` (trusted listener), Jupyter, experiments, updates, `net start/stop`, terminal action | code execution as the user |
| Research data | dossiers, notes, sources (PDFs), library, articles | confidentiality, integrity |
| Proof integrity | `leancheck.judge` strict verdict | « proved » must mean Lean accepted it |
| Update channel | `stable.json`(+.sig), `SHA256SUMS`(+.sig), APK cert pin | supply chain of all users |
| Tailscale node identity | `$MADALEAN_HOME/tailscale/` (0700) | impersonation on the tailnet |

## 2. Actors

1. **Malicious web page in the host's browser.** It runs at its own origin, or at another local origin such as
   `http://127.0.0.1:8888` or a dev server. Its targets:
   - CSRF against `127.0.0.1:11500`, which trusts every request;
   - DNS rebinding;
   - cross-site GETs with side effects.
2. **Paired but compromised device** (stolen phone, malware on a laptop). It holds a valid token on the remote
   listener. Its goal is to escalate to host-only powers or to code execution.
3. **Unpaired tailnet node / LAN attacker.** It can reach the remote listener through `madalean-net`, or the optional
   LAN listener. Its tools are pairing brute force, header spoofing and slow-loris.
4. **Hostile content.** A PDF, a TeX e-print, a BibTeX/CSL record, a notebook or an archive. It reaches parsers, TeX,
   Lean and the models.
5. **Prompt injection.** Text inside sources, web or literature results, or model output that tries to make a model
   emit dangerous Lean, LaTeX or experiment code, or tool calls.
6. **Malicious upstream.** A compromised GitHub account or release, a compromised dependency, or a GGUF model.
7. **Other local users / processes.** Anything that can `connect()` to `127.0.0.1:11500`.

## 3. Trust boundaries

```
 browser (host) ──HTTP──▶ 127.0.0.1:11500  local, TRUSTED  ─┐
 desktop shell (Rust)  ──▶ 127.0.0.1:11500                  │
 tailnet device ─HTTPS─▶ madalean-net (tsnet) ─▶ 127.0.0.1:11501  remote, token
 LAN (opt-in) ──HTTP──▶ 0.0.0.0:lan_port  token             │
                                                            ▼
                                   madalean serve (aiohttp, one process, the user's uid)
        ┌──────────────┬───────────────┬────────────────┬────────────┬───────────────┐
        ▼              ▼               ▼                ▼            ▼               ▼
  lean (bwrap:     TeX (bwrap:    experiment kernels  JupyterLab   llama-server   scholarly APIs
  no net, no home, no net, build  (bwrap, no net,     (+ user       127.0.0.1      (https only,
  read-only)       dir only)      IPC relay)          kernels:      only           resolve-then-
                                                      NOT sandboxed)               connect)
```

A boundary is crossed in four places, and each place must hold:
- the security middleware (`madalean/server/auth.py`);
- the D28 gate plus the Lean sandbox (`leancheck.exec_risks`, `madalean/leansandbox.py`);
- the TeX sandbox (`export.tex_confine`);
- the experiment launcher (`research/sagebridge.py`).

## 4. Controls (as implemented after this review)

### Listeners (`server/auth.py`)
- **Local listener.**
  - `Host` must be a loopback name. This is the DNS-rebinding guard.
  - A browser `Origin` must be exactly the request's `Host:port`. It was any loopback port before (F2).
  - The `Origin` check applies to every state-changing method and to WebSocket upgrades.
  - Fetch Metadata: with `Sec-Fetch-Site` set to `cross-site` or `same-site`, only GET/HEAD top-level navigations to
    UI paths, `/api/session` or `/api/hello` are allowed; anything else gets a 403 `cross_site`. This blocks `<img>`,
    `<script>` and no-cors probes, and navigations to `/jupyter/…`, which started Jupyter as a GET side effect.
  - No CORS headers are ever sent, including on preflight.
- **Remote listener.**
  - The `Host` allow-list is loopback, `*.ts.net` and the node's names.
  - Every route needs a token except `hello`, `pair`, `logout`, `session` and the static files. This is enumerated
    from the router in the tests.
  - Host-only handlers answer 403. `HOST_ONLY_SETTINGS` keys are refused.
  - `madalean-net` overwrites `X-Forwarded-*` (Go `Rewrite`). A client reaching 11501 directly can forge them, but
    they grant nothing: `local` is decided by the socket port, and `X-Forwarded-Host` never counts on 11500.
- **Pairing.**
  - 6 digits, 5 minutes, single use.
  - 5 wrong codes lock pairing for 10 minutes and burn the code.
  - Rate limits: 10 per minute per peer, 30 per minute overall.
  - Code comparison is constant-time.
  - **Apps vs browsers** (user decision 2026-11-21: apps reconnect automatically, a browser needs a code at every
    connection). `POST /api/pair` creates a persistent *device* (256-bit token, only its SHA-256 stored) only for the
    shells' native HTTP clients (`client: app-desktop|app-android`, and no `Origin`/`Sec-Fetch-*` header). Anything a
    browser sends gets a *browser session*: no token in the body, a session cookie (no Max-Age/Expires,
    `HttpOnly; SameSite=Strict`, `Secure` over HTTPS), kept in memory only, closed after `browser_session_idle_minutes`
    of inactivity (default 120, host-only) and after 12 h at most, and on server restart. A browser-session secret is
    accepted only as the cookie: never as a Bearer token, never for `/api/session/ticket`, so it cannot be turned into
    a device token (tested). The LAN listener follows the same rules.
  - Revocation, logout, self-forget and browser-session expiry close that credential's open WebSockets at once
    (code 4401, tracked per credential in the event bus) and cancel the assistant streaming it started (tested).
  - App web views get their cookie through a one-time session ticket (below); app cookies are `HttpOnly;
    SameSite=Strict` (`Secure` over HTTPS) and revoked with the device.
- **Session tickets.** 192 bits, 60 s, single use, in memory only. `next` accepts same-origin relative paths only.
  The response carries a meta refresh under `CSP: default-src 'none'`.
- **UI.**
  - CSP `script-src 'self'`, no remote origin, `frame-ancestors 'self'`, `object-src 'none'`.
  - Markdown goes through markdown-it with `html:false`, a link scheme allow-list (now also refusing `/\`), KaTeX with
    `trust:false` and `maxExpand:500`, then DOMPurify without `<img>`.
  - Attachments and source files are served with `CSP: sandbox`.

### Code execution
- **Lean (D28 + F1).**
  - `exec_risks` deny list. It now also covers `attribute […]`, simprocs, `norm_num`/`positivity`/`aesop`
    extensions and the elaborator framework names (`Elab`, `Meta`, `CommandElab`, `MetaM`, `unsafe*`, `loadDynlib`,
    …). Measured false positives: 0 of 493 miniF2F statements and 10 of 87 Mathlib Archive files (notations/macros,
    already refused before).
  - The deny list is defence in depth, because the language is user-extensible. **The boundary is `leansandbox`.**
    Every `lean` process (server checker, brain self-test, update re-verification) runs under
    `bwrap --unshare-all --die-with-parent --cap-drop ALL`:
    - system directories, the toolchain, the workspace and the checked file are mounted read-only;
    - `/tmp` is an empty tmpfs, the home directory is absent and there is no network;
    - the environment is rebuilt from an allow-list (no API keys).
- **TeX (F5).**
  - `sanitize_math` refuses `^^` and `\csname`, and BibTeX URLs are percent-encoded.
  - Every engine run (tectonic `--untrusted --only-cached`, or the xelatex/lualatex fallback with
    `-no-shell-escape`, `openin_any=p` and `openout_any=p`) is confined: the build directory is writable, the prefix
    and the TeX/font trees are read-only, the rest of the home directory is absent and there is no network.
  - The environment is reduced to an allow-list.
- **Experiments (F6).**
  - Code runs only after approval of the exact code by hash (an edit resets the approval), or with the host-only
    `experiments_auto`. Paired devices are allowed only when `experiments_remote` is on.
  - The kernel runs in bwrap:
    - the file system is read-only except the experiment directory;
    - hidden paths: config, keyrings, SSH, GnuPG, browser profiles, Tailscale state, and now JupyterLab's runtime
      directory (token and other kernels' connection files);
    - `/run`, `/tmp` and `/dev/shm` are empty;
    - **own network namespace**. The launcher moves the kernel's ZMQ sockets to IPC in the experiment directory and
      relays JupyterLab's TCP ports to them from outside the namespace.
  - rlimits: address space, file size and core. Wall-clock timeout and output cap.
- **Agent.**
  - Tools are `lean_check` (gate + sandbox), read-only searches, and the optional `lean_search_online`, which sends
    the query text to LeanSearch/Loogle.
  - There is no file-write or shell tool. `agent_exec` is a host-only setting that no code uses today.
- **Jupyter.**
  - JupyterLab gets a random token kept server side and its own config dir.
  - The proxy strips the client's cookie, `Authorization` and `Origin`, and removes the token from pages.
  - From paired devices it is reachable only with the host-only `remote_jupyter`.
  - User kernels are **not** sandboxed: they are a code-execution feature by design.

### Hostile input
- **Fetchers.**
  - https only, port 443, no IP literals, no internal TLDs (`.ts.net`, `.local`, …).
  - Metadata calls go to an allow-list of scholarly hosts.
  - Resolve-then-connect pinning: every DNS answer must be global, with no loopback, private, CGNAT or mapped/6to4
    address. This also defeats rebinding between check and connect.
  - Redirects are re-validated hop by hop, with size and content-type caps. `trust_env=False`.
- **Archives.** Traversal, links and devices are skipped, with bomb budgets (`research/safety.py`).
- **XML.** Entities are refused.
- **PDF tools.** Run under rlimits and timeouts.
- **Paper TeX.** Parsed, never compiled.
- **Article projects (S-R, docs/ARTICLE.md §6).** The user's own LaTeX is compiled, always inside `tex_confine`
  (tectonic `--untrusted --only-cached`), after `texbuild.guard` refuses file/shell primitives, `^^`, `\csname`,
  `\catcode`, `\scantokens`, absolute or `..` paths in the whole project. AI text enters only as suggestions the user
  accepts; `guard_ai` also refuses definitions and inclusions in them. Overleaf imports: `.tex/.bib`/images only
  (third-party `.sty/.cls/.lua` refused), guarded. The network is shared with the sandbox only for the explicit
  « Télécharger une fois » (files of the pinned bundle, generated or guarded source).

### Secrets
- **Keys.**
  - Stored in the keyring, or in `keys.json` 0600. They are never returned (`set: true/false`) and never logged; the
    only log line is « stored for <provider> ».
  - Not passed to Lean, TeX or experiment kernels (environment allow-lists, tested).
  - Each key is attached only to its provider's exact host(s) (`net.Http.check`, no subdomains). The Hugging Face
    token (S-T) has two: `router.huggingface.co` (inference) and `huggingface.co` (`/api/whoami-v2`, the key test);
    the Hub's public model-mapping API is called without it (tested in `tests/test_hf_goedel.py`).
- **Device tokens.**
  - Hashed.
  - The `devices.updated` event shows names and last IPs to every paired device (accepted, R-7).
- **Tailscale.**
  - The state dir is 0700.
  - `TS_NO_LOGS_NO_SUPPORT=true` and `logtail.Disable()` are set before the node starts (`net/main.go`).
  - Funnel APIs are absent; a test greps the source for them.
  - Not verified by strace here: starting a second node would contact the control plane with the user's identity.

### Updates
- **Server self-update.**
  - The Ed25519 signature over `stable.json` (or `SHA256SUMS`) is verified with the embedded public key before
    anything else.
  - Checks in order: channel field, strictly newer version, https only, size, SHA-256.
  - Safe tar extraction (`filter="data"` plus explicit checks), then a health check.
  - Atomic `current` switch, with one previous version kept for rollback (host-only).
  - A replayed old release cannot be installed under a newer tag: the archive name carries the version and must be
    listed in the signed sums.
  - Freeze (an old valid manifest) only delays updates. There is no expiry field; accepted, R-8.
- **D29 (F4).**
  - Automatic installs run only from an installed layout (code under `MADALEAN_HOME`), with the default config
    directory and the prefix's own elan.
  - Lean, Mathlib and Lake installs are refused (`no_prefix_elan`) when `ELAN_HOME` would be `~/.elan`.
  - `ELAN_HOME` is passed explicitly to the updater.

**Calcul (S-M).** The Calcul screen executes code only through `SageBridge` (same sandbox, offline kernel, timeouts,
output caps). Model-written cells need the explicit approval of their exact code (hash), as experiments; a user's
edit of model code does not lift that requirement. Rich outputs: LaTeX rendered by KaTeX with `trust: false`, never as
HTML; PNG checked by magic number; SVG sanitised and served with `Content-Security-Policy: default-src 'none';
style-src 'unsafe-inline'; img-src data:; sandbox`, displayed via `<img>`. Spending: `<config>/brain-spend.json`
(0600) holds token counts and costs only, no prompt and no key.

## 5. Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| F1 | **Critical** | D28 gate bypass. `attribute [command_elab Lean.Parser.Command.check] f` + `#check 1` ran arbitrary IO when the file was checked: `pwned_cmdelab` was written to disk by the real `lean` v4.36.0. Reachable by model output, paper hints, remote devices and the agent's `lean_check`. The update re-verifier also compiled stored proofs without the gate. | **Fixed.** Deny list extended. Every `lean` is sandboxed (`leansandbox.py`). The re-verifier is gated. Tests: `test_security_review.py` (17 bypass forms, sandbox proof: no network/home/write, no secret in env). |
| F2 | High | Local-listener CSRF. `origin_ok` accepted *any* loopback origin on any port (another local web app, dev server, notebook server, a page served by any local process). `X-Forwarded-Host` was also trusted on 11500. No Fetch Metadata check, so a cross-site `<img src=…/jupyter/x>` started JupyterLab. | **Fixed.** Tests enumerate every state-changing route × 6 bad origins × 3 content types (>1000 requests), plus Fetch Metadata, WebSocket from another port, and preflight. They fail on the old code. |
| F3 | Medium | A paired device could set `model_path` to any file, such as an uploaded attachment, which `pick_model` then handed to llama.cpp's GGUF parser (see CVE-2026-133710). | **Fixed.** Only scanned models are accepted. Test included. |
| F4 | High | The D29 rule was not implemented. A dev-checkout or test server with `updates_auto` on auto-installed again. `config.ELAN_HOME` falls back to `~/.elan`. The test suite and dev servers share the user's real prefix (`WORKSPACES_DIR`, tectonic cache) unless `MADALEAN_HOME` is set. | **Fixed** for installs: `auto_install_blocked`, `prefix_elan_ok`, explicit `ELAN_HOME`; tests. Recommendation (open, low): set `MADALEAN_HOME` to a temp dir in `tests/conftest.py`. |
| F5 | High | TeX injection through `^^5c` in model or paper math. Tectonic `--untrusted` ignores `openin_any`/`openout_any`: it read `/etc/hostname` into the PDF and wrote `OUT.tex` at an absolute path. Demonstrated with the prefix's tectonic 0.17 (copied) and Madalean's own `build_tex`. File write as the user means code execution at the next login (`~/.bashrc`). | **Fixed.** Sanitiser change, URL percent-encoding and TeX sandbox. Re-test: the injection is printed literally, and the raw injection inside the sandbox fails with `Read-only file system`. |
| F6 | High | The experiment sandbox could be escaped. The kernel had the host network: `POST 127.0.0.1:11500/api/settings {experiments_auto, remote_jupyter…}` with no Origin is trusted. It could also read JupyterLab's token and the other kernels' HMAC keys, and reach `/run/user/…/bus` (systemd --user). | **Fixed.** `--unshare-net` with an IPC relay; `/run`, `/tmp` and `/dev/shm` are tmpfs; the Jupyter runtime dir and browser profiles are hidden. Real-kernel tests pass (sage + python); new test: only `lo`, 11500 unreachable, no Jupyter config, `/run` empty. |
| F7 | High | The release signing key (`ed25519.pem`, **unencrypted**), the APK keystore and its password file are in `~/.config/madalean/release-keys/`, on the host that runs unsandboxed Jupyter user kernels (reachable from paired devices when `remote_jupyter` is on). Theft of this key compromises every user's update channel. | **Open, blocking.** The user must move and encrypt the key (§9). `sign_release.sh` now refuses an unencrypted key, or one inside the config dir, unless `MADALEAN_ALLOW_WEAK_RELEASE_KEY=1`. |
| F8 | Medium | The local listener trusts every process that can connect to 127.0.0.1, including other OS users and the user's own unsandboxed Jupyter kernels. | **Accepted** (R-1) for a single-user host; documented. Lean, TeX and experiments can no longer reach it. |
| F9 | Low | A Markdown link `/\evil.example` was accepted as same-origin; browsers treat it as protocol-relative. | **Fixed** (web `md.ts`, rebuilt `madalean/static`); new `web/tests/unit/md.test.ts`. |
| F10 | Low | Pairing lockout is global: an unpaired tailnet node can keep pairing locked (DoS). | **Accepted** (R-6). Tailnet-only, and the host can retry after 10 minutes. |
| F11 | Medium | llama.cpp b11375 (pinned): CVE-2026-133710 (GGUF `hrm_text` heap overflow → code execution with a crafted model) and CVE-2026-107183 (use-after-free in `POST /completion`; llama-server is on 127.0.0.1 only). | **Open, blocking**: bump to ≥ b12556 (§9). |
| F12 | Low | Supply-chain hygiene: no Dependabot, Gradle wrapper without `distributionSha256Sum`. | **Fixed**: `.github/dependabot.yml`; checksum pinned and cross-checked against the cached zip. Dependabot alerts and secret scanning must be switched on in the GitHub settings. |
| F14 | Low | `serve --demo` grew ~1.4 MB/min under the soak: the scripted brain kept every request forever (`FakeBrain.requests`). Jobs are already bounded (`KEEP_FINISHED = 200`). | **Fixed** (bounded record); re-soak in ACCEPTANCE. |
| F13 | Info | `tests/test_update_checkers.py::test_recheck_marks_regressions_after_update` failed once in the full suite and passes alone. The toast arrives asynchronously, so the test is flaky. | Open (test quality). |

## 6. Dependency audit (2026-11-21)

| Ecosystem | Tool | Result |
|---|---|---|
| Python main env (conda-lock, 112 PyPI-mapped) | pip-audit 2.10.1 | 0 |
| Python Sage env (on demand) | pip-audit | pillow 12.3.0: 42 advisories (5 critical), fixed in 13.0.0. sage 10.10 pins pillow < 13. **Accepted** (R-4): only reached by Sage kernels opening untrusted images, which now run sandboxed and offline. |
| Native conda libs | NVD CPE match | libssh2 1.11.1 (7 high, via libcurl, SSH servers only), libexpat 2.9.0 (1 high DoS), sqlite CLI-only, krb5 acceptor-side: low relevance, **accepted** (R-5); bump at next lock refresh |
| npm (web, prod + dev) | npm audit (npm 12.2.3) | 0 / 0 |
| Rust (desktop shell) | cargo-audit 0.22.2 | 0 vulnerabilities. Warnings: glib 0.18.5 unsound (RUSTSEC-2024-0429, Tauri/gtk-rs stack, iterator not used); 6 unmaintained transitive crates |
| Go (madalean-net) | govulncheck 1.10.0 | 0 called. GO-2026-5932 (x/crypto openpgp, not imported) |
| Flutter / Gradle | osv-scanner 2.7.1 | pubspec.lock 0; direct Maven deps 0; transitive Maven not audited (no lockfile) |
| llama.cpp b11375 | OSV by commit | **F11** |
| GitHub workflows | manual | all actions pinned by SHA (verified against the tags); least-privilege permissions; no `pull_request_target`; no untrusted interpolation |

## 7. Robustness (measured)

- **Storage.**
  - `atomic_write_text` keeps the previous file under ENOSPC (`fsync` failing) and under a real EFBIG
    (`RLIMIT_FSIZE`).
  - 12 × `kill -9` during a write loop: the target was always complete JSON.
  - All in `tests/test_robustness.py`.
- **Children.** A `lean` child killed with -9 mid-check gives a failed verdict, and the runner is clean afterwards.
  llama (fake) and Jupyter kill tests already existed (`test_llama.py`, `test_jupyter.py`).
- **Load.** 150 slow-loris sockets per listener plus 200 WebSockets (both listeners) plus a 50-event burst: a POST
  still answered in < 5 s, every socket got the events, and every subscriber was released on close.
  - JSON bodies are capped at 4 MiB and all bodies at 16 MiB (413), unauthenticated ones included.
  - `madalean-net` has `ReadHeaderTimeout: 20s`. The aiohttp listeners have no header timeout, but they are
    loopback-only.
- **Soak (scaled, 20 min).** See ACCEPTANCE « S-H ».

## 8. Accepted risks

| Id | Risk | Why accepted | Revisit |
|---|---|---|---|
| R-1 | Any local process of any user that can reach 127.0.0.1:11500 has full host rights. | Single-user desktop host by design (the shells and the browser need a no-login local door). Lean, TeX and experiment code are now network-isolated. | A per-boot capability (Unix socket with `SO_PEERCRED`, or a secret given to the shell) before multi-user hosts are supported. |
| R-2 | JupyterLab and the user's own kernels run arbitrary code unsandboxed and share the UI origin (`/jupyter/`). | Jupyter is a code-execution feature. It is host-only unless `remote_jupyter` is on. Notebook JS outputs are trusted only after the user trusts the notebook. | — |
| R-3 | Without a working bubblewrap (no user namespaces), Lean, TeX and experiments run unsandboxed and only the deny lists apply. | Lean is the product. The health page shows it (`sandbox` check, added by this review). | — |
| R-4 | pillow 12.3.0 in the Sage env | sage pin; sandboxed and offline | next Sage release |
| R-5 | libssh2 / libexpat advisories in the main env | not reachable in Madalean's flows | next lock refresh |
| R-6 | Global pairing lockout (DoS by a tailnet node) | tailnet only, 10 minutes | — |
| R-7 | Paired devices see each other's names and last IPs (`devices.updated`) | same owner | — |
| R-8 | Signed manifest has no expiry (freeze attack delays updates) | integrity unaffected | add `expires` to the channel |
| R-9 | `lean_search_online` and literature search send model-chosen query text to public services, so a prompt-injected model could leak snippets in queries | `local` mode disables all of it; the permanent indicator shows online use | — |
| R-10 | The D28 deny list can still refuse a legitimate file (10 of 87 Mathlib Archive files) and cannot be complete | the sandbox is the boundary; the refusal message names the construct | — |

## 9. Release readiness

**Verdict: GO with conditions.** Release only after both blocking items are done:

1. **F7 — release key.** Move `~/.config/madalean/release-keys/` off the host, or at least out of
   `~/.config/madalean`, and encrypt the Ed25519 key:
   `openssl pkey -in ed25519.pem -aes256 -out ed25519.enc.pem`, then shred the plaintext. Use a strong passphrase for
   the JKS. Consider an offline machine or a hardware token for signing. `sign_release.sh` enforces the first part.
2. **F11 — llama.cpp.** Bump the pinned llama.cpp to ≥ b12556. Update `madalean/deps/manifest.toml` (hashes) and
   re-run the real-model smoke test.

Non-blocking but recommended for 2.0.x: R-1 capability for the local door, `MADALEAN_HOME` isolation in
`tests/conftest.py`, `expires` in the update channel, Dependabot alerts
and secret scanning switched on, and an investigation of the flaky test F13.

- **R-11 (accepted by the user, D32)** — LAN listener over plain HTTP: pairing code and browser session cookie are unencrypted on the local network while a session is open. Mitigations: code at every browser visit, short sessions (2 h idle / 12 h max), host-only switch; Tailscale recommended.
