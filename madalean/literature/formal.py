"""Cited results in Lean: formalization of a verbatim quote, Mathlib / library check, conditional proofs.

- **Formalization**: the verified quote (never a model's paraphrase) goes to the usual formalizer (Goedel prompt,
  Lean check of the statement, D39/D45 catalogue unchanged) through `LitIO`: free online models only, within the
  search budget. The Lean statement is a *translation by a model*: shown « à relire », never as the paper's text.
- **Status**: `in_mathlib` when a Mathlib name closes it under the strict verdict (`MathlibFirst` without a model:
  templates on the index candidates, then `exact?`), `proved` when the library already holds it, else `to_prove`.
- **Conditional proof**: the dossier's theorem with the cited lemmas stated before it with `sorry` (the
  « admitted lemma » form of proof plans, research/proofplan.py). Lean checks the implication; the strict verdict
  ALWAYS rejects such a file (`sorry`, axiom `sorryAx`), so it can never become « vérifiée »: it is recorded in
  `dossier.extra["conditional_proof"]` (`verdict: "proved_modulo"`, `source: "literature"`), shown as « preuve
  conditionnelle : repose sur [réf.] » everywhere, and never enters `dossier.proofs` or the library. When every
  cited lemma has a real Lean proof in the library, `upgrade` substitutes the proofs and runs the strict check:
  only then the proof is recorded, as any verified proof."""
from __future__ import annotations

import asyncio
import re
import time
from types import SimpleNamespace

from .. import leancheck
from ..brain.api import BrainError
from ..i18n import msg
from ..logs import get
from .types import Budget, LiteratureItem

log = get("literature")

CHECK_TIMEOUT = 90
CONDITIONAL_TACTICS = [
    "exact {n}", "exact {n} _", "exact {n} _ _", "simpa using {n}", "exact?",
    "apply {n}\nall_goals first | assumption | omega | norm_num | positivity",
    "intros\napply {n}\nall_goals first | assumption | omega | norm_num | positivity",
    "intro n hn\nexact {n} n hn", "intro n\nexact {n} n",
]
MAX_COND_TRIES = 3                   # strict re-checks after the batch of short tactics


def cited_name(item: LiteratureItem) -> str:
    """A Lean identifier unique to the reference: `cited_<firstauthor>_<year>_<hash>`."""
    who = ""
    if item.reference.authors:
        who = re.sub(r"[^a-z]", "", item.reference.authors[0].split()[-1].lower())[:16]
    year = str(item.reference.year or "")
    base = "_".join(x for x in ("cited", who, year) if x)
    return f"{base}_{item.id[-6:].lower()}"


