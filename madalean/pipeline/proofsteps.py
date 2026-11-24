"""What surrounds the proof tournament (S-BI, D67): the split without a model, the bounded reasoned search when the best
model failed, the rule for open problems, the lessons of a failed search, and the honest final report. Every verified
thing here comes from a fresh strict Lean check."""
from __future__ import annotations

import asyncio
import time

from .. import leancheck
from ..i18n import msg
from ..logs import get
from . import blackboard as BB, decompose as DC, probes as P
from .goedel import ProveResult

log = get("pipeline.proofsteps")
DECOMPOSE_SHARE = 0.4            # share of the remaining tournament time
DECOMPOSE = {"max_attempts": 10, "max_nodes": 12, "max_expansions": 1, "max_depth": 2, "no_progress": 4}
OPEN = {"max_attempts": 6, "max_nodes": 6, "max_expansions": 1, "max_depth": 1, "no_progress": 3, "wall_s": 360}
SPLIT_TIMEOUT = 150
PATTERNS = {"and": "conjonction", "iff": "équivalence", "cases": "disjonction de cas"}
REPORT_LEMMAS = 6


def board_of(job) -> BB.Board | None:
    return getattr(job, "board", None)


def env_of(ws) -> dict:
    from ..runtime.lean import workspace_info
    try:
        return workspace_info(ws) or {}
    except Exception:  # noqa: BLE001
        return {}


def begin(pipe, job, d, ws, statement: str) -> BB.Board:
    job.board = BB.Board.load(d, statement, env_of(ws))
    job.split = None
    job.tried_steps = []
    return job.board


def graphs_of(ctx):
    if not getattr(ctx.settings, "problem_graph", True):
        return None
    return getattr(getattr(ctx, "research", None), "graphs", None)


def status_of(d) -> str:
    m = d.extra.get("meaning")
    s = str(m.get("known_status") or "") if isinstance(m, dict) else ""
    return s if s in ("open", "false") else ""


def search_allowed(job, d) -> bool:
    """No one-shot search on an open / false claim, unless the user asked for it with a budget."""
    return not status_of(d) or int(getattr(job, "step_budget", 0) or 0) > 0


def can_search(pipe, d) -> bool:
    """May the reasoned search run here (real Lean, a graph, not a lemma of the user's own plan: D31)?"""
    gs = graphs_of(pipe.ctx)
    if gs is None or not pipe._lean_real() or isinstance(d.extra.get("plan"), dict):
        return False
    r = gs.runs.get(d.id)
    return r is None or r["task"].done()


def _tried(job, what: str, **kw) -> None:
    getattr(job, "tried_steps", []).append({"what": what, **kw})


def _clean(code: str) -> str:
    """A declaration without its `set_option … in` lines (an assembled proof has none)."""
    return "\n".join(ln for ln in code.split("\n") if not ln.startswith("set_option")).strip()


async def _strict(pipe, io, ws, statement: str, code: str) -> ProveResult | None:
    try:
        full = leancheck.assemble_proof(statement, code)
    except leancheck.StatementError:
        return None
    name = leancheck.theorem_name(statement)
    r = await io.check(leancheck.with_axiom_probe(full, name), ws, pipe.settings.compile_timeout_s, name)
    if not r.verdict.ok:
        return None
    return ProveResult(True, full, r.verdict.summary, [], "madalean:decompose", r.verdict.axioms, r.seconds)


async def split_first(pipe, job, d, io, ws, statement: str) -> ProveResult | None:
    """Conjunction / equivalence / cases: cut without a model, Lean accepts the cut, automation proves what it can."""
    if not pipe._lean_real():
        return None
    sp = DC.split(statement)
    if sp is None:
        return None
    from ..research.graphsearch import CLOSERS
    board = board_of(job)
    try:
        r = await io.check(DC.gate_code(statement, sp), ws, SPLIT_TIMEOUT, None)
        if r.verdict.errors or r.timed_out or r.infra_error:
            return None
        sig = P.split_statement(statement)
        probes = []
        for p in sp.parts:
            head = p["lean"][len(f"theorem {p['name']} "):].rsplit(":= by sorry", 1)[0].strip()
            p["head"] = head
            if p["name"] not in board.lemmas:
                probes.append(P.Probe(p["name"], P.decl(p["name"], head, CLOSERS, 100000), "part"))
        await P.run_batch(io, ws, sig.preamble, probes, SPLIT_TIMEOUT)
        for p in [x for x in probes if x.ok]:
            s = await P.strict(io, ws, sig.preamble, p, SPLIT_TIMEOUT)
            if s.verdict.ok:
                board.add_lemma(p.name, next(x["head"] for x in sp.parts if x["name"] == p.name), _clean(p.code),
                                "lean")
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 (the cut is a help)
        log.warning("split: %s", e)
        return None
    job.split, board.cut = sp, sp.pattern
    done = [p for p in sp.parts if p["name"] in board.lemmas]
    _tried(job, "split", pattern=sp.pattern, n=len(sp.parts), k=len(done))
    _seed(pipe, d, sp, board)
    await pipe.event(d, job, "info", "Découpage sans modèle ({pattern}) : {n} morceaux, {k} prouvés directement par "
                     "Lean.", pattern=msg(PATTERNS[sp.pattern])["text"], n=len(sp.parts), k=len(done))
    if len(done) < len(sp.parts):
        return None
    return await _strict(pipe, io, ws, statement, DC.combined(statement, sp, {p["name"]: board.lemmas[p["name"]]["code"]
                                                                             for p in sp.parts}))


