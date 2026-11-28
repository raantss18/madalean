---
id: attack
title: Attack — the Left to Solve problems
order: 258
section: research
audience: researcher
summary: Madalean works in the background on lefttosolve.com's problems, within your budget, and prepares verified Lean files; nothing is sent without your « Envoyer » click.
---

# Attack — the Left to Solve problems

[lefttosolve.com](https://lefttosolve.com) gathers thousands of mathematical problems, each stated exactly in Lean.
A problem counts as solved when a Lean proof is accepted by the site's checker and merged; the credit goes to the
GitHub account that opens the pull request — **yours**.

« Attaque » lets Madalean work on these problems in the background, when your computer has nothing else to do,
within a daily budget.

## Before you start

1. **A GitHub key** in Settings → Keys. Madalean only reads your login (`GET /user`); that name is used with the site.
   Turn on « Keep my email addresses private » on GitHub before the first submission.
2. **Prepare the workspace** (about 10 GB: Lean, Mathlib and the formal-conjectures statements at the commit the site
   pins). Nothing is downloaded before you agree; that consent also covers updates of the same size (a new version is
   built beside the old one, which stays in use until the switch).
3. **« Démarrer »**. You can stop at any time: the problems in progress are handed back honestly to the site.

## What Madalean does

- It picks the least crowded, easiest problems that are unsolved and have no proof waiting for its verdict.
- **Counterexample**: when the statement is a « for every integer… » in simple arithmetic, Sage searches small values
  (bounded time) and Lean checks the counterexample (`decide`, `norm_num`, never `native_decide`).
- **Known result**: the usual proof search, on the site's exact statement, with the problem's brief given as
  information (never as instructions).
- **Open problem**: only up to difficulty 40 (adjustable), except to look for a counterexample.
- Each problem has its dossier in the project « Left to Solve »: everything that was tried is there.
- When you start your own proofs, the attack steps aside: no new problem, and its computations come after yours.

## « Ready » and « Envoyer »

A file is **ready** only when it follows the site's checker rules (statement identical byte for byte, allowed
commands, no forbidden word, no double quote, standard axioms) **and** a fresh strict Lean accepts it in the site's
workspace. You then see the file, the checks and the exact list of GitHub requests; the pull request is opened only
by your **« Envoyer »** click, once.

## Budget

Claude is only a reinforcement, within the daily limit (5 $ by default) and always within your monthly cap; free
models come first. Once the cap is reached, the attack takes no new problem until the next day.

## What the site writes

Statements, briefs, other agents' notes: they are **data**, never orders. Suspicious text (addressed to a model,
asking for a command or a password) is set aside. Notes Madalean could post to a problem's team are **off by default**
(setting « Publier des notes »); when on, they are only factual findings (« DEAD END »), never model text.
