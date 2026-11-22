---
id: install
title: Installing Madalean
order: 10
section: start
audience: all
summary: What the computer needs, the three ways to install (graphical installer, terminal assistant, unattended install), what install.sh does, its options, updating and uninstalling.
---

# Installing Madalean

Madalean is installed on **one computer only**, the **host computer**: it runs the server, Lean and the local models,
and it keeps your data. Your other devices (another PC, a tablet, a phone) install only a light app, or nothing at
all: a browser is enough. See [Link a device](pairing.md).

This page covers the installation itself. Two pages complete it:

- [What Madalean installs, component by component](components.md): what each piece is for (Lean, SageMath, LaTeX,
  local models…), its size, and whether it is better to reuse what is already on your computer;
- [First configuration](first-config.md): the keys of online providers, where the models work and the automatic
  behaviours, to set once the installation is done.

## Before you start

| | Minimum | Recommended |
|---|---|---|
| System | 64-bit Linux (x86_64), any recent distribution | — |
| Memory (RAM) | 8 GB | 16 GB or more |
| Graphics card | none | NVIDIA with at least 8 GB of graphics memory, to run the local prover |
| Disk | ≈ 6 GB free without local models or SageMath | an SSD, with the space listed below |

Disk space, depending on what you install:

| Item | Space |
|---|---|
| Madalean and its basic components (Python, JupyterLab, LaTeX, fonts, Lean, model engine) | ≈ 6 GB |
| The three local models (in `~/models`) | ≈ 15 GB more, i.e. ≈ 25 GB in all with the basics and some margin |
| SageMath (the “Calcul” screen) | ≈ 5 GB more |
| Each Lean/Mathlib workspace built on the computer | ≈ 5 GB |

