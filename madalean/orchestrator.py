"""Jobs of different dossiers run in parallel, limited by the resource slots (ARCHITECTURE §6).

A dossier has at most one active job. Each job is an asyncio task carrying its id (`slots.CURRENT_JOB`) and its
priority (user-started first), so every slot it waits for is attributed to it. Cancelling a job cancels the task:
the model request is aborted and the Lean process killed. Finished jobs go to the dossier's history.

Sub-dossiers: when a lemma split from a parent (`parent_id`) ends and all the parent's children are finished, the
parent is retried automatically (proof + explanation) with the proven children given as library lemmas."""
from __future__ import annotations

import asyncio
import time

from . import repo
from .dossiers import PHASE_OF_STAGE, Dossier
from .i18n import msg
from .jobs import Job, JobHistory
from .logs import get
from .pipeline.runner import DossierPipeline
from .slots import CURRENT_JOB, CURRENT_PRIORITY

log = get("orchestrator")
KEEP_FINISHED = 200


class DossierBusy(Exception):
    def __init__(self, job: Job):
        super().__init__(job.id)
        self.job = job


class Orchestrator:
    def __init__(self, ctx, history: JobHistory):
        self.ctx = ctx
        self.history = history
        self.jobs: dict[str, Job] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.by_dossier: dict[str, str] = {}
        self._waits: dict[str, dict[str, list[str]]] = {}     # job id → owner → resources it waits for (D38)
        self.pipeline = DossierPipeline(ctx)
        ctx.slots.on_wait = self._on_wait
        self._now: dict[str, str] = {}                        # last `dossier.now` sent, per dossier (S-BG)
        repo.NOW[:] = [self.now_of]

    # ------------------------------------------------------------ queries
    def active(self) -> list[Job]:
        return [j for j in self.jobs.values() if j.active]

    def recent(self, n: int = 50) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.created, reverse=True)[:n]

    def active_for(self, dossier_id: str) -> Job | None:
        jid = self.by_dossier.get(dossier_id)
        return self.jobs.get(jid) if jid else None

    # ------------------------------------------------------------ « now » (docs/DOSSIER_FLOW.md, S-BG)
    def now_of(self, d: Dossier) -> dict | None:
        """Derived from the running job and the gate, never stored."""
        job = self.active_for(d.id)
        if job is None:
            g = d.extra.get("gate")
            if isinstance(g, dict) and g.get("state") == "pending":
                return {"phase": "understand" if g.get("kind") == "meaning" else "translate",
                        "run": (d.extra.get("gate_plan") or {}).get("run", ""), "attempt": 0,
                        "activity": f"gate.{g.get('kind')}", "params": {}, "model": "", "started": g.get("t"),
                        "waiting": "user", "side": []}
            return None
        row = next((r for r in reversed(job.timings) if r["stage"] == job.stage and r["end"] is None), None)
        phase = PHASE_OF_STAGE.get(job.stage, "understand")
        att = next((a for a in reversed(job.attempts) if a.stage == job.stage), None)
        asking = bool((job.conductor or {}).get("ask"))
        return {"phase": phase, "run": job.run, "attempt": (getattr(job, "phase_attempt", None) or {}).get(phase, 0),
                "activity": f"stage.{job.stage}" if job.stage else "", "params": {},
                "model": att.model if att is not None else "",
                "started": row["start"] if row else job.started or job.created,
                "waiting": "user" if asking else "quota" if job.waiting == "quota" else
                "slot" if job.waiting or job.state == "queued" else "",
                "side": [{"phase": PHASE_OF_STAGE.get(s, "prove"), "activity": f"stage.{s}", "params": {}}
                         for s in dict.fromkeys(job.stages) if s != job.stage]}

    def publish_now(self, dossier_id: str) -> None:
        d = self.ctx.repo.get(dossier_id)
        if d is None:
            return
        now = self.now_of(d)
        sig = repr(now)
        if self._now.get(dossier_id, "None") != sig:
            self._now.pop(dossier_id, None)
            self._now[dossier_id] = sig
            if len(self._now) > 2000:
                self._now.pop(next(iter(self._now)))
            self.ctx.publish("dossier.now", {"dossier_id": dossier_id, "now": now})

    async def history_for(self, dossier_id: str) -> list[Job]:
        done = await asyncio.to_thread(self.history.load, dossier_id)
        act = self.active_for(dossier_id)
        return done + ([act] if act else [])

    # ------------------------------------------------------------ control
    def submit(self, dossier_id: str, plan: list[dict], *, mode: str | None = None, strategy: str | None = None,
               user: bool = True, gates: bool | None = None, run: str = "", priority: int | None = None) -> Job:
        """`gates`: stop at the dossier's gates (D65) — by default for a person's jobs; bench, lemma plans and
        scripted runs pass False. `run`: the user request it continues (default: a new one). `priority`: slot
        priority (0 a person's job, 1 automatic, 2 « Attaque », D69: always served last)."""
        cur = self.active_for(dossier_id)
        if cur is not None:
            raise DossierBusy(cur)
        s = self.ctx.settings
        job = Job.new(dossier_id, plan, mode or s.mode, strategy or s.prove_strategy, user)
        job.gates = user if gates is None else gates
        job.run = run or job.id
        job.priority = priority if priority is not None else (0 if user else 1)
        self.jobs[job.id] = job
        self.by_dossier[dossier_id] = job.id
        self.tasks[job.id] = asyncio.create_task(self._run(job), name=f"job-{job.id}")
        self._trim()
        self.ctx.publish_job(job)
        log.info("job %s submitted for %s: %s (%s)", job.id, dossier_id, [p.get("stage") for p in plan], job.mode)
        return job

    async def cancel(self, job_id: str, wait: bool = True) -> bool:
        t = self.tasks.get(job_id)
        if t is None or t.done():
            return False
        t.cancel()
        if wait:
            try:
                await asyncio.wait_for(asyncio.shield(t), 15)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass
        return True

    async def cancel_dossier(self, dossier_id: str) -> bool:
        j = self.active_for(dossier_id)
        return await self.cancel(j.id) if j else False

    async def shutdown(self) -> None:
        for t in list(self.tasks.values()):
            t.cancel()
        if self.tasks:
            await asyncio.wait(list(self.tasks.values()), timeout=10)

    # ------------------------------------------------------------ internals
    def _on_wait(self, owner: str, resource: str, waiting: bool) -> None:
        # a stage running in parallel inside a job owns « <job id>#<stage> » (pipeline/runner.py, D38): the job waits
        # only while ALL its running stages wait (one stage waiting for the GPU while the proof search works is not
        # « en attente »)
        jid = owner.split("#", 1)[0]
        job = self.jobs.get(jid)
        if job is None or not job.active:
            return
        waits = self._waits.setdefault(jid, {})
        stack = waits.setdefault(owner, [])
        if waiting:
            stack.append(resource)
        elif resource in stack:
            stack.remove(resource)
        if not stack:
            del waits[owner]
        live = getattr(job, "live", None) or {jid}           # owners working right now (pipeline, D38)
        blocked = bool(waits) and len(waits) >= max(1, len(live))
        job.waiting = next(iter(waits.values()))[-1] if blocked else ""
        job.state = "queued" if blocked else "running"
        self.ctx.publish_job(job)

    def wait_recheck(self, job: Job) -> None:
        """Called by the pipeline when its set of running stages changes (D38)."""
        self._on_wait(job.id, "", False)

    def _trim(self) -> None:
        done = [j for j in self.jobs.values() if not j.active]
        if len(done) > KEEP_FINISHED:
            for j in sorted(done, key=lambda j: j.created)[: len(done) - KEEP_FINISHED]:
                self.jobs.pop(j.id, None)
                self.tasks.pop(j.id, None)

    async def _run(self, job: Job) -> None:
        CURRENT_JOB.set(job.id)
        CURRENT_PRIORITY.set(getattr(job, "priority", 0 if job.user else 1))
        job.state, job.started = "running", time.time()
        self.ctx.publish_job(job)
        d = self.ctx.repo.get(job.dossier_id)
        try:
            await self.pipeline.run(job)
            job.state = "failed" if job.error else "done"
        except asyncio.CancelledError:
            job.state, job.error = "cancelled", "cancelled"
            job.summary = msg("Arrêté à votre demande.")
            for a in job.attempts:
                if a.status in ("generating", "compiling"):
                    a.status = "cancelled"
            if d is not None:
                if d.status in ("translating", "proving"):
                    d.status = "proved" if d.proof_is_current else "stopped"
                try:
                    await self.pipeline.event(d, job, "info", "Arrêté à votre demande.")
                except Exception:  # noqa: BLE001
                    log.exception("could not record the cancellation")
        except Exception as e:  # noqa: BLE001
            log.exception("job %s crashed", job.id)
            job.state, job.error = "failed", "internal"
            job.summary = msg("Erreur interne : {err}", err=str(e)[:300])
            if d is not None:
                if d.status in ("translating", "proving"):
                    d.status = "failed"
                try:
                    await self.pipeline.event(d, job, "error", "Erreur interne : {err}", err=str(e)[:300])
                except Exception:  # noqa: BLE001
                    pass
        finally:
            job.ended = time.time()
            job.stage, job.waiting, job.stages = "", "", []
            self._waits.pop(job.id, None)
            streams = getattr(self.ctx, "streams", None)
            if streams is not None:
                streams.finish(job.id)
            # the job's parallel stages own « <job id>#<stage> » (D38): give back whatever any of them still holds
            subs = {h for hs in self.ctx.slots.holders.values() for h in hs if h.startswith(job.id + "#")}
            for owner in [job.id, *sorted(subs)]:
                try:
                    self.ctx.local.release_owner(owner)
                except Exception:  # noqa: BLE001
                    pass
                self.ctx.slots.release_all(owner)
            if self.by_dossier.get(job.dossier_id) == job.id:
                del self.by_dossier[job.dossier_id]
            # S-AO (D47): a dossier re-run many times gets its history compacted here, when no job holds an index
            dd = self.ctx.repo.get(job.dossier_id)
            if dd is not None and self.active_for(job.dossier_id) is None and hasattr(self.ctx.repo, "compact"):
                try:
                    await asyncio.shield(self.ctx.repo.compact(dd))
                except Exception:  # noqa: BLE001
                    log.exception("history compaction of %s failed", job.dossier_id)
            self.ctx.publish_job(job)
            try:
                await asyncio.shield(asyncio.to_thread(self.history.append, job))
            except Exception:  # noqa: BLE001
                log.exception("could not write job history")
            log.info("job %s %s", job.id, job.state)
        if job.state != "cancelled":
            await self._after(job)

    async def _after(self, job: Job) -> None:
        d = self.ctx.repo.get(job.dossier_id)
        if d is None or not d.parent_id:
            return
        parent = self.ctx.repo.get(d.parent_id)
        if parent is None or not parent.retry_parent or parent.proof_is_current or not parent.statement:
            return
        kids = self.ctx.repo.children(parent.id)
        if any(self.active_for(k.id) for k in kids):
            return
        proven = [k for k in kids if k.proof_is_current]
        if not proven or self.active_for(parent.id):
            return
        parent.retry_parent = False
        await self.pipeline.event(parent, None, "info", "Lemmes prouvés : {n}/{m}. Nouvel essai de la preuve avec ces "
                                  "lemmes.", n=len(proven), m=len(kids))
        try:
            self.submit(parent.id, [{"stage": "proof"}, {"stage": "explanation"}], user=False)
        except DossierBusy:
            pass