def _seed(pipe, d, sp: DC.Split, board: BB.Board) -> None:
    """The Lean-accepted cut in the problem graph: parts as lemmas of the goal, with the combination."""
    gs = graphs_of(pipe.ctx)
    if gs is None or isinstance(d.extra.get("plan"), dict):
        return
    try:
        from ..research import proofgraph as G
        g = gs.ensure(d.id)
        root = g["nodes"][g["root"]]
        if G.uses_of(g, g["root"]):
            return                              # the user's plan or an earlier track: left alone
        for p in sp.parts:
            node, _c = G.add_node(g, G.new_node("lemma", p["title"], lean=p["lean"], why=sp.pattern,
                                                source={"kind": "split"}), parent=g["root"])
            m = board.lemmas.get(p["name"])
            if m and node["status"] == "open":
                node["proof"], node["tactics"] = m["code"], G.tactics_of(m["code"])
                G.set_status(g, node["id"], "proved", "", self_contained=True)
        root["combination"] = sp.combination
        gs.save(d.id)
        gs.publish(d.id)
    except Exception:  # noqa: BLE001
        log.exception("seed")


async def reasoned(pipe, job, d, io, ws, statement: str, seconds: float, budgets: dict) -> ProveResult | None:
    """The bounded reasoned search of D57 inside the proof stage: the stored cut, else a split proposed by a model and
    accepted by Lean. Its verified lemmas go on the blackboard."""
    if seconds < 20 or not can_search(pipe, d):
        return None
    from ..research import graphsearch as GS, proofgraph as G
    gs, board = graphs_of(pipe.ctx), board_of(job)
    BB.mirror(gs, d.id, board)
    g = gs.ensure(d.id)
    root = g["nodes"][g["root"]]
    if not G.uses_of(g, g["root"]):
        root["expand_first"] = True             # a one-shot proof has just failed: split, do not try it again
    b = GS.Budgets.from_settings(pipe.settings, budgets)
    b.wall_s = min(b.wall_s, seconds)
    search = GS.ReasonedSearch(g, GS.LeanOps(pipe.ctx, gs, d.id, job.mode), b, save=lambda: gs.save(d.id),
                               publish=lambda: gs.publish(d.id))
    summary = None
    try:
        summary = await asyncio.wait_for(search.run(), seconds + 5)
    except asyncio.TimeoutError:
        gs.save(d.id)
    except asyncio.CancelledError:
        gs.save(d.id)
        raise
    except Exception:  # noqa: BLE001
        log.exception("reasoned search")
    verified, left = 0, 0
    for nid in search.live():
        n = g["nodes"][nid]
        if nid == g["root"]:
            continue
        ok = n["status"] == "proved" and n.get("self_contained", True) and n.get("proof")
        verified, left = verified + bool(ok), left + (not ok)
        parts = GS.split_decl(n.get("lean") or "") if ok else None
        if parts:
            code = GS._decls_only(n["proof"], search.ops.context)
            if leancheck.declared_names(code) == {parts[1]}:      # self-contained text: usable above a proof
                board.add_lemma(parts[1], parts[2], _clean(code), "graph")
    board.cut = board.cut or "search"
    _tried(job, "search", n=verified, left=left, reason=(summary or {}).get("reason", "budget_time"))
    await pipe.event(d, job, "info", "Découpage en lemmes : {n} vérifiés par Lean, {m} encore ouverts.", n=verified,
                     m=left)
    if not root.get("proof") or root["status"] not in G.VERIFIED or not root.get("self_contained", True):
        return None
    res = await _strict(pipe, io, ws, statement, root["proof"])
    if res is None:
        G.set_status(g, g["root"], "open", "")
        gs.save(d.id)
    return res


# ---------------------------------------------------------------- learning
def learn(pipe, job, d, ok: bool, strategy: str) -> None:
    """Dead ends (with the statement's shape), accepted splits, and what the lessons given to the models were worth."""
    try:
        from ..research import lessons
        st = lessons.store_of(pipe.ctx)
        board = board_of(job)
        if st is None or board is None:
            return
        env = env_of(pipe.ctx.workspace(d.workspace or pipe.ctx.settings.workspace))
        ran = any(a.stage == "proof" and a.model and a.status in ("accepted", "rejected") for a in job.attempts)
        if ran and not status_of(d):             # an open problem says nothing about a lesson
            st.outcome(getattr(job, "lesson_ids", []), ok)
        if ok and strategy == "graph" and board.cut:
            sp = getattr(job, "split", None)
            st.learn_split(d.statement, board.cut, [p["lean"] for p in sp.parts] if sp else [], env, d.id)
        if not ok and not status_of(d):
            for a in sorted(board.approaches.values(), key=lambda x: -x["n"])[:2]:
                if a["n"] >= 3 and a["how"]:
                    st.learn_approach(d.statement, a["how"], a["why"], env, d.id)
    except Exception:  # noqa: BLE001 (learning never breaks a job)
        log.exception("learn")


