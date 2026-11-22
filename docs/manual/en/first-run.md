---
id: first-run
title: First run
order: 20
section: start
audience: all
summary: Guided tour, choice of mode, first statement, demo mode.
---

# First run

On first opening (in *Learn* mode, the default), a short four-step tour presents the ideas of the interface: write
a statement, check the translation, Lean checks every proof, you stay in control. “Skip the tour” closes it.

The state of the installation (Lean workspaces, models, TeX, fonts, sandbox, disk) is shown in “Settings › System”,
under “Health”: each problem is reported there, with a “Repair” button when a repair exists (to be started from the
host computer).

## Three choices to make

1. **Where the models work** (“Settings › Models”):
   - *Local*: nothing leaves the host computer; only the models installed here work.
   - *Automatic* (default): the best available model, online first, local models when the network is missing.
   - *Online*: online models only.

   What each mode sends, and to whom: [Models and keys](models-keys.md).
2. **Learn or Research** (button at the top right): *Learn* offers hints before the proof, a glossary on hover and
   line-by-line explanations; *Research* is dense, keyboard-first, with nothing pedagogical in the way. You can
   switch at any time.
3. **Your profile** (“Settings › Profile”): intended audience, level, preferred notations. It is read before every
   translation and every explanation.

## A first statement

On the home screen, write for example:

> Show that the sum of two even integers is even.

then “Translate and prove”. The stages follow one another by themselves: understanding, translation into Lean, proof search,
explanation. What comes next is described in [From statement to proof](workflow.md).

## Trying without models or Lean: demo mode

```bash
~/madalean/bin/madalean serve --demo --port 11600 --remote-port 11601
```

then open `http://127.0.0.1:11600`. The models and Lean are **simulated**: a banner says so, and nothing there is
really checked. Demo mode is for discovering the interface; its data is kept apart from yours
(`~/.config/madalean-demo`).
