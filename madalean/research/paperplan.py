"""« De l'article au plan formel » (TODO Stratégie 2.1 item 6, DECISIONS D60, docs/BLUEPRINT.md).

A paper's blueprint (`papers.py`: statements, labels, verbatim TeX, `\\ref` / « Proof of Theorem X » edges) becomes a
formal plan, progressively and within a budget:

1. **Selection → dependency closure.** The user picks theorems; the closure follows the paper's explicit edges only
   (`\\ref` in proofs and statements, « Proof of … » sections, textual « by Lemma 2.3 » in PDFs, edges the user
   added or accepted). A model-proposed edge counts only once the user accepted it: unknown dependencies stay
   unknown, never invented.
2. **Statements.** Each node of the closure, dependencies first: the verbatim statement (and the verbatim
   definitions it uses, as context) goes to the usual formalizer (Goedel prompt, verified catalogue, Lean check of
   the statement — `pipeline.goedel.Formalizer`), then the Mathlib-first check without a model
   (`literature.formal.mathlib_status`: library → « prouvé », a Mathlib name closing it under the strict verdict →
   « dans Mathlib », else « à prouver »). A Lean statement is a model's translation: shown « à relire », never as
   the paper's text. Definitions are not formalised in this version (honestly « non formalisé »).
3. **Problem graph (D57 / D57b).** One top-level dossier per selected main result (a selected node that no other
   selected node uses); the results it rests on become nodes of its graph with the paper's edges — Mathlib ones
   verified, the others `cited` (conditional: the paper claims them, Lean has not proved them) — and each
   formalised one « à prouver » is opened as a sub-dossier (`GraphService.open_node`), so that its Lean proof rolls
   up through the existing machinery. Nothing is started: the user launches the provers.
4. **Budget and resume.** At most `statements` formalisations and `seconds` per run, cancellable; every node's
   record is saved as soon as it is known, so a stopped run resumes where it stopped (done nodes are skipped,
   nodes stopped by the budget or a missing model are retried).

Status per node (`plan_status`): proved · in_mathlib · to_prove (formalised, a dossier to prove it) · formalised
(Lean statement, no dossier) · unformalised; `rests_on` lists the results of the closure that are not yet proved
(a result is « conditionnel » while that list is not empty)."""
from __future__ import annotations

import asyncio
import html
import re
import time
from dataclasses import dataclass

from .. import leancheck
from ..logs import get

log = get("research.paperplan")

STATUSES = ("proved", "in_mathlib", "to_prove", "formalised", "unformalised")
DONE = ("proved", "in_mathlib")
# notes of an unformalised node that a new run may change (everything else is final for this text)
RETRY_NOTES = ("budget", "no_model", "error", "stopped", "no_workspace", "")
MAX_SELECTED = 40
MAX_CONTEXT_DEFS = 4


# ---------------------------------------------------------------- graph of the paper
def _edges(node: dict) -> list[str]:
    """The dependencies the closure follows: explicit ones, and proposed ones only once accepted by the user."""
    return [u["to"] for u in node.get("uses", []) if not u.get("rejected") and (not u.get("proposed") or
                                                                                   u.get("accepted"))]


def closure(bp: dict, selected: list[str]) -> list[str]:
    """The selected nodes and everything they (transitively) use, dependencies first, in paper order otherwise.
    Cycle-safe (a cycle in a paper's references is cut, never followed forever)."""
    nodes = {n["id"]: n for n in bp.get("nodes", [])}
    rank = {nid: i for i, nid in enumerate(nodes)}
    out: list[str] = []
    state: dict[str, int] = {}                      # 1 visiting, 2 done

    def visit(nid: str) -> None:
        stack = [(nid, iter(sorted(_edges(nodes[nid]), key=lambda x: rank.get(x, 0))))]
        state[nid] = 1
        while stack:
            cur, it = stack[-1]
            nxt = next((x for x in it if x in nodes and state.get(x) is None), None)
            if nxt is None:
                stack.pop()
                state[cur] = 2
                out.append(cur)
                continue
            state[nxt] = 1
            stack.append((nxt, iter(sorted(_edges(nodes[nxt]), key=lambda x: rank.get(x, 0)))))
    for nid in sorted((s for s in selected if s in nodes), key=lambda x: rank[x]):
        if state.get(nid) is None:
            visit(nid)
    return out


