"""The conductor inside a dossier job (session S-AI, DECISIONS D41) — a contained hook of `runner.DossierPipeline`.

The runner calls, in this order:
    hook = conductor_hook.attach(pipeline, job, d, io)   # NullHook when no conductor can run: nothing changes
    await hook.start()                  # the plan is written beside the first stage (never delays it)
    await hook.before_stage(stage)      # statement / proof wait (bounded) for the plan's model choices and hints
    hook.prefer(role) / hook.cards(role, messages) / hook.hint(kind) / hook.lead(contestants)
    await hook.after_stage(stage)       # Lean rejected the statement → the conductor corrects it (≤ 3 tries)
    await hook.recover(stage, failed)   # no proof found → the conductor corrects the closest attempt (≤ 3 tries)
    await hook.finish()                 # final coherence check statement ↔ proof ↔ explanation
    await hook.close()                  # always (finally): cancels the plan task, drops the request's cap

Everything the hook does is bounded, never raises into the pipeline (except cancellation), and every proof or
statement it proposes is judged by Lean exactly like the others (strict verdict, D28 gate). Its state for the UI is
`job.conductor`: who directs, the request's cost so far and cap, the plan with the model of each step, the pending
cap question."""
from __future__ import annotations

import asyncio
import time

from .. import leancheck
from ..brain import conductor as cmod
from ..brain import spend, toolcards
from ..i18n import language, msg
from ..logs import get

log = get("conductor")
PLAN_WAIT = 25.0               # the statement / proof stage waits at most this long for the plan
PLAN_DEADLINE = 60.0           # the planning decision itself (whole fallback chain)
ASK_TIMEOUT = 600.0            # unanswered cap question: go on without Claude
MAX_FIX = 3                    # corrections per failure (Sonnet, Sonnet, then Opus)
ASKS: dict[str, "Hook"] = {}   # job id → hook waiting for the user's answer to the cap question
ROLE_KINDS = {"understand": "understand", "formalize": "formalize", "explain": "explain", "prove": "prove"}


def answer(job_id: str, approve: bool) -> bool:
    """The user's answer to « Plafond atteint : continuer avec Claude (+0,50 $) ? » (POST /api/jobs/{id}/conductor)."""
    h = ASKS.get(job_id)
    if h is None or h._ask_event is None:                                 # noqa: SLF001
        return False
    h._answer = bool(approve)                                             # noqa: SLF001
    h._ask_event.set()                                                    # noqa: SLF001
    return True


class NullHook:
    active = False

    async def start(self) -> None: ...
    async def before_stage(self, stage: str) -> None: ...
    async def after_stage(self, stage: str) -> None: ...
    async def recover(self, stage: str, failed) -> bool: return False
    async def finish(self) -> None: ...
    async def close(self) -> None: ...
    def prefer(self, role: str) -> str | None: return None
    def hint(self, kind: str) -> str: return ""
    def lead(self, contestants: list) -> list: return contestants
    def cards(self, role: str, messages: list[dict]) -> list[dict]: return messages


def hook_of(job) -> "Hook | NullHook":
    return getattr(job, "conductor_hook", None) or NullHook()


def attach(pipeline, job, d, io) -> "Hook | NullHook":
    """A hook for this job when a conductor can run (setting on, not local, a real brain), else NullHook."""
    try:
        ctx = pipeline.ctx
        if not getattr(pipeline.settings, "conductor", True) or job.mode == "local":
            return NullHook()
        c = cmod.conductor_of(ctx.brain)
        if c is None or not c.enabled(job.mode):
            return NullHook()
        stages = {p.get("stage") for p in job.plan}
        if not stages & {"understand", "statement", "proof", "route", "explanation"}:
            return NullHook()
        if not c.claude_models(job.mode) and not c.free_conductors(job.mode):
            return NullHook()                    # no capable conductor: the pipeline runs exactly as before
        h = Hook(pipeline, job, d, io, c)
    except Exception:  # noqa: BLE001 (the conductor never prevents a job from running)
        log.exception("conductor not attached to job %s", getattr(job, "id", "?"))
        return NullHook()
    job.conductor_hook = h
    return h