class LitIO:
    """The small `StageIO` the formalizer / Mathlib search need, outside a job's attempt list: free online models
    only (`only=` pinned, paid answers dropped), every model call and Lean check counted in the budget."""

    def __init__(self, ctx, mode: str, budget: Budget, owner: str = "literature", warm: bool = False):
        self.ctx, self.mode, self.budget, self.owner, self.warm = ctx, mode, budget, owner, warm
        self.models: list[str] = []

    def new_attempt(self, stage: str, kind: str):
        return SimpleNamespace(stage=stage, kind=kind, status="", summary="", errors_text="", raw="", model="",
                               finish="", gen_seconds=0.0, tokens=0, code="", compile_seconds=0.0)

    def update_attempt(self, a) -> None:
        return None

    def drop_attempt(self, a) -> None:
        return None

    def free_models(self, role: str) -> list:
        if self.mode == "local":
            return []
        try:
            return [c for c in self.ctx.brain.candidates(role, self.mode) if not c.paid and not c.local]
        except Exception:  # noqa: BLE001
            return []

    async def complete(self, role: str, messages: list[dict], attempt=None, *, temperature=None, max_tokens=None,
                       extra=None, mode=None, stage="", only=None, prefer=None, **_kw):
        cands = self.free_models(role)
        if not cands:
            raise BrainError("no_model", "no free online model for the literature search")
        if not self.budget.take("model"):
            raise BrainError("no_model", "literature budget: no model call left")
        last: Exception | None = None
        for c in cands[:2]:
            left = self.budget.left()
            if left < 3:
                break
            try:
                res = await asyncio.wait_for(self.ctx.brain.complete(
                    role, messages, mode=self.mode, temperature=temperature, max_tokens=min(max_tokens or 2000, 6000),
                    extra=extra, only=c.key), left)
            except (BrainError, asyncio.TimeoutError) as e:
                last = e
                continue
            if getattr(res.model, "paid", False):
                continue                               # belt and braces: `only` pinned a free model
            self.models.append(res.model.key)
            return res
        raise BrainError("no_model", str(last or "no answer"))

    async def check(self, code: str, ws, timeout_s: int, strict_name: str | None):
        from ..runtime.lean import CompileResult
        if not self.budget.take("lean"):
            v = leancheck.Verdict(False, "budget")
            return CompileResult(v, code, 0.0, "", infra_error="literature budget: no Lean check left")
        t = max(10, min(int(timeout_s), CHECK_TIMEOUT, int(self.budget.left()) + 5))
        return await self.ctx.lean.check(code, ws, t, strict_name, owner=self.owner, warm=self.warm)


def formalize_input(item: LiteratureItem) -> str:
    q = item.quotes[0]
    return (f"{q.text}\n\n(Result quoted verbatim from: {item.reference.title}, {item.reference.short()}. State "
            "exactly this result, with all its hypotheses; do not prove it.)")


async def formalize(io: LitIO, item: LiteratureItem, ws, timeout_s: int) -> None:
    """Fill `item.lean` (statement, compiled, model, note). Never raises."""
    from ..pipeline.goedel import Formalizer
    from ..pipeline.io import InfraError
    name = cited_name(item)
    item.lean.name = name
    if not item.quotes:
        item.lean.note = "no_quote"
        return
    if any(item.texts[q.text_index].suspect for q in item.quotes[:1]):
        item.lean.note = "suspect_text"            # a text that addresses a model is never sent to one
        return
    try:
        f = await Formalizer(io, io.mode).run(formalize_input(item), ws, 1, timeout_s, name=name)
    except (BrainError, InfraError) as e:
        item.lean.note = "no_model" if "model" in str(e).lower() or getattr(e, "kind", "") == "no_model" else "error"
        return
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        log.warning("formalization of %s failed: %s", item.id, e)
        item.lean.note = "error"
        return
    item.lean.model = f.model
    if f.statement and f.ok:
        st = f.statement
        try:
            if leancheck.theorem_name(st) != name:
                st = re.sub(rf"\btheorem\s+{re.escape(leancheck.theorem_name(st))}\b", f"theorem {name}", st, count=1)
        except leancheck.StatementError:
            item.lean.note = "lean_refused"
            return
        item.lean.statement, item.lean.compiled, item.lean.status = st, True, "to_prove"
    else:
        item.lean.note = "lean_refused" if f.statement else "no_statement"


async def mathlib_status(ctx, io: LitIO, item: LiteratureItem, ws, timeout_s: int) -> None:
    """`in_mathlib` (with the Mathlib name) or `proved` (library) for a compiled cited statement."""
    if not item.lean.compiled:
        return
    sig = _signature(item.lean.statement)
    lib = getattr(ctx, "library", None)
    for e in getattr(lib, "entries", []) or []:
        if e.workspace == ws.key and sig and _norm(e.statement) == sig:
            item.lean.status, item.lean.library_name = "proved", e.name
            return
    if io.budget.over:
        return
    from ..pipeline.mathlib_first import MathlibFirst
    try:
        mf = MathlibFirst(io, io.mode, getattr(ctx, "retriever", None), lean_real=_lean_real(ctx), use_model=False)
        texts = [item.quotes[0].text] if item.quotes and not item.texts[item.quotes[0].text_index].suspect else []
        res = await asyncio.wait_for(mf.run(item.lean.statement, ws, texts, timeout_s), max(5.0, io.budget.left()))
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 (timeout, budget: the status stays « à prouver »)
        log.info("mathlib check of %s: %s", item.id, e)
        return
    if res.ok:
        item.lean.status = "in_mathlib"
        item.lean.mathlib_name = res.lemma or res.tactic


