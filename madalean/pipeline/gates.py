"""The gates of a dossier (S-BG, D65, docs/DOSSIER_FLOW.md): the user validates the meaning, then the Lean statement,
before any proof. Nothing waits in memory: a gate is data of the dossier (`extra.gate`, plus the rest of the plan in
`extra.gate_plan`); the job ends, and the user's answer starts another one. It therefore survives a restart, holds no
resource, and two clients answering at once cannot both win (the state changes before any await).

Who is gated: jobs started by a person on a dossier created since this feature (`extra.flow`), unless they opt out
(`gates=False`: bench, plans and reasoned search on lemmas, Mathlib contributions, scripted API runs)."""
from __future__ import annotations

import asyncio
import time
import uuid

from .. import leancheck
from ..dossiers import Dossier
from ..i18n import language, msg
from ..logs import get
from . import faithful as F

log = get("pipeline.gates")
STATUS_SECONDS = 60            # the literature never holds the meaning gate longer than this
MAX_REPORTS = 40


# ---------------------------------------------------------------- state
def enabled(settings, d: Dossier) -> bool:
    return bool(getattr(settings, "validate_before_proof", True)) and bool(d.extra.get("flow"))


def active(pipe, job, d: Dossier) -> bool:
    return bool(getattr(job, "gates", False)) and enabled(pipe.settings, d)


def may_prove(settings, d: Dossier) -> bool:
    """Searches started beside the pipeline (plans, reasoned search): only on a statement the user approved."""
    return not enabled(settings, d) or approved_statement(d) or d.proof_is_current


def pending(d: Dossier, kind: str = "") -> dict | None:
    g = d.extra.get("gate")
    if isinstance(g, dict) and g.get("state") == "pending" and (not kind or g.get("kind") == kind):
        return g
    return None


def approved_statement(d: Dossier) -> bool:
    """The current statement was approved by the user (the approval belongs to this exact text)."""
    if not 0 <= d.cur_statement < len(d.statements):
        return False
    v = d.statements[d.cur_statement]
    return v.meta.get("approved") == v.code_key()


def approve_statement(d: Dossier, by: str = "user") -> None:
    v = d.statements[d.cur_statement]
    v.meta["approved"] = v.code_key()
    v.meta["approved_by"] = by


async def open_gate(pipe, d: Dossier, job, kind: str, payload: dict, rest: list[dict]) -> dict:
    """Put the gate, keep the rest of the plan, end the job."""
    prev = d.extra.get("gate") if isinstance(d.extra.get("gate"), dict) else {}
    g = {"id": "g-" + uuid.uuid4().hex[:10], "kind": kind, "state": "pending",
         "version": int(prev.get("version", 0) or 0) + 1, "t": time.time(), **payload}
    d.extra["gate"] = g
    d.extra["gate_plan"] = {"gate": g["id"], "plan": [dict(p) for p in rest], "run": job.run, "mode": job.mode,
                            "strategy": job.strategy}
    job.plan = []
    d.status = "draft"
    key = ("Vérifiez que le problème est bien compris avant la traduction en Lean." if kind == "meaning" else
           "Vérifiez l'énoncé Lean avant la recherche de preuve.")
    job.summary = msg("En attente de votre validation.")
    await pipe.event(d, job, "info", key, gate=g["id"], gate_kind=kind)
    return g


DECISIONS = {("meaning", "approve"): "Sens validé.", ("statement", "approve"): "Énoncé Lean validé.",
             ("meaning", "edit"): "Sens corrigé : il est relu.",
             ("statement", "edit"): "Énoncé Lean corrigé : il est refait.",
             ("meaning", "reject"): "Sens refusé : il est relu.",
             ("statement", "reject"): "Énoncé Lean refusé : il est refait."}


def decided(d: Dossier, g: dict, action: str, run: str = "") -> None:
    """Every decision of the user is in the thread (event kind « gate »)."""
    g["state"] = "approved" if action == "approve" else "rejected"
    m = msg(DECISIONS[(g["kind"], action)])
    d.add_event("gate", m["text"], key=m["key"], params={"gate_kind": g["kind"], "action": action, "gate": g["id"]},
                phase="understand" if g["kind"] == "meaning" else "translate", attempt=0,
                run=run or (d.extra.get("gate_plan") or {}).get("run", ""))


def drop(d: Dossier) -> None:
    """The gate is about something that no longer exists (statement edited, version restored…)."""
    d.extra.pop("gate", None)
    d.extra.pop("gate_plan", None)


class GateError(Exception):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code, self.status = code, status


def _candidate(g: dict, version) -> dict:
    cands = (g.get("statement") or {}).get("candidates") or []
    want = (g.get("statement") or {}).get("chosen") if version is None else version
    c = next((c for c in cands if c.get("version") == want), None)
    if c is None:
        raise GateError("bad_candidate", 400)
    return c


