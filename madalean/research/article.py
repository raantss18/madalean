"""Lean → article (amsart). A project's article = editable metadata (title, authors, abstract, options) + an ordered
list of blocks:

    {id, kind: intro | section | prose | dossier | conclusion, title, source: ai | user | dossier, text,
     dossier_id?, versions: [{text, source, t, model, note}], updated}

- AI drafts (role « explain ») are versions like any other; a block whose current text was written by the user is
  NEVER overwritten: regenerating it needs `force` (and the user's text stays in the history).
- Each dossier is typeset by its kind: Lean-verified results (current proof proves the current statement) as
  theorem / lemma / proposition / corollary / definition with the natural-language proof; anything else as
  « Conjecture » / « Claim » with an explicit « not verified by Lean » mark — never as a theorem.
- Bibliography (biblatex+biber → bibtex+amsalpha → thebibliography), optional appendix with the Lean sources
  (texio listings), verification table (statement, Lean name, verified?, Lean / Mathlib versions, axioms).
- Exports: PDF (XeLaTeX via export.compile_pdf: no shell escape, openin_any=p / openout_any=p), .tex, .zip (tex +
  refs.bib + Lean files + pdf), .md.

Storage: `<config>/projects/<pid>/article.json` (atomic writes; deleted blocks kept in `trash`)."""
from __future__ import annotations

import asyncio
import io
import json
import re
import time
import uuid
import zipfile
from pathlib import Path

from .. import config, texio
from . import biblio
from .safety import UNTRUSTED_RULE, wrap_untrusted

BLOCK_KINDS = ("intro", "section", "prose", "dossier", "conclusion")
ENV_NAMES = {"fr": {"theorem": "Théorème", "lemma": "Lemme", "proposition": "Proposition", "corollary": "Corollaire",
                    "definition": "Définition", "conjecture": "Conjecture", "claim": "Affirmation"},
             "en": {"theorem": "Theorem", "lemma": "Lemma", "proposition": "Proposition", "corollary": "Corollary",
                    "definition": "Definition", "conjecture": "Conjecture", "claim": "Claim"}}
TXT = {"fr": {"unverified": "non vérifié par Lean", "lean_ok": "Vérifié par Lean : \\texttt{{{name}}} (table {tab}).",
              "table": "Vérification formelle", "appendix": "Code Lean", "refs": "Références",
              "cols": ("Résultat", "Nom Lean", "Vérifié", "Lean", "Mathlib", "Axiomes"), "yes": "oui", "no": "non",
              "defined": "énoncé accepté",
              "intro": "Introduction", "conclusion": "Conclusion", "abstract": "Résumé", "babel": "french",
              "nolean": "Ce résultat n'a pas (encore) de preuve vérifiée par Lean.",
              "table_note": "Un résultat n'est marqué vérifié que si Lean a accepté sa preuve (verdict strict : aucun "
                            "« sorry », aucun axiome hors propext, Classical.choice, Quot.sound)."},
       "en": {"unverified": "not verified by Lean", "lean_ok": "Verified by Lean: \\texttt{{{name}}} (table {tab}).",
              "table": "Formal verification", "appendix": "Lean code", "refs": "References",
              "cols": ("Result", "Lean name", "Verified", "Lean", "Mathlib", "Axioms"), "yes": "yes", "no": "no",
              "defined": "statement accepted",
              "intro": "Introduction", "conclusion": "Conclusion", "abstract": "Abstract", "babel": "english",
              "nolean": "This result has no Lean-verified proof (yet).",
              "table_note": "A result is marked verified only if Lean accepted its proof (strict verdict: no "
                            "« sorry », no axiom besides propext, Classical.choice, Quot.sound)."}}


class ArticleError(Exception):
    def __init__(self, kind: str, status: int = 400, **info):
        super().__init__(kind)
        self.kind, self.status, self.info = kind, status, info


# ================================================================ model
def path_of(ctx, pid: str) -> Path:
    return ctx.projects.store.dir(pid) / "article.json"


def new_block(kind: str, title: str = "", text: str = "", source: str = "user", dossier_id: str = "",
              model: str = "") -> dict:
    now = time.time()
    b = {"id": "b-" + uuid.uuid4().hex[:8], "kind": kind, "title": title[:300], "source": source, "text": text,
         "dossier_id": dossier_id, "versions": [], "updated": now}
    if text or source != "dossier":
        b["versions"].append({"text": text, "source": source, "t": now, "model": model, "note": "", "title": title})
    return b