def mains(bp: dict, selected: list[str]) -> list[str]:
    """Selected nodes that no other selected node (transitively) uses: one top-level dossier each."""
    sel = [s for s in selected if any(n["id"] == s for n in bp.get("nodes", []))]
    used: set[str] = set()
    for s in sel:
        used |= set(closure(bp, [s])) - {s}
    return [s for s in sel if s not in used]


# ---------------------------------------------------------------- statements
def lean_name(node: dict) -> str:
    """A readable, valid Lean identifier for the node: `paper_<label>` or `paper_<kind>_<number>`."""
    base = node.get("label") or f"{node.get('kind', 'result')}_{node.get('number') or node['id']}"
    slug = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower()[:48] or "result"
    return "paper_" + slug


def verbatim(node: dict) -> str:
    return (node.get("verbatim") or node.get("tex") or node.get("text") or "").strip()


def location(bp: dict, node: dict) -> str:
    loc = node.get("locator") or f"{node.get('name', '')} {node.get('number', '')}".strip()
    if node.get("line"):
        loc += f", l. {node['line']}"
    return loc


def formalize_text(bp: dict, node: dict) -> str:
    """What the formalizer receives: the verbatim statement, the verbatim definitions it uses, the place."""
    nodes = {n["id"]: n for n in bp.get("nodes", [])}
    defs = [nodes[t] for t in _edges(node) if t in nodes and nodes[t].get("kind") == "definition"][:MAX_CONTEXT_DEFS]
    head = f"{node.get('name', '')} {node.get('number', '')}".strip()
    text = f"{head}. {verbatim(node)}"
    if defs:
        text += "\n\nDefinitions used (verbatim from the same paper):\n" + "\n".join(
            f"- {d.get('name', '')} {d.get('number', '')}: {verbatim(d)[:800]}" for d in defs)
    return (text + f"\n\n(Result quoted verbatim from the paper {bp.get('paper_key', '')}, {location(bp, node)}. "
            "State exactly this result, with all its hypotheses; do not prove it.)")


@dataclass
class PlanBudget:
    statements: int = 6              # formalisations per run
    seconds: float = 900.0           # wall clock of a run
    tries: int = 2                   # formalizer tries per statement (Lean feedback between them)
    timeout_s: int = 120             # one Lean check

    @classmethod
    def from_request(cls, data: dict) -> "PlanBudget":
        def num(k, lo, hi, d):
            try:
                return max(lo, min(hi, type(d)(data.get(k, d))))
            except (TypeError, ValueError):
                return d
        return cls(statements=num("statements", 1, 40, 6), seconds=num("seconds", 30.0, 7200.0, 900.0),
                   tries=num("tries", 1, 3, 2))


def _io(ctx, mode: str, b: PlanBudget):
    """The formalizer's IO: the literature one (D56: every call and check counted), but in Local mode the local
    models may translate (the user started this run explicitly); never a paid model."""
    from ..literature import formal
    from ..literature.types import Budget

    class PaperIO(formal.LitIO):
        def free_models(self, role: str) -> list:
            try:
                cands = self.ctx.brain.candidates(role, self.mode)
            except Exception:  # noqa: BLE001
                return []
            return [c for c in cands if not getattr(c, "paid", False)]
    budget = Budget(seconds=b.seconds, requests=0, model_calls=b.statements * b.tries + 2,
                    lean_checks=b.statements * (b.tries + 8), items=0, formalize=b.statements).start()
    return PaperIO(ctx, mode, budget, owner="paperplan")


def _item(bp: dict, node: dict, statement: str = ""):
    """The node as a literature item (origin `paper`), so that the Mathlib / library check of D56 applies as is."""
    from ..literature import quotes as Q
    from ..literature.types import LeanLink, LiteratureItem, Quote, Reference, SourceText
    text = verbatim(node)
    ref = Reference(id=f"source:{bp.get('shelf', '')}/{bp.get('source_id', '')}", title=bp.get("title") or
                    bp.get("paper_key", ""), source_id=bp.get("source_id", ""), shelf=bp.get("shelf", ""))
    it = LiteratureItem(id=f"{bp.get('source_id', '')}-{node['id']}"[:60], reference=ref, origin="paper",
                        label=f"{node.get('name', '')} {node.get('number', '')}".strip(), key=bp.get("paper_key", ""))
    it.texts = [SourceText("fulltext", "sources", text, locator=location(bp, node), suspect=Q.suspect(text))]
    it.quotes = [Quote(text, 0, 0, len(text), location(bp, node), picked_by="rules")]
    if statement:
        it.lean = LeanLink(name=lean_name(node), statement=statement, compiled=True, status="to_prove")
    return it


