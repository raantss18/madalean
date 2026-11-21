---
id: security
title: Security, explained simply
order: 320
section: settings
audience: all
summary: Who can access Madalean, how devices are linked and unlinked, where the keys are, and what Madalean never does.
---

# Security, explained simply

## Who can talk to Madalean

Madalean listens at two doors, both closed to the outside of the host computer:

1. **The local door** (`127.0.0.1:11500`), used by the browser or desktop application **of the host**. It accepts
   only requests coming from the host itself.
2. **The device door** (`127.0.0.1:11501`), published on your private Tailscale network. Every request must present
   the **token** of a linked device, except the pairing page itself.

There is no Madalean account, no Madalean server on the Internet, no telemetry.

## Devices and codes

- Linking a device needs a **6-digit code** shown on the host: valid 5 minutes, usable once. Five wrong codes lock
  pairing for 10 minutes; rapid attempts are throttled.
- The device then receives a 256-bit **token**. The host keeps only a fingerprint of it (SHA-256): even someone who
  read the host's files could not recover the token.
- On the phone, the token is in Android's protected storage; on a PC, in the system keyring; in a browser, in a
  cookie inaccessible to the page's scripts.
- **Unlinking** a device (“Settings › Devices”) cuts its access immediately.

A lost or stolen device: unlink it from the host, and remove it from your Tailscale network.

## What a linked device cannot do

Some settings would open the machine; they can be changed **only from the host** (padlock in the interface):

- listening on the local network;
- opening Jupyter (which runs code) to linked devices;
- allowing experiments to run from a linked device, or without prior approval.

## Your API keys

Kept in the host's keyring (otherwise in a file readable only by you). Never sent back to the interface (it only
knows whether a key is saved), never written to a log, never sent to a provider other than their own.

## Code run on the host

- **Lean** compiles the proofs written by the models. Forbidden constructs (`sorry`, new axioms, search commands)
  are refused before compiling.
- **Lean can also run code** while it reads a file: `#eval`, `initialize`, `run_cmd`, tactics, macros or elaborators
  defined in the file (`elab`, `macro`, `syntax`…), `unsafe`, `implemented_by`. Since Lean code may come from a
  model, from the text of a paper or from a paired device, Madalean **refuses to compile** any file containing one of
  these constructs, at a single point that every compilation goes through. `import`s are limited to Mathlib, Aesop,
  Batteries, Std, Qq, ProofWidgets and Plausible. The check works on words, outside comments and strings: it can
  wrongly refuse a legitimate file (a variable named `prefix`, for instance); the refusal message names the
  construct.
- **Experiments of the conjecture workshop**: the code is shown to you, and runs only after your approval of **this
  exact code**. It runs with time, memory and file-size limits, without your keys or secret variables; if
  `bubblewrap` is installed, with a read-only file system in which your configuration folder, `~/.ssh` and your
  keyrings are hidden. The network is **not** cut for these experiments.
- **Jupyter** runs what you type into it, like any Jupyter installation.
- A model's text never becomes a system command.

## Documents from outside

PDFs, TeX sources, BibTeX files and website responses can be booby-trapped. Madalean never compiles a paper's TeX
(it only reads it), compiles its own TeX exports without any shell access, limits the size and content of archives,
and treats the text of sources as **data**: a passage saying “ignore your instructions” has no effect on the tools,
because answers grounded in your sources have access to no tool.

## What Madalean never does

- Open a port on the Internet (no Tailscale Funnel, no port forwarding).
- Run `sudo`, or install a system package for you.
- Send your data to a service you did not choose, or anything at all in *Local* mode.
- Show a proof as verified without Lean's strict verdict.
- Publish anything before you have approved, item by item, what leaves.
- Install an update whose signature is not valid.

An independent security review is done before each major version.
<!-- verify after integration: S-H review done before 2.0.0; forbidden-construct list in leancheck -->
