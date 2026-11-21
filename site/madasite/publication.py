"""Publication template: a project (publication.json, format in docs/SITE.md) -> static, verifiable site.

Pages: index.html (article), graph.html (blueprint SVG), results/<id>.html, verification.html, bibliography.html,
verification/badge.svg + result.json (placeholders until the CI workflow re-runs `lake build`), files/ (downloads).
No client script is required. Status is recomputed here from facts (statement_ok, proof_ok, uses): the input cannot
make an unverified result look verified."""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from . import layout
from .graph import render_svg
from .leanhl import code_block
from .mathrender import MathBatch
from .mdrender import Hooks, Renderer

E = html.escape
SCHEMA = "madalean-publication/1"
KINDS = ("definition", "lemma", "theorem", "proposition", "corollary", "conjecture", "claim")
THEOREM_LIKE = ("lemma", "theorem", "proposition", "corollary")

T = {
    "fr": {
        "article": "Article", "graph": "Graphe", "results": "Résultats", "verification": "Vérification",
        "bibliography": "Bibliographie", "downloads": "Téléchargements", "abstract": "Résumé",
        "kind": {"definition": "Définition", "lemma": "Lemme", "theorem": "Théorème", "proposition": "Proposition",
                 "corollary": "Corollaire", "conjecture": "Conjecture", "claim": "Affirmation"},
        "unverified_label": "Affirmation",
        "status": {"verified": "vérifié par Lean", "proved": "prouvé, dépendances non vérifiées",
                   "defined": "définition acceptée par Lean", "statement": "énoncé Lean accepté, sans preuve",
                   "stated": "énoncé en langage naturel seulement", "blocked": "bloqué : dépend d'une définition non formalisée"},
        "legend": "Légende", "graph_title": "Graphe des dépendances",
        "graph_desc": "Chaque résultat est relié aux résultats qu'il utilise (flèche du résultat utilisé vers celui qui l'utilise).",
        "statement": "Énoncé", "proof": "Preuve", "lean": "Code Lean", "uses": "Utilise", "used_by": "Utilisé par",
        "verif_info": "Vérification", "lean_name": "Nom Lean", "toolchain": "Lean", "mathlib": "Mathlib",
        "axioms": "Axiomes", "checked": "Vérifié le", "checker": "Vérificateur", "none": "aucun",
        "no_proof": "Aucune preuve vérifiée par Lean pour l'instant.",
        "not_verified_note": "Ce résultat n'est pas vérifié par Lean : il ne doit pas être cité comme théorème.",
        "source": "Source", "refs": "Références", "summary": "{v} sur {n} résultats vérifiés par Lean",
        "ci": "Vérification indépendante", "ci_text": "Une action GitHub recompile le projet Lean publié avec "
              "<code>lake build</code> à chaque modification ; le badge ci-dessous donne son dernier résultat.",
        "lake": "Projet Lean (Lake)", "pdf": "Article (PDF)", "result": "Résultat", "state": "État",
        "footer": "Publié avec Madalean. Seuls les résultats marqués « vérifié par Lean » ont une preuve acceptée "
                  "par Lean (verdict strict), ainsi que toutes leurs dépendances.",
        "badge_alt": "Résultat de la dernière vérification lake build",
        "all_results": "Tous les résultats", "back": "Retour à l'article",
        "standard_axioms": "axiomes standard de Lean",
    },
    "en": {
        "article": "Article", "graph": "Graph", "results": "Results", "verification": "Verification",
        "bibliography": "Bibliography", "downloads": "Downloads", "abstract": "Abstract",
        "kind": {"definition": "Definition", "lemma": "Lemma", "theorem": "Theorem", "proposition": "Proposition",
                 "corollary": "Corollary", "conjecture": "Conjecture", "claim": "Claim"},
        "unverified_label": "Claim",
        "status": {"verified": "verified by Lean", "proved": "proved, dependencies not verified",
                   "defined": "definition accepted by Lean", "statement": "Lean statement accepted, no proof",
                   "stated": "natural-language statement only", "blocked": "blocked: uses a definition not formalised"},
        "legend": "Legend", "graph_title": "Dependency graph",
        "graph_desc": "Each result is linked to the results it uses (arrow from the result used to the one using it).",
        "statement": "Statement", "proof": "Proof", "lean": "Lean code", "uses": "Uses", "used_by": "Used by",
        "verif_info": "Verification", "lean_name": "Lean name", "toolchain": "Lean", "mathlib": "Mathlib",
        "axioms": "Axioms", "checked": "Checked on", "checker": "Checker", "none": "none",
        "no_proof": "No proof verified by Lean yet.",
        "not_verified_note": "This result is not verified by Lean: it must not be cited as a theorem.",
        "source": "Source", "refs": "References", "summary": "{v} of {n} results verified by Lean",
        "ci": "Independent verification", "ci_text": "A GitHub Action rebuilds the published Lean project with "
              "<code>lake build</code> on every change; the badge below shows its latest result.",
        "lake": "Lean project (Lake)", "pdf": "Article (PDF)", "result": "Result", "state": "Status",
        "footer": "Published with Madalean. Only results marked “verified by Lean” have a proof accepted by Lean "
                  "(strict verdict), together with all their dependencies.",
        "badge_alt": "Result of the latest lake build verification",
        "all_results": "All results", "back": "Back to the article",
        "standard_axioms": "Lean's standard axioms",
    },
}
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