async def formalise_node(ctx, io, bp: dict, node: dict, ws, b: PlanBudget) -> dict:
    """{status, lean, name, compiled, mathlib_name, library_name, model, note, t} for one node. Never raises
    (except on cancellation)."""
    from ..brain.api import BrainError
    from ..literature import formal
    from ..pipeline.goedel import Formalizer
    from ..pipeline.io import InfraError
    rec = {"status": "unformalised", "lean": "", "name": lean_name(node), "compiled": False, "mathlib_name": "",
           "library_name": "", "model": "", "note": "", "t": time.time()}
    if node.get("kind") == "definition":
        rec["note"] = "definition"                # cut in this version (docs/BLUEPRINT.md)
        return rec
    if len(verbatim(node)) < 8:
        rec["note"] = "no_text"
        return rec
    item = _item(bp, node)
    if item.texts[0].suspect:
        rec["note"] = "suspect_text"              # a text that addresses a model is never sent to one
        return rec
    if io.budget.over or io.budget.used_model_calls >= io.budget.model_calls:
        rec["note"] = "budget"
        return rec
    try:
        f = await Formalizer(io, io.mode).run(formalize_text(bp, node), ws, b.tries, b.timeout_s, name=rec["name"])
    except (BrainError, InfraError) as e:
        rec["note"] = "no_model" if "model" in str(e).lower() or getattr(e, "kind", "") == "no_model" else "error"
        if io.budget.over or "budget" in str(e):
            rec["note"] = "budget"
        return rec
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        log.warning("formalisation of %s failed: %s", node["id"], e)
        rec["note"] = "error"
        return rec
    rec["model"] = f.model
    if not (f.statement and f.ok):
        rec["note"] = "lean_refused" if f.statement else "no_statement"
        rec["lean"] = f.statement or ""          # kept for the user to read, marked as refused
        return rec
    st = f.statement
    try:
        old = leancheck.theorem_name(st)
        if old != rec["name"]:
            st = re.sub(rf"\btheorem\s+{re.escape(old)}\b", f"theorem {rec['name']}", st, count=1)
    except leancheck.StatementError:
        rec["note"] = "lean_refused"
        return rec
    rec.update(lean=st, compiled=True, status="to_prove")
    item = _item(bp, node, st)
    await formal.mathlib_status(ctx, io, item, ws, b.timeout_s)
    if item.lean.status == "in_mathlib":
        rec.update(status="in_mathlib", mathlib_name=item.lean.mathlib_name)
    elif item.lean.status == "proved":
        rec.update(status="proved", library_name=item.lean.library_name)
    return rec


def needs_work(node: dict) -> bool:
    rec = node.get("formal")
    if not rec:
        return True
    return rec.get("status") == "unformalised" and rec.get("note", "") in RETRY_NOTES


