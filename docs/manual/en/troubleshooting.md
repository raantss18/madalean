---
id: troubleshooting
title: Troubleshooting
order: 400
section: help
audience: all
summary: Error messages in plain language, their cause and what to do.
---

# Troubleshooting

“Settings › System”, “Health” part, shows the state of each component (Lean workspaces, models, TeX, fonts, Jupyter,
sandbox, disk) with a “Repair” button when one exists. Start there.

## Installation

The full installation log is in `~/.local/share/madalean/install.log`. `install.sh` is safe to run again: it resumes
where it stopped. See [Installing Madalean](install.md).

### The .run installer does not start

- **Nothing happens on double-click, or “Permission denied”**: the file is not executable. Right-click › “Properties”
  › “Permissions” › “Allow executing file as program”, or in a terminal `chmod +x Madalean-installer.run`, then
  start it again.
- **Double-clicking opens the file in a text editor**: start it from a terminal, `./Madalean-installer.run`
  (with the right version number).
- **“Damaged or modified file (wrong SHA-256)”**: the file was damaged during the download, or it is
  incomplete. Delete it and **download it again** from the releases page; never bypass this check.


### No browser opens

Without a graphical session, the installer switches by itself to the terminal assistant. If there is a desktop but no
browser opens, the installer prints the address of its page in the terminal (`http://127.0.0.1:…`, with its
one-time key): copy it into a browser on the **same** computer. You can also force the terminal assistant from
source: `./install.sh --assistant` (or `./Madalean-installer.run --terminal`).

### The disk is full

