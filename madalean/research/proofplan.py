"""Guided proof design (ARCHITECTURE §14) — session S-G.

A proof plan is a tree attached to a dossier: the root is the dossier's goal, below it intermediate claims (natural-
language statement, why it helps, proposed Lean statement), down to leaves. The brain drafts it (agent mode when the
engine has it, with Mathlib search as a tool; an optional proof sketch — e.g. a paper's proof — is given as a hint);
the user edits, reorders, adds, deletes, accepts nodes; every change is a new plan version (manual edits are never
overwritten without `force`).

Submitting creates one sub-dossier per accepted node (`parent_id` = the parent node's dossier, the parent's `uses`
lists its children, `retry_parent` set): the orchestrator's existing sub-dossier logic re-runs a parent when its
children are finished, with the proven children forced in as library lemmas. Leaves are started by a scheduler that
keeps at most `limit` of them in the orchestrator at once (resource slots are still the orchestrator's); a subtree can
be cancelled. A failed leaf can be re-planned (split further) or marked « admitted for now »:

    proved modulo admitted lemmas — the parent's proof is checked by Lean with the admitted lemmas stated with
    `sorry`. That check never enters `dossier.proofs`: the strict verdict (leancheck.judge) rejects it (`sorry`,
    axiom `sorryAx`), the dossier is NOT proved, and the conditional state is explicit in data:
    `dossier.extra["conditional_proof"] = {verdict: "proved_modulo", admitted: [...], strict_ok: false, axioms}`.
    When every admitted lemma later gets a real, sorry-free proof (library entry), the parent proof is re-checked
    with the real lemma code under the strict verdict, and only then becomes the dossier's proof."""
from __future__ import annotations

import asyncio
import copy
import json
import re
import time
import uuid
from pathlib import Path

from .. import config, leancheck
from ..i18n import msg

MARK = "[madalean:proofplan]"
EDITABLE = ("title", "statement_nl", "why", "lean")


class PlanError(Exception):
    def __init__(self, kind: str, status: int = 400, key: str = "", **data):
        super().__init__(kind)
        self.kind, self.status, self.key, self.data = kind, status, key, data


def _nid() -> str:
    return "pn-" + uuid.uuid4().hex[:8]


def node(title: str, statement_nl: str = "", why: str = "", lean: str = "", parent: str | None = None) -> dict:
    return {"id": _nid(), "parent": parent, "children": [], "title": title[:200], "statement_nl": statement_nl[:5000],
            "why": why[:3000], "lean": lean[:20000], "status": "draft", "dossier_id": "", "admitted": False,
            "edited": False, "cancelled": False}