def decide(ctx, d: Dossier, gate_id: str, action: str, text: str = "", candidate=None) -> list[dict]:
    """Synchronous (no await): the first answer wins. Returns the plan to run."""
    g = pending(d)
    if g is None or g["id"] != gate_id:
        raise GateError("stale_gate")
    rest = [dict(p) for p in (d.extra.get("gate_plan") or {}).get("plan") or []]
    if action == "approve":
        if g["kind"] == "meaning":
            d.extra["meaning"] = dict(g.get("meaning") or {})
            plan = rest or [{"stage": "statement"}, {"stage": "proof"}, {"stage": "explanation"}]
            for p in plan:
                if p["stage"] == "statement":
                    p["meaning_ok"] = True
        else:
            c = _candidate(g, candidate)
            if c.get("verdict") == "refused" and c.get("hard"):
                raise GateError("refused_statement")
            # by text: the history's compaction may have moved the index (the gate keeps the code it showed)
            i = next((i for i in range(len(d.statements) - 1, -1, -1) if d.statements[i].code == c["code"]), -1)
            if i < 0:
                i = d.add_statement(c["code"], model=c.get("model", ""))
            d.cur_statement = i
            g["statement"]["chosen"] = c["version"]
            approve_statement(d)
            plan = rest or [{"stage": "proof"}, {"stage": "explanation"}]
    else:
        req = text.strip()[:4000]
        if g["kind"] == "meaning":
            plan = [{"stage": "understand", "request": req}] + (rest or [
                {"stage": "statement"}, {"stage": "proof"}, {"stage": "explanation"}])
        else:
            try:
                code = leancheck.prepare_statement(req) if action == "edit" and "theorem" in req else ""
            except leancheck.StatementError:
                code = ""
            tail = [p for p in rest if p.get("stage") != "statement"] or [{"stage": "proof"}, {"stage": "explanation"}]
            if code:                         # the user wrote the Lean statement: read back to him, then proved
                old = leancheck.theorem_name(code)
                d.add_statement(code, source="user")
                d.theorem = old or d.theorem
                plan = tail
            else:
                _refuse(d, (g.get("statement") or {}).get("candidates") or [])
                plan = [{"stage": "statement", "request": req, "meaning_ok": True}] + tail
    decided(d, g, action)
    if d.extra.get("gate_plan"):
        d.extra["gate_plan"]["plan"] = []
    d.touch()
    return plan


def _refuse(d: Dossier, candidates: list[dict]) -> None:
    from ..research.proofgraph import statement_key
    ref = d.extra.setdefault("refused", [])
    for c in candidates:
        k = statement_key(c.get("code", ""))
        if k and k not in ref:
            ref.append(k)
    del ref[:-20]


def submit(ctx, d: Dossier, plan: list[dict], run: str = "", **opts):
    gp = d.extra.get("gate_plan") or {}
    if "mode" not in opts and gp.get("mode"):
        opts["mode"] = gp["mode"]
    if "strategy" not in opts and gp.get("strategy"):
        opts["strategy"] = gp["strategy"]
    return ctx.orchestrator.submit(d.id, plan, run=run or gp.get("run", ""), **opts)


def force(d: Dossier) -> None:
    """« Prouver quand même »: the explicit approval of the current statement."""
    if d.statement:
        approve_statement(d, "force")
    g = pending(d, "statement")
    if g is not None:
        decided(d, g, "approve")


# ---------------------------------------------------------------- meaning gate
async def meaning_gate(pipe, job, d: Dossier, meaning: dict, rest: list[dict]) -> None:
    """Status from the literature (bounded, never blocking), known results as sub-dossiers, then the gate."""
    items = await _literature(pipe, job, d, meaning)
    meaning.update(F.status_of(meaning, items))
    F.source_known(meaning, items)
    old = {k["statement"]: k.get("dossier_id", "") for k in ((d.extra.get("meaning") or {}).get("known_results") or [])}
    for k in meaning["known_results"]:
        if old.get(k["statement"]):
            k["dossier_id"] = old[k["statement"]]
    d.extra.pop("meaning", None)
    if meaning["known_status"] in ("open", "false", "unclear"):
        await status_event(pipe, job, d, meaning)
    if meaning["known_status"] in ("open", "false") or (meaning["known_status"] == "unclear" and meaning["known_results"]):
        await launch_known(pipe, job, d, meaning)
    else:
        meaning["known_results"] = []
    await open_gate(pipe, d, job, "meaning", {"meaning": meaning}, rest)


