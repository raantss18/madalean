"""« Calculs » page of a publication (S-W): the `computations` section of publication.json (docs/SITE.md §4, produced
by madalean.research.notebook.publication_computations) → computations.html. Cells in order: requests in words,
code, outputs (text, maths rendered with KaTeX at build time, images, figures drawn as static SVG), with the state of
each result (out of date, error, not run). Files (notebooks, images) are copied from the input's files/calcul/."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from typing import Callable

from . import figure
from .leanhl import code_block

E = html.escape
PATH_RE = re.compile(r"files/calcul/[A-Za-z0-9][A-Za-z0-9._-]{0,120}")
KINDS = ("code", "ask", "markdown", "figure")
OUT_KINDS = ("text", "latex", "image", "figure", "error")

T = {
    "fr": {"title": "Calculs", "lead": "Calculs faits avec {engine}. Chaque carnet se télécharge et se relance tel quel.",
           "download": "Télécharger le carnet", "ask": "Demande", "input": "Entrée", "output": "Résultat",
           "stale": "Ce résultat date d'avant une modification d'une cellule précédente : à recalculer.",
           "error": "Erreur", "not_run": "Pas encore calculé.", "timeout": "Calcul trop long, arrêté.",
           "interrupted": "Calcul interrompu.", "approx": "Valeur approchée", "figure": "Figure",
           "contents": "Carnets", "cells": "{n} cellules"},
    "en": {"title": "Computations", "lead": "Computations made with {engine}. Each notebook can be downloaded and run "
                                            "again as is.",
           "download": "Download the notebook", "ask": "Request", "input": "Input", "output": "Result",
           "stale": "This result predates a change in an earlier cell: to be computed again.",
           "error": "Error", "not_run": "Not computed yet.", "timeout": "Computation too long, stopped.",
           "interrupted": "Computation interrupted.", "approx": "Approximate value", "figure": "Figure",
           "contents": "Notebooks", "cells": "{n} cells"},
}

# Sage's LaTeX macros (sage/misc/latex_macros.py) that KaTeX does not define
SAGE_MACROS = [(r"\\Bold\{([A-Za-z])\}", r"\\mathbb{\1}"), (r"\\ZZ\b", r"\\mathbb{Z}"), (r"\\QQ\b", r"\\mathbb{Q}"),
               (r"\\RR\b", r"\\mathbb{R}"), (r"\\CC\b", r"\\mathbb{C}"), (r"\\NN\b", r"\\mathbb{N}"),
               (r"\\GF\b", r"\\mathbb{F}"), (r"\\Z\b", r"\\mathbb{Z}"), (r"\\Q\b", r"\\mathbb{Q}"),
               (r"\\R\b", r"\\mathbb{R}"), (r"\\C\b", r"\\mathbb{C}"), (r"\\SL\b", r"\\mathrm{SL}"),
               (r"\\left\[", "["), (r"\\right\]", "]"), (r"\\mbox\{", r"\\text{"), (r"\\verb\|([^|]*)\|", r"\\texttt{\1}")]


def katex_tex(tex: str) -> str:
    t = tex.strip()
    t = re.sub(r"^\$\$?|\$\$?$", "", t).strip()
    for a, b in SAGE_MACROS:
        t = re.sub(a, b, t)
    return t


def validate(c: dict) -> list[str]:
    """Shape and file paths of the computations section (paths stay inside files/calcul/)."""
    err = []
    if not isinstance(c, dict) or not isinstance(c.get("documents"), list):
        return ["computations.documents must be a list"]
    ids = set()
    for d in c["documents"]:
        did = str((d or {}).get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", did) or did in ids:
            err.append(f"computations: bad or duplicate document id {did!r}")
        ids.add(did)
        if d.get("notebook") and not PATH_RE.fullmatch(str(d["notebook"])):
            err.append(f"computations: bad notebook path {d.get('notebook')!r}")
        for cell in d.get("cells") or []:
            if cell.get("kind") not in KINDS:
                err.append(f"computations: {did}: bad cell kind {cell.get('kind')!r}")
            for o in cell.get("outputs") or []:
                if o.get("kind") not in OUT_KINDS:
                    err.append(f"computations: {did}: bad output kind {o.get('kind')!r}")
                if o.get("kind") == "image" and not PATH_RE.fullmatch(str(o.get("path", ""))):
                    err.append(f"computations: bad image path {o.get('path')!r}")
            svg = (cell.get("figure") or {}).get("svg")
            if svg and not PATH_RE.fullmatch(str(svg)):
                err.append(f"computations: bad figure path {svg!r}")
    return err


def _anchor(did: str) -> str:
    return "calc-" + re.sub(r"[^A-Za-z0-9_-]", "-", did)


def render(c: dict, lg: str, md: Callable[[str, str], str], math, src: Path, out: Path,
           problems: list[str]) -> str:
    """Body (<main>) of computations.html; copies the files it refers to and writes figure SVGs."""
    t = T[lg]
    eng = c.get("engine") or {}
    engine = (str(eng.get("name") or "SageMath") + (" " + str(eng.get("version")) if eng.get("version") else "")).strip()
    docs = [d for d in c.get("documents") or [] if d.get("cells")]
    (out / "files" / "calcul").mkdir(parents=True, exist_ok=True)

    def copy(rel: str) -> bool:
        p = src / rel
        if not p.is_file():
            problems.append(f"computations: missing file {rel}")
            return False
        dst = out / rel
        if not dst.exists():
            shutil.copy2(p, dst)
        return True

    def fig_img(spec: dict, alt_extra: str = "") -> str:
        svg, desc = figure.render(spec if isinstance(spec, dict) else {}, lg)
        name = "fig-" + hashlib.sha256(svg.encode()).hexdigest()[:16] + ".svg"
        (out / "files" / "calcul" / name).write_text(svg, encoding="utf-8")
        alt = (alt_extra + " — " if alt_extra else "") + desc
        return (f'<figure class="calc-figure"><img src="files/calcul/{name}" alt="{E(alt[:600])}" width="640" '
                f'height="400" loading="lazy"><figcaption>{E(desc[:600])}</figcaption></figure>')

    body = [f'<main id="main" class="narrow prose pub calc" tabindex="-1"><h1>{E(t["title"])}</h1>',
            f'<p>{E(t["lead"].format(engine=engine))}</p>']
    if len(docs) > 1:
        body.append(f'<nav aria-labelledby="calc-toc"><h2 id="calc-toc">{E(t["contents"])}</h2><ul>' +
                    "".join(f'<li><a href="#{_anchor(d["id"])}">{E(d.get("title") or d["id"])}</a> '
                            f'<span class="muted">({E(t["cells"].format(n=len(d["cells"])))})</span></li>'
                            for d in docs) + "</ul></nav>")
    for d in docs:
        did = d["id"]
        lang = "sage" if d.get("language") == "sage" else "python"
        body.append(f'<section class="calc-doc" aria-labelledby="{_anchor(did)}">'
                    f'<h2 id="{_anchor(did)}">{E(d.get("title") or did)}</h2>')
        nb = d.get("notebook")
        if nb and copy(nb):
            body.append(f'<p><a class="button" href="{E(nb)}" download>{E(t["download"])}</a> '
                        f'<span class="muted">{E(Path(nb).name)}</span></p>')
        for cell in d["cells"]:
            kind = cell.get("kind")
            if kind == "markdown":
                text = cell.get("markdown") or ""
                if text.strip():
                    body.append(f'<div class="calc-md">{md(text, "")}</div>')
                continue
            if kind == "figure":
                fg = cell.get("figure") or {}
                if fg.get("svg") and copy(fg["svg"]):
                    _svg, desc = figure.render(fg.get("spec") or {}, lg)
                    body.append(f'<figure class="calc-figure"><img src="{E(fg["svg"])}" alt="{E(desc[:600])}" '
                                f'loading="lazy"><figcaption>{E(desc[:600])}</figcaption></figure>')
                elif fg.get("spec"):
                    body.append(fig_img(fg["spec"]))
                continue
            # code / ask
            n = cell.get("execution_count")
            parts = ['<div class="calc-cell">']
            if kind == "ask" and cell.get("prompt"):
                parts.append(f'<p class="calc-ask"><strong>{E(t["ask"])} :</strong> {E(cell["prompt"])}</p>'
                             .replace(" :</strong>", ":</strong>" if lg == "en" else " :</strong>"))
            label = f'{t["input"]}{f" [{n}]" if isinstance(n, int) else ""}'
            if (cell.get("code") or "").strip():
                parts.append(f'<p class="calc-label muted">{E(label)}</p>' +
                             code_block(lang, cell["code"].rstrip(), label=label))
            status = cell.get("status") or "ok"
            outs = cell.get("outputs") or []
            note = ""
            if cell.get("stale"):
                note = t["stale"]
            elif status in ("timeout", "interrupted"):
                note = t[status]
            elif status == "not_run" and not outs:
                note = t["not_run"]
            if note:
                parts.append(f'<p class="calc-note">{E(note)}</p>')
            if outs:
                parts.append(f'<div class="calc-out" role="group" aria-label="{E(t["output"])}">')
                for o in outs:
                    k = o.get("kind")
                    if k == "text":
                        parts.append(f'<pre class="calc-text">{E(str(o.get("text", "")))}</pre>')
                    elif k == "latex":
                        tex = katex_tex(str(o.get("latex", "")))
                        plain = f'<pre class="calc-text">{E(str(o.get("text") or o.get("latex", "")))}</pre>'
                        parts.append(f'<div class="calc-math">{math.add(tex, True, fallback=plain)}</div>'
                                     if tex else plain)
                    elif k == "image":
                        if copy(str(o.get("path"))):
                            alt = str(o.get("alt") or t["figure"])[:300]
                            parts.append(f'<figure class="calc-figure"><img src="{E(o["path"])}" alt="{E(alt)}" '
                                         f'loading="lazy"></figure>')
                    elif k == "figure":
                        parts.append(fig_img(o.get("spec") or {}))
                    elif k == "error":
                        parts.append(f'<pre class="calc-error"><span class="sr-only">{E(t["error"])} : </span>'
                                     f'{E(str(o.get("text", "")))}</pre>')
                    if k in ("text", "latex") and o.get("approx"):
                        parts.append(f'<p class="calc-approx muted">{E(t["approx"])} ≈ {E(str(o["approx"]))}</p>')
                parts.append("</div>")
            parts.append("</div>")
            body.append("".join(parts))
        body.append("</section>")
    body.append("</main>")
    return "".join(body)


def load(d: dict) -> dict | None:
    c = d.get("computations")
    if not c or not any((x or {}).get("cells") for x in c.get("documents") or []):
        return None
    return json.loads(json.dumps(c))
