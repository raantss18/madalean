"""In-memory view of the dossiers and projects, backed by the JSON stores (single writer: the server).

Every mutation goes through `save()`, which writes the file in a worker thread (serialised per dossier) and
publishes `dossier.updated` so that every connected client sees the same thing."""
from __future__ import annotations

import asyncio
from typing import Callable

from .dossiers import Dossier, DossierStore
from .projects import Project, ProjectStore


NOW: list[Callable[[Dossier], dict | None]] = []      # set by the orchestrator (docs/DOSSIER_FLOW.md « now »)


def dossier_api(d: Dossier) -> dict:
    out = d.to_dict()
    out.setdefault("gate", None)                # docs/DOSSIER_FLOW.md (S-BG)
    out["now"] = NOW[0](d) if NOW else None
    out["current"] = {"statement": d.statement, "proof": d.proof, "explanation": d.explanation,
                      "statement_notes": d.notes, "informal_proof": d.informal_proof,
                      "proof_is_current": d.proof_is_current}
    return out


def dossier_summary(d: Dossier) -> dict:
    return {"id": d.id, "title": d.title, "project_id": d.project_id, "status": d.status, "parent_id": d.parent_id,
            "kind": d.kind, "theorem": d.theorem, "workspace": d.workspace, "created": d.created, "updated": d.updated,
            "archived": d.archived, "has_statement": bool(d.statement), "proved": d.proof_is_current,
            "gate": {k: d.extra["gate"].get(k) for k in ("id", "kind", "state")}
            if isinstance(d.extra.get("gate"), dict) else None,
            "now": NOW[0](d) if NOW else None}


class DossierRepo:
    def __init__(self, store: DossierStore, publish: Callable[[str, dict], None]):
        self.store = store
        self.publish = publish
        self.cache: dict[str, Dossier] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._gen: dict[str, int] = {}          # S-AO: changes saved per dossier (save calls) …
        self._written: dict[str, int] = {}      # … and the last one already on disk
        self.writes = self.coalesced = self.compactions = 0

    async def load_all(self) -> None:
        items = await asyncio.to_thread(self.store.list)
        self.cache = {d.id: d for d in items}
        for d in items:                       # S-AO (D47): migration of dossiers grown big before compaction existed
            try:
                await self.compact(d, publish=False)
            except Exception:  # noqa: BLE001 (never block the start on one dossier)
                import logging
                logging.getLogger("madalean.repo").exception("compaction of %s failed", d.id)

    async def compact(self, d: Dossier, publish: bool = True) -> bool:
        """S-AO (D47): compact a dossier's history when it is over the limits (madalean/history.py): the removed
        versions and events are appended to its archive first, then the dossier is written. Call only when no job
        works on it (version indices move); a save in progress is waited for. Returns True when it changed."""
        from . import history
        if not history.needs(d):
            return False
        lock = self._locks.setdefault(d.id, asyncio.Lock())
        async with lock:
            rec = history.compact(d)
            if rec is None:
                return False
            await asyncio.to_thread(self.store.archive_append, d.id, rec)
            self.compactions += 1
        await self.save(d, publish=publish)
        return True

    def get(self, did: str) -> Dossier | None:
        return self.cache.get(did)

    def list(self, project_id: str | None = None, include_archived: bool = True) -> list[Dossier]:
        out = [d for d in self.cache.values() if (project_id is None or d.project_id == project_id)
               and (include_archived or not d.archived)]
        return sorted(out, key=lambda d: d.updated, reverse=True)

    def children(self, did: str) -> list[Dossier]:
        return [d for d in self.cache.values() if d.parent_id == did]

    def new(self, problem: str = "", workspace: str = "", title: str = "") -> Dossier:
        d = self.store.new(problem, workspace, title)
        while d.id in self.cache:
            d = self.store.new(problem, workspace, title)
        return d

    async def save(self, d: Dossier, publish: bool = True) -> None:
        """Write the dossier (atomic replace) before returning. S-AO (D47): saves that queue up behind a write in
        progress are coalesced — the first of them to get the lock serialises the dossier as it is then (every
        earlier change included) and the others return without writing again."""
        self.cache[d.id] = d
        lock = self._locks.setdefault(d.id, asyncio.Lock())
        mine = self._gen[d.id] = self._gen.get(d.id, 0) + 1
        async with lock:
            if self._written.get(d.id, 0) < mine:
                gen = self._gen[d.id]
                text = d.to_json()
                await asyncio.to_thread(self._write, d.id, text)
                self._written[d.id] = gen
                self.writes += 1
            else:
                self.coalesced += 1
        if publish:
            self.publish("dossier.updated", {"dossier": dossier_api(d)})

    def _write(self, did: str, text: str) -> None:
        from . import config
        config.atomic_write_text(self.store.root / f"{did}.json", text)

    async def delete(self, did: str) -> bool:
        ok = await asyncio.to_thread(self.store.delete, did)
        if ok:
            self.cache.pop(did, None)
            self.publish("dossier.deleted", {"id": did})
        return ok

    async def restore(self, did: str) -> Dossier | None:
        ok = await asyncio.to_thread(self.store.undelete, did)
        if not ok:
            return None
        d = await asyncio.to_thread(self.store.load, did)
        if d is not None:
            self.cache[d.id] = d
            self.publish("dossier.updated", {"dossier": dossier_api(d)})
        return d


class ProjectRepo:
    def __init__(self, store: ProjectStore, publish: Callable[[str, dict], None]):
        self.store = store
        self.publish = publish
        self.cache: dict[str, Project] = {}

    async def load_all(self) -> None:
        self.cache = {p.id: p for p in await asyncio.to_thread(self.store.list)}

    def get(self, pid: str) -> Project | None:
        return self.cache.get(pid)

    def list(self) -> list[Project]:
        return sorted(self.cache.values(), key=lambda p: p.updated, reverse=True)

    async def save(self, p: Project) -> None:
        self.cache[p.id] = p
        await asyncio.to_thread(self.store.save, p)
        self.publish("project.updated", {"project": p.to_dict()})

    async def delete(self, pid: str) -> bool:
        ok = await asyncio.to_thread(self.store.delete, pid)
        if ok:
            self.cache.pop(pid, None)
            self.publish("project.deleted", {"id": pid})
        return ok

    async def restore(self, pid: str) -> Project | None:
        if not await asyncio.to_thread(self.store.undelete, pid):
            return None
        p = await asyncio.to_thread(self.store.load, pid)
        if p:
            self.cache[p.id] = p
            self.publish("project.updated", {"project": p.to_dict()})
        return p