def _lean_real(ctx) -> bool:
    from ..brain.fake import FakeLean
    return not isinstance(getattr(ctx, "lean", None), FakeLean)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _signature(statement: str) -> str:
    """`binders : type` of the target theorem (name removed), white space normalised."""
    try:
        body = leancheck.remove_comments(statement)
        name = leancheck.theorem_name(body)
    except leancheck.StatementError:
        return ""
    m = re.search(rf"\btheorem\s+{re.escape(name)}\b(.*?):=\s*by\s+sorry", body, re.S)
    return _norm(m.group(1)) if m else ""


# ---------------------------------------------------------------- conditional proofs
def admitted_block(items: list[LiteratureItem]) -> str:
    """The cited lemmas as Lean declarations stated with `sorry` (each with its citation in a comment)."""
    out = []
    for it in items:
        body = _decl_only(it.lean.statement)
        if not body:
            continue
        ref = re.sub(r"[\n\r]", " ", f"{it.reference.short()} — {it.reference.title}")[:200]
        out.append(f"-- cited, not proved in Lean: {ref}\n{body}")
    return "\n\n".join(out)


def _decl_only(statement: str) -> str:
    """The `theorem … := by sorry` declaration of a cited statement, without its header (imports / open)."""
    src = statement or ""
    m = list(re.finditer(r"(?m)^\s*theorem\b", src))
    if not m:
        return ""
    return src[m[-1].start():].strip()


def conditional_statement(goal_statement: str, items: list[LiteratureItem]) -> str:
    """The dossier's statement with the cited lemmas inserted just before its theorem."""
    st = leancheck.prepare_statement(goal_statement)
    starts = [m.start() for m in re.finditer(r"(?m)^theorem\s", st)]
    block = admitted_block(items)
    if not starts or not block:
        return st
    cut = starts[-1]
    return st[:cut] + block + "\n\n" + st[cut:]


async def check_conditional(ctx, code: str, name: str, ws, admitted: list[str], owner: str = "literature") -> dict:
    """ok = Lean accepts the file, the target's own proof uses no forbidden construct, and its axioms are the
    standard ones plus `sorryAx` from the admitted lemmas. `strict_ok` (the real verdict) is computed too: it is
    False whenever a cited lemma is involved."""
    r = await ctx.lean.check(leancheck.with_axiom_probe(code, name), ws, getattr(ctx.settings, "compile_timeout_s",
                                                                                180), None, owner=owner)
    msgs = leancheck.parse_lean_json(r.stdout) if r.stdout else []
    strict = leancheck.judge(leancheck.with_axiom_probe(code, name), msgs or r.verdict.errors, name, 0)
    d = r.to_dict()
    if d["errors"] or d["timed_out"] or d["infra_error"]:
        return {"ok": False, "why": "; ".join(e["text"][:200] for e in d["errors"][:3]) or d["infra_error"]
                or "timeout", "strict_ok": False, "axioms": None}
    target = leancheck.remove_comments(code)
    target = target[target.rfind(f"theorem {name}"):]
    if leancheck.forbidden_reasons(target):
        return {"ok": False, "why": "forbidden: " + ", ".join(leancheck.forbidden_reasons(target)),
                "strict_ok": False, "axioms": strict.axioms}
    axioms = strict.axioms
    if axioms is None:
        return {"ok": False, "why": "axioms unknown", "strict_ok": False, "axioms": None}
    bad = [a for a in axioms if a not in leancheck.ALLOWED_AXIOMS | {"sorryAx"}]
    if bad:
        return {"ok": False, "why": "axioms: " + ", ".join(bad), "strict_ok": False, "axioms": axioms}
    return {"ok": True, "axioms": axioms, "strict_ok": strict.ok, "uses_cited": "sorryAx" in axioms}


