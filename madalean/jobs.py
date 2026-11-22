"""Jobs: one run of the pipeline on a dossier (ARCHITECTURE §3). History is kept per dossier (last 50 jobs)."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config

STAGES = ("understand", "route", "statement", "proof", "explanation")
STATES = ("queued", "running", "done", "failed", "cancelled")
HISTORY = 50


@dataclass
class Attempt:
    index: int
    stage: str                       # statement | proof | …
    kind: str = "initial"            # initial | correction | refinement | translation | agent | recheck
    status: str = "generating"       # generating | compiling | accepted | rejected | error | cancelled
    summary: str = ""
    errors_text: str = ""
    code: str = ""
    raw: str = ""                    # model answer (capped)
    model: str = ""
    gen_seconds: float = 0.0
    compile_seconds: float = 0.0
    tokens: int = 0
    finish: str = ""
    round: int = -1                  # proof tournament round (0 = best models, 1… = races); -1 = no tournament
    t: float = field(default_factory=time.time)

    def to_dict(self, raw: bool = True) -> dict:
        d = asdict(self)
        if not raw:
            d.pop("raw")
        return d


@dataclass
class Job:
    id: str
    dossier_id: str
    plan: list[dict]                 # [{stage, request}] still to run (route may rewrite it)
    mode: str = "local"
    strategy: str = "auto"
    user: bool = True                # started by a person (served first) or automatically (sub-dossiers, retries)
    state: str = "queued"
    stage: str = ""
    waiting: str = ""                # resource the job is waiting for (gpu | online | lean), "" when running
    created: float = field(default_factory=time.time)
    started: float | None = None
    ended: float | None = None
    attempts: list[Attempt] = field(default_factory=list)
    done_stages: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)      # i18n message {key, params, text}
    error: str = ""                  # error kind (no_model, workspace, infra, cancelled…)
    tournament: dict = field(default_factory=dict)   # proof tournament: {round, models, state, winner, …} (S-J)
    # D38 (S-AF): stages running right now (several at once: guided reading, statement check, Mathlib search and proof
    # search run together); `stage` stays the main one. `timings`: one row per stage run
    # {stage, start, end, seconds} (unix seconds; end/seconds None while it runs) — read by scripts/perf_report.py
    stages: list[str] = field(default_factory=list)
    timings: list[dict] = field(default_factory=list)
    # S-AI (D41): who directs this request and what it costs: {by, name, tier, usd, cap, difficulty, summary,
    # plan: [{id, kind, goal, model, model_name, why, wave, depends_on, advisory, stage}], ask: {spent, cap, step} |
    # None (the cap question waiting for the user), state: planning | running | asking | off | done, final}
    conductor: dict = field(default_factory=dict)

    @classmethod
    def new(cls, dossier_id: str, plan: list[dict], mode: str, strategy: str, user: bool = True) -> "Job":
        return cls("j-" + uuid.uuid4().hex[:10], dossier_id, [dict(p) for p in plan], mode, strategy, user)

    @property
    def active(self) -> bool:
        return self.state in ("queued", "running")

    def to_dict(self, raw: bool = False) -> dict:
        d = asdict(self)
        d["attempts"] = [a.to_dict(raw) for a in self.attempts]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        d = dict(d)
        an = set(Attempt.__dataclass_fields__)
        d["attempts"] = [Attempt(**{k: v for k, v in a.items() if k in an}) for a in d.get("attempts", [])]
        names = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in names})


class JobHistory:
    """jobs/<dossier_id>.json = list of finished jobs, most recent last."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def load(self, dossier_id: str) -> list[Job]:
        try:
            data = json.loads((self.root / f"{dossier_id}.json").read_text(encoding="utf-8"))
            return [Job.from_dict(j) for j in data]
        except (OSError, ValueError, TypeError):
            return []

    def append(self, job: Job) -> None:
        jobs = self.load(job.dossier_id)
        jobs = [j for j in jobs if j.id != job.id] + [job]
        config.atomic_write_text(self.root / f"{job.dossier_id}.json",
                                 json.dumps([j.to_dict(raw=True) for j in jobs[-HISTORY:]], ensure_ascii=False))