# ---------------------------------------------------------------- the final report
def cause_of(job, d, verdict: str) -> str:
    board = board_of(job)
    t = getattr(job, "tournament", {}) or {}
    if status_of(d):
        return "false" if status_of(d) == "false" else "open"
    if verdict in ("false", "doubtful"):
        return "translation"
    ran = [a for a in job.attempts if a.stage == "proof" and a.status in ("accepted", "rejected")]
    if not ran and any(a.stage == "proof" and a.status == "error" for a in job.attempts):
        return "providers"
    if t.get("state") in ("time", "attempts", "tokens"):
        return "budget"
    if board is not None and len(board.names) >= 3:
        return "mathlib"
    return "unknown"


CAUSES = {
    "open": "le problème est ouvert, d'après l'étude du sens : une preuve directe n'est pas à attendre",
    "false": "l'affirmation est dite fausse dans l'étude du sens",
    "translation": "la traduction Lean est mise en doute",
    "providers": "les fournisseurs de modèles n'ont pas répondu : ce n'est pas un échec mathématique",
    "budget": "le budget de recherche est épuisé",
    "mathlib": "plusieurs noms cherchés n'existent pas dans ce Mathlib : une théorie manque peut-être",
    "unknown": "indéterminée",
}


def report(pipe, job, d) -> tuple[str, dict]:
    """(French key, params) of the final message; `detail` is the report in words, `report` its data."""
    board = board_of(job)
    verdict = str((pipe._check_of(d) or {}).get("verdict") or "")
    cause = cause_of(job, d, verdict)
    n = len([a for a in job.attempts if a.stage == "proof" and a.status in ("accepted", "rejected", "error")])
    nodes = BB.mirror(graphs_of(pipe.ctx), d.id, board) if board and not isinstance(d.extra.get("plan"), dict) else {}
    tried, lines = [], []
    steps = [dict(x) for x in getattr(job, "tried_steps", [])]
    stages = {"mathlib": "Recherche dans Mathlib.", "certificate": "Certificat par le calcul."}
    for row in job.timings:
        if (k := stages.get(row.get("stage", ""))) and msg(k)["text"] not in tried:
            tried.append(msg(k)["text"])
    for s in steps:
        if s["what"] == "split":
            tried.append(msg("Découpage sans modèle ({pattern}) : {k} morceaux sur {n} prouvés.",
                             pattern=msg(PATTERNS[s["pattern"]])["text"], k=s["k"], n=s["n"])["text"])
        elif s["what"] == "search":
            tried.append(msg("Recherche par lemmes : {n} vérifiés, {m} ouverts.", n=s["n"], m=s["left"])["text"])
        elif s["what"] == "models":
            tried.append(msg("Essais directs : {models} ({n} essais).", models=", ".join(s["models"]), n=s["n"])["text"])
    if status_of(d) and not search_allowed(job, d):
        tried.append(msg("Aucun essai direct : problème ouvert ou dit faux, sans budget demandé.")["text"])
    if (stop := (getattr(job, "tournament", {}) or {}).get("state")) == "no_progress":
        tried.append(msg("Arrêt : plus aucun progrès.")["text"])
    lines.append("**" + msg("Essayé, dans l'ordre")["text"] + "**")
    lines += [f"{i}. {x}" for i, x in enumerate(tried, 1)] or ["—"]
    lines.append("\n**" + msg("Établi (vérifié par Lean)")["text"] + "**")
    lemmas = list(board.lemmas.values())[:REPORT_LEMMAS] if board else []
    lines += [f"- `{m['head'][:300]}`" for m in lemmas] or [msg("Rien de plus que l'énoncé.")["text"]]
    goal = board.goals[-1] if board and board.goals else ""
    lines.append("\n**" + msg("Où cela bloque")["text"] + "**")
    lines.append(f"`⊢ {goal}`" if goal else msg("Aucun but précis n'a été relevé.")["text"])
    cause_text = msg(CAUSES[cause])["text"]
    lines.append("\n**" + msg("Cause probable")["text"] + "** — " + cause_text)
    actions = [{"id": "misunderstood", "target": "statement"}, {"id": "plan", "part": "plan"}, {"id": "hint"}]
    if cause in ("open", "false"):
        actions.append({"id": "budget", "minutes": 10})
    elif cause in ("providers", "budget"):
        actions.append({"id": "retry"})
    data = {"cause": cause, "tried": tried, "goal": goal, "stop": stop or "",
            "lemmas": [{"name": m["name"], "statement": m["head"][:300], "node": nodes.get(m["name"], "")}
                       for m in lemmas], "actions": actions, "t": time.time()}
    key = "Preuve directe non cherchée : {cause}." if status_of(d) and not search_allowed(job, d) else \
        "Aucune preuve trouvée après {n} essais. Cause probable : {cause}."
    return key, {"n": n, "cause": cause_text, "detail": "\n".join(lines), "report": data}