# ---------------------------------------------------------------- the run
class PlanRun:
    """One budgeted run over a blueprint. `load()` / `save(bp)` read and write the blueprint (the run merges its
    records into the CURRENT file at every save: an edge curated meanwhile is kept)."""

    def __init__(self, ctx, pid: str, sid: str, selected: list[str], *, mode: str, budget: PlanBudget,
                 dossiers: bool = True, publish=None):
        self.ctx, self.pid, self.sid, self.mode, self.b = ctx, pid, sid, mode, budget
        self.selected = list(dict.fromkeys(selected))[:MAX_SELECTED]
        self.dossiers = dossiers
        self.publish = publish or (lambda bp: None)
        self.stop = asyncio.Event()
        self.state = {"id": "pr-" + format(int(time.time() * 1000) % 10**10, "x"), "running": True, "done": 0,
                      "skipped": 0, "total": 0, "current": "", "reason": "", "started": time.time()}

    def _load(self) -> dict:
        from . import papers
        bp = papers.load(self.ctx, self.pid, self.sid)
        if bp is None:
            raise LookupError("blueprint")
        return bp

    async def _merge_save(self, records: dict, plan: dict | None = None, dossier_links: dict | None = None) -> dict:
        from . import papers
        bp = await asyncio.to_thread(self._load)
        for n in bp["nodes"]:
            if n["id"] in records:
                n["formal"] = records[n["id"]]
            if dossier_links and n["id"] in dossier_links and not n.get("dossier_id"):
                n["dossier_id"] = dossier_links[n["id"]]
        if plan is not None:
            bp["plan"] = plan
        await asyncio.to_thread(papers.save, self.ctx, self.pid, bp)
        self.publish(bp)
        return bp

    async def run(self) -> dict:
        try:
            return await self._run()
        except asyncio.CancelledError:
            self.state["reason"] = "stopped"
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("paper plan run failed")
            self.state["reason"] = "error"
            self.state["error"] = str(e)[:300]
            return self.state
        finally:
            self.state["running"] = False
            self.state["current"] = ""

    async def _run(self) -> dict:
        bp = await asyncio.to_thread(self._load)
        order = closure(bp, self.selected)
        nodes = {n["id"]: n for n in bp["nodes"]}
        self.state["total"] = len(order)
        plan = dict(bp.get("plan") or {})
        plan.update(selected=self.selected, order=order, mains=mains(bp, self.selected))
        plan.setdefault("tops", {})
        plan.setdefault("runs", [])
        try:
            ws = self.ctx.workspace(self._ws_key())
        except Exception:  # noqa: BLE001
            ws = None
        io = _io(self.ctx, self.mode, self.b)
        records: dict[str, dict] = {}
        done = 0
        for nid in order:
            node = nodes[nid]
            if not needs_work(node):
                self.state["skipped"] += 1
                continue
            if self.stop.is_set():
                self.state["reason"] = "stopped"
                break
            if done >= self.b.statements or io.budget.over:
                self.state["reason"] = "budget"
                break
            self.state["current"] = nid
            if ws is None:
                rec = {"status": "unformalised", "note": "no_workspace", "name": lean_name(node), "t": time.time()}
            else:
                rec = await formalise_node(self.ctx, io, bp, node, ws, self.b)
            if rec.get("note") not in ("definition", "no_text", "suspect_text"):
                done += 1
            node["formal"] = records[nid] = rec
            self.state["done"] = done
            await self._merge_save({nid: rec})
        if not self.state["reason"]:
            self.state["reason"] = "complete"
        links: dict[str, str] = {}
        # the problem graph is built once the whole closure is known (a partial run only records statements)
        if self.dossiers and self.state["reason"] == "complete" and \
                getattr(getattr(self.ctx, "research", None), "graphs", None) is not None:
            bp = await asyncio.to_thread(self._load)
            links = await self._graphs(bp, plan)
            records = {n["id"]: n["formal"] for n in bp["nodes"] if n.get("formal")}
        plan["runs"] = (plan["runs"] + [{k: self.state[k] for k in ("id", "done", "skipped", "total", "reason",
                                                                     "started")} | {"ended": time.time()}])[-10:]
        await self._merge_save(records, plan, links)
        return self.state

    def _ws_key(self) -> str:
        p = self.ctx.projects.get(self.pid)
        return (p.workspace if p is not None and p.workspace else "") or self.ctx.settings.workspace

    # -- the problem graph (D57 / D57b), through the graph service's public functions only
    async def _graphs(self, bp: dict, plan: dict) -> dict[str, str]:
        from ..server.routes_work import create_dossier
        from . import proofgraph as G
        svc = self.ctx.research.graphs
        nodes = {n["id"]: n for n in bp["nodes"]}
        links: dict[str, str] = {}
        for main in plan["mains"]:
            mn = nodes[main]
            if mn.get("kind") == "definition":
                continue
            rec = mn.setdefault("formal", {"status": "unformalised", "note": "budget", "name": lean_name(mn)})
            top_id = plan["tops"].get(main) or rec.get("dossier_id") or mn.get("dossier_id") or ""
            top = self.ctx.repo.get(top_id) if top_id else None
            if top is None:
                spec = {"title": (f"{mn.get('name', '')} {mn.get('number', '')}".strip() +
                                  (f" — {mn['title']}" if mn.get("title") else "") +
                                  f" [{bp.get('paper_key', '')}]")[:200],
                        "problem": f"{verbatim(mn)}\n\n({bp.get('paper_key', '')}, {location(bp, mn)})"[:20000],
                        "statement": rec.get("lean", "") if rec.get("compiled") else "",
                        "project_id": self.pid, "workspace": self._ws_key(), "kind": "theorem", "start": False}
                try:
                    top, _job = await create_dossier(self.ctx, spec, user_event=True)
                except leancheck.StatementError:
                    spec["statement"] = ""
                    top, _job = await create_dossier(self.ctx, spec, user_event=True)
                top.source = {"paper_key": bp.get("paper_key", ""), "locator": location(bp, mn),
                              "original_text": verbatim(mn)[:20000]}
                top.extra["paperplan"] = {"source_id": bp["source_id"], "node_id": main}
                await self.ctx.repo.save(top)
            plan["tops"][main] = top.id
            rec["dossier_id"] = top.id
            links[main] = top.id
            g = svc.ensure(top.id)
            if rec.get("status") == "in_mathlib" and g["nodes"][g["root"]]["status"] not in G.VERIFIED:
                G.set_status(g, g["root"], "mathlib", rec.get("mathlib_name", ""))
            gid_of = {main: g["root"]}
            for nid in closure(bp, [main]):
                if nid == main:
                    continue
                n = nodes[nid]
                r = n.get("formal") or {}
                gid = (r.get("graph") or {}).get(top.id)
                if gid not in g["nodes"]:
                    gid = self._graph_node(g, bp, n, r)
                gid_of[nid] = gid
                r.setdefault("graph", {})[top.id] = gid
                n["formal"] = r
            for nid, gid in gid_of.items():
                for t in _edges(nodes[nid]):
                    if t in gid_of and gid_of[t] != gid:
                        G.add_edge(g, gid, "uses", gid_of[t])
            svc.save(top.id)
            for nid, gid in gid_of.items():
                r = nodes[nid].get("formal") or {}
                if nid == main or r.get("status") != "to_prove" or not r.get("compiled"):
                    continue
                existing = r.get("dossier_id") or nodes[nid].get("dossier_id") or ""
                gn = g["nodes"][gid]
                if existing and self.ctx.repo.get(existing) is not None and not gn.get("dossier_id"):
                    d = self.ctx.repo.get(existing)          # a dossier made earlier for this node: linked, kept
                    d.extra.setdefault("graph", {"graph_dossier": top.id, "node": gid})
                    await self.ctx.repo.save(d)
                    gn["dossier_id"] = existing
                    svc.save(top.id)
                    sub = existing
                else:
                    try:
                        sub = (await svc.open_node(top.id, gid))["dossier_id"]
                    except G.GraphError as e:
                        r["note"] = f"sub_dossier:{e.kind}"
                        continue
                r["dossier_id"] = sub
                links[nid] = sub
            svc.publish(top.id)
        return links

    def _graph_node(self, g: dict, bp: dict, n: dict, r: dict) -> str:
        from . import proofgraph as G
        title = (f"{n.get('name', '')} {n.get('number', '')}".strip() + (f" — {n['title']}" if n.get("title") else ""))
        src = {"kind": "paper", "source_id": bp.get("source_id", ""), "node": n["id"]}
        lean = r.get("lean", "") if r.get("compiled") else ""
        if r.get("status") == "in_mathlib":
            node = G.new_node("mathlib", title, lean=lean, statement_nl=verbatim(n), status="mathlib",
                              source={**src, "name": r.get("mathlib_name", "")})
        elif r.get("status") == "proved":
            node = G.new_node("library", title, lean=lean, statement_nl=verbatim(n), status="proved", source=src)
        else:
            # the paper proves it, Lean has not: a cited result, conditional until a Lean proof rolls up
            node = G.new_node("cited", title, lean=lean, statement_nl=verbatim(n), status="cited", source=src)
            node["claimed"] = "proved" if n.get("proof") else "stated"
        node["citation"] = {"title": bp.get("title") or bp.get("paper_key", ""), "key": bp.get("paper_key", ""),
                            "locator": location(bp, n), "quote": verbatim(n)[:1500], "verified": True}
        got, _created = G.add_node(g, node)
        return got["id"]