def verdict_of(check: dict) -> str:
    """« vérifiée » only for a strict acceptance without `sorryAx`; a proof through a cited lemma is conditional."""
    if not check.get("ok"):
        return "rejected"
    if check.get("strict_ok") and "sorryAx" not in (check.get("axioms") or []):
        return "verified"
    return "conditional"


async def try_conditional(ctx, io: "LitIO", goal_statement: str, items: list[LiteratureItem], ws,
                          owner: str = "literature") -> dict | None:
    """Short tactics through each cited lemma (no model), all in ONE Lean file (probes); the first one that closes
    the goal is re-checked alone (`check_conditional`) and must really go through a cited lemma (`sorryAx`).
    → {code, theorem, admitted, axioms, cited, tactic} or None."""
    from ..pipeline import probes as P
    usable = [it for it in items if it.is_cited_lemma]
    if not usable or io.budget.over:
        return None
    try:
        statement = conditional_statement(goal_statement, usable)
        name = leancheck.theorem_name(statement)
    except leancheck.StatementError:
        return None
    sig = P.split_statement(statement)
    if sig is None:
        return None
    head = f"{sig.binders} : {sig.concl}"
    probes: list = []
    for i, it in enumerate(usable):
        for j, tpl in enumerate(CONDITIONAL_TACTICS):
            tac = tpl.format(n=it.lean.name)
            if "?" in tac:
                continue                                # `exact?` is never part of a recorded proof (D28)
            probes.append(P.Probe(f"madalean_cond_{i}_{j}", P.decl(f"madalean_cond_{i}_{j}", head, tac, 40000),
                                  "cond", {"tactic": tac, "item": it}))
    try:
        await P.run_batch(io, ws, sig.preamble, probes, CHECK_TIMEOUT)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        log.info("conditional batch failed: %s", e)
        return None
    names = [it.lean.name for it in usable]
    for p in [p for p in probes if p.ok][:MAX_COND_TRIES]:
        if not io.budget.take("lean"):
            return None
        tac = p.meta["tactic"]
        body = "\n".join("  " + ln for ln in tac.split("\n"))
        try:
            code = leancheck.assemble_proof(statement, f"theorem {name} := by\n{body}")
        except leancheck.StatementError:
            continue
        res = await check_conditional(ctx, code, name, ws, names, owner)
        if res["ok"] and res.get("uses_cited"):
            used = [x for x in usable if re.search(rf"(?<![\w.']){re.escape(x.lean.name)}(?![\w'])", tac)]
            return {"code": code, "theorem": name, "admitted": [x.lean.name for x in used],
                    "axioms": res["axioms"], "tactic": tac, "cited": [_cite(x) for x in used]}
    return None


def _cite(it: LiteratureItem) -> dict:
    q = it.quotes[0] if it.quotes else None
    return {"name": it.lean.name, "item": it.id, "ref": it.reference.id, "title": it.reference.title,
            "short": it.reference.short(), "kind": it.reference.kind, "peer_reviewed": it.reference.peer_reviewed,
            "quote": q.text if q else "", "location": q.location if q else ""}