async def status_event(pipe, job, d: Dossier, meaning: dict) -> None:
    key = {"open": "D'après ce qui a été trouvé, ce problème est ouvert : personne n'en connaît de preuve.",
           "false": "D'après ce qui a été trouvé, l'énoncé est faux tel quel.",
           "unclear": "Le statut de ce problème n'est pas clair."}[meaning["known_status"]] \
        if meaning["status_confidence"] == "cited" else \
        {"open": "Problème ouvert, d'après un modèle, à vérifier.",
         "false": "Énoncé faux, d'après un modèle, à vérifier.",
         "unclear": "Statut incertain, d'après un modèle, à vérifier."}[meaning["known_status"]]
    await pipe.event(d, job, "status", key, detail="\n".join(
        f"> « {s['quote']} » — {s['title']} {s['url']}" for s in meaning["status_sources"]),
        status=meaning["known_status"], confidence=meaning["status_confidence"])


async def _literature(pipe, job, d: Dossier, meaning: dict) -> list:
    from . import literature_hook
    if not literature_hook.enabled(pipe, job, d, None):
        return []
    from .. import literature
    budget = literature.Budget.for_depth("quick")
    try:
        ws = pipe.ctx.workspace(d.workspace or pipe.settings.workspace)
        res = await asyncio.wait_for(literature.search(
            "", pipe.ctx, budget, text=" ".join([meaning.get("claim") or "", meaning.get("restated") or d.problem]),
            names=meaning.get("names") or [], mode=job.mode, project_id=d.project_id, ws=ws, formalize=False,
            owner=f"{job.id}#status", lang=language()), STATUS_SECONDS)
        return list(res.items)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 (no status check: « unknown » or the model's word, never a stop)
        log.info("status search of %s: %s", job.id, e)
        return []


async def launch_known(pipe, job, d: Dossier, meaning: dict) -> None:
    """Known results → sub-dossiers, run up to their own statement gate. Deduplicated by their words."""
    if d.extra.get("known_result"):
        return                               # a known result never opens known results (no recursion)
    ctx = pipe.ctx
    kids = [c for c in ctx.repo.children(d.id) if c.extra.get("known_result")]
    for k in meaning["known_results"]:
        if k.get("dossier_id") and ctx.repo.get(k["dossier_id"]) is not None:
            continue
        twin = next((c for c in kids if F.same_words(c.problem, k["statement"])), None)
        if twin is not None:
            k["dossier_id"] = twin.id
            continue
        if len(kids) >= F.MAX_KNOWN:
            continue
        c = ctx.repo.new(k["statement"], d.workspace, k["title"][:200])
        c.project_id, c.parent_id = d.project_id, d.id
        c.understood = c.understood_display = k["statement"]
        c.extra["known_result"] = {"dossier": d.id, "id": k["id"], "source": k.get("source")}
        c.extra["meaning"] = {"restated": k["statement"], "objects": [], "hypotheses": [], "claim": k["statement"],
                              "known_status": "known", "status_sources": [k["source"]] if k.get("source") else [],
                              "status_confidence": "cited" if k.get("source") else "model_only",
                              "known_results": [], "questions": [], "names": []}
        m = msg("Résultat connu, ouvert depuis « {title} ».", title=d.title)
        c.add_event("info", m["text"], key=m["key"], params=m["params"])
        await ctx.repo.save(c)
        kids.append(c)
        k["dossier_id"] = c.id
        ctx.orchestrator.submit(c.id, [{"stage": "statement", "meaning_ok": True}, {"stage": "proof"},
                                       {"stage": "explanation"}], mode=job.mode, user=False, gates=True)


# ---------------------------------------------------------------- statement gate
async def evaluate(pipe, job, d: Dossier, io, ws, code: str, model: str, version: int) -> dict:
    """One candidate as the gate shows it: deterministic refusals, Lean refusals, then a blind reading."""
    meaning = d.extra.get("meaning") or {}
    words = request_words(d)
    r = F.refusals(code, meaning, words)
    notes: list[str] = []
    if pipe._lean_real() and not r["hard"]:
        hard, notes = await F.lean_refusals(io, ws, code, meaning.get("known_status", ""))
        r["hard"] += hard
    back, reader = "", ""
    if pipe.has_model("understand", job.mode):
        try:
            c = await asyncio.wait_for(pipe._short(io, "understand", F.back_messages(code, language()), 0.2, 900), 120)
            back, reader = leancheck.clean_model_text(c.text).strip()[:3000], c.model.key
        except Exception as e:  # noqa: BLE001 (no reading: the candidate is shown without it)
            log.info("back-translation: %s", e)
    missing = list(dict.fromkeys(r["missing"] + F.back_missing(back, meaning, words)))
    reasons = r["hard"] + r["soft"]
    if set(missing) - set(r["missing"]):
        reasons.append(msg("La relecture de l'énoncé (sans voir le problème) ne mentionne pas : {names}.",
                           names=", ".join(x for x in missing if x not in r["missing"]))["text"])
    verdict = "refused" if r["hard"] or r["soft"] else "doubtful" if missing else "ok"
    return {"version": version, "code": code, "back_translation": back, "back_model": reader, "model": model,
            "objects_missing": missing, "verdict": verdict, "reasons": reasons + notes, "hard": bool(r["hard"])}


def request_words(d: Dossier) -> str:
    """What the user asked: the problem's words and the change he asked for since (never a suggested fix nobody chose)."""
    return " ".join([d.problem] + [str(x) for x in d.extra.get("asked") or []]).strip()


def merge_check(c: dict, chk: dict | None) -> None:
    """The existing statement check (S-K) of this candidate, in the gate's vocabulary."""
    if not chk or chk.get("verdict") not in ("doubtful", "false"):
        return
    if c["verdict"] != "refused":
        c["verdict"] = chk["verdict"]
    c["reasons"] += [i["explanation"] for i in chk.get("issues") or [] if i.get("explanation")][:4]
    if chk.get("verdict") == "false":
        c["reasons"].insert(0, msg("Lean prouve le contraire de cet énoncé.")["text"])


async def statement_gate(pipe, job, d: Dossier, io, ws, cands: list[dict], agree: str, rest: list[dict]) -> None:
    good = [c for c in cands if c["verdict"] != "refused"] or cands
    chosen = good[0]
    d.cur_statement = next((i for i in range(len(d.statements) - 1, -1, -1)
                            if d.statements[i].code == chosen["code"]), d.cur_statement)
    if pipe.settings.statement_check and not chosen["hard"]:
        chk = pipe._check_of(d) or await pipe._cached_check(job, d, ws)
        if chk is None:
            try:
                r = await pipe._run_check(job, d, io, stop_plan=False)
                chk = r.to_dict() if r is not None else None
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("statement check before the gate failed: %s", e)
        merge_check(chosen, chk)
    await open_gate(pipe, d, job, "statement", {
        "meaning": d.extra.get("meaning") or None,
        "statement": {"candidates": cands, "chosen": chosen["version"], "agreement": agree}}, rest)


# ---------------------------------------------------------------- « Mal compris »
REASONS = ("wrong_object", "too_general", "missing_hypothesis", "wrong_claim", "ignored_request", "other")
TARGETS = ("meaning", "statement", "proof", "event")


def target_of_event(d: Dossier, ref) -> str:
    ev = d.events[ref] if isinstance(ref, int) and not isinstance(ref, bool) and 0 <= ref < len(d.events) else None
    if ev is None:
        raise GateError("bad_ref", 400)
    if ev.phase == "understand" or ev.kind in ("understood", "status"):
        return "meaning"
    if ev.phase in ("prove", "verify", "explain", "literature", "decompose"):
        return "proof"
    return "statement"


def reason_text(reason: str) -> str:
    return msg({"wrong_object": "ce n'est pas le bon objet", "too_general": "c'est trop général",
                "missing_hypothesis": "il manque une hypothèse", "wrong_claim": "ce n'est pas ce qui est affirmé",
                "ignored_request": "une demande a été ignorée", "other": "autre raison"}[reason])["text"]


def check_ref(d: Dossier, target: str, ref) -> None:
    """`ref`: the version index of a statement / a proof (an event's index for « event », checked elsewhere)."""
    seq = {"statement": d.statements, "proof": d.proofs}.get(target)
    if ref is not None and seq is not None and not (isinstance(ref, int) and not isinstance(ref, bool)
                                                    and 0 <= ref < len(seq)):
        raise GateError("bad_ref", 400)


def report_plan(d: Dossier, target: str, reason: str, text: str, ref: int | None = None) -> list[dict]:
    """Marks what depends on the reported part as rejected and returns the plan that redoes it."""
    req = (reason_text(reason) + (" : " + text if text else "")).strip()
    g = pending(d)
    if g is not None:
        g["state"] = "rejected"
    if target == "proof" and d.statement:
        return [{"stage": "proof", "request": req}, {"stage": "explanation"}]
    chain = [{"stage": "proof"}, {"stage": "explanation"}]
    if target in ("statement", "proof") and (d.extra.get("meaning") or d.understood):
        if d.statement:
            v = d.statements[d.cur_statement if ref is None else ref]
            _refuse(d, [{"code": v.code}])
            v.meta.pop("approved", None)
        return [{"stage": "statement", "request": req, "meaning_ok": True}] + chain
    d.extra.pop("meaning", None)
    return [{"stage": "understand", "request": req}, {"stage": "statement"}] + chain


def record_report(d: Dossier, entry: dict) -> None:
    reps = d.extra.setdefault("reports", [])
    reps.append(entry)
    del reps[:-MAX_REPORTS]