def default_article(ctx, pid: str) -> dict:
    p = ctx.projects.get(pid)
    lang = ctx.settings.language if ctx.settings.language in ENV_NAMES else "fr"
    blocks = [new_block("intro", TXT[lang]["intro"], "", "ai")]
    ds = [d for d in ctx.repo.list(pid) if not d.archived and not d.parent_id]
    ds.sort(key=lambda d: d.created)
    for d in ds:
        blocks.append(new_block("dossier", "", "", "dossier", d.id))
    return {"title": p.title if p else "", "authors": [], "abstract": new_block("prose", "", "", "ai"),
            "blocks": blocks, "options": {"lean_appendix": True, "verification_table": True, "lang": lang,
                                          "numbering": "section"},
            "trash": [], "created": time.time(), "updated": time.time()}


def load(ctx, pid: str, create: bool = True) -> dict | None:
    try:
        return json.loads(path_of(ctx, pid).read_text(encoding="utf-8"))
    except FileNotFoundError:
        if not create:
            return None
        art = default_article(ctx, pid)
        save(ctx, pid, art)                  # block ids must stay stable from the first read on
        return art
    except (OSError, ValueError):
        return default_article(ctx, pid) if create else None


def save(ctx, pid: str, art: dict) -> None:
    art["updated"] = time.time()
    config.atomic_write_text(path_of(ctx, pid), json.dumps(art, ensure_ascii=False, indent=1))


def find_block(art: dict, bid: str) -> dict:
    if bid == "abstract":
        return art["abstract"]
    b = next((x for x in art["blocks"] if x["id"] == bid), None)
    if b is None:
        raise ArticleError("not_found", 404)
    return b


def set_text(b: dict, text: str, source: str, model: str = "", note: str = "", title: str | None = None) -> None:
    b["text"] = text
    b["source"] = source
    if title is not None:
        b["title"] = title[:300]
    b["versions"].append({"text": text, "source": source, "t": time.time(), "model": model, "note": note[:500],
                          "title": b.get("title", "")})
    b["versions"] = b["versions"][-50:]
    b["updated"] = time.time()


def patch_meta(art: dict, data: dict) -> list[str]:
    bad = []
    for k, v in data.items():
        if k == "title" and isinstance(v, str):
            art["title"] = v.strip()[:300]
        elif k == "authors" and isinstance(v, list) and all(isinstance(a, dict) for a in v):
            art["authors"] = [{x: str(a.get(x, ""))[:200] for x in ("name", "affiliation", "email")}
                              for a in v[:30] if str(a.get("name", "")).strip()]
        elif k == "options" and isinstance(v, dict):
            for ok_, ov in v.items():
                if ok_ in ("lean_appendix", "verification_table") and isinstance(ov, bool):
                    art["options"][ok_] = ov
                elif ok_ == "lang" and ov in ENV_NAMES:
                    art["options"]["lang"] = ov
                elif ok_ == "numbering" and ov in ("section", "global"):
                    art["options"]["numbering"] = ov
                else:
                    bad.append(f"options.{ok_}")
        elif k == "order" and isinstance(v, list):
            ids = [b["id"] for b in art["blocks"]]
            if sorted(v) != sorted(ids):
                bad.append("order")
            else:
                art["blocks"] = [next(b for b in art["blocks"] if b["id"] == i) for i in v]
        else:
            bad.append(k)
    return bad


# ================================================================ AI drafts
DRAFT_PROMPTS = {
    "abstract": "Write the abstract (at most 150 words) of a mathematics article titled « {title} » whose results are "
                "listed below as data. Say which results are verified in Lean and which are only stated.",
    "intro": "Write the introduction (3 to 5 short paragraphs) of a mathematics article titled « {title} »: context, "
             "the main results listed below (as data), what is formally verified in Lean, organisation of the paper.",
    "section": "Write a short connecting paragraph for the section « {block_title} » of the article « {title} », "
               "introducing the results that follow (listed below as data).",
    "prose": "Write a short paragraph for the article « {title} » ({block_title}) about the results listed below as "
             "data.",
    "conclusion": "Write a short conclusion for the article « {title} »: what was proved and verified, what remains "
                  "open (the unverified statements below), possible next steps.",
}
LANG_RULE = {"fr": "Écris EN FRANÇAIS.", "en": "Write IN ENGLISH."}
RULES = ("Rules: plain mathematical prose (no Markdown headings), formulas in LaTeX between $...$; never present a "
         "statement that is not verified in Lean as proved; do not restate full proofs.")