class PublicationError(Exception):
    pass


def validate(d: dict) -> list[str]:
    err = []
    if d.get("schema") != SCHEMA:
        err.append(f"schema must be {SCHEMA!r}")
    if d.get("lang") not in ("fr", "en"):
        err.append("lang must be 'fr' or 'en'")
    if not (d.get("project") or {}).get("title"):
        err.append("project.title is required")
    ids = set()
    for n in d.get("nodes", []):
        nid = n.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", nid):
            err.append(f"bad node id {nid!r}")
        if nid in ids:
            err.append(f"duplicate node id {nid}")
        ids.add(nid)
        if n.get("kind") not in KINDS:
            err.append(f"{nid}: kind must be one of {KINDS}")
        lean = n.get("lean") or {}
        if lean.get("proof_ok") and not lean.get("statement_ok"):
            err.append(f"{nid}: proof_ok requires statement_ok")
        if lean.get("proof_ok") and "sorryAx" in (lean.get("axioms") or []):
            err.append(f"{nid}: a proof using sorryAx cannot be proof_ok")
    for n in d.get("nodes", []):
        for u in n.get("uses", []):
            if u not in ids:
                err.append(f"{n.get('id')}: uses unknown node {u}")
    keys = {b.get("key") for b in d.get("bibliography", [])}
    for f in d.get("files", []):
        if not re.fullmatch(r"files/[A-Za-z0-9._-]+", f.get("path", "")):
            err.append(f"bad file path {f.get('path')!r} (must be files/<name>)")
    del keys
    return err


def statuses(nodes: list[dict]) -> dict[str, str]:
    by = {n["id"]: n for n in nodes}
    memo: dict[str, bool] = {}

    def ok(nid: str, stack: frozenset = frozenset()) -> bool:
        """verified (definitions: accepted statement), all dependencies included; cycles are never verified."""
        if nid in memo:
            return memo[nid]
        if nid in stack:
            return False
        n = by[nid]
        lean = n.get("lean") or {}
        own = bool(lean.get("statement_ok")) if n["kind"] == "definition" else bool(lean.get("proof_ok"))
        r = own and all(ok(u, stack | {nid}) for u in n.get("uses", []))
        memo[nid] = r
        return r

    out = {}
    for n in nodes:
        lean = n.get("lean") or {}
        nid = n["id"]
        blocked = any(by[u]["kind"] == "definition" and not (by[u].get("lean") or {}).get("statement_ok")
                      for u in n.get("uses", []))
        if n["kind"] == "definition":
            out[nid] = "defined" if lean.get("statement_ok") else "stated"
        elif ok(nid):
            out[nid] = "verified"
        elif blocked:
            out[nid] = "blocked"
        elif lean.get("proof_ok"):
            out[nid] = "proved"
        elif lean.get("statement_ok"):
            out[nid] = "statement"
        else:
            out[nid] = "stated"
    return out