# ---------------------------------------------------------------- status and exports
def node_status(ctx, node: dict) -> str:
    rec = node.get("formal") or {}
    for did in (rec.get("dossier_id"), node.get("dossier_id")):
        d = ctx.repo.get(did) if did else None
        if d is not None and d.proof_is_current:
            return "proved"
    if rec.get("status") in DONE:
        return rec["status"]
    if rec.get("compiled"):
        return "to_prove" if rec.get("dossier_id") else "formalised"
    return "unformalised"


def plan_status(ctx, bp: dict) -> dict:
    """{nodes: {id: {status, rests_on, lean, name, dossier_id, note, mathlib_name, location, verbatim}},
    progress: {proved, in_mathlib, to_prove, formalised, unformalised, total, done}, plan}."""
    nodes = {n["id"]: n for n in bp.get("nodes", [])}
    st = {nid: node_status(ctx, n) for nid, n in nodes.items()}
    out = {}
    for nid, n in nodes.items():
        rec = n.get("formal") or {}
        deps = [x for x in closure(bp, [nid]) if x != nid]
        rests = [x for x in deps if st[x] not in DONE and nodes[x].get("kind") != "definition"]
        out[nid] = {"status": st[nid], "rests_on": [] if st[nid] in DONE else rests, "deps": deps,
                    "lean": rec.get("lean", ""), "compiled": bool(rec.get("compiled")), "name": rec.get("name", ""),
                    "dossier_id": rec.get("dossier_id") or n.get("dossier_id", ""), "note": rec.get("note", ""),
                    "mathlib_name": rec.get("mathlib_name", ""), "library_name": rec.get("library_name", ""),
                    "model": rec.get("model", ""), "location": location(bp, n), "verbatim": verbatim(n),
                    "tried": bool(rec)}
    plan = bp.get("plan") or {}
    scope = plan.get("order") or list(nodes)
    counts = {s: sum(1 for x in scope if x in st and st[x] == s) for s in STATUSES}
    counts["total"] = len([x for x in scope if x in st])
    counts["done"] = counts["proved"] + counts["in_mathlib"]
    return {"nodes": out, "progress": counts, "plan": plan}


