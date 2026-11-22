---
id: install
title: Install on the host computer
order: 10
section: start
audience: all
summary: Recommended hardware, installation with install.sh, what is installed and where.
---

# Install on the host computer

The **host computer** is the machine that runs Madalean: the server, Lean, the local models and your data. Other
devices install only a light app (or nothing at all: a browser is enough), see [Link a device](pairing.md).

## Hardware and system

| | Minimum | Recommended |
|---|---|---|
| System | 64-bit Linux (x86_64), any recent distribution | — |
| Graphics card | none (local models on the CPU, very slow) | NVIDIA with ≥ 8 GB of memory |
| RAM | 16 GB | 32 GB |
| Disk | ≈ 40 GB free | SSD |

Without an NVIDIA card everything works, but a proof by a local model can take tens of minutes. Online models (free
or with a key) do not depend on your graphics card.

With an NVIDIA card, only the **NVIDIA driver** must be installed (by you, with your distribution's tools): the
script never touches drivers and does not need the CUDA Toolkit. If the driver is too old, the script installs the
CPU engine.

## Install

```bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh
```

No `sudo`, no system package: everything goes into a single folder, `~/.local/share/madalean`. Only `bash`, `curl`
and `tar` are needed. The script can be re-run safely: it resumes where it stopped and does not redo what is already
done. Every download is checked against its SHA-256 checksum.

It installs:

- Madalean itself (server and interface);
- a Python environment with JupyterLab, the LaTeX engine and its fonts (PDF export then works without network);
- the Lean version manager **elan** and the Lean **workspaces** (see below);
- the **llama.cpp** engine (pinned version, for your card or for the CPU);
- Madalean's built-in Tailscale node, to reach the host from your other devices (see [Tailscale](tailscale.md));
- three local models (≈ 5 GB each) in `~/models`: Goedel-Prover-V2-8B (proofs), Goedel-Formalizer-V2-8B
  (translation into Lean), Qwen3-8B (explanations). Models already in `~/models` are reused;
- the systemd user service `madalean.service` and the “Madalean” entry in the applications menu.

SageMath (for the “Calcul” screen) is not installed in advance: it is installed on demand, see [Calcul](calcul.md).

**Lean workspaces.** The script reuses the Lean workspaces already built on the machine (for example those of Lean
AI Station 1.x), without taking extra space. If it finds none, run it again with `--build-workspace`: it builds the
“Current Lean” workspace (latest Mathlib, ≈ 5 GB, network needed). The “Prover” workspace (Lean 4.9, the Mathlib the
Goedel models were trained on) is not built by the script: it is reused if it already exists.

Useful options (`./install.sh --help`):

| Option | Effect |
|---|---|
| `--cpu` | model engine for the CPU (no graphics card) |
| `--no-models` | does not download the local models (≈ 15 GB): only online models will be used |
| `--no-workspaces` | installs no Lean workspace |
| `--build-workspace` | builds the “Current Lean” workspace if none exists |
| `--no-systemd` | does not install the systemd service |
| `--no-desktop` | adds no entry to the applications menu |
| `--offline FOLDER` | installs without network, from an export made with `./export_offline.sh` |

## Where things are

| What | Where |
|---|---|
| Madalean and all its components | `~/.local/share/madalean/` |
| Settings, projects, dossiers, linked devices | `~/.config/madalean/` |
| Search index, caches | `~/.cache/madalean/` |
| Local models | `~/models/` |
| Jupyter notebooks | `~/Documents/Madalean/notebooks/` |

On first start, if you had Lean AI Station 1.x, the server **copies** (never moves) your settings, dossiers and
library from `~/.config/lean-ai-station/`.

## Starting and stopping

The service starts with your session. In a terminal, if needed:

```bash
systemctl --user status madalean      # status
systemctl --user restart madalean     # restart
journalctl --user -u madalean -e      # log
```

Then open the interface on the host: “Madalean” in the applications menu, or `http://127.0.0.1:11500` in a
browser. Next: [First run](first-run.md).

## Uninstalling

`./uninstall.sh` lists exactly what will be deleted and asks for confirmation before doing it. It deletes
`~/.local/share/madalean`, `~/.cache/madalean`, the systemd service and the menu entry. It **keeps** your settings,
projects and dossiers (`~/.config/madalean`), your models (`~/models`) and your notebooks (`~/Documents/Madalean`).
`./uninstall.sh --purge` additionally offers, with one question each, to delete `~/.config/madalean` and `~/models`.