def _csl_authors(csl: dict) -> list[str]:
    out = []
    for a in csl.get("author", []) or []:
        out.append(a.get("literal") or " ".join(x for x in (a.get("given"), a.get("family")) if x))
    return out


def _label(b: dict) -> str:
    if b.get("label"):
        return b["label"]
    csl = b.get("csl", {})
    fam = [a.get("family") or a.get("literal") or "" for a in csl.get("author", []) or []]
    year = str(((csl.get("issued") or {}).get("date-parts") or [[""]])[0][0])[-2:]
    pre = (fam[0][:3] if len(fam) == 1 else "".join(f[:1] for f in fam[:4])) if fam else b["key"][:3]
    return f"{pre}{year}"


def _bib_entry(b: dict) -> str:
    c = b.get("csl", {})
    parts = []
    au = _csl_authors(c)
    if au:
        parts.append(E(", ".join(au)))
    parts.append(f"<cite>{E(c.get('title', ''))}</cite>")
    venue = c.get("container-title") or c.get("publisher") or ""
    if venue:
        v = E(venue)
        if c.get("volume"):
            v += f" {E(str(c['volume']))}"
        parts.append(v)
    year = ((c.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    if year:
        parts.append(str(year))
    if c.get("page"):
        parts.append(E(f"p. {c['page']}"))
    links = []
    if c.get("DOI"):
        links.append(f'<a href="https://doi.org/{E(c["DOI"])}" rel="noopener noreferrer">doi:{E(c["DOI"])}</a>')
    if c.get("arxiv"):
        links.append(f'<a href="https://arxiv.org/abs/{E(c["arxiv"])}" rel="noopener noreferrer">arXiv:{E(c["arxiv"])}</a>')
    if c.get("zbl"):
        links.append(f'<a href="https://zbmath.org/?q=an:{E(c["zbl"])}" rel="noopener noreferrer">Zbl {E(c["zbl"])}</a>')
    if c.get("ISBN"):
        links.append(f"ISBN {E(c['ISBN'])}")
    return ". ".join(parts) + "." + (" " + " · ".join(links) if links else "")


def build(src: Path, out: Path, math: MathBatch | None = None, problems: list[str] | None = None) -> dict:
    """src = directory with publication.json (+ files/). Returns a summary. Raises PublicationError on bad input."""
    problems = problems if problems is not None else []
    d = json.loads((src / "publication.json").read_text(encoding="utf-8"))
    errs = validate(d)
    if errs:
        raise PublicationError("; ".join(errs))
    own_math = math is None
    math = math or MathBatch()
    lg = d["lang"]
    t = T[lg]
    proj = d["project"]
    nodes = d.get("nodes", [])
    by = {n["id"]: n for n in nodes}
    st = statuses(nodes)
    bib = {b["key"]: b for b in d.get("bibliography", [])}
    used_by: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for n in nodes:
        for u in n.get("uses", []):
            used_by[u].append(n["id"])
    cited: list[str] = []
    out.mkdir(parents=True, exist_ok=True)
    (out / "results").mkdir(exist_ok=True)

    def md(text: str, root: str, offset: int = 0) -> str:
        def cite(items):
            parts = []
            for key, loc in items:
                if key not in bib:
                    problems.append(f"publication: unknown citation key {key!r}")
                    parts.append(f"?{E(key)}")
                    continue
                if key not in cited:
                    cited.append(key)
                lab = E(_label(bib[key])) + (f", {E(loc)}" if loc else "")
                parts.append(f'<a href="{root}bibliography.html#ref-{E(key)}">{lab}</a>')
            return '<span class="cite">[' + "; ".join(parts) + "]</span>"

        def link(h: str):
            if h.startswith(("https://", "http://")):
                return h
            pm = re.fullmatch(r"page:(graph|verification|bibliography|index)", h)
            if pm:
                return f"{root}{pm.group(1)}.html"
            m = re.fullmatch(r"node:([A-Za-z0-9._-]+)", h)
            if m and m.group(1) in by:
                return f"{root}results/{m.group(1)}.html"
            return None
        r = Renderer(Hooks(link=link, math=math.add, cite=cite, heading_offset=offset,
                           code=lambda lang, code: code_block(lang, code))).render(text or "")
        for b in r.broken_links:
            problems.append(f"publication: bad link {b!r}")
        return r.html

    def label(n: dict) -> str:
        num = f" {n['number']}" if n.get("number") else ""
        if n["kind"] in THEOREM_LIKE and st[n["id"]] != "verified":
            return f"{t['unverified_label']}{num}"
        return f"{t['kind'][n['kind']]}{num}"

    def chip(nid: str) -> str:
        s = st[nid]
        return f'<span class="chip st-{s}"><span aria-hidden="true">{_MARK[s]}</span> {E(t["status"][s])}</span>'

    def node_link(nid: str, root: str) -> str:
        n = by[nid]
        title = f" — {E(n['title'])}" if n.get("title") else ""
        return f'<a href="{root}results/{E(nid)}.html">{E(label(n))}{title}</a> {chip(nid)}'

    def stmt_box(n: dict, root: str, heading: str = "h3") -> str:
        s = st[n["id"]]
        title = f" ({E(n['title'])})" if n.get("title") else ""
        warn = "" if s in ("verified", "defined") or n["kind"] in ("conjecture", "claim") else \
            f'<p class="unverified-note">{E(t["not_verified_note"])}</p>'
        return (f'<section class="result st-{s}" aria-labelledby="h-{E(n["id"])}"><{heading} id="h-{E(n["id"])}">'
                f'<a href="{root}results/{E(n["id"])}.html">{E(label(n))}</a>{title}</{heading}>'
                f'{chip(n["id"])}<div class="statement">{md(n.get("statement", ""), root)}</div>{warn}</section>')

    nav_items = [("index.html", t["article"]), ("graph.html", t["graph"]), ("verification.html", t["verification"]),
                 ("bibliography.html", t["bibliography"])]

    def nav(root: str, cur: str) -> str:
        return (f'<nav class="top-nav" aria-label="{E(proj["title"])}"><ul>'
                + "".join(f'<li><a href="{root}{h}"{" aria-current=\"page\"" if h == cur else ""}>{E(x)}</a></li>'
                          for h, x in nav_items) + "</ul></nav>")

    def page(name: str, title: str, body: str, root: str = "") -> None:
        doc = layout.page(lang=lg, title=f"{title} — {proj['title']}", body=body, root=root,
                          site_name=proj.get("short_title") or proj["title"], header_nav=False,
                          home=f"{root}index.html", footer=E(t["footer"]), nav_html=nav(root, name),
                          extra_css=["assets/math.css", "assets/katex/katex.min.css"],
                          description=proj.get("subtitle", ""))
        (out / name).write_text(doc, encoding="utf-8")

    n_ver = sum(1 for n in nodes if st[n["id"]] == "verified")
    n_res = sum(1 for n in nodes if n["kind"] != "definition")
    lean = d.get("lean", {})
    files = d.get("files", [])
    for f in files:
        p = src / f["path"]
        if not p.is_file():
            problems.append(f"publication: missing file {f['path']}")
            continue
        (out / "files").mkdir(exist_ok=True)
        shutil.copy2(p, out / f["path"])

    # ------------------------------------------------------------ index (article)
    authors = ", ".join(E(a["name"]) + (f' <span class="muted">({E(a["affiliation"])})</span>' if a.get("affiliation") else "")
                        for a in proj.get("authors", []))
    dl = "".join(f'<li><a class="button" href="{E(f["path"])}" download>{E(f.get("title") or f["path"])}</a> '
                 f'<span class="muted">{_fsize(src / f["path"], lg)}</span></li>' for f in files)
    body = [f'<main id="main" class="narrow prose pub" tabindex="-1"><header class="pub-head"><h1>{E(proj["title"])}</h1>',
            f'<p class="subtitle">{E(proj.get("subtitle", ""))}</p>' if proj.get("subtitle") else "",
            f'<p class="authors">{authors}</p>' if authors else "",
            f'<p class="muted">{E(proj.get("date", ""))}</p></header>',
            f'<div class="pub-status"><p><strong>{E(t["summary"].format(v=n_ver, n=n_res))}</strong></p>'
            f'<p><img class="badge" src="verification/badge.svg" alt="{E(t["badge_alt"])}" height="20"></p></div>']
    if proj.get("abstract"):
        body.append(f'<section class="abstract" aria-labelledby="abstract"><h2 id="abstract">{E(t["abstract"])}</h2>'
                    f'{md(proj["abstract"], "")}</section>')
    for sec in (d.get("article") or {}).get("sections", []):
        sid = E(sec.get("id") or "")
        body.append(f'<section aria-labelledby="s-{sid}"><h2 id="s-{sid}">{E(sec.get("title", ""))}</h2>{md(sec.get("body", ""), "", 1)}')
        for nid in sec.get("nodes", []):
            if nid in by:
                body.append(stmt_box(by[nid], ""))
            else:
                problems.append(f"publication: section {sid} lists unknown node {nid}")
        body.append("</section>")
    if dl:
        body.append(f'<section aria-labelledby="downloads"><h2 id="downloads">{E(t["downloads"])}</h2><ul class="plain">{dl}</ul></section>')
    body.append("</main>")
    page("index.html", t["article"], "".join(body))

    # ------------------------------------------------------------ results
    for n in nodes:
        nid = n["id"]
        ln = n.get("lean") or {}
        parts = [f'<main id="main" class="narrow prose pub" tabindex="-1"><p class="crumbs"><a href="../index.html">{E(t["back"])}</a></p>',
                 f'<h1>{E(label(n))}{(" — " + E(n["title"])) if n.get("title") else ""}</h1>{chip(nid)}',
                 f'<section aria-labelledby="st"><h2 id="st">{E(t["statement"])}</h2><div class="statement">{md(n.get("statement", ""), "../")}</div></section>']
        if st[nid] not in ("verified", "defined") and n["kind"] in THEOREM_LIKE:
            parts.append(f'<p class="unverified-note">{E(t["not_verified_note"])}</p>')
        if n.get("uses"):
            parts.append(f'<p><strong>{E(t["uses"])} :</strong></p><ul>'.replace(" :", ":" if lg == "en" else " :")
                         + "".join(f"<li>{node_link(u, '../')}</li>" for u in n["uses"]) + "</ul>")
        if used_by[nid]:
            parts.append(f'<p><strong>{E(t["used_by"])} :</strong></p><ul>'.replace(" :", ":" if lg == "en" else " :")
                         + "".join(f"<li>{node_link(u, '../')}</li>" for u in used_by[nid]) + "</ul>")
        if n["kind"] != "definition":
            parts.append(f'<section aria-labelledby="pf"><h2 id="pf">{E(t["proof"])}</h2>')
            parts.append(md(n["informal_proof"], "../") if n.get("informal_proof") else f'<p class="muted">{E(t["no_proof"])}</p>')
            parts.append("</section>")
        code = ln.get("code") or ""
        if code:
            parts.append(f'<section aria-labelledby="lc"><h2 id="lc">{E(t["lean"])}</h2>'
                         + code_block("lean", code, numbered=True, label=f'{t["lean"]} — {ln.get("name", "")}') + "</section>")
        ax = ln.get("axioms")
        ax_txt = (", ".join(f"<code>{E(a)}</code>" for a in ax) if ax else E(t["none"])) if ax is not None else "—"
        if ax and set(ax) <= STANDARD_AXIOMS:
            ax_txt += f' <span class="muted">({E(t["standard_axioms"])})</span>'
        rows = [(t["state"], chip(nid)), (t["lean_name"], f'<code>{E(ln.get("name", "—"))}</code>'),
                (t["toolchain"], E(ln.get("toolchain") or lean.get("toolchain", "—"))),
                (t["mathlib"], f'<code>{E(ln.get("mathlib") or lean.get("mathlib", "—"))}</code>'),
                (t["axioms"], ax_txt), (t["checked"], E(ln.get("checked_at") or lean.get("checked_at", "—"))),
                (t["checker"], E(lean.get("checker", "—")))]
        parts.append(f'<section aria-labelledby="vi"><h2 id="vi">{E(t["verif_info"])}</h2><div class="table-wrap"><table class="kv"><tbody>'
                     + "".join(f"<tr><th scope=\"row\">{E(k)}</th><td>{v}</td></tr>" for k, v in rows) + "</tbody></table></div></section>")
        refs = n.get("refs") or []
        srcref = n.get("source")
        if refs or srcref:
            items = []
            if srcref:
                items.append(md(f"{t['source']} : [@{srcref['paper_key']}, {srcref.get('locator', '')}]".replace(" :", ":" if lg == "en" else " :"), "../"))
            for r in refs:
                items.append(md(f"[@{r['key']}{', ' + r['locator'] if r.get('locator') else ''}]" + (f" — {r['note']}" if r.get("note") else ""), "../"))
            parts.append(f'<section aria-labelledby="rf"><h2 id="rf">{E(t["refs"])}</h2>{"".join(items)}</section>')
        parts.append("</main>")
        page(f"results/{nid}.html", label(n), "".join(parts), root="../")

    # ------------------------------------------------------------ graph
    gnodes = [{"id": n["id"], "label": label(n), "sub": n.get("title", ""), "status": st[n["id"]],
               "status_text": t["status"][st[n["id"]]], "href": f"results/{n['id']}.html"} for n in nodes]
    edges = [(u, n["id"]) for n in nodes for u in n.get("uses", [])]
    svg = render_svg(gnodes, edges, t["graph_title"], t["graph_desc"])
    legend = "".join(f'<li>{chip_for(s, t)}</li>' for s in ("verified", "proved", "defined", "statement", "stated", "blocked"))
    table = "".join(f'<tr><td>{node_link(n["id"], "")}</td><td>{", ".join(E(label(by[u])) for u in n.get("uses", [])) or "—"}</td></tr>'
                    for n in nodes)
    page("graph.html", t["graph"], f'<main id="main" class="wide prose pub" tabindex="-1"><h1>{E(t["graph_title"])}</h1>'
         f'<p>{E(t["graph_desc"])}</p><div class="graph-scroll" tabindex="0">{svg}</div>'
         f'<h2>{E(t["legend"])}</h2><ul class="legend">{legend}</ul>'
         f'<h2>{E(t["all_results"])}</h2><div class="table-wrap"><table><thead><tr><th>{E(t["result"])}</th><th>{E(t["uses"])}</th></tr></thead>'
         f'<tbody>{table}</tbody></table></div></main>')

    # ------------------------------------------------------------ verification
    vrows = "".join(
        f'<tr><td><a href="results/{E(n["id"])}.html">{E(label(n))}</a></td><td><code>{E((n.get("lean") or {}).get("name", "—"))}</code></td>'
        f'<td>{chip(n["id"])}</td><td>{", ".join(E(a) for a in ((n.get("lean") or {}).get("axioms") or [])) or "—"}</td></tr>'
        for n in nodes)
    page("verification.html", t["verification"],
         f'<main id="main" class="narrow prose pub" tabindex="-1"><h1>{E(t["verification"])}</h1>'
         f'<p>{E(t["summary"].format(v=n_ver, n=n_res))}. {E(t["toolchain"])} <code>{E(lean.get("toolchain", "—"))}</code>, '
         f'{E(t["mathlib"])} <code>{E(lean.get("mathlib", "—"))}</code>, {E(t["checker"]).lower()} : {E(lean.get("checker", "—"))}.</p>'.replace(" :", ":" if lg == "en" else " :")
         + f'<div class="table-wrap"><table><thead><tr><th>{E(t["result"])}</th><th>{E(t["lean_name"])}</th><th>{E(t["state"])}</th>'
         f'<th>{E(t["axioms"])}</th></tr></thead><tbody>{vrows}</tbody></table></div>'
         f'<h2>{E(t["ci"])}</h2><p>{t["ci_text"]}</p><p><img class="badge" src="verification/badge.svg" alt="{E(t["badge_alt"])}" height="20"></p>'
         f'<p><a href="verification/result.json">verification/result.json</a></p></main>')

    # ------------------------------------------------------------ bibliography
    keys = cited + [k for k in bib if k not in cited]
    items = "".join(f'<li id="ref-{E(k)}"><span class="bib-label">[{E(_label(bib[k]))}]</span> {_bib_entry(bib[k])}</li>' for k in keys)
    page("bibliography.html", t["bibliography"], f'<main id="main" class="narrow prose pub" tabindex="-1"><h1>{E(t["bibliography"])}</h1>'
         f'<ol class="bib">{items}</ol></main>')

    # ------------------------------------------------------------ verification placeholders (overwritten by CI)
    (out / "verification").mkdir(exist_ok=True)
    if not (out / "verification" / "result.json").exists():
        (out / "verification" / "result.json").write_text(json.dumps(
            {"state": "pending", "note": "lake build has not run yet (local preview)"}, indent=1) + "\n")
        (out / "verification" / "badge.svg").write_text(badge_svg("lake build", "en attente" if lg == "fr" else "pending", "#6b7280"))
    expected = expected_checks(d, st)
    (out / "verification" / "expected.json").write_text(json.dumps(expected, indent=1, ensure_ascii=False) + "\n")
    (out / "verification" / "Verify.lean").write_text(verify_file(d, st))
    if own_math:
        math.finish()
        for f in out.rglob("*.html"):
            f.write_text(math.apply(f.read_text(encoding="utf-8")), encoding="utf-8")
    return {"nodes": len(nodes), "verified": n_ver, "statuses": st}


_MARK = {"verified": "✓", "proved": "(✓)", "defined": "≔", "statement": "◇", "stated": "…", "blocked": "✕"}


def chip_for(s: str, t: dict) -> str:
    return f'<span class="chip st-{s}"><span aria-hidden="true">{_MARK[s]}</span> {E(t["status"][s])}</span>'


def _fsize(p: Path, lg: str) -> str:
    if not p.is_file():
        return ""
    n = p.stat().st_size
    if n < 1e6:
        return f"{n / 1e3:.0f} ko" if lg == "fr" else f"{n / 1e3:.0f} kB"
    return (f"{n / 1e6:.1f} Mo".replace(".", ",")) if lg == "fr" else f"{n / 1e6:.1f} MB"


def badge_svg(left: str, right: str, color: str) -> str:
    """Flat badge, no external font (system sans); same function used by site/publication/ci/make_badge.py."""
    lw, rw = 8 + 7 * len(left), 8 + 7 * len(right)
    w = lw + rw
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{E(left)}: {E(right)}">'
            f'<title>{E(left)}: {E(right)}</title><rect width="{lw}" height="20" fill="#3b4252"/>'
            f'<rect x="{lw}" width="{rw}" height="20" fill="{color}"/>'
            f'<g fill="#fff" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11">'
            f'<text x="{lw / 2}" y="14" text-anchor="middle">{E(left)}</text>'
            f'<text x="{lw + rw / 2}" y="14" text-anchor="middle">{E(right)}</text></g></svg>\n')


def expected_checks(d: dict, st: dict | None = None) -> dict:
    """What the site claims, for the CI to re-check independently: every result shown as verified must compile and
    depend only on Lean's standard axioms."""
    st = st or statuses(d.get("nodes", []))
    names = [(n.get("lean") or {}).get("name") for n in d.get("nodes", [])
             if st[n["id"]] == "verified" and (n.get("lean") or {}).get("name")]
    return {"schema": "madalean-verification/1", "toolchain": (d.get("lean") or {}).get("toolchain", ""),
            "root_module": (d.get("lean") or {}).get("root_module", ""), "verified": names,
            "allowed_axioms": sorted(STANDARD_AXIOMS)}


def verify_file(d: dict, st: dict | None = None) -> str:
    """lean/Verify.lean of the published Lake project: `#print axioms` for every result the site calls verified.
    The CI runs `lake env lean Verify.lean` and compares the output with verification/expected.json."""
    e = expected_checks(d, st)
    lines = [f"import {e['root_module'] or 'Main'}", "", "-- Generated by Madalean: checked by the CI workflow."]
    lines += [f"#print axioms {n}" for n in e["verified"]]
    return "\n".join(lines) + "\n"
