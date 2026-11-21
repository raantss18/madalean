---
id: first-run
title: First run
order: 20
section: start
audience: all
summary: Guided tour, choice of mode, first statement, demo mode.
---

# First run

The first time it opens on the host computer, Madalean checks its environment (Lean workspaces, models, TeX, fonts,
disk) and shows what is missing, with a repair button when one exists. A short tour then presents the four ideas of
the interface: write a statement, check the translation, let Lean judge, stay in control.
<!-- verify after integration: first-run checks and tour wording -->

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

then start. The stages follow one another by themselves: understanding, translation into Lean, proof search,
explanation. What comes next is described in [From statement to proof](workflow.md).

## Trying without models or Lean: demo mode

```bash
~/madalean/bin/madalean serve --demo --port 11600 --remote-port 11601
```

then open `http://127.0.0.1:11600`. The models and Lean are **simulated**: a banner says so, and nothing there is
really checked. Demo mode is for discovering the interface; its data is kept apart from yours
(`~/.config/madalean-demo`).