def record_conditional(d, found: dict, ws_key: str) -> bool:
    """Store a conditional proof on the dossier (never in `proofs`). A proof-plan conditional proof is kept as is."""
    cur = d.extra.get("conditional_proof")
    if isinstance(cur, dict) and cur.get("verdict") == "proved_modulo" and cur.get("source") != "literature":
        return False
    if d.proof_is_current:
        return False
    d.extra["conditional_proof"] = {
        "verdict": "proved_modulo", "source": "literature", "admitted": found["admitted"], "cited": found["cited"],
        "code": found["code"], "theorem": found["theorem"], "axioms": found["axioms"], "strict_ok": False,
        "tactic": found.get("tactic", ""), "checked": time.time(), "workspace": ws_key,
        "statement_index": d.cur_statement}
    refs = ", ".join(c["short"] for c in found["cited"])
    m = msg("Preuve conditionnelle : repose sur {refs} (résultat cité, non prouvé en Lean). Ce n'est PAS une preuve "
            "vérifiée.", refs=refs)
    d.add_event("info", m["text"], key=m["key"], params=m["params"])
    return True


def supersede(d) -> bool:
    """A verified proof exists now: the literature conditional proof is history."""
    cur = d.extra.get("conditional_proof")
    if isinstance(cur, dict) and cur.get("source") == "literature" and cur.get("verdict") == "proved_modulo" \
            and d.proof_is_current:
        cur["verdict"], cur["superseded"] = "superseded", time.time()
        return True
    return False


async def upgrade(ctx, d) -> dict:
    """Every cited lemma of the conditional proof has a library proof → substitute and judge STRICTLY; only an
    acceptance makes it the dossier's proof (« vérifiée »)."""
    cond = d.extra.get("conditional_proof")
    if not isinstance(cond, dict) or cond.get("source") != "literature" or cond.get("verdict") != "proved_modulo":
        return {"upgraded": False, "reason": "nothing"}
    if d.proof_is_current:
        supersede(d)
        await ctx.repo.save(d)
        return {"upgraded": False, "reason": "already_proved"}
    lib = ctx.library
    real = {nm: lib.get(nm) for nm in cond.get("admitted") or []}
    missing = [k for k, e in real.items() if e is None]
    if missing or not real:
        return {"upgraded": False, "reason": "cited_unproved", "missing": missing}
    code = re.sub(r"(?m)^-- cited, not proved in Lean:[^\n]*\n", "", cond["code"])
    for nm, e in real.items():
        pat = re.compile(rf"(?ms)^theorem\s+{re.escape(nm)}\b.*?:=\s*by\s+sorry\s*$")
        code = pat.sub(lambda _m, c=e.code: c.strip(), code, count=1)
    ws = ctx.workspace(cond.get("workspace") or d.workspace)
    if ws is None:
        return {"upgraded": False, "reason": "no_workspace"}
    name = cond["theorem"]
    r = await ctx.lean.check(leancheck.with_axiom_probe(code, name), ws, ctx.settings.compile_timeout_s, name,
                             owner=f"lit-up-{d.id}")
    if not r.verdict.ok:
        cond["upgrade_failed"] = {"t": time.time(), "summary": r.verdict.summary}
        await ctx.repo.save(d)
        return {"upgraded": False, "reason": "strict_rejected", "summary": r.verdict.summary}
    from ..runtime.lean import workspace_info
    info = workspace_info(ws)
    meta = {"axioms": r.verdict.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
            "workspace": ws.key, "seconds": round(r.seconds, 1), "strategy": "literature", "attempts": 1,
            "checked": time.time(), "cited": cond.get("cited", [])}
    idx = d.add_proof(code, note="literature: cited lemmas now proved in Lean", meta=meta)
    d.status = "proved"
    cond["verdict"], cond["upgraded"] = "superseded", time.time()
    m = msg("Les résultats cités sont maintenant prouvés en Lean : la preuve est vérifiée (verdict strict).")
    d.add_event("proof", m["text"], ref=idx, key=m["key"])
    await ctx.repo.save(d)
    entry = await asyncio.to_thread(lib.add_proof, code, d.title, ws.key, d.id, list(real))
    if entry:
        ctx.publish("library.updated", {"added": entry.name})
    return {"upgraded": True, "proof": idx}