def results_digest(ctx, art: dict, near: list[str] | None = None) -> str:
    out = []
    for b in art["blocks"]:
        if b["kind"] != "dossier" or (near and b["dossier_id"] not in near):
            continue
        d = ctx.repo.get(b["dossier_id"])
        if d is None:
            continue
        status = "VERIFIED in Lean" if d.proof_is_current else "NOT verified (stated only)"
        stmt = (d.understood_display or d.problem or "").strip()[:800]
        out.append(wrap_untrusted(f"{d.title} — {status}\n{stmt}", d.id))
    return "\n\n".join(out) or "(no results yet)"


def draft_messages(ctx, art: dict, block: dict, kind: str, instructions: str = "") -> tuple[list[dict], set]:
    lang = art["options"].get("lang", "fr")
    near = None
    if kind in ("section", "prose"):
        idx = next((i for i, b in enumerate(art["blocks"]) if b["id"] == block["id"]), 0)
        near = [b["dossier_id"] for b in art["blocks"][idx + 1: idx + 6] if b["kind"] == "dossier"]
    entries = []
    try:
        from .sources import library
        entries = library(ctx).project_entries(_pid_of(ctx, art))
    except Exception:  # noqa: BLE001
        entries = []
    prompt = DRAFT_PROMPTS.get(kind, DRAFT_PROMPTS["prose"]).format(title=art.get("title", ""),
                                                                    block_title=block.get("title", ""))
    content = (f"{prompt}\n{LANG_RULE.get(lang, '')} {RULES}\n{UNTRUSTED_RULE}\n\n{results_digest(ctx, art, near)}" +
               biblio.known_keys_prompt(entries, lang))
    if instructions.strip():
        content += "\n\nThe author's instructions for this block: " + instructions.strip()[:2000]
    keys = {k for k, _ in entries}
    return [{"role": "user", "content": content}], keys


def _pid_of(ctx, art: dict) -> str | None:
    return art.get("_pid")


def clean_draft(text: str, keys: set) -> tuple[str, list[str]]:
    t = re.sub(r"<think>.*?(</think>|$)", "", text or "", flags=re.S).strip()
    t = re.sub(r"(?m)^\s*#{1,6}\s+", "", t)
    res = biblio.check_citations(t, keys)
    return res.text.strip(), res.unknown


# ================================================================ LaTeX
def _status(d) -> bool:
    return bool(d is not None and d.proof_is_current)


def statement_text(d) -> str:
    """Natural-language statement shown in the article (a blueprint node's own text, without the context added for
    the formalizer)."""
    bp = (d.extra or {}).get("blueprint") or {}
    text = bp.get("statement") or d.understood_display or d.problem or (d.source or {}).get("original_text", "") \
        or d.title
    return re.sub(r"^(Theorem|Lemma|Proposition|Corollary|Definition|Conjecture|Claim|Théorème|Lemme|Corollaire|"
                  r"Définition)\s+[\dA-Z][\d.]*\s*(\([^)]*\))?\.\s*", "", text.strip())


def env_for(d) -> str:
    """theorem-like environment of a dossier: only Lean-verified results get a theorem-like env."""
    paper_kind = ((d.extra or {}).get("blueprint") or {}).get("paper_kind", "") if d is not None else ""
    if d is not None and (d.kind == "definition" or paper_kind == "definition"):
        return "definition"
    if not _status(d):
        return "conjecture" if paper_kind in ("conjecture", "question") or d.kind == "conjecture" else "claim"
    if paper_kind in ("theorem", "lemma", "proposition", "corollary"):
        return paper_kind
    return {"lemma": "lemma", "theorem": "theorem", "claim": "proposition"}.get(d.kind, "theorem")


def article_bib(ctx, pid: str, art: dict) -> list[tuple[str, dict]]:
    from .sources import library
    known = library(ctx).all_entries(pid)
    order: list[str] = []
    texts = [art["abstract"].get("text", "")] + [b.get("text", "") for b in art["blocks"]]
    for b in art["blocks"]:
        d = ctx.repo.get(b.get("dossier_id") or "") if b["kind"] == "dossier" else None
        if d is not None:
            for r in d.refs or []:
                k = r.get("key") if isinstance(r, dict) else None
                if k in known and k not in order:
                    order.append(k)
            texts += biblio.dossier_texts(d)
    for t in texts:
        for c in biblio.find_citations(t):
            if c.key in known and c.key not in order:
                order.append(c.key)
    return [(k, known[k]) for k in order]