Step 1 shows the free space. Plan for ≈ 6 GB without local models or SageMath, ≈ 25 GB with the local models, 5 GB
more for SageMath (see [Installing Madalean](install.md#before-you-start)). Free some space, or reduce the plan:
`--models none` (or `--models prover`), `--sage later`. Then run `install.sh` again: what is already installed is not
redone. Ongoing downloads are kept in `~/.local/share/madalean/downloads/` and resumed.

### “micromamba failed”

Installing the main environment (step 3) failed, most often because of a network interruption or a full disk. The
last lines of the log are shown; details are in `~/.local/share/madalean/install.log`. Check the connection and the
free space, then run `install.sh` again.

### “Wrong SHA-256 fingerprint: …”

A downloaded file does not match the expected fingerprint: it was truncated or altered on the way. The faulty file
is deleted; run `install.sh` again, which downloads it again. If the error repeats, a proxy or filter on your network
may be modifying downloads.

### No NVIDIA card, or driver too old

This is not an error: Madalean then installs the processor version of the model engine and advises no local model.
Online models work normally. If you do have an NVIDIA card, check that the driver is installed (`nvidia-smi` must
answer), then run `./install.sh --gpu` again. See [Local models](components.md#local-models).

### The system's SageMath is not used

To be reused, your system's SageMath must be version 10.0 or newer **and** provide its Jupyter kernel `sagemath`
(for example `/usr/share/jupyter/kernels/sagemath`). Otherwise Madalean uses its own copy (≈ 5 GB). Install the
Jupyter kernel with your distribution, or let Madalean install its copy. See [SageMath](components.md#sagemath).

### LaTeX export fails

“Settings › System”, “Health” part, “LaTeX (PDF export)” line: “Repair” reinstalls the TeX bundle. If you use the
system's TeX Live first (`tex_engine = system`), it must be version 2022 or newer, with `fontspec`. See also
[Export](#export) below and [LaTeX](components.md#latex).

### The service does not start

At the end of the installation, “The server does not answer yet” means the service did not start in time. Look at
its log:

```bash
systemctl --user status madalean
journalctl --user -u madalean -e
```

The log gives the cause (port 11500 already taken by another program, missing component…). If `systemctl --user` is
not available (some containers or sessions without systemd), start Madalean by hand:
`~/.local/share/madalean/current/bin/madalean serve`.

### The sandbox is reported inactive

bubblewrap is not installed: it is a package of your distribution, to install yourself (for example
`sudo apt install bubblewrap`). See [bubblewrap](components.md#bubblewrap-the-sandbox).

## Connection and devices

### The device cannot reach the host

1. Is the host computer on, and not asleep?
2. Is Tailscale **connected** on the device, with the same account as the host? (Tailscale app: switch on.)
3. Is the server running? On the host: `systemctl --user status madalean`.
4. Is Madalean's Tailscale node approved and running? On the host: `curl -s http://127.0.0.1:11500/api/net` must
   show `"state": "running"` (otherwise, see [Link a device › Step 1](pairing.md)). If you use the system's Tailscale
   instead: `scripts/tailscale_setup.sh --status`.
5. Is the address typed in full, `madalean.tailXXXX.ts.net` (or `pc-name.tailXXXX.ts.net:10500` with the system's
   Tailscale)?

### “This device is not (or no longer) linked to Madalean”

The device was unlinked, or its data was erased. Ask for a new code on the host and link it again.

### The HTTPS certificate is refused, or the first connection is very slow

HTTPS is not enabled on your tailnet: see [Tailscale › Enable HTTPS](tailscale.md#enable-https). The very first
connection may take a few seconds while the certificate is issued.

### “Host computer only”

This setting opens the machine to other devices; it can only be changed on the host. See [Security](security.md).

## Models

### “No model available”

- *Local* mode: no local model is installed or loadable. “Settings › System” says which one is missing;
  `./install.sh` downloads the models.
- *Online* mode: no network, or all providers are paused (quotas). Switch to *Automatic* to use the local models as a
  fallback.

### “The provider refuses the key”

The key was badly copied (extra space), revoked, or the account has no credit left. Create it again on the
provider's site and paste it again (“Settings › Providers”): Madalean tests it at once. After a key refusal, Madalean
pauses the provider for 12 h (“Paused for now (key refused (check it))”). For Hugging Face, a new token that passes
the test lifts the pause at once; for the other providers, the pause runs its course, then the new key is used
normally.

### The local model is slow, or “not enough GPU memory”

Another program is using the graphics card (game, another AI). “Settings › System” shows the memory used per
application. Without an NVIDIA card, local models run on the processor: expect minutes per answer.

### “Paused: quota reached” on a free provider

Normal: Madalean moves on to the next model and retries the provider later (after the time given by the provider, or
the next day for a daily quota).

## Lean

### “Lean rejects the statement”

The translation is not valid Lean for this workspace (unknown name, notation from another Mathlib version). Lean's
message is shown below the statement. “Fix the statement…” reruns the translation with the error; or “Edit by
hand”.

### “Refused before compiling: …”

The code contains a construct that could run code on the host (`#eval`, `macro`, `elab`, `unsafe`,
`native_decide`…) or an `import` outside Mathlib and its dependencies: Madalean refuses to compile it (see
[Security](security.md#code-run-on-the-host)). The message gives the kind of construct found, for example
meta-programming, system access (IO, unsafe) or the import of a module that is not allowed. Remove it. If the word at
fault is just a variable name (`prefix`, `syntax`, `IO`…), rename the variable.

### “No proof found”

The attempts are exhausted. This does not prove the statement false. Try: re-reading the statement (missing
hypothesis?), “Another method”, a stronger model (a key), “Split into lemmas”, or a hint in a follow-up request
(“use induction on $n$”).

### “Proof rejected: contains sorry” or “non-standard axiom”

The strict verdict rejects an incomplete proof or one that adds an axiom. Only `propext`, `Classical.choice` and
`Quot.sound` are allowed.

### “Compilation timeout”

Compilation exceeded the maximum time (“Settings › Models”, 10 to 1800 s). A tactic such as `simp` or `nlinarith`
can search for a long time; a more explicit proof compiles faster.

### “Lean workspace not found” or “workspace not ready”

The workspace is not installed or its build is not finished. “Settings › Lean workspaces” gives its state; rerun
`./install.sh` if needed.

### “This dossier already has work in progress”

A dossier has only one active job. Wait for it to finish, or “Stop”.

## Export

### “No LaTeX on the host computer: the HTML version opens”

Madalean's LaTeX engine (installed by `./install.sh`) is missing or could not typeset the document, and no system
LaTeX replaced it. The HTML prints to PDF from the browser. For the real PDF: “Settings › System”, “Health” part,
LaTeX line, “Repair” button (or rerun `./install.sh`).

### Symbols are missing in the PDF

The DejaVu Sans Mono and Noto Sans Math fonts are installed with Madalean; “Settings › System” checks that they are
present. Rerun `./install.sh` if one is missing.

## Jupyter

### “Jupyter is not available”

JupyterLab (installed with Madalean) is missing or did not start. “Settings › System” gives the cause, with a
“Repair” button.

### “Jupyter is reachable only from the host”

The host has not opened Jupyter to linked devices (“Settings › Notebook and access”, on the host).

## When nothing works

```bash
systemctl --user restart madalean
journalctl --user -u madalean -e
```

The log contains no key and no token: you can attach it to a problem report.