class Hook:
    active = True

    def __init__(self, pipeline, job, d, io, conductor: cmod.Conductor):
        self.p, self.ctx, self.job, self.d, self.io, self.c = pipeline, pipeline.ctx, job, d, io, conductor
        self.scope = f"{d.id}:{job.id}"
        self.claude = bool(conductor.claude_models(job.mode))
        self.declined = False
        self.cap = float(getattr(pipeline.settings, "conductor_cap_usd", 1.0) or 0.0)
        self.assign: dict[str, str] = {}
        self.hints: dict[str, str] = {}
        self.plan_task: asyncio.Task | None = None
        self.features = frozenset()
        self.difficulty = "medium"
        self.fixes = {"statement": 0, "proof": 0}
        self._ask_event: asyncio.Event | None = None
        self._answer: bool | None = None
        self._ws = None
        self.conductor.brain.ledger.scope_caps[self.scope] = self.cap
        job.conductor = {"by": "", "name": "", "tier": "", "usd": 0.0, "cap": self.cap, "difficulty": "",
                         "summary": "", "plan": [], "ask": None, "state": "planning", "decisions": 0,
                         "claude": self.claude}

    @property
    def conductor(self) -> cmod.Conductor:
        return self.c

    # ------------------------------------------------------------ helpers
    def _publish(self) -> None:
        self.job.conductor["usd"] = round(self.c.brain.ledger.scope_total(self.scope), 5)
        self.ctx.publish_job(self.job)

    async def _event(self, kind: str, key: str, **params) -> None:
        try:
            await self.p.event(self.d, self.job, kind, key, model=self.job.conductor.get("by", ""), **params)
        except Exception:  # noqa: BLE001
            log.exception("conductor event failed")

    def _problem(self) -> str:
        d = self.d
        return (d.understood_display or d.understood or d.problem or "").strip()

    def _domain(self) -> str:
        from ..brain.leaderboard import domain_of
        return domain_of(f"{self.d.statement}\n{self._problem()}")

    async def _ws_of(self):
        if self._ws is None:
            try:
                self._ws = self.ctx.workspace(self.d.workspace or self.p.settings.workspace)
            except Exception:  # noqa: BLE001
                self._ws = None
        return self._ws

    def _set_by(self, r: cmod.Reply) -> None:
        self.job.conductor.update(by=r.key, name=r.name, tier=r.tier)
        self.job.conductor["decisions"] = int(self.job.conductor.get("decisions", 0)) + 1

    def _on_try(self, ch: cmod.Choice) -> None:
        cur = self.job.conductor.get("by")
        if cur and cur != ch.key and ch.tier == "free" and self.job.conductor.get("tier") != "free":
            self.job.conductor["fallback"] = ch.name

    async def _decide(self, decision: str, kind: str, user: str, schema: dict, *, attempt: int = 0,
                      deadline: float | None = None) -> cmod.Reply | None:
        """One decision of the conductor within the request's budget; None when nobody could answer."""
        tok = spend.SPEND_SCOPE.set(self.scope)
        try:
            r = await self.c.ask(decision, kind=kind, user=user, schema=schema, difficulty=self.difficulty,
                                 mode=self.job.mode, scope=self.scope, features=self.features,
                                 ws=await self._ws_of(), attempt=attempt, claude=self.claude and not self.declined,
                                 deadline=deadline, on_cap=self._on_cap, on_try=self._on_try)
        except cmod.NoConductor as e:
            log.info("job %s: no conductor for %s: %s", self.job.id, decision, "; ".join(e.tried)[:400])
            return None
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("conductor decision %s failed", decision)
            return None
        finally:
            spend.SPEND_SCOPE.reset(tok)
        prev_tier = self.job.conductor.get("tier")
        self._set_by(r)
        if r.tier == "free" and self.claude and not self.declined and prev_tier != "free":
            await self._event("info", "Claude indisponible : {name} dirige à sa place.", name=r.name)
        self._publish()
        return r

    async def _on_cap(self, est: float) -> bool:
        """« Plafond atteint : continuer avec Claude (+0,50 $) ? » — the job waits for the user's answer."""
        if self.declined:
            return False
        if self.c.month_room() < cmod.CAP_STEP:
            self.claude = False
            await self._event("info", "Plafond mensuel atteint : suite sans Claude.")
            return False
        self._ask_event = asyncio.Event()
        self._answer = None
        spent = self.c.brain.ledger.scope_total(self.scope)
        self.job.conductor["ask"] = {"spent": round(spent, 4), "cap": self.cap, "step": cmod.CAP_STEP,
                                     "estimate": round(est, 4), "t": time.time()}
        self.job.conductor["state"] = "asking"
        ASKS[self.job.id] = self
        self._publish()
        await self._event("info", "Plafond atteint : continuer avec Claude (+{step} $) ?", step=f"{cmod.CAP_STEP:.2f}")
        try:
            await asyncio.wait_for(self._ask_event.wait(), ASK_TIMEOUT)
        except asyncio.TimeoutError:
            self._answer = False
        finally:
            ASKS.pop(self.job.id, None)
            self._ask_event = None
            self.job.conductor["ask"] = None
            self.job.conductor["state"] = "running"
        if self._answer:
            self.cap = round(self.cap + cmod.CAP_STEP, 2)
            self.c.brain.ledger.scope_caps[self.scope] = self.cap
            self.job.conductor["cap"] = self.cap
            self._publish()
            await self._event("info", "Plafond de la demande relevé à {cap} $.", cap=f"{self.cap:.2f}")
            return True
        self.declined = True
        self.claude = False
        self.job.conductor["claude"] = False
        self.assign = {r: k for r, k in self.assign.items() if not k.startswith("anthropic:")}
        self._publish()                       # the next best (free) conductor goes on, or none: pipeline as before
        await self._event("info", "Suite sans Claude : la chaîne gratuite habituelle continue.")
        return False

    # ------------------------------------------------------------ plan
    async def start(self) -> None:
        try:
            self.features = toolcards.features_of(self.d.problem, self.d.understood, self.d.statement,
                                                  " ".join(p.get("request", "") for p in self.job.plan))
            fails = sum(1 for e in self.d.events[-30:] if (getattr(e, "key", "") or "").startswith(
                "Aucune preuve trouvée"))
            self.difficulty = cmod.difficulty_of(self._problem(), self.d.statement, fails)
            self.job.conductor["difficulty"] = self.difficulty
            self._ws = await self._ws_of()
        except Exception:  # noqa: BLE001
            log.exception("conductor start")
        self.plan_task = asyncio.create_task(self._plan_safe(), name=f"{self.job.id}-conductor-plan")
        self._publish()

    async def _plan_safe(self) -> None:
        try:
            await self._make_plan()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("conductor plan")
            self.job.conductor["state"] = "off"

    def _candidates(self) -> dict[str, list[dict]]:
        out = {}
        for role in ("understand", "formalize", "prove", "explain"):
            try:
                out[role] = self.c.worker_candidates(role, self.job.mode, domain=self._domain(), scope=self.scope,
                                                     claude=self.claude)
            except Exception:  # noqa: BLE001
                log.exception("worker candidates for %s", role)
                out[role] = []
        return out

    async def _make_plan(self) -> None:
        cands = self._candidates()
        # the code's own choice first: it applies even if the plan decision fails
        for role, cs in cands.items():
            if cs:
                self.assign[role] = cs[0]["key"]
        d = self.d
        req = " / ".join(p.get("request", "") for p in self.job.plan if p.get("request"))
        lines = [f"Problem (user's words): {d.problem[:2500]}"]
        if d.understood:
            lines.append(f"Understood as: {d.understood[:1500]}")
        if d.statement:
            lines.append(f"Current Lean statement:\n```lean4\n{d.statement[:2500]}\n```"
                         + (" (proved)" if d.proof_is_current else ""))
        if req:
            lines.append(f"Follow-up request: {req[:800]}")
        lines.append(f"Stages to run: {', '.join(p.get('stage', '') for p in self.job.plan)}")
        lines.append(f"Domain: {self._domain()}; estimated difficulty: {self.difficulty}; interface language: "
                     f"{language()}; budget left for this request: {self.c.room(self.scope):.2f} $")
        lines.append("Candidates per kind (best first, ranked by Madalean from measured success, latency, cost):")
        for role, cs in cands.items():
            kinds = [k for k, r in cmod.KIND_ROLE.items() if r == role]
            row = "; ".join(f"{c['key']} ({c['name']}, score {c['utility']}"
                            + (f", {c['latency']} s" if c.get("latency") is not None else "")
                            + (f", ≈{c['est_usd']} $" if c.get("paid") else ", free") + ")" for c in cs)
            lines.append(f"- {'/'.join(kinds)}: {row or 'auto'}")
        r = await self._decide("plan", "plan", "\n".join(lines), cmod.PLAN_SCHEMA,
                               deadline=time.monotonic() + PLAN_DEADLINE)
        if r is None:
            self.job.conductor["state"] = "off"
            self.job.conductor["plan"] = self._code_plan(cands)
            self._publish()
            return
        v = cmod.validate_plan(r.data, {role: [c["key"] for c in cs] for role, cs in cands.items()})
        if v is None:
            self.job.conductor["plan"] = self._code_plan(cands)
            self.job.conductor["state"] = "running"
            self._publish()
            return
        diff, summary, tasks = v
        self.difficulty = diff
        names = {c["key"]: c["name"] for cs in cands.values() for c in cs}
        rows = []
        for t in tasks:
            role = cmod.KIND_ROLE.get(t.kind)
            key = t.model or (self.assign.get(role, "") if role else "")
            if role and t.model and role in ROLE_KINDS:
                self.assign[role] = t.model                     # the conductor's choice (among the candidates)
            if t.hint and t.kind in ("formalize", "prove", "mathlib", "explain"):
                k = "prove" if t.kind == "mathlib" else t.kind
                self.hints[k] = (self.hints.get(k, "") + " " + t.hint).strip()[:800]
            rows.append({"id": t.id, "kind": t.kind, "goal": t.goal, "model": key,
                         "model_name": names.get(key, key.split(":", 1)[-1] if key else ""), "why": t.why,
                         "wave": t.wave, "depends_on": t.depends_on, "advisory": t.advisory,
                         "stage": cmod.KIND_STAGE.get(t.kind, "")})
        self.job.conductor.update(plan=rows, summary=summary, difficulty=diff, state="running")
        self._publish()
        await self._event("info", "Dirigé par {name} : plan en {n} étapes.", name=r.name, n=len(rows))

    def _code_plan(self, cands: dict[str, list[dict]]) -> list[dict]:
        """The plan without a conductor's answer: Madalean's stages with the code's model choice."""
        rows = []
        order = [("t1", "understand", []), ("t2", "formalize", ["t1"]), ("t3", "check", ["t2"]),
                 ("t4", "mathlib", ["t2"]), ("t5", "prove", ["t2"]), ("t6", "explain", ["t5"])]
        for tid, kind, deps in order:
            role = cmod.KIND_ROLE[kind]
            c = (cands.get(role) or [{}])[0]
            rows.append({"id": tid, "kind": kind, "goal": "", "model": c.get("key", ""),
                         "model_name": c.get("name", ""), "why": "", "wave": 0 if not deps else (
                             1 if deps == ["t1"] else 2 if kind != "explain" else 3),
                         "depends_on": deps, "advisory": False, "stage": cmod.KIND_STAGE[kind]})
        return rows

    async def before_stage(self, stage: str) -> None:
        t = self.plan_task
        if t is None or t.done() or stage not in ("statement", "proof", "explanation"):
            return
        try:
            await asyncio.wait_for(asyncio.shield(t), PLAN_WAIT)
        except asyncio.TimeoutError:
            pass                              # the stage goes on; the plan applies when it arrives
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ what the workers get
    def prefer(self, role: str) -> str | None:
        if role not in ("understand", "formalize", "explain"):
            return None
        k = self.assign.get(role)
        if k and k.startswith("anthropic:") and (self.declined or not self.claude):
            return None
        return k or None

    def hint(self, kind: str) -> str:
        h = self.hints.get(kind, "")
        return f"\n\nAdvice from the conductor: {h}" if h else ""

    def lead(self, contestants: list) -> list:
        """Tournament round 0: the conductor's prover (a free model of the pool) leads."""
        k = self.assign.get("prove")
        if not k:
            return contestants
        i = next((i for i, c in enumerate(contestants) if getattr(c, "key", "") == k), -1)
        if i <= 0:
            return contestants
        head = [c for c in contestants[:i] if getattr(c, "kind", "") == "goedel_online"]
        rest = [c for j, c in enumerate(contestants) if j != i and c not in head]
        return head + [contestants[i]] + rest

    def cards(self, role: str, messages: list[dict]) -> list[dict]:
        """The tool rule cards of the role, compacted for this request, in front of the worker's messages."""
        if role not in ("formalize", "explain", "understand"):
            return messages
        try:
            out, _c = toolcards.worker_messages(messages, role, self.features, self._ws)
            return out
        except Exception:  # noqa: BLE001
            return messages

    # ------------------------------------------------------------ corrections
    async def after_stage(self, stage: str) -> None:
        if stage == "statement" and self.job.error == "statement_rejected":
            await self._fix_statement()

    async def _fix_statement(self) -> None:
        job, d = self.job, self.d
        ws = await self._ws_of()
        if ws is None:
            return
        s = self.p.settings
        name = d.theorem or leancheck.DEFAULT_THEOREM_NAME
        rejected = [a for a in job.attempts if a.stage == "statement" and a.code and a.status == "rejected"][-2:]
        feedback = "\n\n".join(f"Attempt:\n```lean4\n{a.code[:3000]}\n```\nLean errors:\n{a.errors_text[:1500]}"
                               for a in rejected)
        for i in range(MAX_FIX):
            self.fixes["statement"] += 1
            user = (f"Theorem name: {name}\nProblem: {self._problem()[:3000]}\n\nRejected translations:\n{feedback}")
            r = await self._decide("fix", "fix_statement", user, cmod.FIX_STATEMENT_SCHEMA, attempt=i,
                                   deadline=time.monotonic() + 240)
            if r is None:
                return
            a = self.io.new_attempt("statement", "correction")
            a.model = r.key
            raw = str(r.data.get("statement") or "")
            a.raw = raw
            code = leancheck.extract_code(raw) or raw
            try:
                a.code = leancheck.normalize_formal_statement(code)
            except leancheck.StatementError as e:
                a.status, a.summary = "rejected", str(e)
                self.io.update_attempt(a)
                self.c.stats.record(r.key, "fix", False, r.seconds, r.usd)
                feedback += f"\n\nYour correction was not a Lean statement: {e}"
                continue
            a.status = "compiling"
            self.io.update_attempt(a)
            res = await self.io.check(a.code, ws, s.compile_timeout_s, None)
            a.compile_seconds = res.seconds
            ok = not res.verdict.errors and not res.timed_out and not res.infra_error \
                and not leancheck.vacuous(a.code)
            self.c.stats.record(r.key, "fix", ok, r.seconds, r.usd)
            if not ok:
                a.status = "rejected"
                a.errors_text = "\n".join(f"line {m.line}: {m.text[:300]}" for m in res.verdict.errors[:4]) \
                    or ("trivial statement" if leancheck.vacuous(a.code) else res.infra_error or "timeout")
                self.io.update_attempt(a)
                feedback += f"\n\nYour correction:\n```lean4\n{a.code[:3000]}\n```\nLean errors:\n{a.errors_text}"
                continue
            a.status, a.summary = "accepted", msg("Énoncé valide en Lean (à relire)")["text"]
            self.io.update_attempt(a)
            idx = d.add_statement(a.code, ok=True, note="", model=r.key)
            d.status = "draft"
            job.error, job.summary = "", {}
            await self._event("info", "{name} a corrigé l'erreur Lean : {what}", name=r.name,
                              what=str(r.data.get("what") or "")[:300])
            await self.p.event(d, job, "statement", "L'IA a traduit le problème en Lean et Lean accepte l'énoncé. "
                               "Relisez-le : la preuve portera exactement sur ce texte.", ref=idx, model=r.key)
            if s.pause_after_translation:
                job.plan = []
                await self.p.event(d, job, "info", "Pause : relisez l'énoncé, puis cliquez sur « Prouver cet énoncé ».")
            else:
                job.plan = ([{"stage": "notes"}] if s.statement_notes else []) + \
                    [{"stage": "proof"}, {"stage": "explanation"}]
            return

    async def recover(self, stage: str, failed) -> bool:
        """A failure the conductor may correct: no proof found. True when a Lean-verified proof was recorded."""
        if stage != "proof" or getattr(failed, "error", "") != "no_proof" or not self.d.statement:
            return False
        try:
            return await self._fix_proof()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("conductor proof correction failed")
            return False

    async def _fix_proof(self) -> bool:
        job, d = self.job, self.d
        ws = await self._ws_of()
        if ws is None:
            return False
        s = self.p.settings
        statement_src = d.statement
        try:
            statement = leancheck.prepare_statement(statement_src)
            name = leancheck.theorem_name(statement)
        except leancheck.StatementError:
            return False
        tried = [a for a in job.attempts if a.stage == "proof" and a.code and a.status == "rejected"]
        tried.sort(key=lambda a: len(a.errors_text or "x" * 9999))
        feedback = "\n\n".join(f"Attempt ({a.model}):\n```lean4\n{a.code[:3500]}\n```\nLean errors:\n"
                               f"{a.errors_text[:1500]}" for a in tried[:2]) or "(no attempt compiled)"
        mh = getattr(job, "mathlib_hint", "") or ""
        for i in range(MAX_FIX):
            self.fixes["proof"] += 1
            user = (f"Theorem to prove (exactly as given):\n```lean4\n{statement[:4000]}\n```\n"
                    + (f"\nMathlib candidates: {mh[:800]}\n" if mh else "")
                    + f"\nClosest attempts:\n{feedback}")
            r = await self._decide("fix", "fix_proof", user, cmod.FIX_PROOF_SCHEMA, attempt=i,
                                   deadline=time.monotonic() + 300)
            if r is None or d.statement != statement_src:
                return False
            a = self.io.new_attempt("proof", "correction")
            a.model = r.key
            raw = str(r.data.get("proof") or "")
            a.raw = raw
            model_code = leancheck.extract_code(raw) or raw
            try:
                code = leancheck.assemble_proof(statement, model_code)
            except leancheck.StatementError as e:
                a.status, a.summary = "rejected", str(e)
                self.io.update_attempt(a)
                self.c.stats.record(r.key, "fix", False, r.seconds, r.usd)
                feedback += f"\n\nYour proof could not be assembled: {e}"
                continue
            a.code = code
            a.status = "compiling"
            self.io.update_attempt(a)
            t0 = time.monotonic()
            res = await self.io.check(leancheck.with_axiom_probe(code, name), ws, s.compile_timeout_s, name)
            a.compile_seconds = res.seconds
            ok = bool(res.verdict.ok)
            self.c.stats.record(r.key, "fix", ok, r.seconds, r.usd)
            if not ok:
                a.status = "rejected"
                a.errors_text = "\n".join(f"line {m.line}: {m.text[:300]}" for m in res.verdict.errors[:4]) \
                    or "; ".join(res.verdict.reasons[:3]) or res.infra_error or "rejected"
                self.io.update_attempt(a)
                feedback += f"\n\nYour proof:\n```lean4\n{code[:3500]}\n```\nLean errors:\n{a.errors_text}"
                continue
            a.status, a.summary = "accepted", msg("Preuve vérifiée par Lean")["text"]
            self.io.update_attempt(a)
            from ..runtime.lean import workspace_info
            info = workspace_info(ws)
            meta = {"axioms": res.verdict.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
                    "workspace": ws.key, "seconds": round(time.monotonic() - t0 + r.seconds, 1),
                    "strategy": "conductor", "attempts": len([x for x in job.attempts if x.stage == "proof"]),
                    "checked": time.time()}
            idx = d.add_proof(code, model=r.key, meta=meta)
            d.status = "proved"
            job.error, job.summary = "", {}
            await self._event("info", "{name} a corrigé l'erreur Lean : {what}", name=r.name,
                              what=str(r.data.get("what") or "")[:300])
            await self.p.event(d, job, "proof", "Preuve trouvée et vérifiée par Lean (essai {i}, {s:.0f} s).",
                               ref=idx, model=r.key, i=meta["attempts"], s=meta["seconds"])
            try:
                lib = self.ctx.library
                entry = await asyncio.to_thread(lib.add_proof, code, d.title, ws.key, d.id, d.lemmas_used)
                if entry:
                    self.ctx.bus.publish("library.updated", {"added": entry.name})
            except Exception:  # noqa: BLE001
                log.exception("library add after a conductor proof")
            return True
        return False

    # ------------------------------------------------------------ final check
    async def finish(self) -> None:
        d, job = self.d, self.job
        if "explanation" not in job.done_stages or not d.explanation or not d.statement:
            self._publish()
            return
        user = (f"User's problem: {d.problem[:2500]}\n"
                + (f"Understood as: {d.understood[:1500]}\n" if d.understood else "")
                + f"\nLean statement:\n```lean4\n{d.statement[:3000]}\n```\n"
                + ("Lean verified the proof:\n```lean4\n" + d.proof[:3000] + "\n```\n" if d.proof_is_current
                   else "No verified proof.\n")
                + f"\nExplanation given to the user:\n{d.explanation[:5000]}")
        r = await self._decide("final", "final", user, cmod.FINAL_SCHEMA, deadline=time.monotonic() + 90)
        if r is None:
            self._publish()
            return
        issues = [i for i in (r.data.get("issues") or []) if isinstance(i, dict) and i.get("text")]
        if r.data.get("consistent") and not issues:
            await self._event("info", "Vérification finale ({name}) : énoncé, preuve et explication concordent.",
                              name=r.name)
        else:
            text = " ; ".join(f"{i.get('part', '')}: {str(i['text'])[:200]}" for i in issues[:4]) \
                or str(r.data.get("summary") or "")[:300]
            await self._event("info", "Vérification finale ({name}) : à revoir — {issues}", name=r.name, issues=text)
        self.job.conductor["final"] = {"consistent": bool(r.data.get("consistent")) and not issues,
                                       "issues": issues[:6], "summary": str(r.data.get("summary") or "")[:300]}
        self._publish()

    async def close(self) -> None:
        t = self.plan_task
        if t is not None and not t.done():
            t.cancel()
            await asyncio.gather(t, return_exceptions=True)
        ASKS.pop(self.job.id, None)
        try:
            self.job.conductor["usd"] = round(self.c.brain.ledger.scope_total(self.scope), 5)
            if self.job.conductor.get("state") in ("planning", "running", "asking"):
                self.job.conductor["state"] = "done"
        except Exception:  # noqa: BLE001
            pass
        self.c.brain.ledger.scope_caps.pop(self.scope, None)
        self.ctx.publish_job(self.job)
