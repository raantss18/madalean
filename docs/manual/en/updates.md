---
id: updates
title: Updates
order: 310
section: settings
audience: all
summary: What updates on its own, what needs a click, how an update is verified, and how to roll back.
---

# Updates

Everything updates from within Madalean, without a terminal, by a single rule: **install alongside, verify, switch,
then delete the old version**. A failure changes nothing and you are told.

## What is updated, and how

Everything is set in “Settings › Updates”.

| Component | Default behaviour |
|---|---|
| Madalean (server and interface), “Madalean itself” part | checked every week (except in *Local* mode), downloaded, verified, installed at a quiet moment (no running work), then restarted; “Install” and “Restart now” do it at once. The previous version is kept for rolling back |
| Desktop application (AppImage) | replaces itself after verification; the new version opens at the next start (or at once with “Restart”) |
| Android application | the app's “Automatic updates” setting: it checks at most twice a day, downloads and verifies the signature; installing always asks for your confirmation (Android rule) |
| Lean, Mathlib, Lean packages of the “Current Lean” workspace, SageMath, LaTeX (“Tracked components” part) | automatic: installed alongside, verified (test theorem and re-check of the proved dossiers), switched |
| Goedel models, catalogue of online models | automatic, checksums verified |
| “Prover” workspace (Lean 4.9) | **never**: pinned, it is the models' training environment |
| llama.cpp | notification only; its pinned version changes with Madalean's versions |
| Programs installed on the system outside Madalean (“System components” part) | notification only, with the exact command and an “Open a terminal with the command” button; you type your password. Madalean never runs `sudo`, `pacman`, `apt` or `dnf` itself. |

Untick “Install automatically when nothing is running” to be told before each installation instead of the automatic
behaviour. “Check every week (nothing installs without your click)” sets the automatic check; “Check for updates”
runs it at once.

## Why a Madalean update is safe

Every published version comes with a list of checksums (`SHA256SUMS`) **signed** with an Ed25519 key kept outside
GitHub. The public key is built into Madalean. A version whose signature does not match is refused, **even if the
GitHub account were compromised**. The update channel (`updates/stable.json`, on the site) is signed the same way.

To verify a download yourself: see the [install page](site:install#verify).

## After a Lean or Mathlib update

The proved dossiers of the affected workspace are re-checked automatically (“Re-checking proofs” part, “Re-check
now” button). A dossier
whose proof no longer passes (a renamed lemma, a changed tactic) is flagged; its old verdict is never shown alone.

## Rolling back

For Madalean: “Settings › Updates”, “Madalean itself” part, “Go back to …” button (with the number of the previous
version). For Lean and Mathlib, the old version is replaced only after a successful verification; if it fails,
nothing changes.