def build_tex(ctx, pid: str, art: dict, bib: list, backend: str, verbatim: bool = False,
              f: texio.Fonts | None = None) -> str:
    from ..export import _esc
    from ..runtime.lean import workspace_info
    f = f or texio.fonts()
    lang = art["options"].get("lang", "fr")
    T, N = TXT[lang], ENV_NAMES[lang]
    keys = {k: True for k, _ in bib}

    def md(text: str) -> str:
        if verbatim:
            return texio.verbatim_text(text, f)
        return texio.sanitize_markdown(text or "", f, keys)

    math = (r"\usepackage{unicode-math}" + "\n" + r"\setmathfont{" + texio.MATH_FONT_FILE + "}") if f.has_math else \
        r"\usepackage{amssymb}"
    mono = (r"\setmonofont{" + texio.MONO_FAMILY + r"}[Scale=0.86]") if f.has_mono else ""
    within = "[section]" if art["options"].get("numbering") == "section" else ""
    pre = [
        "% !TEX program = xelatex",
        "% Generated by Madalean (article). Compile with XeLaTeX.",
        r"\documentclass[11pt]{amsart}",
        r"\usepackage[a4paper,margin=2.6cm]{geometry}",
        r"\usepackage{amsmath,amsthm}", r"\usepackage{fontspec}", math, mono, f.preamble(),
        r"\usepackage[" + T["babel"] + "]{babel}",
        r"\usepackage[dvipsnames]{xcolor}", r"\usepackage{fvextra}", r"\usepackage{longtable}",
        r"\usepackage{enumitem}",
    ]
    if bib and backend == "biblatex":
        pre += [r"\usepackage[backend=biber,style=alphabetic,maxbibnames=99,giveninits=true]{biblatex}",
                r"\addbibresource{refs.bib}"]
    pre += [r"\usepackage[hidelinks,pdfcreator={Madalean}]{hyperref}",
            r"\newcommand\MLbs{\char`\\}\newcommand\MLlb{\char`\{}\newcommand\MLrb{\char`\}}",
            r"\fvset{breaklines=true,breakanywhere=true,fontsize=\small,frame=single,framesep=2mm,"
            r"rulecolor=\color{black!25},numbersep=6pt,breaksymbolleft={},breakanywheresymbolpre={}}",
            r"\theoremstyle{plain}",
            r"\newtheorem{theorem}{" + N["theorem"] + "}" + within,
            r"\newtheorem{lemma}[theorem]{" + N["lemma"] + "}",
            r"\newtheorem{proposition}[theorem]{" + N["proposition"] + "}",
            r"\newtheorem{corollary}[theorem]{" + N["corollary"] + "}",
            r"\newtheorem{conjecture}[theorem]{" + N["conjecture"] + "}",
            r"\newtheorem{claim}[theorem]{" + N["claim"] + "}",
            r"\theoremstyle{definition}", r"\newtheorem{definition}[theorem]{" + N["definition"] + "}",
            r"\newcommand\MLunverified{\textcolor{BrickRed}{\textup{[" + T["unverified"] + "]}}}"]
    title = art.get("title") or "—"
    body = [r"\title{" + _esc(title, f) + "}"]
    for a in art.get("authors", []):
        body.append(r"\author{" + _esc(a.get("name", ""), f) + "}")
        if a.get("affiliation"):
            body.append(r"\address{" + _esc(a["affiliation"], f) + "}")
        if a.get("email"):
            body.append(r"\email{" + _esc(a["email"], f) + "}")
    abstract = art["abstract"].get("text", "").strip()
    if abstract:
        body += [r"\begin{abstract}", md(abstract), r"\end{abstract}"]
    body += [r"\maketitle", ""]
    rows = []
    lean_parts = []
    for b in art["blocks"]:
        kind = b["kind"]
        if kind in ("intro", "section", "conclusion"):
            if b.get("title"):
                body.append(r"\section{" + _esc(b["title"], f) + "}")
            if b.get("text", "").strip():
                body.append(md(b["text"]))
            continue
        if kind == "prose":
            if b.get("text", "").strip():
                body.append(md(b["text"]))
            continue
        d = ctx.repo.get(b.get("dossier_id") or "")
        if d is None:
            continue
        if b.get("text", "").strip():
            body.append(md(b["text"]))
        env = env_for(d)
        verified = _status(d)
        stmt = statement_text(d)
        opt = _esc(re.sub(r"\s*\[[^\]]*\]$", "", d.title)[:120], f)
        mark = r"\MLunverified\ " if not verified and env != "definition" else ""
        label = "ml:" + re.sub(r"[^A-Za-z0-9]", "", d.id)
        body.append(r"\begin{" + env + "}[{" + opt + "}]" + r"\label{" + label + "}" + (" " + mark if mark else ""))
        body.append(md(stmt))
        body.append(r"\end{" + env + "}")
        if verified:
            proof = re.sub(r"\s*[□∎■]\s*$", "", (d.informal_proof or d.explanation).strip())
            if proof.strip():
                body += [r"\begin{proof}", md(proof), "", r"{\footnotesize " +
                         T["lean_ok"].format(name=_esc(d.theorem, f, ), tab=r"\ref{ml:table}") + "}", r"\end{proof}"]
        elif env != "definition":
            body.append(r"\noindent{\small\itshape " + _esc(T["nolean"], f) + r"}\par")
        info = workspace_info(ctx.workspace(d.workspace)) if verified else {}
        meta = (d.proofs[d.cur_proof].meta or {}) if verified else {}
        ax = meta.get("axioms")
        defined = env == "definition" and bool(d.statement) and d.statements[d.cur_statement].ok
        rows.append((r"\ref{" + label + "}", _esc(d.theorem or "—", f, True),
                     T["yes"] if verified else (T["defined"] if defined else T["no"]),
                     _esc(str(meta.get("lean") or info.get("lean") or "—"), f, True),
                     _esc(str(meta.get("mathlib") or info.get("mathlib") or "—"), f, True)[:40],
                     _esc(", ".join(ax) if ax else ("—" if ax is None else "∅"), f, True)))
        if verified:
            lean_parts.append((d.theorem, d.proof))
    if art["options"].get("verification_table", True) and rows:
        c = T["cols"]
        body += [r"\section*{" + _esc(T["table"], f) + r"}\label{ml:table}",
                 r"{\footnotesize " + _esc(T["table_note"], f) + r"\par}\smallskip",
                 r"{\footnotesize\begin{longtable}{@{}p{0.11\linewidth}p{0.27\linewidth}p{0.08\linewidth}"
                 r"p{0.13\linewidth}p{0.13\linewidth}p{0.18\linewidth}@{}}",
                 " & ".join(r"\textbf{" + _esc(x, f) + "}" for x in c) + r"\\\hline\endhead"]
        for r in rows:
            body.append(" & ".join(r[:2]) + " & " + (r"\textcolor{OliveGreen}{" + r[2] + "}" if r[2] != T["no"] else
                                                     r"\textcolor{BrickRed}{" + r[2] + "}") + " & " +
                        " & ".join(r"\texttt{" + x + "}" for x in r[3:]) + r"\\")
        body.append(r"\end{longtable}}")
    if bib:
        from ..export import Content, bib_section
        cobj = Content("", "", "", "", "", "", "", False, "", False, None, "", __import__("datetime").date.today(),
                       lang, bib=bib, bib_backend=backend)
        body.append(bib_section(cobj, f, T["refs"]))
    if art["options"].get("lean_appendix", True) and lean_parts:
        body += [r"\appendix", r"\section{" + _esc(T["appendix"], f) + "}"]
        for name, code in lean_parts:
            body += [r"\subsection*{\texttt{" + _esc(name, f, True) + "}}", texio.lean_listing(code, f=f)]
    return "\n".join(pre + [r"\begin{document}"] + body + [r"\end{document}", ""])


