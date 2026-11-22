---
id: components
title: What Madalean installs, component by component
order: 12
section: start
audience: all
summary: Lean, SageMath, JupyterLab, local models, LaTeX, Python, Tailscale, Ollama, bubblewrap — what each is for, whether it is required, its size, where it lives, whether to reuse what is already installed, and how to repair or remove it.
---

# What Madalean installs, component by component

Madalean relies on several programs: Lean to check proofs, SageMath to compute, LaTeX to typeset PDFs, AI models…
For each of them this page says **what it is for**, whether it is **required**, **how much space** it takes,
**where it lives**, and whether it is better to **reuse** a version already installed on your computer or to let
Madalean install **its own copy**.

One principle holds for all of them: Madalean installs its components in **its own folder**,
`~/.local/share/madalean` (called “Madalean's folder” below). It never modifies the programs of your system and never
runs `sudo` or your distribution's package manager. When it reuses a program that is already installed, it does so
**read-only**.

## Overview

| Component | Used for | Required | Space | Where |
|---|---|---|---|---|
| [Lean, elan, Mathlib workspaces](#lean-elan-and-the-mathlib-workspaces) | checking every proof | yes | ≈ 5 GB per built workspace | Madalean's folder |
| [SageMath](#sagemath) | the “Calcul” screen, experiments | no | ≈ 5 GB (Madalean's copy) | Madalean's folder, or the system's |
| [JupyterLab](#jupyterlab) | notebooks | yes (included) | part of the main environment | Madalean's folder |
| [Local models](#local-models) | working without Internet | no | ≈ 5 GB per model | `~/models` |
| [LaTeX](#latex) | PDF export | yes (included) | ≈ 50 MB for the TeX bundle | Madalean's folder, or the system's TeX Live |
| [Python](#python) | running Madalean | yes (included) | part of the main environment | Madalean's folder |
| [Tailscale](#tailscale) | reaching the host from your devices | yes (included) | ≈ 25 MB | Madalean's folder |
| [Ollama](#ollama) | — (optional, already yours) | no | — | the system's |
| [bubblewrap](#bubblewrap-the-sandbox) | isolating compilations and computations | recommended | < 1 MB | system package |

The main environment (Python, JupyterLab, tectonic, poppler, git…) takes ≈ 1.3 GB once installed.

## Repair, install later, remove

**In the application.** “Settings › System”, “Health” part, checks each component (Lean workspaces, local model
server, models, LaTeX, fonts, Jupyter, SageMath, sandbox, disk). A line with a problem has a “Repair” button when a
repair exists; “Check again” runs the check again. Repairs are started from the host computer. “Settings ›
Updates”, “Tracked components” part, shows the installed version of Lean, Mathlib, SageMath and LaTeX, and the
“System components” part the programs you install yourself (such as bubblewrap), with the exact command and the
“Open a terminal with the command” button.

<!-- verify after integration: name of the screen that lists the components and offers « install later / repair » (a dedicated « Components » screen may be added to Settings › System). -->

**In a terminal**, on the host, the same tool `install.sh` uses:

```bash
cd ~/.local/share/madalean/current
~/.local/share/madalean/env/bin/python -m madalean.deps health           # state of each component
~/.local/share/madalean/env/bin/python -m madalean.deps install sage     # install or repair a component
~/.local/share/madalean/env/bin/python -m madalean.deps list             # known components, versions
```

Component names are `micromamba`, `env` (the main environment), `sage`, `fonts`, `tex-bundle`, `elan`, `llama.cpp`
and `madalean-net`. `rollback <component>` goes back to a component's previous version. Running `./install.sh` again
also repairs whatever is missing, without redoing what is fine.

**Removing** a required component makes no sense; everything goes away with [uninstalling](install.md#uninstalling).
Optional components are removed as described in their part.

## Lean, elan and the Mathlib workspaces

**What it is for.** Lean is the proof checker: it decides, and nothing is declared proved without its approval.
Mathlib is the large library of mathematics written in Lean. A **workspace** (or Lean workspace) is a version of Lean
together with an already compiled Mathlib, ready to use. **elan** is the small program that installs and selects
Lean versions.

**Required**: yes.

**The workspaces.**

| Workspace | Content | Role |
|---|---|---|
| “Current Lean” (`lean-current`) | a recent Lean (v4.34.1 when this page was written) and the matching Mathlib | the default workspace, kept up to date |
| “Prover” (`lean-prover49`) | Lean 4.9 and the Mathlib of that time | the one the Goedel models were trained on; never updated |

**Space**: ≈ 5 GB per built workspace; elan itself is ≈ 5 MB.

**Where**: `~/.local/share/madalean/workspaces/` and `~/.local/share/madalean/elan/`.

**Reuse or not.** If Lean workspaces are already built on the computer (for example those of Lean AI Station 1.x),
`install.sh` **reuses them through hard links**: files are not copied, no extra space. Lean versions already in your
`~/.elan` are read for this import, **never modified**. This is the recommended solution when possible. Otherwise,
`./install.sh --build-workspace` builds the “Current Lean” workspace (≈ 5 GB, network needed, it takes a good while).
The “Prover” workspace is not built by the script: it is reused if it exists.

**Install later, repair**: “Settings › Lean workspaces” gives the state of each workspace; run
`./install.sh --build-workspace` again if none is installed. New versions of Lean and Mathlib are installed from
“Settings › Updates” (see [Updates](updates.md)).

## SageMath

**What it is for.** SageMath is free software for mathematical computation (algebra, number theory,
combinatorics, plots…). Madalean uses it in the “Calcul” screen, for the experiments of the conjecture workshop and
for the examples and figures of an article. See [Calcul](calcul.md).

**Required**: no. Without SageMath, Python notebooks work, and so does the rest of Madalean.

**Two possibilities.**

| | Madalean's copy | Your system's SageMath |
|---|---|---|
| Version | SageMath 10.10 | yours, **10.0 or newer** |
| Space | ≈ 1.4 GB to download, ≈ 5 GB on disk | none extra |
| Updates | by Madalean (“Tracked components”) | by your distribution |
| Condition | none | the Jupyter kernel `sagemath` must be installed (for example in `/usr/share/jupyter/kernels/sagemath`) |

**What is recommended.** If your system already has a compatible SageMath (version ≥ 10.0 **and** its Jupyter
kernel `sagemath`), reuse it: you save 5 GB and your distribution keeps it up to date. Otherwise, let Madalean
install its own copy. In both cases, the computation runs in **the same sandbox**: no network, no access to your home
folder (see [bubblewrap](#bubblewrap-the-sandbox)).

**The `sage_source` setting** fixes this choice:

| Value | Effect |
|---|---|
| `auto` (default) | Madalean's copy when it is installed, else the system's |
| `own` | always Madalean's copy |
| `system` | always the system's |

It is written at installation (`--sage`, or the choice made in the graphical installer) and can then be changed in
the application. <!-- verify after integration: where sage_source is shown and changed in the app (Settings › System or the Calcul screen). -->

**Install later.** By default (`--sage later`), Madalean's copy is installed **on first use**: in a SageMath notebook
of the “Calcul” screen, “Install SageMath” button, on the host computer; the screen shows the step and the
percentage. To install it right away: `./install.sh --sage now`, or `python -m madalean.deps install sage` (see
[above](#repair-install-later-remove)).

**Removing Madalean's copy**: stop Madalean (`systemctl --user stop madalean`), delete
`~/.local/share/madalean/envs/sage` and the `~/.local/share/madalean/envs/sage-…` folders, then start it again.
<!-- verify after integration: no « remove SageMath » button in the app; removing envs/sage* by hand is safe. -->

## JupyterLab

**What it is for.** JupyterLab is the notebook environment: cells of code and their results. Madalean uses it for
the notebooks of the “Calcul” screen and for the “Notebook” screen (see [Jupyter and Sage](jupyter.md)).

**Required**: yes, it is part of Madalean's main environment; there is nothing to choose.

**Where**: in the main environment, `~/.local/share/madalean/env/`. The notebooks themselves are stored in
`~/Documents/Madalean/notebooks/`.

**Access from your other devices**: off by default. The `remote_jupyter` setting (“Settings › Notebook and access” ›
“Open the notebook to linked devices”, on the host only) opens it to linked devices. A notebook runs code on the
host: only turn it on if you trust your devices.

**Repair**: “Jupyter” line of “Health”, “Repair” button.

## Local models

**What they are for.** AI models that run **on the host computer**, without sending anything to the Internet. They
are used in *Local* mode (nothing leaves the computer) and, in *Automatic* mode, when the Internet is missing. See
[Models and keys](models-keys.md).

**Required**: no. Without a local model, Madalean uses online models (free, or with your keys).

**The engine, llama.cpp.** This is the program that runs the models. `install.sh` chooses the version suited to your
computer from the NVIDIA driver: a version for the graphics card (CUDA) if the driver is suitable, otherwise a
processor version (`--cpu` / `--gpu` force the choice). It is installed in Madalean's folder (≈ 25 MB for the
processor, ≈ 650 MB with the CUDA libraries), even if you take no model.

**The three models** (GGUF files, Q4_K_M quantization), in `~/models`:

| File | Role | Size |
|---|---|---|
| `Goedel-Prover-V2-8B.Q4_K_M.gguf` | the **prover**: writes Lean proofs | ≈ 5 GB |
| `Goedel-Formalizer-V2-8B.Q4_K_M.gguf` | the **translator**: puts statements into Lean | ≈ 5 GB |
| `Qwen3-8B-Q4_K_M.gguf` | the **explainer**: explanations and written proofs | ≈ 5 GB |

**When it is worth it.** A local model is only useful if it runs on a large enough graphics card. The recommended
plan follows this rule:

| Your computer | Advice |
|---|---|
| NVIDIA card with 10 GB of graphics memory or more, and 16 GB of RAM or more | all three models (`--models all`) |
| NVIDIA card with 8 to 10 GB of graphics memory | the prover only (`--models prover`) |
| less than 8 GB, or no NVIDIA card | **no local model advised** (`--models none`) |

Without a suitable card, a local model runs on the processor: a single answer can take many minutes, whereas online
models are both faster and better. As an order of magnitude, the prover is set up for a context of 24,000 tokens,
which takes about 7 GB of graphics memory.

**Reuse or not.** Files already in `~/models` (with their `.sha256` fingerprint) are reused and never moved.

**Adding a model later**: run `./install.sh --models all` again (only missing files are downloaded), or download a
specific model from the source folder:

```bash
./scripts/download_model.sh Q4_K_M formalizer explainer   # prover, translator, explainer
```

(any subset; `Q4_K_M` stands for the prover). Each file is checked against its fingerprint.

**Freeing the graphics card.** The local model is stopped after 10 minutes without work, to give the graphics memory
back to other programs (setting `local_idle_unload_minutes`, 0 = never; see
[First configuration](first-config.md#automatic-and-manual-behaviours)).

**Removing a model**: delete its file (and the `.sha256` next to it) in `~/models`. Madalean stops offering it;
uninstalling, by contrast, keeps `~/models`.

## LaTeX

**What it is for.** LaTeX typesets PDF documents: export of a dossier, a written proof, an article.

**Required**: yes, and included. Without LaTeX, Madalean opens an HTML version to print from the browser.

**Two possibilities.**

| | Madalean's LaTeX (recommended) | Your system's TeX Live |
|---|---|---|
| Program | **tectonic**, in the main environment | `xelatex` or `lualatex`, with `latexmk` |
| LaTeX packages | a fixed TeX bundle (version v33, ≈ 50 MB), downloaded once at installation | all those of your installation |
| Network | none after installation | none |
| Sandbox | yes | yes |

**What is recommended.** Madalean's LaTeX: it gives **the same result on every computer** (the TeX bundle is fixed
and verified), works **offline** and runs in the sandbox. An existing TeX Live is used anyway **as a fallback** if
tectonic fails. Choose to use it **first** if you need LaTeX packages missing from Madalean's TeX bundle; it then
requires TeX Live 2022 or newer, with `fontspec`.

**The `tex_engine` setting**:

| Value | Effect |
|---|---|
| `auto` (default) | tectonic first, the system's TeX Live as a fallback |
| `tectonic` | tectonic only |
| `system` | the system's TeX Live first |

It is written at installation (`--tex own` or `--tex system`, or the choice made in the graphical installer).
<!-- verify after integration: where tex_engine is shown and changed in the app; fallback order of export.py with tex_engine = system. -->

**Repair**: “LaTeX (PDF export)” line of “Health”, “Repair” button, or `python -m madalean.deps install tex-bundle`.
The fonts used in PDFs (DejaVu Sans Mono, Noto Sans Math) are installed with Madalean and checked in the same place.

## Python

Madalean has **its own Python** (3.13), in its main environment (`~/.local/share/madalean/env/`). Your system's
Python is **never modified**, and the server does not use it. Only the launcher of the experiment kernels may find
it on your system, if there is one, to start a Python kernel in the sandbox. Nothing to choose, nothing to install.

## Tailscale

**What it is for.** Tailscale creates an encrypted private network between your devices (your “tailnet”). Madalean
uses it so that your phone, your tablet or another PC can reach the host computer, without opening anything to the
Internet.

**Included**: Madalean ships **its own Tailscale node**, `madalean-net` (≈ 25 MB, in Madalean's folder). It shows up
as “madalean” in your tailnet. It needs neither `sudo` nor a system service.

**A Tailscale already installed** on the host can stay: no conflict, both coexist.

**Setting up**: the node must be approved once in your Tailscale account, then each device is linked. See
[Link a device](pairing.md) and [Tailscale](tailscale.md).

## Ollama

Ollama is another program that runs models locally. Madalean **does not install it** and does not need it. If it is
already installed and running on the host, its models show up among the available local models and can be chosen;
the two programs coexist without conflict.

Mind only the **graphics memory**: if Ollama and Madalean's local model run at the same time, they share the graphics
card, and one or the other may run out of memory. “Settings › System” shows the graphics memory used by each
program.

## bubblewrap, the sandbox

**What it is for.** bubblewrap is a small Linux tool that locks a program in a **sandbox**: no network, no access to
your home folder, with Lean and Mathlib read-only. Madalean uses it for every Lean compilation, every LaTeX
compilation and every computation (SageMath, Python). This is an important protection, since the code compiled or
run may come from an AI model. See [Security](security.md).

**Required**: no, but **strongly recommended**. Without bubblewrap, compilations and computations run without this
isolation; “Settings › System” shows whether the sandbox is active.

**Installing**: it is a package of your distribution, which Madalean cannot install for you (that would need `sudo`).
Run the command for your system yourself:

| Distribution | Command |
|---|---|
| Arch Linux, Manjaro | `sudo pacman -S bubblewrap` |
| Debian, Ubuntu, Linux Mint | `sudo apt install bubblewrap` |
| Fedora | `sudo dnf install bubblewrap` |
| openSUSE | `sudo zypper install bubblewrap` |

Then “Check again” in “Settings › System”: the sandbox line should turn fine.
