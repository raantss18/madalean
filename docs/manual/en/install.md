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
| System | Linux (Arch/EndeavourOS, Fedora, Debian, Ubuntu, openSUSE) | recent Arch or Fedora |
| Graphics card | none (local models on the CPU, very slow) | NVIDIA with ≥ 8 GB of memory |
| RAM | 16 GB | 32 GB |
| Disk | ≈ 40 GB free | SSD |

Without an NVIDIA card everything works, but a proof by a local model can take tens of minutes. Online models (free
or with a key) do not depend on your graphics card.

The NVIDIA driver and the CUDA Toolkit (`nvcc`) must be installed **by you** beforehand: the script never touches
drivers.

| Distribution | Driver + CUDA |
|---|---|
| Arch / EndeavourOS | `sudo pacman -S nvidia-open nvidia-utils cuda` |
| Fedora | driver from RPM Fusion (`akmod-nvidia`, `xorg-x11-drv-nvidia-cuda`), CUDA from the NVIDIA repository |
| Debian / Ubuntu | `sudo apt install nvidia-driver-XXX nvidia-cuda-toolkit` (or the NVIDIA repository) |
| openSUSE | NVIDIA repository |

## Install

```bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh --install-deps
```

`--install-deps` installs the build tools once with `sudo` (you type your password). The script can be re-run
safely: it resumes where it stopped and does not redo what is already done.

It installs, at user level:

- the Lean version manager **elan** and two Lean **workspaces**: “Prover” (Lean 4.9 and the Mathlib the Goedel
  models were trained on; Mathlib is built from source, ≈ 1 h 30 once) and “Recent Lean” (latest Mathlib);
- the **llama.cpp** engine built for your card (pinned version);
- three local models (≈ 5 GB each, SHA-256 checksums verified): Goedel-Prover-V2-8B (proofs),
  Goedel-Formalizer-V2-8B (translation into Lean), Qwen3-8B (explanations);
- the Madalean server and its systemd user service `madalean.service`.

Useful options (`./install.sh --help`):

| Option | Effect |
|---|---|
| `--backend cpu` | no graphics card: engine for the CPU |
| `--no-models` | does not download the local models (≈ 15 GB): only online models will be used |
| `--no-prover49` | skips the Lean 4.9 workspace (the long Mathlib build) |
| `--no-current` | skips the “Recent Lean” workspace |
| `--no-service` | does not install the systemd service |

## Where things are

| What | Where |
|---|---|
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

Then open the interface on the host: `http://127.0.0.1:11500`, or the Madalean desktop app (AppImage), which finds
the host by itself. Next: [First run](first-run.md).
<!-- verify after integration: final repository name raantss18/madalean, install.sh installs the 2.0 server and unit, menu entry name -->

## Uninstalling

`./uninstall.sh` lists exactly what will be deleted before doing it. Your dossiers are not deleted without your
consent.
<!-- verify after integration: uninstall.sh covers ~/.config/madalean and the systemd unit in 2.0 -->