# ---------------------------------------------------------------- store (one JSON file per dossier, all versions)
class PlanStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache: dict[str, dict] = {}

    def _path(self, did: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", did):
            raise PlanError("bad_id")
        return self.root / f"{did}.json"

    def load(self, did: str) -> dict | None:
        if did in self.cache:
            return self.cache[did]
        try:
            data = json.loads(self._path(did).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        self.cache[did] = data
        return data

    def save(self, data: dict) -> None:
        self.cache[data["dossier_id"]] = data
        config.atomic_write_text(self._path(data["dossier_id"]), json.dumps(data, ensure_ascii=False, indent=1))

    def current(self, did: str) -> dict | None:
        data = self.load(did)
        return data["versions"][-1] if data and data["versions"] else None

    def push(self, did: str, plan: dict, *, source: str, model: str = "", device: str = "", note: str = "") -> dict:
        data = self.load(did) or {"dossier_id": did, "versions": []}
        plan = copy.deepcopy(plan)
        plan.update({"rev": len(data["versions"]) + 1, "t": time.time(), "source": source, "model": model,
                     "device": device, "note": note[:500], "dossier_id": did})
        data["versions"].append(plan)
        self.save(data)
        return plan


def subtree(plan: dict, nid: str) -> list[str]:
    out, stack = [], [nid]
    while stack:
        x = stack.pop()
        if x in plan["nodes"]:
            out.append(x)
            stack += plan["nodes"][x]["children"]
    return out


def depth_first(plan: dict) -> list[str]:
    out = []

    def walk(x: str) -> None:
        out.append(x)
        for c in plan["nodes"][x]["children"]:
            if c in plan["nodes"]:
                walk(c)
    walk(plan["root"])
    return out


# ---------------------------------------------------------------- prompts / parsing
def draft_messages(goal_nl: str, lean: str, hint: str = "", sketch: str = "", max_depth: int = 2) -> list[dict]:
    return [{"role": "user", "content": (
        f"{MARK} task=draft\nYou design the proof of a theorem before anyone writes Lean. Break it into intermediate "
        f"claims (lemmas), at most {max_depth} levels deep, each strictly easier than its parent, so that the parent "
        "follows from its children quickly.\nTheorem: " + (goal_nl or "(see the Lean statement)") + "\n"
        + (f"Lean statement:\n```lean\n{lean}\n```\n" if lean else "")
        + (f"Proof sketch to follow (from a paper or the user):\n{sketch}\n" if sketch else "")
        + (f"Hint: {hint}\n" if hint else "")
        + "For each claim give: title, statement (precise natural language), why (how it helps the parent), lean "
          "(a Lean 4 + Mathlib statement `theorem name … := by sorry`, self-contained), children (sub-claims, may be "
          "empty). Answer with JSON only: {\"claims\": [{\"title\":…, \"statement\":…, \"why\":…, \"lean\":…, "
          "\"children\": […]}]}")}]


def parse_claims(text: str) -> list[dict]:
    text = leancheck.clean_model_text(text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    claims = data.get("claims") if isinstance(data, dict) else None
    return claims if isinstance(claims, list) else []


def claims_to_nodes(plan: dict, parent: str, claims: list, depth: int = 0) -> None:
    for c in claims[:12]:
        if not isinstance(c, dict) or not (c.get("title") or c.get("statement")):
            continue
        n = node(str(c.get("title") or c.get("statement"))[:200], str(c.get("statement", "")), str(c.get("why", "")),
                 str(c.get("lean") or ""), parent)
        plan["nodes"][n["id"]] = n
        plan["nodes"][parent]["children"].append(n["id"])
        if depth < 3 and isinstance(c.get("children"), list):
            claims_to_nodes(plan, n["id"], c["children"], depth + 1)


def new_plan(d) -> dict:
    root = node(d.title, d.understood_display or d.understood or d.problem, "", d.statement, None)
    root["status"] = "accepted"
    root["dossier_id"] = d.id
    return {"root": root["id"], "nodes": {root["id"]: root}}


# ---------------------------------------------------------------- planner
class Planner:
    def __init__(self, ctx, store: PlanStore, limit: int | None = None):
        self.ctx, self.store = ctx, store
        caps = getattr(ctx.slots, "caps", {}) or {}
        self.limit = limit or max(1, min(4, int(caps.get("online", 3)) + int(caps.get("gpu", 1))))
        self.queues: dict[str, list[tuple[str, list[dict]]]] = {}     # plan dossier -> [(dossier id, job plan)]
        self.runners: dict[str, asyncio.Task] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    # -- views
    def node_state(self, n: dict) -> dict:
        d = self.ctx.repo.get(n["dossier_id"]) if n.get("dossier_id") else None
        st = n["status"]
        cond = (d.extra.get("conditional_proof") if d is not None else None) or None
        if n.get("cancelled"):
            st = "stopped"
        if d is not None:
            act = self.ctx.orchestrator.active_for(d.id)
            if d.proof_is_current:
                st = "proved"
            elif n.get("cancelled") and act is None:
                st = "stopped"
            elif n.get("admitted"):
                st = "admitted"
            elif cond and cond.get("verdict") == "proved_modulo":
                st = "proved_modulo"
            elif act is not None:
                st = "proving"
            elif any(x == d.id for x, _p in sum(self.queues.values(), [])):
                st = "queued"
            elif d.status in ("failed", "stopped"):
                st = "failed" if d.status == "failed" else "stopped"
            elif n["status"] in ("accepted", "submitted"):
                st = "submitted" if n["status"] == "submitted" else st
        return {**n, "state": st, "proved": bool(d is not None and d.proof_is_current),
                "conditional": cond, "dossier_status": d.status if d is not None else ""}

    def public(self, did: str) -> dict | None:
        p = self.store.current(did)
        if p is None:
            return None
        nodes = {k: self.node_state(v) for k, v in p["nodes"].items()}
        root = nodes[p["root"]]
        d = self.ctx.repo.get(did)
        cond = (d.extra.get("conditional_proof") if d is not None else None) or None
        admitted = [n for n in nodes.values() if n["state"] == "admitted"]
        if d is not None and d.proof_is_current:
            verdict = {"state": "proved", "verified": True, "admitted": 0}
        elif cond and cond.get("verdict") == "proved_modulo":
            verdict = {"state": "proved_modulo", "verified": False, "admitted": len(cond.get("admitted", [])),
                       "admitted_names": cond.get("admitted", [])}
        else:
            verdict = {"state": "open", "verified": False, "admitted": len(admitted)}
        data = self.store.load(did) or {"versions": []}
        return {**p, "nodes": nodes, "root_state": root["state"], "verdict": verdict,
                "versions": [{"rev": v["rev"], "t": v["t"], "source": v["source"], "model": v.get("model", ""),
                              "device": v.get("device", ""), "note": v.get("note", "")} for v in data["versions"]],
                "queued": [x for x, _p in self.queues.get(did, [])], "limit": self.limit}

    def publish(self, did: str) -> None:
        pub = self.public(did)
        if pub is not None:
            self.ctx.publish("plan.updated", {"dossier_id": did, "plan": pub})

    def _cur(self, did: str, base_rev: int | None = None) -> dict:
        p = self.store.current(did)
        if p is None:
            raise PlanError("no_plan", 404)
        if base_rev is not None and base_rev != p["rev"]:
            raise PlanError("conflict", 409, current=self.public(did))
        return copy.deepcopy(p)

    def _push(self, did: str, plan: dict, source: str, device: str = "", model: str = "", note: str = "") -> dict:
        self.store.push(did, plan, source=source, model=model, device=device, note=note)
        self.publish(did)
        return self.public(did)

    # -- drafting
    async def _ask(self, messages: list[dict], mode: str, owner: str) -> tuple[str, str]:
        brain = self.ctx.brain
        use_agent = mode != "local" and hasattr(brain, "run_agent") and self.ctx.settings.prove_strategy != "goedel"
        if use_agent:
            from ..brain.api import ToolSpec
            ws = self.ctx.settings.workspace

            async def search(args: dict) -> str:
                hits = await self.ctx.retriever.search(ws, str(args.get("query", "")), 8) if self.ctx.retriever else []
                return json.dumps([{k: h.get(k) for k in ("name", "signature", "doc")} for h in hits or []])
            tools = [ToolSpec("search_mathlib", "Search Mathlib declarations (name, signature, docstring).",
                              {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                              search)]
            need = True
            try:
                await self.ctx.slots.acquire("online", owner)
                res = await brain.run_agent("prove", "You plan proofs. Answer with the requested JSON only.",
                                            messages[0]["content"], tools, mode=mode, max_steps=8, max_seconds=300)
                return res.final_text, res.model.key
            except Exception:  # noqa: BLE001 (agent unavailable: one plain completion)
                pass
            finally:
                if need:
                    self.ctx.slots.release("online", owner)
        from ..server.helpers import complete_once
        c = await complete_once(self.ctx, "prove", messages, mode, owner=owner, max_tokens=4000, temperature=0.5)
        return c.text, c.model.key

    async def draft(self, d, *, hint: str = "", sketch: str = "", mode: str | None = None, force: bool = False,
                    device: str = "") -> dict:
        cur = self.store.current(d.id)
        if cur is not None and not force and any(n.get("edited") for n in cur["nodes"].values()):
            raise PlanError("would_overwrite", 409, "Le plan contient des modifications manuelles : confirmez pour "
                                                    "créer une nouvelle version proposée par l'IA (l'ancienne reste "
                                                    "disponible).")
        mode = mode or self.ctx.settings.mode
        text, model = await self._ask(draft_messages(d.understood_display or d.understood or d.problem, d.statement,
                                                     hint, sketch), mode, f"plan-{d.id}")
        claims = parse_claims(text)
        if not claims:
            raise PlanError("no_plan_proposed", 422, "Le modèle n'a proposé aucun plan utilisable.")
        plan = new_plan(d)
        claims_to_nodes(plan, plan["root"], claims)
        return self._push(d.id, plan, "sketch" if sketch else "ai", device, model,
                          note=(hint or sketch[:200]))

    async def replan(self, did: str, nid: str, *, hint: str = "", mode: str | None = None, base_rev: int | None = None,
                     device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        n = plan["nodes"].get(nid)
        if n is None:
            raise PlanError("not_found", 404)
        text, model = await self._ask(draft_messages(n["statement_nl"] or n["title"], n["lean"], hint, "", 1),
                                      mode or self.ctx.settings.mode, f"plan-{did}")
        claims = parse_claims(text)
        if not claims:
            raise PlanError("no_plan_proposed", 422, "Le modèle n'a proposé aucun plan utilisable.")
        claims_to_nodes(plan, nid, claims)
        n["admitted"] = False
        return self._push(did, plan, "ai", device, model, note=f"replan {nid}")

    # -- manual edits
    def create_empty(self, d, device: str = "") -> dict:
        if self.store.current(d.id) is not None:
            return self.public(d.id)
        return self._push(d.id, new_plan(d), "user", device)

    def edit_node(self, did: str, nid: str, fields: dict, base_rev: int | None, device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        n = plan["nodes"].get(nid)
        if n is None:
            raise PlanError("not_found", 404)
        bad = [k for k in fields if k not in EDITABLE or not isinstance(fields[k], str)]
        if bad:
            raise PlanError("bad_fields", 400, fields=bad)
        if n.get("dossier_id") and nid != plan["root"] and "lean" in fields and fields["lean"] != n["lean"]:
            raise PlanError("submitted", 409, "Ce nœud a déjà son dossier : modifiez l'énoncé dans le dossier.")
        for k, v in fields.items():
            n[k] = v[:20000]
        n["edited"] = True
        return self._push(did, plan, "user", device, note=f"edit {nid}")

    def add_node(self, did: str, parent: str, fields: dict, index: int | None, base_rev: int | None,
                 device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        if parent not in plan["nodes"]:
            raise PlanError("not_found", 404)
        n = node(str(fields.get("title") or fields.get("statement_nl") or "?"), str(fields.get("statement_nl", "")),
                 str(fields.get("why", "")), str(fields.get("lean", "")), parent)
        n["edited"] = True
        plan["nodes"][n["id"]] = n
        kids = plan["nodes"][parent]["children"]
        kids.insert(len(kids) if index is None else max(0, min(int(index), len(kids))), n["id"])
        return self._push(did, plan, "user", device, note=f"add {n['id']}")

    def delete_node(self, did: str, nid: str, base_rev: int | None, device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        if nid == plan["root"] or nid not in plan["nodes"]:
            raise PlanError("not_found" if nid not in plan["nodes"] else "bad_node", 404 if nid not in plan["nodes"]
                            else 400)
        sub = subtree(plan, nid)
        if any(plan["nodes"][x].get("dossier_id") and self.ctx.orchestrator.active_for(plan["nodes"][x]["dossier_id"])
               for x in sub):
            raise PlanError("busy", 409)
        par = plan["nodes"][nid]["parent"]
        plan["nodes"][par]["children"].remove(nid)
        for x in sub:
            del plan["nodes"][x]
        return self._push(did, plan, "user", device, note=f"delete {nid}")

    def move_node(self, did: str, nid: str, parent: str, index: int | None, base_rev: int | None,
                  device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        if nid == plan["root"] or nid not in plan["nodes"] or parent not in plan["nodes"]:
            raise PlanError("not_found", 404)
        if parent in subtree(plan, nid):
            raise PlanError("cycle", 400)
        old = plan["nodes"][nid]["parent"]
        plan["nodes"][old]["children"].remove(nid)
        kids = plan["nodes"][parent]["children"]
        kids.insert(len(kids) if index is None else max(0, min(int(index), len(kids))), nid)
        plan["nodes"][nid]["parent"] = parent
        plan["nodes"][nid]["edited"] = True
        return self._push(did, plan, "user", device, note=f"move {nid}")

    def set_status(self, did: str, nids: list[str], status: str, base_rev: int | None, device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        for nid in nids:
            if nid not in plan["nodes"]:
                raise PlanError("not_found", 404)
            if nid != plan["root"]:
                plan["nodes"][nid]["status"] = status
        return self._push(did, plan, "user", device, note=f"{status} {','.join(nids)[:200]}")

    def restore_version(self, did: str, rev: int, device: str = "") -> dict:
        data = self.store.load(did)
        if not data or not 1 <= rev <= len(data["versions"]):
            raise PlanError("not_found", 404)
        return self._push(did, copy.deepcopy(data["versions"][rev - 1]), "user", device, note=f"restore {rev}")

    # -- submission and scheduling
    async def submit(self, did: str, nids: list[str] | None, base_rev: int | None, device: str = "",
                     mode: str | None = None) -> dict:
        from ..server.routes_work import create_dossier
        plan = self._cur(did, base_rev)
        root_d = self.ctx.repo.get(did)
        if root_d is None:
            raise PlanError("not_found", 404)
        order = [x for x in depth_first(plan) if x != plan["root"]]
        chosen = set(nids or [x for x in order if plan["nodes"][x]["status"] == "accepted"])
        chosen = {x for x in chosen if x in plan["nodes"] and not plan["nodes"][x].get("dossier_id")}
        if not chosen:
            raise PlanError("nothing_to_submit", 422, "Acceptez d'abord au moins un nœud du plan.")
        created = []
        for x in order:                                # parents before children: parent dossier ids exist
            if x not in chosen:
                continue
            n = plan["nodes"][x]
            par = plan["nodes"][n["parent"]]
            parent_d = self.ctx.repo.get(par.get("dossier_id") or "") if par.get("dossier_id") else None
            if parent_d is None:
                continue                               # its parent was not submitted: skip (not reachable)
            spec = {"title": n["title"], "problem": n["statement_nl"] or n["title"], "statement": n["lean"],
                    "project_id": root_d.project_id, "workspace": root_d.workspace, "parent_id": parent_d.id,
                    "kind": "lemma", "start": False}
            try:
                child, _job = await create_dossier(self.ctx, spec)
            except leancheck.StatementError:
                spec["statement"] = ""
                child, _job = await create_dossier(self.ctx, spec)
            child.extra["plan"] = {"plan_dossier": did, "node": x}
            await self.ctx.repo.save(child)
            n["dossier_id"], n["status"] = child.id, "submitted"
            if child.id not in parent_d.uses:
                parent_d.uses.append(child.id)
            parent_d.retry_parent = True
            await self.ctx.repo.save(parent_d)
            created.append(x)
        plan_pub = self._push(did, plan, "user", device, note=f"submit {len(created)}")
        plan = self.store.current(did)
        q = self.queues.setdefault(did, [])
        for x in created:
            n = plan["nodes"][x]
            kids_submitted = [c for c in n["children"] if plan["nodes"][c].get("dossier_id")]
            dd = self.ctx.repo.get(n["dossier_id"])
            if kids_submitted:
                if not dd.statement:                   # internal node: formalise now, prove after its children
                    q.append((dd.id, [{"stage": "understand"}, {"stage": "statement"}]))
                dd.retry_parent = True
                await self.ctx.repo.save(dd)
                continue
            jp = ([{"stage": "proof"}, {"stage": "explanation"}] if dd.statement else
                  [{"stage": "understand"}, {"stage": "statement"}, {"stage": "proof"}, {"stage": "explanation"}])
            q.append((dd.id, jp))
        self._kick(did, mode)
        return {"plan": self.public(did), "submitted": created}

    def _kick(self, did: str, mode: str | None = None) -> None:
        t = self.runners.get(did)
        if t is None or t.done():
            self.runners[did] = self.ctx.spawn(self._schedule(did, mode))

    async def _schedule(self, did: str, mode: str | None) -> None:
        """Keep at most `limit` jobs of this plan in the orchestrator; the slots still decide what really runs."""
        from ..orchestrator import DossierBusy
        started: set[str] = set()
        while self.queues.get(did):
            active = sum(1 for x in started if self.ctx.orchestrator.active_for(x) is not None)
            q = self.queues[did]
            changed = False
            while q and active < self.limit:
                x, jp = q.pop(0)
                try:
                    self.ctx.orchestrator.submit(x, jp, mode=mode, user=False)
                    started.add(x)
                    active += 1
                except DossierBusy:
                    started.add(x)
                changed = True
            if changed:
                self.publish(did)
            await asyncio.sleep(0.2)
        self.publish(did)

    async def cancel(self, did: str, nid: str, device: str = "") -> dict:
        plan = self._cur(did)
        if nid not in plan["nodes"]:
            raise PlanError("not_found", 404)
        sub = subtree(plan, nid)
        ids = {plan["nodes"][x]["dossier_id"] for x in sub if plan["nodes"][x].get("dossier_id")}
        if nid == plan["root"]:
            ids.discard(did)
        self.queues[did] = [(x, jp) for x, jp in self.queues.get(did, []) if x not in ids]
        for x in ids:
            await self.ctx.orchestrator.cancel_dossier(x)
            dd = self.ctx.repo.get(x)
            if dd is not None and dd.retry_parent:
                dd.retry_parent = False
                await self.ctx.repo.save(dd)
        for x in sub:
            if x != plan["root"]:
                plan["nodes"][x]["cancelled"] = True
        return self._push(did, plan, "user", device, note=f"cancel {nid}")

    # -- admitted lemmas: conditional proofs, never verified
    def admit(self, did: str, nid: str, base_rev: int | None, device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        n = plan["nodes"].get(nid)
        if n is None or nid == plan["root"]:
            raise PlanError("not_found", 404)
        dd = self.ctx.repo.get(n.get("dossier_id") or "")
        if dd is None or not dd.statement:
            raise PlanError("no_statement", 409, "Un lemme admis doit avoir un énoncé Lean accepté.")
        if dd.proof_is_current:
            raise PlanError("already_proved", 409)
        n["admitted"], n["cancelled"] = True, False
        return self._push(did, plan, "user", device, note=f"admit {nid}")

    def unadmit(self, did: str, nid: str, base_rev: int | None, device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        if nid not in plan["nodes"]:
            raise PlanError("not_found", 404)
        plan["nodes"][nid]["admitted"] = False
        return self._push(did, plan, "user", device, note=f"unadmit {nid}")

    def _children_material(self, plan: dict, nid: str) -> tuple[list, list[str], list[str]]:
        """(library entries of proven children, admitted lemma declarations with sorry, admitted names)."""
        entries, admitted_decls, names = [], [], []
        for c in plan["nodes"][nid]["children"]:
            cn = plan["nodes"].get(c)
            dd = self.ctx.repo.get(cn.get("dossier_id") or "") if cn else None
            if dd is None:
                continue
            if dd.proof_is_current:
                e = next((e for e in self.ctx.library.entries if e.dossier == dd.id), None)
                if e is not None:
                    entries.append(e)
            elif cn.get("admitted") and dd.statement:
                sig = leancheck.remove_comments(dd.statement)
                sig = sig[sig.rfind("theorem"):].strip()
                admitted_decls.append(f"-- admitted for now (plan): {cn['title']}\n{sig}")
                names.append(leancheck.theorem_name(dd.statement))
        return entries, admitted_decls, names

    @staticmethod
    def conditional_statement(parent_statement: str, entries: list, admitted_decls: list[str]) -> str:
        from ..dossiers import with_lemmas
        st = with_lemmas(parent_statement, entries)
        starts = [m.start() for m in re.finditer(r"(?m)^theorem\s", st)]
        cut = starts[-1]
        return st[:cut] + "\n\n".join(admitted_decls) + ("\n\n" if admitted_decls else "") + st[cut:]

    async def prove_modulo(self, did: str, nid: str | None = None, *, attempts: int = 4, mode: str | None = None,
                           code: str | None = None) -> dict:
        """Search a proof of node `nid` (default: the root) using its proven children AND its admitted children
        (stated with `sorry`). Success = `proved_modulo`, recorded in data, never as a verified proof."""
        from ..server.helpers import complete_once
        plan = self._cur(did)
        nid = nid or plan["root"]
        n = plan["nodes"].get(nid)
        dd = self.ctx.repo.get(n.get("dossier_id") or "") if n else None
        if dd is None or not dd.statement:
            raise PlanError("no_statement", 409)
        entries, decls, names = self._children_material(plan, nid)
        if not names:
            raise PlanError("no_admitted", 409, "Aucun lemme admis sous ce nœud.")
        ws = self.ctx.workspace(dd.workspace or self.ctx.settings.workspace)
        if ws is None:
            raise PlanError("no_workspace", 409)
        from ..dossiers import closure
        entries = closure(self.ctx.library, entries)
        statement = leancheck.prepare_statement(self.conditional_statement(dd.statement, entries, decls))
        name = leancheck.theorem_name(statement)
        lk = self.locks.setdefault(did, asyncio.Lock())
        if lk.locked():
            raise PlanError("busy", 409)
        async with lk:
            tried = []
            for i in range(max(1, min(attempts, 8))):
                model = ""
                if code is None or i > 0:
                    if code is not None:
                        break
                    c = await complete_once(self.ctx, "prove", [{"role": "user",
                                                                 "content": leancheck.initial_prompt(statement)}],
                                            mode or self.ctx.settings.mode, owner=f"plan-mod-{did}",
                                            max_tokens=8000, temperature=1.0)
                    body, model = leancheck.extract_code(c.text), c.model.key
                    if not body:
                        tried.append({"ok": False, "why": "no code"})
                        continue
                else:
                    body = code
                try:
                    full = leancheck.assemble_proof(statement, body)
                except leancheck.StatementError as e:
                    tried.append({"ok": False, "why": str(e)})
                    continue
                res = await self.check_conditional(full, name, ws, names)
                tried.append({"ok": res["ok"], "why": res.get("why", ""), "model": model})
                if res["ok"]:
                    cond = {"verdict": "proved_modulo", "admitted": names, "code": full, "theorem": name,
                            "axioms": res["axioms"], "strict_ok": res["strict_ok"], "strict_summary":
                            res["strict_summary"], "checked": time.time(), "model": model, "plan_node": nid,
                            "workspace": ws.key}
                    dd.extra["conditional_proof"] = cond
                    m = msg("Prouvé modulo {n} lemme(s) admis ({names}) : ce n'est PAS une preuve vérifiée.",
                            n=len(names), names=", ".join(names))
                    dd.add_event("info", m["text"], key=m["key"], params=m["params"], model=model)
                    await self.ctx.repo.save(dd)
                    self.publish(did)
                    return {"ok": True, "conditional": cond, "tries": tried}
            return {"ok": False, "tries": tried}

    async def check_conditional(self, code: str, name: str, ws, admitted: list[str]) -> dict:
        """Lean check of a proof that may rely on admitted lemmas. ok = no error, the target's own proof has no
        forbidden construct, and its axioms are the standard ones plus `sorryAx` (from the admitted lemmas). The
        strict verdict of the same output is computed too: it is always a rejection when sorryAx is involved."""
        r = await self.ctx.lean.check(leancheck.with_axiom_probe(code, name), ws, self.ctx.settings.compile_timeout_s,
                                      None, owner=f"plan-check-{name}")
        msgs = leancheck.parse_lean_json(r.stdout) if r.stdout else []
        strict = leancheck.judge(leancheck.with_axiom_probe(code, name), msgs or r.verdict.errors, name, 0)
        res = r.to_dict()
        if res["errors"] or res["timed_out"] or res["infra_error"]:
            return {"ok": False, "why": "; ".join(e["text"][:200] for e in res["errors"][:3]) or res["infra_error"]
                    or "timeout", "strict_ok": False, "strict_summary": strict.summary, "axioms": None}
        target = leancheck.remove_comments(code)
        target = target[target.rfind(f"theorem {name}"):]
        if leancheck.forbidden_reasons(target):
            return {"ok": False, "why": "forbidden: " + ", ".join(leancheck.forbidden_reasons(target)),
                    "strict_ok": strict.ok, "strict_summary": strict.summary, "axioms": strict.axioms}
        axioms = strict.axioms
        if axioms is None:
            return {"ok": False, "why": "axioms unknown", "strict_ok": False, "strict_summary": strict.summary,
                    "axioms": None}
        bad = [a for a in axioms if a not in leancheck.ALLOWED_AXIOMS | {"sorryAx"}]
        if bad:
            return {"ok": False, "why": "axioms: " + ", ".join(bad), "strict_ok": False,
                    "strict_summary": strict.summary, "axioms": axioms}
        return {"ok": True, "axioms": axioms, "strict_ok": strict.ok, "strict_summary": strict.summary}

    async def upgrade_conditional(self, did: str) -> dict:
        """When every admitted lemma of a conditional proof has a real proof (library entry), re-check the parent
        proof with the real lemma code under the STRICT verdict; only then it becomes the dossier's proof."""
        dd = self.ctx.repo.get(did)
        cond = (dd.extra.get("conditional_proof") if dd is not None else None) or None
        if not cond or cond.get("verdict") != "proved_modulo" or dd.proof_is_current:
            return {"upgraded": False, "reason": "nothing"}
        lib = self.ctx.library
        real = {nm: lib.get(nm) for nm in cond["admitted"]}
        if any(e is None for e in real.values()):
            return {"upgraded": False, "reason": "admitted_unproved",
                    "missing": [k for k, e in real.items() if e is None]}
        code = cond["code"]
        for nm, e in real.items():
            code = re.sub(r"-- admitted for now \(plan\):[^\n]*\n", "", code)
            pat = re.compile(rf"(?ms)^theorem\s+{re.escape(nm)}\b.*?:=\s*by\s+sorry\s*$")
            code = pat.sub(lambda _m: e.code.strip(), code, count=1)
        ws = self.ctx.workspace(cond.get("workspace") or dd.workspace)
        name = cond["theorem"]
        r = await self.ctx.lean.check(leancheck.with_axiom_probe(code, name), ws, self.ctx.settings.compile_timeout_s,
                                      name, owner=f"plan-up-{did}")
        if not r.verdict.ok:
            cond["upgrade_failed"] = {"t": time.time(), "summary": r.verdict.summary}
            await self.ctx.repo.save(dd)
            return {"upgraded": False, "reason": "strict_rejected", "check": r.to_dict()}
        from ..runtime.lean import workspace_info
        info = workspace_info(ws)
        meta = {"axioms": r.verdict.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
                "workspace": ws.key, "seconds": round(r.seconds, 1), "strategy": "plan", "attempts": 1,
                "checked": time.time()}
        idx = dd.add_proof(code, note="proof plan: admitted lemmas now proved", model=cond.get("model", ""),
                           meta=meta)
        dd.status = "proved"
        cond["verdict"], cond["upgraded"] = "superseded", time.time()
        m = msg("Les lemmes admis sont maintenant prouvés : la preuve est vérifiée par Lean (verdict strict).")
        dd.add_event("proof", m["text"], ref=idx, key=m["key"])
        await self.ctx.repo.save(dd)
        entry = await asyncio.to_thread(lib.add_proof, code, dd.title, ws.key, dd.id, list(cond["admitted"]))
        if entry:
            self.ctx.publish("library.updated", {"added": entry.name})
        return {"upgraded": True}

    # -- reaction to finished jobs (called by the plugin's bus watcher)
    async def on_job(self, job: dict) -> None:
        if job.get("state") not in ("done", "failed", "cancelled"):
            return
        d = self.ctx.repo.get(job.get("dossier_id", ""))
        if d is None:
            return
        link = d.extra.get("plan") if isinstance(d.extra.get("plan"), dict) else None
        plan_id = link["plan_dossier"] if link else (d.id if self.store.current(d.id) else None)
        if plan_id is None:
            return
        self.publish(plan_id)
        # conditional proofs whose admitted lemma just got proved
        for x in [d.parent_id, plan_id]:
            if x:
                pd = self.ctx.repo.get(x)
                if pd is not None and (pd.extra.get("conditional_proof") or {}).get("verdict") == "proved_modulo":
                    try:
                        await self.upgrade_conditional(pd.id)
                    except Exception:  # noqa: BLE001
                        pass
        self.publish(plan_id)


# ---------------------------------------------------------------- demo answer (scripted brain)
def demo_answer(first: str) -> str | None:
    if not first.startswith(MARK):
        return None
    return json.dumps({"claims": [
        {"title": "a pair", "statement": "Il existe $k$ tel que $a = 2k$.", "why": "Définition de la parité.",
         "lean": "theorem plan_a_even (a : ℕ) (ha : Even a) : ∃ k, a = k + k := by sorry", "children": []},
        {"title": "b pair", "statement": "Il existe $l$ tel que $b = 2l$.", "why": "Idem pour $b$.",
         "lean": "theorem plan_b_even (b : ℕ) (hb : Even b) : ∃ l, b = l + l := by sorry", "children": []},
        {"title": "Somme", "statement": "$a + b = 2(k + l)$ est pair.", "why": "Conclut la preuve.",
         "lean": "theorem plan_sum (k l : ℕ) : Even ((k + k) + (l + l)) := by sorry", "children": []}]},
        ensure_ascii=False)
