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

| Component | Default behaviour |
|---|---|
| Madalean (server and interface) | downloaded and verified in the background, installed at a quiet moment (no running work); previous version kept for one-click rollback |
| Desktop application (AppImage) | replaces itself, then restarts |
| Android application | downloaded and verified by the app; Android always requires **one tap** from you to install (system rule) |
| Lean, Mathlib, Lean packages of the “Recent Lean” workspace | automatic: installed alongside, verified (test theorem and re-check of the proved dossiers), switched |
| Goedel models, catalogue of online models | automatic, checksums verified |
| “Prover” workspace (Lean 4.9) | **never**: pinned, it is the models' training environment |
| llama.cpp | notification only (pinned version) |
| SageMath, JupyterLab, TeX, poppler | notification, and an “Install” button that opens a terminal with the exact command; you type your password. Madalean never runs `sudo`, `pacman`, `apt` or `dnf` itself. |

The “Ask before installing” setting (“Settings › Updates”) replaces the automatic behaviour by a notification.
Checks run every week and on demand. In *Local* mode, no check touches the network.
<!-- verify after integration: self-update installer, AppImage updater and APK download are built (§16); setting label -->

## Why a Madalean update is safe

Every published version comes with a list of checksums (`SHA256SUMS`) **signed** with an Ed25519 key kept outside
GitHub. The public key is built into Madalean. A version whose signature does not match is refused, **even if the
GitHub account were compromised**. The update channel (`updates/stable.json`, on the site) is signed the same way.

To verify a download yourself: see the [install page](site:install#verify).

## After a Lean or Mathlib update

The proved dossiers of the affected workspace are marked “to re-check”, then re-checked automatically. A dossier
whose proof no longer passes (a renamed lemma, a changed tactic) is flagged; its old verdict is never shown alone.

## Rolling back

“Settings › Updates › Back to the previous version” for Madalean. For Lean and Mathlib, the previous version stays
installed as long as one of your projects uses it.
<!-- verify after integration: rollback control exists and its label -->