TEX_ENV = {"theorem": "theorem", "lemma": "lemma", "proposition": "proposition", "corollary": "corollary",
           "definition": "definition", "conjecture": "conjecture", "claim": "lemma", "question": "conjecture"}


def _tex_label(n: dict) -> str:
    return n.get("label") or re.sub(r"[^A-Za-z0-9:_-]", "-", n["id"])


def export_tex(bp: dict, status: dict) -> str:
    """A blueprint-style LaTeX summary (leanblueprint macros `\\lean`, `\\leanok`, `\\mathlibok`, `\\uses`), with
    the paper's statements verbatim. Compiles alone: the macros are defined as no-ops when the package is absent."""
    nodes = {n["id"]: n for n in bp.get("nodes", [])}
    p = status["progress"]
    lines = [r"\documentclass{article}", r"\usepackage{amsmath,amssymb,amsthm}",
             r"\providecommand{\lean}[1]{}\providecommand{\leanok}{}\providecommand{\mathlibok}{}"
             r"\providecommand{\uses}[1]{}",
             *(rf"\newtheorem{{{e}}}{{{e.capitalize()}}}" for e in dict.fromkeys(TEX_ENV.values())),
             rf"\title{{Blueprint: {_tex_escape(bp.get('title') or bp.get('paper_key', ''))}}}",
             r"\begin{document}", r"\maketitle",
             rf"\noindent Formal plan generated by Madalean from \texttt{{{_tex_escape(bp.get('paper_key', ''))}}}. "
             rf"Proved in Lean: {p['proved']}; in Mathlib: {p['in_mathlib']}; to prove: {p['to_prove']}; "
             rf"formalised: {p['formalised']}; not formalised: {p['unformalised']} (of {p['total']}). "
             r"Statements are quoted verbatim from the paper; Lean statements are translations to be re-read.", ""]
    scope = set(status["plan"].get("order") or nodes)
    for nid, n in nodes.items():
        if nid not in scope:
            continue
        s = status["nodes"][nid]
        env = TEX_ENV.get(n.get("kind", ""), "lemma")
        title = f"[{n['title']}]" if n.get("title") else ""
        lines.append(rf"\begin{{{env}}}{title}\label{{{_tex_label(n)}}}")
        if s["name"] and s["compiled"]:
            lines.append(rf"\lean{{{s['name']}}}")
        if s["status"] == "in_mathlib":
            lines.append(r"\mathlibok")
        elif s["status"] in ("proved", "to_prove", "formalised"):
            lines.append(r"\leanok" if s["status"] == "proved" else "% statement formalised, not proved")
        uses = [_tex_label(nodes[x]) for x in _edges(n) if x in nodes]
        if uses:
            lines.append(rf"\uses{{{','.join(uses)}}}")
        lines.append(f"% {s['location']} -- status: {s['status']}")
        lines.append(verbatim(n))
        lines.append(rf"\end{{{env}}}")
        if s["lean"] and s["compiled"]:
            lines += [r"\begin{verbatim}", s["lean"].replace(r"\end{verbatim}", ""), r"\end{verbatim}"]
        lines.append("")
    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"