**Without an NVIDIA card**, everything works: online models (free, or with a key) do not depend on your graphics
card, and they are what Madalean uses by default. Only the local models would be too slow on the processor; the
installation then does not suggest them (see [Local models](components.md#local-models)).

**With an NVIDIA card**, only the **NVIDIA driver** must be installed, by you, with your distribution's tools.
Madalean never touches drivers and does not need the “CUDA Toolkit”. If the driver is too old, it installs the
processor version of the model engine.

You also need an Internet connection during the installation (except for an [offline install](#installing-without-a-network)),
and the basic commands `bash`, `curl`, `tar` and `sha256sum`, present on every common distribution.

## Three ways to install

| Way | For whom | Questions asked |
|---|---|---|
| [Graphical installer](#with-the-graphical-installer-recommended) (recommended) | everyone | in a page of your web browser, with a recommended plan |
| [From source, terminal assistant](#from-source-with-the-terminal-assistant) | whoever prefers the terminal or wants to follow the code | in the terminal, with the same recommended plan |
| [Unattended install](#without-questions-unattended-install) | repeated installs, scripts, remote machines | none: the defaults |

All three lead to the same installation, done by the same program (`install.sh`). None asks for your password:
nothing is installed outside your home folder.

### With the graphical installer (recommended)

1. **Download** the file `Madalean-installer.run`: the link
   <https://github.com/raantss18/madalean/releases/latest/download/Madalean-installer.run> always leads to the
   latest version. The site's
   [download page](site:install) also gives this link.
2. **Make it executable.** A file downloaded by a browser cannot be started as is: this is a Linux protection.
   Either:
   - in the file manager: right-click the file › “Properties” › “Permissions” tab › tick “Allow executing file as
     program” (the wording varies with the desktop: “Executable”, “Is executable”…);
   - or in a terminal, in the file's folder:

     ```bash
     chmod +x Madalean-installer.run
     ```
3. **Start it**: double-click the file, or in the terminal:

   ```bash
   ./Madalean-installer.run
   ```

What happens next:

- The file **first checks its own integrity** (SHA-256 fingerprint) before unpacking anything. A file damaged during
  the download is refused with a clear message: download it again.
- It then opens an **installation assistant in your web browser**. This page is served by the installer itself, on
  your computer only (address `127.0.0.1`, protected by a one-time key): no other computer can reach it.
- The assistant takes you through six screens:
  1. **Welcome**: what will be installed and where.
  2. **Machine check**: system, memory, graphics card, free space, and the tools already present (Lean, SageMath,
     TeX Live, Tailscale, Ollama, bubblewrap…).
  3. **Recommended plan**: for each item (local models, SageMath, LaTeX, Lean workspaces…), the choice advised for
     your computer and the reason; you can change each choice.
  4. **Installation**: live progress, step by step.
  5. **First configuration**: what remains to set in Madalean (online model key, working mode, automatic
     behaviours, devices) and an « Open Madalean » button (`http://127.0.0.1:11500`), where the first-run
     assistant takes over (see [First configuration](first-config.md)).
  6. **Done**: Madalean's address; « Close the assistant » stops the small local page (it also stops by itself
     after 30 minutes without activity, never during an installation).
- On an error, the installation screen shows the last lines, « Show details » the whole log, and « Try again »
  resumes where the installation stopped.
- **Without a graphical session** (for example on a computer you reach through `ssh`), the installer switches by
  itself to the terminal assistant described below.


### From source, with the terminal assistant

If you prefer the terminal, or want to install the development version:

```bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh
```

When started in a terminal, `install.sh`:

1. examines the computer (system, memory, graphics card, free space, tools already installed);
2. shows a **summary table** of what it found;
3. suggests a **recommended plan** (the same as the graphical installer's);
4. lets you **accept** it as is or **change each item**, then installs.

To only see this plan without installing anything: `./install.sh --dry-run`.

### Without questions (unattended install)

```bash
./install.sh --yes
```

`--yes` (or `-y`) installs with the default choices, without asking anything. This is also what happens when
`install.sh` is not started in a terminal (from another script, for example). You can add the options of the
[table below](#installsh-options), or reuse a saved plan with `--plan FILE`.

## What install.sh does, step by step

The script shows nine steps, numbered `1/9` to `9/9`. It is **safe to run again**: if it is interrupted (network
failure, computer switched off), start it again; it resumes where it stopped, without redoing what is already done.
Every downloaded file is checked against its **SHA-256 fingerprint** (a kind of digital signature of the content):
an altered file is refused.

| Step | What is done |
|---|---|
| 1. Checks | Linux x86_64? basic tools present? free disk space |
| 2. Madalean | Madalean's code and web interface are copied into `~/.local/share/madalean/versions/<version>`; a `current` link points to the version in service |
| 3. Environment | the small package manager **micromamba** is downloaded, then it installs the main environment, fixed in advance: Python 3.13, JupyterLab, the LaTeX engine tectonic, poppler (PDF reading), git… Every package is checked against its SHA-256 fingerprint |
| 4. Verified components | fonts (DejaVu Sans Mono, Noto Sans Math), TeX bundle (to typeset PDFs without a network), **elan** (Lean's version manager), **llama.cpp** (engine of the local models, for your NVIDIA card or for the processor), **madalean-net** (the embedded Tailscale node, which lets your devices reach the host) |
| 5. Lean workspaces | Lean workspaces already built on the computer are reused (through hard links: no extra space); otherwise, with `--build-workspace`, the “Current Lean” workspace is built |
| 6. Local models | the models chosen in the plan are downloaded into `~/models`; those already there are reused, never moved |
| 7. Service | the systemd user service `madalean` is installed and started: Madalean runs in the background as soon as your session opens |
| 8. Menu | the **“Madalean Server”** app is added to the applications menu (the Madalean icon with a small server badge): Madalean’s window on this computer, with the server’s status, Start / Stop / Restart buttons and the logs. Without the system library webkit2gtk-4.1, the entry opens a Chromium window (or Chrome, Brave, Edge, Vivaldi), else your browser; the final summary says which |
| 9. Check | a health check of each component, then a connection test to the server |

At the end, the script shows the time taken, the space used and the address to open: `http://127.0.0.1:11500`. The
full log is in `~/.local/share/madalean/install.log`.

## What is already on your computer

Madalean **never uses `sudo`** and **never runs your distribution's package manager** (`pacman`, `apt`, `dnf`,
`zypper`…). It changes no program of the system. For what it finds already installed:

| Already present | What Madalean does |
|---|---|
| Built Lean workspaces, Lean versions in `~/.elan` | reused **read-only** for the import; `~/.elan` is never modified |
| Models in `~/models` | reused (checked by fingerprint), never moved |
| The system's SageMath | reused if it is compatible and you choose it; otherwise Madalean installs its own copy on demand |
| TeX Live | used as a fallback, or first if you choose it |
| The system's Python | never modified; the server uses its own Python |
| Tailscale, Ollama | left in place; no conflict |

Details, and what is best in each case: [What Madalean installs](components.md).

When something can only come from your distribution — this is the case of **bubblewrap**, which isolates
compilations and computations in a “sandbox” —, the script **prints the exact command** for you to run, for example
`sudo pacman -S bubblewrap` on Arch Linux or `sudo apt install bubblewrap` on Debian and Ubuntu. The commands for
each distribution are in [What Madalean installs › bubblewrap](components.md#bubblewrap-the-sandbox).

## install.sh options

`./install.sh --help` lists them all.

| Option | Effect |
|---|---|
| `--yes`, `-y` | no questions: the defaults |
| `--assistant` | forces the terminal assistant (even when it would not be offered) |
| `--plan FILE` | installs according to a plan saved by the assistant or by the graphical installer |
| `--dry-run` | examines the computer and shows the plan, installs nothing |
| `--models all\|prover\|none` | local models: all three, the prover only, or none (no question: all three; the assistant advises from the graphics card) |
| `--sage later\|now\|system` | SageMath: on first use of “Calcul” (default), right away, or the system's one |
| `--tex own\|system` | LaTeX: Madalean's (default) or the system's TeX Live first |
| `--cpu` \| `--gpu` | model engine for the processor, or for the NVIDIA card (default: the card if the driver is suitable) |
| `--no-models` | downloads no local model (files already in `~/models` are still used) |
| `--no-workspaces` | installs no Lean workspace |
| `--build-workspace` | builds the “Current Lean” workspace if none is found (≈ 5 GB, network needed) |
| `--build-net` | builds the Tailscale node `madalean-net` from source (it must give exactly the expected fingerprint) |
| `--offline FOLDER` | installs without a network, from an export made with `./export_offline.sh` |
| `--prefix FOLDER` | installation folder (default `~/.local/share/madalean`) |
| `--config-dir FOLDER` | settings and data folder (default `~/.config/madalean`) |
| `--cache-dir FOLDER` | cache folder (default `~/.cache/madalean`) |
| `--no-systemd` | does not install the systemd service (you then start Madalean yourself) |
| `--no-desktop` | adds no entry to the applications menu |
| `--port N`, `--remote-port N` | server ports: local interface (default 11500) and access of linked devices (default 11501) |


## Where your choices are recorded

The choices made at installation (local models, SageMath, LaTeX…) are written to `~/.config/madalean/setup.json`.
Madalean reads this file at first start and applies the settings that follow from it, for example `sage_source`
(which SageMath to use) and `tex_engine` (which LaTeX to use); you can change
them at any time (the application also reads them through `GET /api/setup`). See [First configuration › Choices made at installation](first-config.md#choices-made-at-installation).

At the first start in the browser on the host, the [“First steps”](first-config.md#the-first-steps-assistant)
assistant shows these choices again (recommended choice and reason for this machine) and lets you change them.

## Where things are

| What | Where |
|---|---|
| Madalean and all its components | `~/.local/share/madalean/` |
| Installation log | `~/.local/share/madalean/install.log` |
| Settings, installation choices, projects, dossiers, linked devices, keys (if no keyring) | `~/.config/madalean/` |
| Search index, caches | `~/.cache/madalean/` |
| Local models | `~/models/` |
| Jupyter notebooks | `~/Documents/Madalean/notebooks/` |
| systemd service | `~/.config/systemd/user/madalean.service` |

At first start, if you had Lean AI Station 1.x, the server **copies** (never moves) your settings, dossiers and
library from `~/.config/lean-ai-station/`.

## Starting and stopping

The service starts with your session. Open the interface on the host: **“Madalean Server”** in the applications
menu, or `http://127.0.0.1:11500` in a browser.

“Madalean Server” is the host computer’s app: it shows Madalean in its own window (no pairing code: it is this
computer) and, in its **Server** menu (or its icon next to the clock), the server’s status, **Start**, **Stop**,
**Restart**, **Open the logs** and **Open in the browser**. When the server stops, the window shows the server panel;
when it comes back, the window returns to Madalean by itself. If the service is not installed, the panel says so and
gives the command to reinstall it. The “Madalean” app (AppImage, no badge) is for the **other** computers: see
[Link a device](pairing.md).

In a terminal, if needed:

```bash
systemctl --user status madalean      # status
systemctl --user restart madalean     # restart
journalctl --user -u madalean -e      # log
```

Next: [First configuration](first-config.md), then [First run](first-run.md) for a first statement.

## Installing without a network

For a computer without Internet access: on a connected computer where Madalean is installed, `./export_offline.sh`
prepares a folder with everything needed (packages, components, Lean workspaces, models). Copy this folder to the
other computer (USB stick, disk), then:

```bash
./install.sh --offline /path/to/the-export
```

SHA-256 fingerprints are checked as for an online installation.

## Updating

Madalean updates **from the application**, in “Settings › Updates”: each new version is **signed**, checked,
installed next to the old one, then put into service; the previous version is kept to roll back. There is no need
to run `install.sh` again. Details: [Updates](updates.md).

## Uninstalling

From the source folder (or `~/.local/share/madalean/current`):

```bash
./uninstall.sh
```

The script **first lists** exactly what will be removed, with the size of each item, then **asks for
confirmation**. It first stops the service and all its processes.

| Removed | Kept |
|---|---|
| `~/.local/share/madalean` (environment, components, Lean workspaces installed by Madalean, TeX bundle, Tailscale node state, Madalean versions) | `~/.config/madalean`: your settings, projects, dossiers, linked devices and keys |
| `~/.cache/madalean` | `~/models`: your models |
| the systemd service and the menu entry | `~/Documents/Madalean`: your notebooks |
| | never touched: `~/.elan`, system packages, the system's Tailscale |

Options:

| Option | Effect |
|---|---|
| `--purge` | also offers, with one question each, to remove `~/.config/madalean` and `~/models` |
| `--yes` | does not ask the general confirmation (the `--purge` questions are still asked) |
| `--prefix`, `--config-dir`, `--cache-dir` | give them if you changed them at installation |

Keys stored in the system keyring stay in the keyring: remove them first in “Settings › Providers” (“Remove the
key”) if you want them erased.