def build_md(ctx, pid: str, art: dict, bib: list) -> str:
    lang = art["options"].get("lang", "fr")
    T, N = TXT[lang], ENV_NAMES[lang]
    labels = biblio.labels_for(bib)

    def cite(t: str) -> str:
        return biblio.CITE_GROUP.sub(lambda m: biblio.cite_to_text(m.group(1), labels) or m.group(0), t or "")
    out = [f"# {art.get('title', '')}", ""]
    if art.get("authors"):
        out += [", ".join(a["name"] for a in art["authors"]), ""]
    if art["abstract"].get("text"):
        out += [f"**{T['abstract']}.** " + cite(art["abstract"]["text"]), ""]
    for b in art["blocks"]:
        if b["kind"] in ("intro", "section", "conclusion") and b.get("title"):
            out += [f"## {b['title']}", ""]
        if b.get("text"):
            out += [cite(b["text"]), ""]
        if b["kind"] == "dossier":
            d = ctx.repo.get(b.get("dossier_id") or "")
            if d is None:
                continue
            env = env_for(d)
            mark = "" if _status(d) or env == "definition" else f" *[{T['unverified']}]*"
            out += [f"**{N[env]} ({d.title}).**{mark} " + cite(statement_text(d)), ""]
            if _status(d) and (d.informal_proof or d.explanation):
                out += ["*Proof.* " if lang == "en" else "*Démonstration.* ", cite(d.informal_proof or d.explanation),
                        ""]
    if bib:
        out += [f"## {T['refs']}", ""] + [f"- [{labels[k]}] {biblio.reference_text(it)}" for k, it in bib] + [""]
    return "\n".join(out)