def _tex_escape(s: str) -> str:
    return re.sub(r"([\\{}$&#%_^~])", lambda m: {"\\": r"\textbackslash{}", "^": r"\^{}", "~": r"\~{}"}.get(
        m.group(1), "\\" + m.group(1)), s)


STATUS_TEXT = {"fr": {"proved": "prouvé (Lean)", "in_mathlib": "dans Mathlib", "to_prove": "à prouver",
                      "formalised": "énoncé formalisé", "unformalised": "non formalisé"},
               "en": {"proved": "proved (Lean)", "in_mathlib": "in Mathlib", "to_prove": "to prove",
                      "formalised": "statement formalised", "unformalised": "not formalised"}}


def export_html(bp: dict, status: dict, lang: str = "fr") -> str:
    """A self-contained HTML summary (no script, every text escaped)."""
    T = STATUS_TEXT["en" if lang == "en" else "fr"]
    e = html.escape
    nodes = {n["id"]: n for n in bp.get("nodes", [])}
    p = status["progress"]
    scope = set(status["plan"].get("order") or nodes)
    rows = []
    for nid, n in nodes.items():
        if nid not in scope:
            continue
        s = status["nodes"][nid]
        uses = ", ".join(e(f"{nodes[x].get('name', '')} {nodes[x].get('number', '')}".strip()) for x in _edges(n)
                         if x in nodes)
        lean = f"<pre>{e(s['lean'])}</pre>" if s["lean"] and s["compiled"] else ""
        rests = ", ".join(e(f"{nodes[x].get('name', '')} {nodes[x].get('number', '')}") for x in s["rests_on"])
        rows.append(f"<tr id=\"{e(nid)}\"><td><b>{e(n.get('name', ''))} {e(n.get('number', ''))}</b>"
                    f"<br><small>{e(s['location'])}</small></td><td class=\"st {e(s['status'])}\">{e(T[s['status']])}"
                    + (f"<br><small>{'repose sur' if lang != 'en' else 'rests on'} {rests}</small>" if rests else "")
                    + f"</td><td><blockquote>{e(verbatim(n))}</blockquote>{lean}</td><td>{uses}</td></tr>")
    head = ("Résultat", "État", "Énoncé (verbatim) et énoncé Lean", "Utilise") if lang != "en" else \
        ("Result", "Status", "Statement (verbatim) and Lean statement", "Uses")
    summary = " · ".join(f"{T[k]} : {p[k]}" for k in STATUSES)
    return ("<!doctype html><html lang=\"" + ("en" if lang == "en" else "fr") + "\"><head><meta charset=\"utf-8\">"
            f"<title>Blueprint — {e(bp.get('paper_key', ''))}</title><style>body{{font-family:sans-serif;margin:1.5rem;"
            "max-width:70rem}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ccc;"
            "padding:.4rem;vertical-align:top;text-align:left}}pre{{white-space:pre-wrap;background:#f4f4f4;"
            "padding:.4rem}}blockquote{{margin:0;font-family:monospace;white-space:pre-wrap}}.proved,.in_mathlib"
            "{{color:#176b2c}}.to_prove{{color:#8a5a00}}</style></head><body>"
            f"<h1>Blueprint — {e(bp.get('title') or bp.get('paper_key', ''))}</h1><p>{e(summary)} "
            f"({p['done']}/{p['total']})</p><table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head) +
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></body></html>\n")
