"""One job = one plan of stages run on one dossier (port of 1.1.4 `ui/pipeline.py` to asyncio + Brain).

Stages: understand → statement (+ notes) → proof → explanation (+ informal). `route` reads a follow-up message and
rewrites the rest of the plan (D26). Every event written to the thread records the model that produced it."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from .. import leancheck, prompts
from ..brain.api import BrainError, Chunk, Completion, ModelRef
from ..dossiers import Dossier, closure, route, route_scores, with_lemmas
from ..errors import friendly
from ..i18n import language, msg
from ..jobs import Attempt, Job
from ..logs import get
from ..runtime.lean import workspace_info
from .goedel import Formalizer, GoedelProver, ProveResult
from .io import InfraError, LoopGuard, outer_cancelled

log = get("pipeline")
STAGES = ("understand", "route", "statement", "notes", "proof", "explanation", "informal")
NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}
RAW_CAP = 200_000


def full_plan() -> list[dict]:
    return [{"stage": "understand"}, {"stage": "statement"}, {"stage": "proof"}, {"stage": "explanation"}]


def stage_plan(d: Dossier, stage: str, text: str) -> list[dict]:
    plan = {"statement": [{"stage": "statement", "request": text}, {"stage": "proof"}, {"stage": "explanation"}],
            "proof": [{"stage": "proof", "request": text}, {"stage": "explanation"}],
            "explanation": [{"stage": "explanation", "request": text}]}[stage]
    if stage == "explanation" and not d.proof_is_current:
        plan = [{"stage": "proof"}, {"stage": "explanation", "request": text}]
    return plan


def plan_for_message(d: Dossier, text: str, stage: str, route_available: bool) -> tuple[list[dict], str]:
    """Plan for a follow-up message (1.1.4 `Pipeline.request`). Returns (plan, stage shown on the user's message).
    Mutates `d.problem` when nothing has been translated yet (the message completes the problem)."""
    if not d.statement:
        d.problem = (d.problem + "\n" + text).strip() if d.problem else text
        return full_plan(), "statement"
    if stage == "auto" and route_available:
        return [{"stage": "route", "request": text}], "auto"
    if stage == "auto":
        stage = route(text, d.proof_is_current, bool(d.explanation))
    return stage_plan(d, stage, text), stage


class JobIO:
    """StageIO bound to one job: attempts are published as `job.updated`, streamed text as `job.token`."""

    def __init__(self, ctx, job: Job):
        self.ctx, self.job = ctx, job

    def new_attempt(self, stage: str, kind: str) -> Attempt:
        a = Attempt(len(self.job.attempts), stage, kind)
        self.job.attempts.append(a)
        self.ctx.publish_job(self.job)
        return a

    def drop_attempt(self, a: Attempt) -> None:
        if a in self.job.attempts:
            self.job.attempts.remove(a)
            for i, x in enumerate(self.job.attempts):
                x.index = i
        self.ctx.publish_job(self.job)

    def update_attempt(self, a: Attempt) -> None:
        if len(a.raw) > RAW_CAP:
            a.raw = a.raw[:RAW_CAP] + "\n…"
        self.ctx.publish_job(self.job)

    def _model_guess(self, role: str, mode: str) -> ModelRef:
        try:
            c = self.ctx.brain.candidates(role, mode)
            if c:
                return c[0]
        except Exception:  # noqa: BLE001
            pass
        return ModelRef("unknown", "unknown")

    async def complete(self, role: str, messages: list[dict], attempt: Attempt | None = None, *,
                       temperature: float | None = None, max_tokens: int | None = None, extra: dict | None = None,
                       mode: str | None = None, stage: str = "") -> Completion:
        ctx, job = self.ctx, self.job
        mode = mode or job.mode
        guard = LoopGuard()
        idx = attempt.index if attempt is not None else -1
        stage = stage or job.stage
        inner: asyncio.Task | None = None

        def on_chunk(ch: Chunk) -> None:
            if ch.kind in ("text", "thinking"):
                if attempt is not None and len(attempt.raw) < RAW_CAP:
                    attempt.raw += ch.text
                ctx.bus.token(job.id, stage, idx, ch.text, ch.kind)
                if guard.feed(ch.text) and inner is not None and not inner.done():
                    inner.cancel()                 # the model is going round in circles: stop wasting minutes
            elif ch.kind == "info":
                ctx.bus.publish("job.info", {"job_id": job.id, "stage": stage, "text": ch.text, "data": ch.data})

        need_online = mode != "local"
        if need_online:
            job.waiting = "online"
            ctx.publish_job(job)
            await ctx.slots.acquire("online", job.id)
            job.waiting = ""
            ctx.publish_job(job)
        try:
            inner = asyncio.create_task(ctx.brain.complete(
                role, messages, mode=mode, temperature=temperature, max_tokens=max_tokens, on_chunk=on_chunk,
                prefer=(ctx.settings.prefer or {}).get(role) or None, extra=extra))
            try:
                return await inner
            except asyncio.CancelledError:
                if guard.loop is not None and not outer_cancelled():
                    return Completion(guard.trimmed(), self._model_guess(role, mode), "loop")
                inner.cancel()
                raise
        finally:
            if need_online:
                ctx.slots.release("online", job.id)
            try:
                ctx.local.release()
            except Exception:  # noqa: BLE001
                pass

    async def check(self, code: str, ws, timeout_s: int, strict_name: str | None):
        return await self.ctx.lean.check(code, ws, timeout_s, strict_name, owner=self.job.id)


class Failed(Exception):
    def __init__(self, key: str, error: str = "failed", **params: Any):
        super().__init__(key)
        self.key, self.error, self.params = key, error, params


class DossierPipeline:
    def __init__(self, ctx):
        self.ctx = ctx

    # ------------------------------------------------------------ helpers
    @property
    def settings(self):
        return self.ctx.settings

    async def event(self, d: Dossier, job: Job | None, kind: str, key: str, ref: int | None = None, stage: str = "",
                    model: str = "", detail: str = "", **params: Any) -> None:
        m = msg(key, **params)
        text = m["text"] + ("\n" + detail if detail else "")
        if detail:
            params = {**params, "detail": detail}
        d.add_event(kind, text, ref, stage, model, key, params, job.id if job else "")
        await self.ctx.repo.save(d)

    def has_model(self, role: str, mode: str) -> bool:
        try:
            return bool(self.ctx.brain.candidates(role, mode))
        except Exception:  # noqa: BLE001
            return False

    async def workspace(self, d: Dossier):
        ws = self.ctx.workspace(d.workspace or self.settings.workspace)
        problems = [] if ws is None else await self.ctx.lean.problems(ws)
        if ws is None or problems:
            f = friendly("workspace")
            raise Failed("Étape impossible : l'espace de travail Lean n'est pas prêt ({why}).", "workspace",
                         why=(problems[0] if problems else f.title))
        if not d.workspace:
            d.workspace = ws.key
        return ws

    # ------------------------------------------------------------ main loop
    async def run(self, job: Job) -> None:
        d = self.ctx.repo.get(job.dossier_id)
        if d is None:
            job.error = "missing"
            return
        io = JobIO(self.ctx, job)
        try:
            while job.plan:
                step = job.plan.pop(0)
                stage, req = step.get("stage", ""), step.get("request", "") or ""
                if stage not in STAGES:
                    continue
                job.stage = stage
                self.ctx.publish_job(job)
                try:
                    await getattr(self, "_" + stage)(job, d, io, req)
                except InfraError as e:
                    if e.kind == "no_model":
                        raise Failed("Étape impossible : le modèle nécessaire n'est pas installé (voir « Modèles »).",
                                     "no_model") from e
                    if e.kind == "workspace":
                        raise Failed("Étape impossible : l'espace de travail Lean n'est pas prêt ({why}).",
                                     "workspace", why=e.details[-300:]) from e
                    raise Failed("Interrompu : le moteur d'IA ou Lean ne répond plus. Voir le message en haut, "
                                 "puis renvoyez votre demande.", e.kind) from e
                except BrainError as e:
                    if e.kind == "no_model":
                        raise Failed("Étape impossible : le modèle nécessaire n'est pas installé (voir « Modèles »).",
                                     "no_model") from e
                    raise Failed("Interrompu : le moteur d'IA ou Lean ne répond plus. Voir le message en haut, "
                                 "puis renvoyez votre demande.", e.kind) from e
                job.done_stages.append(stage)
        except Failed as f:
            job.plan = []
            job.error = f.error
            job.summary = msg(f.key, **f.params)
            if d.status in ("translating", "proving"):
                d.status = "proved" if d.proof_is_current else "failed"
            await self.event(d, job, "error", f.key, **f.params)
            return
        if d.status in ("translating", "proving"):
            d.status = "proved" if d.proof_is_current else "draft"
            await self.ctx.repo.save(d)

    # ------------------------------------------------------------ stages
    async def _short(self, io: JobIO, role: str, messages: list[dict], temperature: float, max_tokens: int = 700):
        return await io.complete(role, messages, None, temperature=temperature, max_tokens=max_tokens,
                                 extra={"top_p": 0.9, **NO_THINK})

    async def _understand(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not (self.has_model("understand", job.mode) and self.has_model("formalize", job.mode)):
            return                     # optional step: the formalizer then gets the user's own words
        try:
            c = await self._short(io, "understand", leancheck.understand_messages(d.problem, self.settings.profile,
                                                                                   language()), 0.3)
        except BrainError:
            return
        text = leancheck.clean_model_text(c.text)
        ok = bool(text) and c.finish not in ("loop", "length")
        if ok and leancheck.is_unknown(text):
            raise Failed("Je ne reconnais pas d'énoncé mathématique dans votre demande. Écrivez le résultat à prouver "
                         "avec ses hypothèses, par exemple : « toute famille libre d'un espace vectoriel de dimension "
                         "finie se complète en une base ».", "unknown")
        if ok and text.strip():
            eng, disp = leancheck.parse_understood(text)
            d.understood, d.understood_display = eng, disp
            await self.event(d, job, "understood", "Problème compris ainsi (c'est ce texte que l'IA traduit en Lean) :",
                             model=c.model.key, detail=disp)

    async def _route(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        try:
            c = await self._short(io, "route", leancheck.route_messages(d.understood or d.problem, d.statement,
                                                                        d.proof_is_current, req, language()), 0.2)
            text = leancheck.clean_model_text(c.text)
            parsed = leancheck.parse_route(text) if text and c.finish not in ("loop",) else None
            model = c.model.key
        except BrainError:
            parsed, model = None, ""
        kw = route(req, d.proof_is_current, bool(d.explanation))
        sc = route_scores(req)
        if parsed is None:
            stage, eng, disp = kw, "", ""
        else:
            stage, eng, disp = parsed
            if stage == "proof" and kw != "proof" and sc[kw] and not sc["proof"]:
                stage = kw                     # the model missed an explicit « pourquoi » / « hypothèse »
        for e in reversed(d.events):
            if e.kind == "user":
                e.stage = stage
                break
        if stage == "statement" and eng:
            d.understood, d.understood_display = eng, disp
            await self.event(d, job, "understood",
                             "Nouvel énoncé compris ainsi (c'est ce texte que l'IA traduit en Lean) :", model=model,
                             detail=disp)
            job.plan = [{"stage": "statement"}, {"stage": "proof"}, {"stage": "explanation"}]
        else:
            job.plan = stage_plan(d, stage, req)
            await self.ctx.repo.save(d)

    async def _statement(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        ws = await self.workspace(d)
        s = self.settings
        d.status = "translating"
        await self.ctx.repo.save(d)
        previous = d.statement if req else ""
        f = await Formalizer(io, job.mode).run(d.understood or d.problem, ws, s.translate_attempts,
                                                s.compile_timeout_s, name=d.theorem, profile=s.profile,
                                                previous=previous, request=req)
        if not f.statement:
            raise Failed("Pas d'énoncé produit. Reformulez le problème (plus précis, avec les hypothèses) ou écrivez "
                         "l'énoncé Lean vous-même dans l'onglet « Énoncé Lean ».", "no_statement")
        idx = d.add_statement(f.statement, ok=f.ok, note=req, model=f.model)
        if f.ok:
            d.status = "draft"
            await self.event(d, job, "statement", "L'IA a traduit le problème en Lean et Lean accepte l'énoncé. "
                             "Relisez-le : la preuve portera exactement sur ce texte.", ref=idx, model=f.model)
            if s.pause_after_translation:
                job.plan = []
                await self.event(d, job, "info", "Pause : relisez l'énoncé, puis cliquez sur « Prouver cet énoncé ».")
            if s.statement_notes:
                job.plan.insert(0, {"stage": "notes"})
        else:
            job.plan = []
            d.status = "draft"
            job.error = "statement_rejected"
            job.summary = msg("Lean refuse la traduction. Corrigez l'énoncé dans l'onglet « Énoncé Lean », ou "
                              "demandez une correction ci-dessous.")
            await self.event(d, job, "error", "Lean refuse la traduction. Corrigez l'énoncé dans l'onglet « Énoncé "
                             "Lean », ou demandez une correction ci-dessous.", ref=idx, model=f.model)

    async def _notes(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not d.statement or not self.has_model("explain", job.mode):
            return
        nl = d.understood_display or d.understood or d.problem
        try:
            c = await self._short(io, "explain", prompts.notes_messages(d.statement, nl, language()), 0.3, 1500)
        except BrainError:
            return                     # optional: the statement stays usable without its gloss
        text = leancheck.clean_model_text(c.text)
        if text:
            idx = d.add_notes(text, c.model.key)
            await self.event(d, job, "notes", "Lecture guidée de l'énoncé Lean, rédigée par l'IA :", ref=idx,
                             model=c.model.key)

    def _choose_strategy(self, job: Job) -> str:
        st = job.strategy or self.settings.prove_strategy
        if st == "goedel":
            return "goedel"
        agent = _agent_fn()
        if agent is None:
            return "goedel"
        if st == "agent":
            return "agent"
        # auto: the agent with an online model when allowed, else goedel (ARCHITECTURE §7)
        if job.mode == "local":
            return "goedel"
        try:
            cands = self.ctx.brain.candidates("prove", job.mode)
        except Exception:  # noqa: BLE001
            cands = []
        return "agent" if any(not c.local for c in cands) else "goedel"

    async def _proof(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        ws = await self.workspace(d)
        if not d.statement:
            raise Failed("Pas d'énoncé à prouver : écrivez ou traduisez d'abord l'énoncé.", "no_statement")
        s, lib = self.settings, self.ctx.library
        d.status = "proving"
        await self.ctx.repo.save(d)
        exclude = leancheck.declared_names(d.statement)
        child_ids = {c.id for c in self.ctx.repo.children(d.id)}
        forced = [e for e in lib.entries if e.dossier in child_ids and e.workspace == ws.key and e.name not in exclude]
        rel = [e for e in lib.relevant(d.statement, ws.key, exclude=exclude) if e not in forced]
        used = closure(lib, forced + rel)
        d.lemmas_used = [e.name for e in used]
        statement = with_lemmas(d.statement, used)
        if used:
            await self.event(d, job, "info", "Résultats de votre bibliothèque proposés à l'IA : {names}.",
                             names=", ".join(e.title for e in used))
        refine = (d.proof, req) if (req and d.proof_is_current) else None
        hint = req if (req and not d.proof_is_current) else ""
        strategy = self._choose_strategy(job)
        res: ProveResult | None = None
        try:
            statement = leancheck.prepare_statement(statement)
        except leancheck.StatementError as e:
            raise Failed("{why}", "statement", why=str(e)) from e
        if strategy == "agent":
            res = await self._agent(job, d, io, ws, statement, hint or req)
            if not (res and res.ok) and (job.strategy or s.prove_strategy) == "auto":
                strategy = "goedel"
                res = None
        if res is None:
            ctx_len = (self.ctx.local.plan.ctx if getattr(self.ctx.local, "plan", None) else s.server.ctx_size)
            res = await GoedelProver(io, "local").run(statement, ws, s.prove_attempts, s.sampling, s.compile_timeout_s,
                                                      ctx_len, refine=refine, hint=hint)
        if not res.ok:
            d.status = "failed"
            raise Failed("Aucune preuve trouvée après {n} essais. Essayez : « autre méthode », un énoncé plus simple, "
                         "ou plus d'essais (⚙ Options).", "no_proof",
                         n=len([a for a in job.attempts if a.stage == "proof"]))
        info = workspace_info(ws)
        meta = {"axioms": res.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
                "workspace": ws.key, "seconds": round(res.seconds, 1), "strategy": strategy,
                "attempts": len([a for a in job.attempts if a.stage == "proof"]), "checked": time.time()}
        idx = d.add_proof(res.code, note=req, model=res.model, meta=meta)
        d.status = "proved"
        await self.event(d, job, "proof", "Preuve trouvée et vérifiée par Lean (essai {i}, {s:.0f} s).", ref=idx,
                         model=res.model, i=meta["attempts"], s=res.seconds)
        entry = await asyncio.to_thread(lib.add_proof, res.code, d.title, ws.key, d.id, d.lemmas_used)
        if entry:
            self.ctx.bus.publish("library.updated", {"added": entry.name})
            await self.event(d, job, "info", "Ajouté à votre bibliothèque sous le nom « {name} » : réutilisable dans "
                             "vos prochaines preuves.", name=entry.name)

    async def _agent(self, job: Job, d: Dossier, io: JobIO, ws, statement: str, hint: str) -> ProveResult | None:
        fn = _agent_fn()
        if fn is None:
            return None
        name = leancheck.theorem_name(statement)
        a = io.new_attempt("proof", "agent")

        async def check(code: str) -> dict:
            try:
                assembled = leancheck.assemble_proof(statement, code)
            except leancheck.StatementError as e:
                return {"ok": False, "feedback": str(e), "verdict": {"ok": False, "summary": str(e)}}
            r = await io.check(leancheck.with_axiom_probe(assembled, name), ws, self.settings.compile_timeout_s, name)
            fb = "" if r.verdict.ok else leancheck.errors_for_feedback(r.code, r.verdict)
            return {"ok": r.verdict.ok, "feedback": fb, "verdict": r.to_dict()}

        async def library_search(query: str, k: int = 8) -> list[dict]:
            from ..dossiers import tokens
            q = tokens(query)
            out = []
            for e in self.ctx.library.entries:
                if e.workspace != ws.key:
                    continue
                sc = len(q & tokens(e.statement)) / max(1, len(q | tokens(e.statement)))
                if sc > 0:
                    out.append({"name": e.name, "title": e.title, "statement": e.statement, "code": e.code,
                                "score": sc})
            return sorted(out, key=lambda x: -x["score"])[:k]

        def on_chunk(ch: Chunk) -> None:
            if ch.kind in ("text", "thinking", "tool_call", "tool_result", "info"):
                self.ctx.bus.token(job.id, "proof", a.index, ch.text, ch.kind)

        need_online = job.mode != "local"
        if need_online:
            await self.ctx.slots.acquire("online", job.id)
        t0 = time.monotonic()
        try:
            out = await fn(self.ctx.brain, self.ctx.retriever, statement=statement, workspace_key=ws.key, check=check,
                           library_search=library_search, hint=hint, on_chunk=on_chunk, mode=job.mode,
                           max_steps=self.settings.agent_max_steps, max_seconds=self.settings.agent_max_seconds)
        except BrainError as e:
            a.status, a.summary, a.errors_text = "error", msg("La génération a échoué.")["text"], str(e)
            io.update_attempt(a)
            return None
        finally:
            if need_online:
                self.ctx.slots.release("online", job.id)
            self.ctx.local.release()
        a.gen_seconds = time.monotonic() - t0
        a.model = model_key(out.get("model"))
        a.raw = "\n".join(str(m.get("content", ""))[:4000] for m in (out.get("transcript") or [])[-40:])
        code = out.get("code")
        if not code:
            a.status, a.summary = "rejected", msg("L'agent n'a pas trouvé de preuve ({steps} étapes).",
                                                  steps=out.get("steps", 0))["text"]
            io.update_attempt(a)
            return ProveResult(False, model=a.model)
        # never trust the agent: the server re-checks the final proof with the strict verdict
        try:
            a.code = leancheck.assemble_proof(statement, code)
        except leancheck.StatementError as e:
            a.status, a.summary = "rejected", str(e)
            io.update_attempt(a)
            return ProveResult(False, model=a.model)
        a.status = "compiling"
        io.update_attempt(a)
        r = await io.check(leancheck.with_axiom_probe(a.code, name), ws, self.settings.compile_timeout_s, name)
        a.compile_seconds, a.summary = r.seconds, r.verdict.summary
        if not r.verdict.ok:
            a.status = "rejected"
            a.errors_text = leancheck.errors_for_feedback(r.code, r.verdict)
            io.update_attempt(a)
            return ProveResult(False, model=a.model)
        a.status = "accepted"
        io.update_attempt(a)
        return ProveResult(True, a.code, msg("Preuve trouvée et vérifiée par Lean (essai {i}).", i=1), [a], a.model,
                           r.verdict.axioms, a.gen_seconds + a.compile_seconds)

    async def _explanation(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not d.proof:
            raise Failed("Pas de preuve à expliquer.", "no_proof")
        s = self.settings
        prev = d.explanation if req else ""
        cites = _citations(self.ctx, d)
        msgs = leancheck.explain_messages(d.proof, d.understood or d.problem, language(), s.profile, prev, req)
        if cites:
            msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + cites["prompt"]}
        c = await io.complete("explain", msgs, None,
                              temperature=0.5, max_tokens=2000, extra={"top_p": 0.9, **NO_THINK, "repeat_penalty": 1.05})
        text = leancheck.clean_model_text(c.text)
        text = await self._check_citations(job, d, text, cites)
        if not text:
            raise Failed("L'IA n'a rien écrit : réessayez.", "empty")
        idx = d.add_explanation(text, note=req, model=c.model.key)
        await self.event(d, job, "explanation", "Explication rédigée par l'IA (la preuve Lean fait foi).", ref=idx,
                         model=c.model.key)
        if c.finish == "loop":
            await self.event(d, job, "info", "Explication prête (réponse interrompue : l'IA tournait en rond).")
        if s.informal_proof and (not req or not d.informal_proof):
            job.plan.insert(0, {"stage": "informal"})

    async def _check_citations(self, job: Job, d: Dossier, text: str, cites: dict | None) -> str:
        """Citations `[@key]` of keys that do not exist are removed by code (never printed) and reported."""
        if not text or "@" not in text:
            return text
        from ..research.biblio import check_citations
        res = check_citations(text, (cites or {}).get("keys") or set())
        if res.unknown:
            await self.event(d, job, "info", "Références inventées par l'IA retirées : {keys}.",
                             keys=", ".join(res.unknown[:10]))
        return res.text

    async def _informal(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not d.proof:
            return
        nl = d.understood_display or d.understood or d.problem
        cites = _citations(self.ctx, d)
        msgs = prompts.informal_messages(d.proof, nl, language())
        if cites:
            msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + cites["prompt"]}
        try:
            c = await io.complete("explain", msgs, None,
                                  temperature=0.4, max_tokens=2500, extra={"top_p": 0.9, **NO_THINK})
        except BrainError:
            return
        text = leancheck.clean_model_text(c.text)
        text = await self._check_citations(job, d, text, cites)
        if text:
            idx = d.add_informal_proof(text, c.model.key)
            await self.event(d, job, "informal", "Preuve rédigée en langage naturel par l'IA (la preuve Lean fait foi).",
                             ref=idx, model=c.model.key)


def _citations(ctx, d: Dossier) -> dict | None:
    """Keys the model may cite in this dossier's texts (research layer, S-E); None without references."""
    try:
        from ..research.biblio import citation_support
        return citation_support(ctx, d, language())
    except Exception:  # noqa: BLE001 (the research layer must never break the pipeline)
        return None


def model_key(m) -> str:
    """"provider:model_id" for a ModelRef (never its Python repr), the string itself otherwise."""
    if m is None:
        return ""
    key = getattr(m, "key", None)
    return key if isinstance(key, str) else str(m)


def _agent_fn():
    try:
        from ..brain.prover_agent import prove_with_agent  # type: ignore
        return prove_with_agent
    except Exception:  # noqa: BLE001 (S-B module absent or broken: goedel only)
        return None


def parse_split(text: str) -> list[dict]:
    """Lemmas proposed by a model for « split into lemmas »: [{title, statement}]."""
    code = leancheck.extract_code(text) or text
    out = []
    pending = ""
    for block in re.split(r"(?m)^(?=--|theorem\s|lemma\s)", code):
        b = block.strip()
        if b.startswith("--"):
            pending = b.split("\n", 1)[0].lstrip("- ").strip()
            rest = b.split("\n", 1)[1].strip() if "\n" in b else ""
            if not rest:
                continue
            b = rest
        if re.match(r"(theorem|lemma)\s", b):
            stmt = b.split(":= by", 1)[0].split(":=", 1)[0].rstrip() + " := by sorry"
            name = re.match(r"(?:theorem|lemma)\s+(\S+)", b).group(1)
            out.append({"title": pending or name, "statement": stmt.replace("lemma ", "theorem ", 1)})
            pending = ""
    return out