async def export(ctx, pid: str, art: dict, fmt: str, tmp_root: Path) -> tuple[str, str, bytes, str]:
    """(filename, content type, data, fallback). PDF falls back to thebibliography, then verbatim text, then HTML."""
    from ..export import _engines, bib_backend, compile_pdf
    from ..dossiers import slugify
    art = dict(art)
    art["_pid"] = pid
    bib = await asyncio.to_thread(article_bib, ctx, pid, art)
    name = slugify(art.get("title") or "article", 40)
    f = await asyncio.to_thread(texio.fonts)

    def bibtext() -> str:
        return "".join(biblio.item_to_bibtex(it, k) + "\n" for k, it in bib)
    if fmt == "md":
        return f"{name}.md", "text/markdown; charset=utf-8", build_md(ctx, pid, art, bib).encode(), ""
    if fmt == "tex":
        tex = await asyncio.to_thread(build_tex, ctx, pid, art, bib, "manual", False, f)
        return f"{name}.tex", "application/x-tex; charset=utf-8", tex.encode(), ""
    pdf, log, used, verbatim = None, "", "", False
    backends = ([bib_backend()] if bib else ["manual"])
    if backends[0] != "manual":
        backends.append("manual")
    engines = _engines()
    for backend in backends if engines else []:
        for vb in (False, True):
            tex = await asyncio.to_thread(build_tex, ctx, pid, art, bib, backend, vb, f)
            pdf, log, timed_out = await compile_pdf(tex, tmp_root, 180, engines,
                                                    {"refs.bib": bibtext()} if bib else None)
            if pdf or timed_out:
                used, verbatim = backend, vb
                break
        if pdf:
            break
    fallback = "" if pdf and not verbatim else ("verbatim" if pdf else "html")
    if fmt == "pdf":
        if pdf:
            return f"{name}.pdf", "application/pdf", pdf, fallback
        page = texio.markdown_to_html(build_md(ctx, pid, art, bib))
        html = (f'<!doctype html><html><head><meta charset="utf-8"><title>{name}</title></head><body>{page}'
                f'<!-- {log[-500:].replace("--", "- -")} --></body></html>')
        return f"{name}.html", "text/html; charset=utf-8", html.encode(), "html"
    # zip
    tex = await asyncio.to_thread(build_tex, ctx, pid, art, bib, used or "manual", verbatim, f)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{name}/{name}.tex", tex)
        if bib:
            z.writestr(f"{name}/refs.bib", bibtext())
        if pdf:
            z.writestr(f"{name}/{name}.pdf", pdf)
        z.writestr(f"{name}/{name}.md", build_md(ctx, pid, art, bib))
        allcode = []
        for b in art["blocks"]:
            d = ctx.repo.get(b.get("dossier_id") or "") if b["kind"] == "dossier" else None
            if d is not None and d.proof_is_current:
                z.writestr(f"{name}/lean/{d.theorem}.lean", d.proof)
                allcode.append(d.proof)
        if allcode:
            z.writestr(f"{name}/lean/README.txt", "Each file was accepted by Lean (strict verdict) in Madalean.\n")
    return f"{name}.zip", "application/zip", buf.getvalue(), fallback
