---
id: troubleshooting
title: Troubleshooting
order: 400
section: help
audience: all
summary: Error messages in plain language, their cause and what to do.
---

# Troubleshooting

“Settings › System” shows the state of each component (Lean workspaces, models, TeX, fonts, Jupyter, disk) with a
repair button when one exists. Start there.

## Connection and devices

### The device cannot reach the host

1. Is the host computer on, and not asleep?
2. Is Tailscale **connected** on both devices, with the same account? (Tailscale app: switch on.)
3. Is the server running? On the host: `systemctl --user status madalean`.
4. Does the Tailscale rule exist? On the host: `scripts/tailscale_setup.sh --status`.
5. Is the address typed in full, `pc-name.tailXXXX.ts.net` (port 10500 by default)?

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

The key was badly copied (extra space), revoked, or the account has no credit left. Create it again in the
provider's console and paste it again. Madalean pauses the provider for 12 h after a key refusal: saving a new key
lifts the pause.
<!-- verify after integration: saving a new key clears the key_refused pause -->

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

### “Lean refuses to compile this code: …”

The code contains a construct that could run code on the host (`#eval`, `macro`, `elab`, `unsafe`…) or an `import`
outside Mathlib and its dependencies: Madalean refuses to compile it (see
[Security](security.md#code-run-on-the-host)). Remove the construct named in the message. If the word at fault is
just a variable name (`prefix`, `syntax`…), rename the variable.
<!-- verify after integration: exact wording of the exec_risks refusal message -->

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

No TeX engine (XeLaTeX or LuaLaTeX) is installed. The HTML prints to PDF from the browser. For the real PDF: install
TeX Live (“Settings › Updates” gives the command for your distribution).

### Symbols are missing in the PDF

The DejaVu Sans Mono and Noto Sans Math fonts must be present on the host; “Settings › System” checks it.

## Jupyter

### “Jupyter is not available”

JupyterLab is not installed on the host, or did not start. “Settings › System” gives the cause; the install command
is in “Settings › Updates”.

### “Jupyter is reachable only from the host”

The host has not opened Jupyter to linked devices (“Settings › Notebook and access”, on the host).

## When nothing works

```bash
systemctl --user restart madalean
journalctl --user -u madalean -e
```

The log contains no key and no token: you can attach it to a problem report.
