"""Reasoned search over the problem graph (session S-AY, DECISIONS D57, docs/PROOF_GRAPH.md).

`ReasonedSearch` is the engine: pure control logic over injected operations (`Ops`), so that its guards are tested
with fakes. Before a branch is expanded or tried, a viability check (deterministic signals + an optional cheap model
opinion) writes a score and a reason on the node; the next action is the one with the best expected value per cost.
Guards: hard budgets (depth, new nodes, attempts per problem and per branch, expansions per node, wall time,
tokens, USD within the conductor's cap), no-progress detection (the same failing Lean state twice, an expansion that
only proposes known statements, K steps without anything new), cycle refusal on « uses » edges (proofgraph), and a
final stop record with what was tried. Abandoned branches keep their reason and are not retried unless something
changed (new Lean / Mathlib, a new proved lemma).

`LeanOps` is the production implementation (one model call to propose lemmas, Lean gates their statements; cheap
closers, certificates and one model proof per attempt; counterexample probes by Lean on the negation; strict
verdict for every proof). `GraphService` owns the graphs of all dossiers (storage in the proof-plan files, project
index, runs, user actions, explanations, recording of finished jobs, the provers' digest)."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field

from .. import leancheck
from ..logs import get
from . import proofgraph as G
from .proofplan import CLOSERS, _json_obj, gate_file, indent, read_gate, split_decl

log = get("graphsearch")
MARK_EXPAND = "[madalean:graph-expand]"
MARK_VIABILITY = "[madalean:graph-viability]"
MARK_ADAPT = "[madalean:graph-adapt]"
MIN_SCORE = 0.15                 # below: the branch is abandoned before any work (reason recorded)
NODE_ATTEMPTS = 3                # direct attempts on one node before only expansion remains
MAX_LEMMAS = 4                   # lemmas per expansion
SMALL_PROBE_SECONDS = 2.0        # small-instance evaluation of one new lemma (D59), before any Lean probe
PUBLISH_EVERY = 0.5              # seconds between two graph.updated events during a run


# ---------------------------------------------------------------- budgets
@dataclass
class Budgets:
    max_depth: int = 3
    max_nodes: int = 24              # new nodes created by one run
    max_attempts: int = 24           # attempts (closers / certificate / model proof / combination) per run
    branch_attempts: int = 8         # attempts inside the subtree of one lemma of the goal
    max_expansions: int = 2          # expansions (proposed splits) per node
    wall_s: float = 1200.0
    tokens: int = 300_000
    usd: float = 0.5
    no_progress: int = 6             # consecutive steps without a new node, a new verified node or a refutation

    LIMITS = {"max_depth": (1, 5), "max_nodes": (1, 60), "max_attempts": (1, 200), "branch_attempts": (1, 60),
              "max_expansions": (1, 4), "wall_s": (10, 4 * 3600), "tokens": (1000, 3_000_000), "usd": (0, 5),
              "no_progress": (2, 30)}

    @classmethod
    def from_settings(cls, settings, overrides: dict | None = None) -> "Budgets":
        b = cls(max_depth=int(getattr(settings, "plan_max_depth", 3) or 3),
                max_attempts=int(getattr(settings, "graph_search_attempts", 24) or 24),
                wall_s=60.0 * float(getattr(settings, "graph_search_minutes", 20) or 20),
                usd=float(getattr(settings, "graph_search_usd", 0.5) or 0.0))
        # never above the conductor's cap per request (D41): the search is one request
        cap = float(getattr(settings, "conductor_cap_usd", 1.0) or 0.0)
        b.usd = min(b.usd, cap)
        for k, v in (overrides or {}).items():
            if k in cls.LIMITS:
                lo, hi = cls.LIMITS[k]
                try:
                    setattr(b, k, type(getattr(b, k))(max(lo, min(hi, float(v)))))
                except (TypeError, ValueError):
                    continue
        b.usd = min(b.usd, max(cap, 0.0)) if cap else min(b.usd, 0.0)
        return b

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.LIMITS}


@dataclass
class Spent:
    attempts: int = 0
    expansions: int = 0
    nodes: int = 0
    tokens: int = 0
    usd: float = 0.0
    model_calls: int = 0
    lean_checks: int = 0
    started: float = field(default_factory=time.monotonic)

    def seconds(self) -> float:
        return time.monotonic() - self.started

    def to_dict(self) -> dict:
        return {"attempts": self.attempts, "expansions": self.expansions, "nodes": self.nodes, "tokens": self.tokens,
                "usd": round(self.usd, 6), "model_calls": self.model_calls, "lean_checks": self.lean_checks,
                "seconds": round(self.seconds(), 1)}


# ---------------------------------------------------------------- operation results
@dataclass
class Expansion:
    lemmas: list[dict] = field(default_factory=list)     # [{title, statement_nl, lean, why}]
    refused: list[dict] = field(default_factory=list)    # [{title, lean, reason}]
    idea: str = ""
    combination: str = ""
    model: str = ""
    tokens: int = 0
    usd: float = 0.0
    error: str = ""


@dataclass
class Attempt:
    ok: bool = False
    proof: str = ""
    error: str = ""
    how: str = ""
    model: str = ""
    tokens: int = 0
    usd: float = 0.0
    seconds: float = 0.0
    self_contained: bool = True
    status: str = "proved"                # proved | certified | mathlib (on success)
    mathlib: str = ""                     # Mathlib declaration the proof is (when known)
    checks: int = 0


@dataclass
class Refutation:
    refuted: bool = False
    proof: str = ""                       # Lean proof of the negation (strictly checked)
    reason: str = ""
    checks: int = 0
    witness: str = ""                     # the small-instance counterexample Lean confirmed (D59)


class Ops:
    """Interface of the operations the search needs (tests give fakes; `LeanOps` is the real one)."""

    def env(self) -> dict:
        return {}

    def project(self) -> list[dict]:
        return []

    def library_keys(self) -> dict:
        return {}

    async def expand(self, g: dict, nid: str, digest: str) -> Expansion:
        raise NotImplementedError

    async def attempt(self, g: dict, nid: str, digest: str) -> Attempt:
        raise NotImplementedError

    async def probe(self, g: dict, nids: list[str]) -> dict[str, Refutation]:
        return {}

    async def opinion(self, g: dict, nid: str, det: dict) -> dict | None:
        return None

    async def same_statement(self, lean_a: str, lean_b: str) -> bool | None:
        """Lean's confirmation that two statements with the same alpha-normal key are the same (D59); None: no
        Lean to ask (the syntactic identity stands)."""
        return None


# ---------------------------------------------------------------- the engine
class ReasonedSearch:
    def __init__(self, g: dict, ops: Ops, budgets: Budgets, *, save=None, publish=None, run_id: str = "",
                 should_stop=None):
        self.g, self.ops, self.b = g, ops, budgets
        self.save = save or (lambda: None)
        self.publish = publish or (lambda: None)
        self.should_stop = should_stop or (lambda: False)
        self.run_id = run_id or "run-" + uuid.uuid4().hex[:6]
        self.spent = Spent()
        self.idle = 0
        self.steps = 0
        self.tried: list[dict] = []
        self.env = ops.env() or {}
        self._last_pub = 0.0

    # -- helpers
    def _n(self, nid: str) -> dict:
        return self.g["nodes"][nid]

    def live(self) -> list[str]:
        """Nodes reachable from the goal along « uses » edges (the current proof attempt)."""
        out, stack, seen = [], [self.g["root"]], set()
        while stack:
            x = stack.pop()
            if x in seen or x not in self.g["nodes"]:
                continue
            seen.add(x)
            out.append(x)
            stack += G.uses_of(self.g, x)
        return out

    def branch_of(self, nid: str) -> str:
        """The lemma of the goal this node hangs under (its « branch »), or the goal itself."""
        root = self.g["root"]
        chain = G._chain(self.g, nid)
        return chain[1] if len(chain) > 1 and chain[0] == root else nid

    def branch_attempts(self, branch: str) -> int:
        return sum(int(self.g["nodes"][x].get("run_attempts", {}).get(self.run_id, 0))
                   for x in G._subtree_uses(self.g, branch))

    def _stuck(self, n: dict) -> bool:
        return any(v >= 2 for v in (n.get("errors_seen") or {}).values())

    def _budget_stop(self) -> str:
        if self.should_stop():
            return "stopped"
        if self.spent.seconds() > self.b.wall_s:
            return "budget_time"
        if self.spent.tokens >= self.b.tokens:
            return "budget_tokens"
        if self.b.usd >= 0 and self.spent.usd > self.b.usd + 1e-9:
            return "budget_usd"
        if self.spent.attempts >= self.b.max_attempts:
            return "budget_attempts"
        if self.idle >= self.b.no_progress:
            return "no_progress"
        return ""

    def _pub(self, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - self._last_pub > PUBLISH_EVERY:
            self._last_pub = now
            try:
                self.publish()
            except Exception:  # noqa: BLE001
                log.exception("graph publish")

    def _abandon(self, nid: str, reason: str) -> None:
        G.set_status(self.g, nid, "abandoned", reason, env=self.env)
        self.tried.append({"node": nid, "title": self._n(nid)["title"], "status": "abandoned", "reason": reason})

    # -- viability
    async def assess(self, nid: str, *, model: bool = True) -> dict:
        det = G.viability_signals(self.g, nid, env=self.env, project=self.ops.project(),
                                  library_keys=self.ops.library_keys())
        op = None
        if model and not det.get("skip") and self.spent.usd <= self.b.usd and self.spent.tokens < self.b.tokens:
            try:
                op = await self.ops.opinion(self.g, nid, det)
            except Exception as e:  # noqa: BLE001 (no model: the deterministic signals decide)
                log.info("viability opinion failed: %s", e)
                op = None
            if op:
                self.spent.tokens += int(op.get("tokens", 0))
                self.spent.usd += float(op.get("usd", 0.0))
                self.spent.model_calls += 1
        v = {"score": G.combine_score(det, op), "signals": det["signals"], "skip": bool(det.get("skip")),
             "model": {k: op[k] for k in ("score", "reason", "model") if k in op} if op else None, "t": time.time(),
             "run": self.run_id}
        self._n(nid)["viability"] = v
        G.touch(self.g, "viability", nid, score=v["score"])
        return {**det, **v}

    def _reuse(self, nid: str, v: dict) -> bool:
        """A statement already verified elsewhere (project dossier, library) is reused, not proved again."""
        n = self._n(nid)
        if v.get("library"):
            G.set_status(self.g, nid, "proved", "", source_reuse={"kind": "library", "name": v["library"]})
            n["self_contained"] = True
            return True
        return False

    # -- actions
    def actions(self) -> list[tuple[float, str, str]]:
        """(priority, kind, node) for every live open node: « attempt » (prove it now / combine its lemmas) or
        « expand » (propose lemmas). Nodes that can do neither are abandoned with the reason."""
        out = []
        for nid in self.live():
            n = self._n(nid)
            if n["status"] != "open" or n.get("admitted"):
                continue
            kids = G.uses_of(self.g, nid)
            if kids:
                states = [G.effective(self.g, k)["state"] for k in kids]
                dead = [k for k, s in zip(kids, states) if s in ("abandoned", "refuted")]
                if dead and self._spare(n, dead, len(kids)):
                    # the recorded combination does not use the dead lemmas: drop them, keep the track
                    self.g["edges"] = [e for e in self.g["edges"]
                                       if not (e[0] == nid and e[1] == "uses" and e[2] in dead)]
                    G.touch(self.g, "lemma_dropped", nid, n=len(dead))
                    kids = G.uses_of(self.g, nid)
                    states = [G.effective(self.g, k)["state"] for k in kids]
                    dead = []
                if dead:
                    self._track_failed(nid, kids, states)
                    kids = []
                if not kids:
                    pass
                elif all(s in ("verified", "conditional") for s in states):
                    ck = json.dumps(sorted(f"{k}:{s}:{self._n(k)['status']}" for k, s in zip(kids, states)))
                    if n.get("combined") != ck:
                        out.append((G.priority(self.g, nid) + 1.0, "combine", nid))   # finishing first
                    elif not self._can_expand(n):
                        self._abandon(nid, "the lemmas are proved but the combination failed: " +
                                      (n.get("last_error") or "")[:200])
                    else:
                        self._unlink(nid, kids, "combination failed")
                        out.append((G.priority(self.g, nid), "expand", nid))
                    continue
                else:
                    continue                    # its lemmas are being worked on
            branch = self.branch_of(nid)
            if branch != self.g["root"] and self.branch_attempts(branch) >= self.b.branch_attempts:
                self._abandon(nid, f"branch budget reached ({self.b.branch_attempts} attempts)")
                continue
            direct = int(n.get("run_attempts", {}).get(self.run_id, 0))
            if direct < NODE_ATTEMPTS and not self._stuck(n) and not n.get("expand_first"):
                out.append((G.priority(self.g, nid), "attempt", nid))
            elif self._can_expand(n):
                out.append((G.priority(self.g, nid) * 0.9, "expand", nid))
            else:
                why = ("the same Lean error came back (no progress)" if self._stuck(n) else
                       f"{NODE_ATTEMPTS} attempts failed")
                if int(n.get("depth", 0)) + 1 > self.b.max_depth:
                    why += f"; maximum depth {self.b.max_depth} reached"
                elif int(n.get("expansions", {}).get(self.run_id, 0)) >= self.b.max_expansions:
                    why += f"; {self.b.max_expansions} splits already tried"
                elif self.spent.nodes >= self.b.max_nodes:
                    why += f"; node budget ({self.b.max_nodes}) reached"
                self._abandon(nid, why)
        live = set(self.live())
        return sorted((a for a in out if a[2] in live and self._n(a[2])["status"] == "open"), key=lambda x: -x[0])

    def _spare(self, n: dict, dead: list[str], total: int) -> bool:
        """Can the track go on without `dead`? Only when a combination was recorded, it names none of them and
        at least one lemma remains."""
        comb = n.get("combination") or ""
        if not comb or len(dead) >= total:
            return False
        for k in dead:
            parts = split_decl(self._n(k).get("lean") or "")
            if parts is None or re.search(r"(?<![\w.'])" + re.escape(parts[1]) + r"(?![\w'])", comb):
                return False
        return True

    def _can_expand(self, n: dict) -> bool:
        return (int(n.get("depth", 0)) + 1 <= self.b.max_depth
                and int(n.get("expansions", {}).get(self.run_id, 0)) < self.b.max_expansions
                and self.spent.nodes < self.b.max_nodes)

    def _unlink(self, nid: str, kids: list[str], why: str) -> None:
        """The current track of `nid` failed: keep it as an abandoned track (with the reason), free the node for
        another split."""
        n = self._n(nid)
        n.setdefault("tracks", []).append({"id": "t" + uuid.uuid4().hex[:4], "idea": n.get("idea", ""),
                                           "lemmas": list(kids), "active": False, "abandoned": True,
                                           "why": why[:300], "check": "failed"})
        del n["tracks"][:-6]
        self.g["edges"] = [e for e in self.g["edges"] if not (e[0] == nid and e[1] == "uses" and e[2] in kids)]
        n["combined"] = None
        G.touch(self.g, "track_failed", nid, why=why[:120])

    def _track_failed(self, nid: str, kids: list[str], states: list[str]) -> None:
        bad = [k for k, s in zip(kids, states) if s in ("abandoned", "refuted")]
        why = "; ".join(f"« {self._n(k)['title'][:60]} » {self._n(k)['status']}: {self._n(k).get('reason', '')[:120]}"
                        for k in bad)
        self._unlink(nid, kids, why)
        self._n(nid)["expand_first"] = True          # direct attempts were already made before the split

    async def do_attempt(self, nid: str, combine: bool = False) -> bool:
        n = self._n(nid)
        dig = self.digest()
        res = await self.ops.attempt(self.g, nid, dig)
        self.spent.attempts += 1
        self.spent.tokens += res.tokens
        self.spent.usd += res.usd
        self.spent.lean_checks += res.checks
        if res.model:
            self.spent.model_calls += 1
        ra = n.setdefault("run_attempts", {})
        ra[self.run_id] = int(ra.get(self.run_id, 0)) + 1
        for k in list(ra)[:-3]:
            ra.pop(k, None)
        rec = G.record_attempt(self.g, nid, how=res.how or ("combination" if combine else "attempt"), ok=res.ok,
                               error=res.error, model=res.model, proof=res.proof, seconds=res.seconds,
                               tokens=res.tokens, usd=res.usd, run=self.run_id)
        if combine:
            kids = G.uses_of(self.g, nid)
            n["combined"] = json.dumps(sorted(f"{k}:{G.effective(self.g, k)['state']}:{self._n(k)['status']}"
                                              for k in kids))
        if res.ok:
            n["proof"] = res.proof[:G.MAX_PROOF_CHARS]
            n["tactics"] = G.tactics_of(res.proof)
            n["how"] = res.how
            if res.mathlib:
                n["source"] = {**(n.get("source") or {}), "name": res.mathlib}
            G.set_status(self.g, nid, res.status if res.status in G.VERIFIED else "proved", "",
                         self_contained=res.self_contained)
            if not combine and G.uses_of(self.g, nid):
                pass
            return True
        n["last_error"] = res.error[:600]
        if rec["repeat"] >= 1:
            G.touch(self.g, "no_progress", nid, fingerprint=rec["fingerprint"])
        return False

    async def do_expand(self, nid: str) -> int:
        n = self._n(nid)
        ex = n.setdefault("expansions", {})
        ex[self.run_id] = int(ex.get(self.run_id, 0)) + 1
        for k in list(ex)[:-3]:
            ex.pop(k, None)
        v = await self.assess(nid)
        if v["score"] < MIN_SCORE and nid != self.g["root"]:
            self._abandon(nid, "not worth splitting: " + G.reason_text(v, "en"))
            return 0
        self.spent.expansions += 1
        res = await self.ops.expand(self.g, nid, self.digest())
        self.spent.tokens += res.tokens
        self.spent.usd += res.usd
        if res.model:
            self.spent.model_calls += 1
        for r in res.refused:
            G.touch(self.g, "lemma_refused", nid, title=str(r.get("title", ""))[:80],
                    reason=str(r.get("reason", ""))[:160])
        if res.error or not res.lemmas:
            n["expand_error"] = (res.error or "no lemma proposed")[:300]
            G.touch(self.g, "expand_failed", nid, why=n["expand_error"][:120])
            return 0
        n["idea"] = res.idea[:300]
        if res.combination:
            n["combination"] = res.combination[:G.MAX_PROOF_CHARS]
        created, linked, new_ids = 0, 0, []
        for lm in res.lemmas[:MAX_LEMMAS]:
            if self.spent.nodes >= self.b.max_nodes:
                G.touch(self.g, "node_budget", nid)
                break
            node = G.new_node("lemma", lm.get("title") or "lemme", lean=lm.get("lean", ""),
                              statement_nl=lm.get("statement_nl", ""), why=lm.get("why", ""),
                              source={"kind": "search", "model": res.model, "run": self.run_id})
            same = G.find_key(self.g, node["key"])
            if same is not None and node.get("exact") and same.get("exact") and node["exact"] != same["exact"]:
                ok = await self.ops.same_statement(same.get("lean") or "", node.get("lean") or "")
                self.spent.lean_checks += ok is not None
                if ok is False:                      # the syntactic renaming was wrong here: kept apart
                    node["key"] = node["exact"]
                    G.touch(self.g, "alpha_refused", same["id"], title=node["title"][:80])
            before = len(self.g["edges"])
            node, was_new = G.add_node(self.g, node, parent=nid)
            if not was_new and len(self.g["edges"]) == before and [nid, "uses", node["id"]] not in self.g["edges"]:
                continue                             # refused (cycle): logged by add_edge
            linked += 1
            new_ids.append(node["id"])
            if was_new:
                created += 1
                self.spent.nodes += 1
                node["depth"] = int(n.get("depth", 0)) + 1
        n.setdefault("tracks", []).append({"id": "t" + uuid.uuid4().hex[:4], "idea": res.idea[:300],
                                           "lemmas": list(new_ids), "active": True, "abandoned": False,
                                           "why": "", "check": "ok" if res.combination else "unchecked"})
        for t in n["tracks"][:-1]:
            t["active"] = False
        del n["tracks"][:-6]
        n["expand_first"] = False
        if not linked:
            return 0
        fresh = [x for x in new_ids if self._n(x)["status"] == "open"]
        if fresh:                                    # counterexample probe: one Lean compile for the new lemmas
            try:
                refs = await self.ops.probe(self.g, fresh)
            except Exception as e:  # noqa: BLE001
                log.info("probe failed: %s", e)
                refs = {}
            for x, r in refs.items():
                self.spent.lean_checks += r.checks
                if r.refuted:
                    self._refute(x, r)
        for x in new_ids:
            if self._n(x)["status"] != "open":
                continue
            v = await self.assess(x)
            if v.get("skip") and self._reuse(x, v):
                continue
            if v.get("skip") or v["score"] < MIN_SCORE:
                self._abandon(x, G.reason_text(v, "en"))
        return created

    def _refute(self, nid: str, r: Refutation) -> None:
        n = self._n(nid)
        cex = G.new_node("certificate", f"¬ {n['title'][:180]}", lean="", status="proved",
                         source={"kind": "counterexample"})
        cex["proof"] = r.proof[:G.MAX_PROOF_CHARS]
        if r.witness:
            cex["witness"] = r.witness[:300]
        cex, _ = G.add_node(self.g, cex)
        G.add_edge(self.g, cex["id"], "refutes", nid)
        G.set_status(self.g, nid, "refuted", r.reason or "Lean proved the negation (counterexample)", env=self.env)
        self.tried.append({"node": nid, "title": n["title"], "status": "refuted", "reason": n["reason"]})

    def digest(self) -> str:
        return G.digest(self.g, self.ops.project())

    def reopen_changed(self) -> list[str]:
        """Closed nodes whose world changed (new Lean / Mathlib, a new verified lemma) become open again; the
        others stay closed with their reason (not retried blindly)."""
        out = []
        facts = G.facts_hash(self.g)
        for n in self.g["nodes"].values():
            if n["status"] == "abandoned" and n["id"] in self.live():
                changed = G.env_changed(n.get("closed"), self.env, facts)
                if changed and changed != ["never_closed"]:
                    G.set_status(self.g, n["id"], "open", "")
                    n["errors_seen"] = {}
                    G.touch(self.g, "reopened", n["id"], why=", ".join(changed))
                    out.append(n["id"])
        return out

    # -- run
    async def run(self) -> dict:
        g = self.g
        g["env"] = dict(self.env or g.get("env") or {})
        root = self._n(g["root"])
        reopened = self.reopen_changed()
        if root["status"] == "abandoned" and not reopened:
            changed = G.env_changed(root.get("closed"), self.env, G.facts_hash(g))
            if changed and changed != ["never_closed"]:
                G.set_status(g, g["root"], "open", "")
                reopened.append(g["root"])
        reason = ""
        while True:
            if G.effective(g, g["root"])["state"] == "verified":
                reason = "solved"
                break
            reason = self._budget_stop()
            if reason:
                break
            acts = self.actions()
            if not acts:
                st = G.effective(g, g["root"])["state"]
                reason = "conditional" if st == "conditional" else "exhausted"
                break
            _p, kind, nid = acts[0]
            before = (len(g["nodes"]), G.facts_hash(g), sum(1 for n in g["nodes"].values() if n["status"] == "refuted"))
            self.steps += 1
            if kind == "expand":
                await self.do_expand(nid)
            else:
                await self.do_attempt(nid, combine=(kind == "combine"))
            after = (len(g["nodes"]), G.facts_hash(g), sum(1 for n in g["nodes"].values() if n["status"] == "refuted"))
            self.idle = 0 if after != before else self.idle + 1
            self.save()
            self._pub()
        summary = self.summary(reason, reopened)
        g.setdefault("runs", []).append(summary)
        del g["runs"][:-G.MAX_RUNS]
        G.touch(g, "run_end", g["root"], reason=reason)
        self.save()
        self._pub(force=True)
        return summary

    def summary(self, reason: str, reopened: list[str] | None = None) -> dict:
        g = self.g
        root_state = G.effective(g, g["root"])
        return {"id": self.run_id, "end": time.time(), "reason": reason, "steps": self.steps,
                "budgets": self.b.to_dict(), "spent": self.spent.to_dict(), "root_state": root_state["state"],
                "rests_on": root_state["rests_on"], "reopened": list(reopened or []),
                "tried": self.tried[-30:],
                "verified": [n["id"] for n in g["nodes"].values() if G.effective(g, n["id"])["state"] == "verified"
                             and n["id"] in self.live()][:40]}


# ---------------------------------------------------------------- production operations (Lean + models)
class _IO:
    def __init__(self, ctx, owner: str):
        self.ctx, self.owner = ctx, owner

    async def check(self, code, ws, timeout_s, name):
        return await self.ctx.lean.check(code, ws, timeout_s, name, owner=self.owner)


def expand_messages(goal_nl: str, lean: str, digest: str, failed: list[str]) -> list[dict]:
    fail = ("\nTracks that already failed for this statement (do not propose them again):\n" + "\n".join(
        f"- {f}" for f in failed[:6])) if failed else ""
    content = (f"{MARK_EXPAND}\nSplit the Lean 4 (Mathlib) statement below into 2 to {MAX_LEMMAS} lemmas that are "
               "each simpler, preferably independent, and from which the statement follows. Answer with JSON only:\n"
               '{"idea": "one sentence", "lemmas": [{"name": "snake_case", "title": "short", "statement": "in words", '
               '"why": "its role", "lean": "theorem name BINDERS : PROP := by sorry"}], '
               '"combination": "the Lean tactic proof of the statement using the lemmas by name"}\n'
               "First place the KNOWN results listed below (use them by their statement, do not re-prove them), "
               "then propose only the MISSING lemmas.\n\n"
               f"Statement ({goal_nl[:400]}):\n```lean4\n{lean.strip()}\n```\n"
               + (f"\n{digest}\n" if digest else "") + fail)
    return [{"role": "user", "content": content}]


def viability_messages(title: str, lean: str, parent: str, signals: str) -> list[dict]:
    content = (f"{MARK_VIABILITY}\nIs the following lemma (a) true and (b) a useful, simpler step towards the parent "
               "statement? Answer with JSON only: {\"score\": 0.0-1.0, \"reason\": \"one short sentence\"}.\n"
               f"Lemma « {title[:200]} »:\n```lean4\n{lean.strip()[:2000]}\n```\nParent:\n```lean4\n{parent[:2000]}\n```\n"
               f"Facts already known: {signals[:600]}")
    return [{"role": "user", "content": content}]


def adapt_messages(source_title: str, source_lean: str, method: str, goal_lean: str) -> list[dict]:
    content = (f"{MARK_ADAPT}\nA known result and its proof method are given. Propose how to GENERALISE or ADAPT this "
               "method to the goal: a generalised statement and the lemmas of the adapted proof. Answer with JSON "
               'only: {"idea": "…", "general": {"title": "…", "statement": "…", "lean": "theorem … := by sorry"}, '
               '"lemmas": [{"name": "…", "title": "…", "statement": "…", "why": "…", "lean": "theorem … := by sorry"}]}\n'
               f"Known result « {source_title[:200]} »:\n```lean4\n{source_lean[:3000]}\n```\n"
               f"Its method (quoted from the record):\n{method[:4000]}\n\nGoal:\n```lean4\n{goal_lean[:3000]}\n```")
    return [{"role": "user", "content": content}]


def parse_lemmas(text: str) -> tuple[str, list[dict], str, dict | None]:
    data = _json_obj(text)
    if not isinstance(data, dict):
        return "", [], "", None
    out = []
    for lm in data.get("lemmas") or []:
        if not isinstance(lm, dict):
            continue
        lean = str(lm.get("lean") or "")
        parts = split_decl(lean)
        if not parts:
            continue
        name = re.sub(r"[^A-Za-z0-9_']", "_", str(lm.get("name") or parts[1]))[:60] or parts[1]
        out.append({"name": name, "title": str(lm.get("title") or name)[:200],
                    "statement_nl": str(lm.get("statement") or "")[:2000], "why": str(lm.get("why") or "")[:500],
                    "sig": parts[2], "lean": f"theorem {name} {parts[2]} := by sorry"})
    gen = data.get("general") if isinstance(data.get("general"), dict) else None
    return str(data.get("idea") or "")[:300], out, str(data.get("combination") or ""), gen


def _decls_only(code: str, context: str = "") -> str:
    """A recorded proof without its header lines and without the dossier's own context (already above)."""
    text = leancheck.remove_comments(code or "")
    lines = [ln for ln in text.split("\n") if not re.match(r"\s*(import|set_option maxHeartbeats \d+\s*$|open)\b", ln)]
    text = "\n".join(lines).strip()
    if context.strip() and text.startswith(context.strip()):
        text = text[len(context.strip()):].strip()
    return text


class LeanOps(Ops):
    """The real operations, for one dossier's graph."""

    def __init__(self, ctx, service: "GraphService", did: str, mode: str):
        self.ctx, self.svc, self.did, self.mode = ctx, service, did, mode
        self.d = ctx.repo.get(did)
        self.ws = ctx.workspace((self.d.workspace if self.d else "") or ctx.settings.workspace)
        self.owner = f"graph-{did}"
        self.io = _IO(ctx, self.owner)
        stmt = self.d.statement if self.d is not None else ""
        parts = split_decl(stmt) if stmt else None
        self.context = parts[0] if parts else ""
        self._project = None

    def _real(self) -> bool:
        from ..brain.fake import FakeLean
        return not isinstance(self.ctx.lean, FakeLean)

    def env(self) -> dict:
        from ..runtime.lean import workspace_info
        info = workspace_info(self.ws) if self.ws is not None else {}
        return {"workspace": info.get("workspace", ""), "lean": info.get("lean", ""),
                "mathlib": info.get("mathlib", "")}

    def project(self) -> list[dict]:
        if self._project is None:
            self._project = self.svc.project_rows(self.d.project_id if self.d else "", self.did)
        return self._project

    def library_keys(self) -> dict:
        return self.svc.library_keys(self.ws.key if self.ws else "")

    def _decl(self, g: dict, nid: str) -> tuple[str, str] | None:
        """(name, signature) of a node."""
        n = g["nodes"][nid]
        src = (self.d.statement if nid == g["root"] and self.d is not None and self.d.statement else n.get("lean", ""))
        parts = split_decl(src or "")
        return (parts[1], parts[2]) if parts else None

    async def _ask(self, messages: list[dict], max_tokens: int = 3000, temperature: float = 0.3):
        from ..server.helpers import complete_once
        c = await complete_once(self.ctx, "prove", messages, self.mode, owner=self.owner, max_tokens=max_tokens,
                                temperature=temperature)
        from ..brain import spend
        usd = 0.0
        try:
            if spend.price_of(c.model.model_id) is not None:
                usd = spend.cost(c.model.model_id, c.tokens_in, c.tokens_out)
        except Exception:  # noqa: BLE001
            usd = 0.0
        return c.text, c.model.key, int(c.tokens_in + c.tokens_out), usd

    async def opinion(self, g: dict, nid: str, det: dict) -> dict | None:
        if not getattr(self.ctx.settings, "graph_viability_model", True) or nid == g["root"]:
            return None
        n = g["nodes"][nid]
        parent = next((g["nodes"][p] for p in G.users_of(g, nid)), None)
        try:
            text, model, tok, usd = await asyncio.wait_for(self._ask(viability_messages(
                n["title"], n.get("lean", ""), (parent or {}).get("lean", "") or (self.d.statement if self.d else ""),
                G.reason_text({"score": det["score"], "signals": det["signals"]}, "en")), 300, 0.1), 60)
        except Exception:  # noqa: BLE001
            return None
        data = _json_obj(text)
        if not isinstance(data, dict) or not isinstance(data.get("score"), (int, float)):
            return {"score": None, "reason": "", "model": model, "tokens": tok, "usd": usd}
        return {"score": max(0.0, min(1.0, float(data["score"]))), "reason": str(data.get("reason") or "")[:200],
                "model": model, "tokens": tok, "usd": usd}

    async def same_statement(self, lean_a: str, lean_b: str) -> bool | None:
        if self.ws is None or not self._real():
            return None
        code = G.same_statement_code(lean_a, lean_b)
        if not code:
            return False
        pa = split_decl(lean_a or "")
        if self.context and pa is not None and not pa[0]:
            code = self.context + "\n\n" + code
        try:
            r = await self.ctx.lean.check(leancheck.with_axiom_probe(leancheck.GOEDEL_HEADER + code, G.ALPHA_THM),
                                          self.ws, 60, G.ALPHA_THM, owner=self.owner)
        except Exception:  # noqa: BLE001
            return False
        return bool(r.verdict.ok)

    async def expand(self, g: dict, nid: str, digest: str) -> Expansion:
        decl = self._decl(g, nid)
        if decl is None or self.ws is None:
            return Expansion(error="no Lean statement")
        pname, psig = decl
        n = g["nodes"][nid]
        failed = [f"{t.get('idea', '')}: {t.get('why', '')}" for t in n.get("tracks") or [] if t.get("abandoned")]
        try:
            text, model, tok, usd = await self._ask(expand_messages(n.get("statement_nl") or n["title"],
                                                                    f"theorem {pname} {psig} := by sorry", digest,
                                                                    failed))
        except Exception as e:  # noqa: BLE001
            return Expansion(error=f"no model: {str(e)[:200]}")
        idea, lemmas, comb, _gen = parse_lemmas(text)
        res = Expansion(idea=idea, model=model, tokens=tok, usd=usd)
        if not lemmas:
            res.error = "the model proposed no usable lemma"
            return res
        lemmas = lemmas[:MAX_LEMMAS]
        names = {pname}
        for lm in lemmas:                          # unique names inside the gate file
            base, k = lm["name"], 1
            while lm["name"] in names:
                lm["name"] = f"{base}_{k}"
                k += 1
            names.add(lm["name"])
            lm["lean"] = f"theorem {lm['name']} {lm['sig']} := by sorry"
            risks = leancheck.exec_risks(lm["lean"])
            lm["err"] = ("refused: " + ", ".join(risks)) if risks else ""
        comb_ok = comb and not leancheck.exec_risks(comb) and not leancheck.forbidden_reasons(comb)
        ok_lemmas = [lm for lm in lemmas if not lm["err"]]
        code, spans = gate_file(self.context, pname, psig, [{"lemmas": ok_lemmas,
                                                             "combination": comb if comb_ok else ""}],
                                equiv=self._real())
        r = await self.ctx.lean.check(code, self.ws, max(120, self.ctx.settings.compile_timeout_s), None,
                                      owner=self.owner)
        if r.timed_out or r.infra_error:
            res.error = "Lean could not check the lemmas: " + (r.verdict.summary or "")[:200]
            return res
        msgs = leancheck.parse_lean_json(r.stdout) if r.stdout else list(r.verdict.errors)
        gate = read_gate(spans, msgs)
        for li, lm in enumerate(ok_lemmas):
            e = gate.get(("lemma", 0, li), {}).get("errors") or []
            if e:
                lm["err"] = "Lean: " + "; ".join(x[:200] for x in e[:2])
            elif self._real():
                dn = gate.get(("dn", 0, li), {"errors": ["?"]})
                up = gate.get(("up", 0, li), {"errors": ["?"]})
                if not dn["errors"] and not up["errors"]:
                    lm["err"] = "equivalent to the statement itself (loop)"
        if comb_ok and not (gate.get(("comb", 0, -1), {}).get("errors")) and all(not lm["err"] for lm in lemmas):
            res.combination = comb
        for lm in lemmas:
            if lm["err"]:
                res.refused.append({"title": lm["title"], "lean": lm["lean"], "reason": lm["err"]})
            else:
                res.lemmas.append({"title": lm["title"], "statement_nl": lm["statement_nl"], "lean": lm["lean"],
                                   "why": lm["why"]})
        return res

    def _statement(self, g: dict, nid: str) -> tuple[str, str, list[str], bool] | None:
        """(prepared statement with the node's proved / admitted lemmas above it, theorem name, hole names,
        self_contained)."""
        decl = self._decl(g, nid)
        if decl is None:
            return None
        name, sig = decl
        blocks, holes = [], []
        for k in G.uses_of(g, nid):
            kn = g["nodes"][k]
            kd = split_decl(kn.get("lean") or "")
            if kd is None:
                continue
            st = G.effective(g, k)["state"]
            if st == "verified" and kn.get("proof") and kn["status"] == "proved":
                body = kn["proof"]
                kparts = split_decl(body)
                if kparts and kparts[1] != kd[1]:
                    body = re.sub(rf"\btheorem\s+{re.escape(kparts[1])}\b", f"theorem {kd[1]}", body, count=1)
                blocks.append(_decls_only(body, self.context))
            elif st == "verified" and kn["status"] in ("mathlib", "certified") and kn.get("proof") and \
                    split_decl(kn["proof"]) and split_decl(kn["proof"])[1] == kd[1]:
                blocks.append(_decls_only(kn["proof"], self.context))
            else:
                blocks.append(f"-- admitted (cited / hole): {kn['title'][:80]}\ntheorem {kd[1]} {kd[2]} := by sorry")
                holes.append(kd[1])
            for al in kn.get("aliases") or []:            # the same statement under other names (D59)
                ad = split_decl(al.get("lean") or "")
                if ad and ad[1] != kd[1] and ad[1] != name:
                    blocks.append(f"theorem {ad[1]} {ad[2]} := {kd[1]}")
        pre = "\n\n".join(b for b in [self.context] + blocks if b.strip())
        text = (leancheck.GOEDEL_HEADER + (pre + "\n\n" if pre else "") + f"theorem {name} {sig} := by sorry")
        try:
            return leancheck.prepare_statement(text), name, holes, not holes
        except leancheck.StatementError:
            return None

    async def _strict(self, statement: str, name: str, body: str, holes: list[str]) -> tuple[bool, str, str, int]:
        """(ok, full code, error) — strict verdict without holes, the conditional check with holes."""
        try:
            full = leancheck.assemble_proof(statement, f"theorem {name} := by\n{indent(body)}")
        except leancheck.StatementError as e:
            return False, "", str(e)[:400], 0
        if holes:
            res = await self.svc.planner.check_conditional(full, name, self.ws, holes)
            return bool(res.get("ok")), full, "" if res.get("ok") else str(res.get("why", ""))[:600], 1
        r = await self.ctx.lean.check(leancheck.with_axiom_probe(full, name), self.ws,
                                      self.ctx.settings.compile_timeout_s, name, owner=self.owner)
        if r.verdict.ok:
            return True, full, "", 1
        return False, full, leancheck.errors_for_feedback(full, r.verdict)[:800] or r.verdict.summary, 1

    async def attempt(self, g: dict, nid: str, digest: str) -> Attempt:
        if self.ws is None:
            return Attempt(error="no workspace", how="none")
        st = self._statement(g, nid)
        if st is None:
            return Attempt(error="no Lean statement", how="none")
        statement, name, holes, contained = st
        n = g["nodes"][nid]
        t0 = time.monotonic()
        checks = 0
        # 1. the combination recorded when the lemmas were proposed (no model)
        if G.uses_of(g, nid) and n.get("combination"):
            from .proofplan import body_of
            body = body_of(n["combination"]) or n["combination"]
            ok, full, err, c = await self._strict(statement, name, body, holes)
            checks += c
            if ok:
                return Attempt(True, full, how="combination", self_contained=contained,
                               seconds=time.monotonic() - t0, checks=checks)
        # 2. cheap closers (no model), never for a node whose lemmas are holes
        ok, full, err, c = await self._strict(statement, name, CLOSERS, holes)
        checks += c
        if ok:
            return Attempt(True, full, how="closers", self_contained=contained, seconds=time.monotonic() - t0,
                           checks=checks)
        last_err = err
        # 3. a certificate (Sage computes, Lean checks), when the statement has the shape
        if getattr(self.ctx.settings, "certificates", False) and not holes:
            try:
                from ..certs import engine, producer
                if engine.kinds_of(statement):
                    async def check(code: str, nm: str):
                        return await self.ctx.lean.check(code, self.ws, 120, nm, owner=self.owner)
                    o = await engine.certify(statement, self.ws, check, producer.for_ctx(self.ctx), sage_seconds=30)
                    checks += 1
                    if o.ok:
                        return Attempt(True, o.code, how="certificate", status="certified", self_contained=True,
                                       seconds=time.monotonic() - t0, checks=checks, model=f"certificat:{o.kind}")
            except Exception as e:  # noqa: BLE001
                log.info("certificate attempt failed: %s", e)
        # 4. one model proof (the prover receives the problem memory)
        hint = digest
        if holes:
            hint += "\nUse the lemmas stated above the theorem (they are admitted)."
        try:
            text, model, tok, usd = await self._ask([{"role": "user", "content": leancheck.initial_prompt(
                statement, hint)}], max_tokens=6000, temperature=0.6)
        except Exception as e:  # noqa: BLE001
            return Attempt(False, error=last_err or f"no model: {str(e)[:200]}", how="closers",
                           seconds=time.monotonic() - t0, checks=checks)
        code = leancheck.extract_code(text) or ""
        from .proofplan import body_of
        body = body_of(code, name) if code else ""
        if not body:
            return Attempt(False, error="the model gave no Lean proof", how="model", model=model, tokens=tok, usd=usd,
                           seconds=time.monotonic() - t0, checks=checks)
        if leancheck.forbidden_reasons(body):
            return Attempt(False, error="forbidden: " + ", ".join(leancheck.forbidden_reasons(body)), how="model",
                           model=model, tokens=tok, usd=usd, seconds=time.monotonic() - t0, checks=checks)
        ok, full, err, c = await self._strict(statement, name, body, holes)
        checks += c
        how = "model"
        from . import lessons
        st = lessons.store_of(self.ctx)
        if not ok and st is not None:
            # D57b: a known rename (exact lesson for this Mathlib) is applied without a model; Lean re-checks
            fixed, used = st.apply_renames(body, self.env())
            if used:
                ok2, full2, err2, c = await self._strict(statement, name, fixed, holes)
                checks += c
                for lid in used:
                    st.feedback(lid, ok2)
                if ok2:
                    ok, full, err, how = True, full2, "", "model+lesson"
        if st is not None:
            prev = n.get("_failed_model")
            if ok and prev and how == "model":
                st.learn_fix(prev["code"], prev["error"], full, statement, self.env(), self.did)
            n["_failed_model"] = None if ok else {"code": (full or body)[:4000], "error": err[:1500]}
        return Attempt(ok, full if ok else "", error=err, how=how, model=model, tokens=tok, usd=usd,
                       self_contained=contained, seconds=time.monotonic() - t0, checks=checks)

    async def probe(self, g: dict, nids: list[str]) -> dict[str, Refutation]:
        """Counterexample probes: Lean tries to prove the NEGATION of each new lemma (automatic tactics, degenerate
        values); a closed probe is re-checked alone, strictly. Only Lean refutes."""
        if self.ws is None:
            return {}
        from ..pipeline import probes as P
        from ..pipeline.verify import CLOSE_HYP, NEG_TACTICS
        from . import smallprobe as SP
        real = self._real()                              # a stand-in Lean proves anything: no refutation from it
        batch: list = []
        owner: dict[str, str] = {}
        pre = None
        stop = lambda: bool((self.svc.runs.get(self.did) or {}).get("stop"))  # noqa: E731
        for i, x in enumerate(nids[:MAX_LEMMAS]):
            node = g["nodes"][x]
            lean = node.get("lean") or ""
            text = leancheck.GOEDEL_HEADER + (self.context + "\n\n" if self.context else "") + lean
            sig = P.split_statement(text)
            if sig is None:
                continue
            # D59: Madalean's own deterministic evaluation on small instances first (no model-written code)
            try:
                found = await asyncio.wait_for(asyncio.to_thread(
                    SP.search, text, seconds=SMALL_PROBE_SECONDS, should_stop=stop), SMALL_PROBE_SECONDS + 5)
            except Exception as e:  # noqa: BLE001
                log.info("small probe failed: %s", e)
                found = None
            wtacs: list[str] = []
            if found is not None and not found["found"]:
                node["tested"] = {"text": found["tested"], "points": found["points"], "dom": found["dom"],
                                  "complete": found["complete"]}
            elif found is not None:
                node["probe"] = {"candidate": SP.witness_text(found), "confirmed": False}
                wtacs = SP.lean_tactics(text, found)
            if not real:
                continue
            pre = pre or sig.preamble
            neg = ": " + sig.negation()
            for k, tac in enumerate(wtacs):
                pn = f"madalean_gcex_{i}_{k}"
                batch.append(P.Probe(pn, P.decl(pn, neg, tac), "cex",
                                     {"tactic": "witness", "witness": SP.witness_text(found)}))
                owner[pn] = x
            tacs = list(NEG_TACTICS[:5])
            subs = [(nm, v[0]) for nm, t in P.explicit_binders(sig.binders) for v in [P.degenerate_value(t)] if v]
            if subs:
                tacs.append("intro h\nhave := h " + " ".join(f"({nm} := {v})" for nm, v in subs) + "\n" + CLOSE_HYP)
            for k, tac in enumerate(tacs):
                pn = f"madalean_gneg_{i}_{k}"
                batch.append(P.Probe(pn, P.decl(pn, neg, tac), "neg", {"tactic": tac}))
                owner[pn] = x
        if not batch or pre is None:
            return {}
        out: dict[str, Refutation] = {}
        await P.run_batch(self.io, self.ws, pre, batch, 90)
        done: set[str] = set()
        for p in batch:
            x = owner[p.name]
            if not p.ok or x in done:
                continue
            r = await P.strict(self.io, self.ws, pre, p, 60)
            if r.verdict.ok:
                done.add(x)
                wit = p.meta.get("witness", "")
                why = (f"counterexample {wit} (small-instance search), confirmed by Lean" if wit else
                       f"Lean proved the negation ({p.meta.get('tactic', '')[:60]})")
                if wit:
                    g["nodes"][x]["probe"] = {"candidate": wit, "confirmed": True}
                out[x] = Refutation(True, p.code, why, 2, witness=wit)
        return out


# ---------------------------------------------------------------- the service (one per server)
class GraphService:
    def __init__(self, ctx, planner):
        self.ctx, self.planner, self.store = ctx, planner, planner.store
        self.runs: dict[str, dict] = {}               # dossier -> {task, search, stop}
        self.locks: dict[str, asyncio.Lock] = {}
        self._libkeys: tuple[int, str, dict] | None = None
        self._index: dict[str, dict[str, list[dict]]] = {}    # project -> dossier -> rows

    # -- storage
    def get(self, did: str) -> dict | None:
        data = self.store.load(did)
        g = (data or {}).get("graph")
        if g is not None and int(g.get("v", 1)) < G.GRAPH_VERSION:
            G.migrate(g)                               # D59: keys up to renaming; alpha-duplicates merged
            self.store.save(data)
        return g

    def ensure(self, did: str) -> dict:
        """The dossier's graph; created from the dossier (and its proof plan, if any) on first use."""
        d = self.ctx.repo.get(did)
        if d is None:
            raise G.GraphError("not_found", 404)
        self.get(did)                                  # migrates a stored graph first
        data = self.store.load(did) or {"dossier_id": did, "versions": []}
        g = data.get("graph")
        if g is None:
            g = G.new_graph(did, d.project_id, d.title, d.statement or "", d.understood or d.problem or "")
            data["graph"] = g
            self.store.cache[did] = data
            G.touch(g, "created", g["root"])
        atts = d.extra.get("attachments") if isinstance(d.extra.get("attachments"), list) else []
        if len(atts) != g.get("attachments_seen", 0):
            # « Comprendre d'abord »: the results provided with the problem are placed as known (cited) nodes,
            # apart from the target; never « proved » until Lean says so
            from . import literature_iface as LI
            for it in LI.provided(self.ctx, d):
                try:
                    G.add_node(g, G.cited_node(it))
                except G.GraphError:
                    break
            g["attachments_seen"] = len(atts)
        root = g["nodes"][g["root"]]
        if d.statement and root.get("lean") != d.statement:          # the statement was corrected
            root["lean"] = d.statement[:8000]
            root["key"] = G.statement_key(d.statement)
            root["exact"] = G.exact_key(d.statement)
            G.touch(g, "statement", g["root"])
        self._sync_dossier(g, d)
        pub = self.planner.public(did) if self.store.current(did) is not None else None
        if pub is not None and pub.get("rev") != g.get("plan_rev"):
            G.sync_from_plan(g, pub)
        return g

    def _sync_dossier(self, g: dict, d) -> None:
        root = g["nodes"][g["root"]]
        cond = (d.extra.get("conditional_proof") or {}) if isinstance(d.extra, dict) else {}
        if d.proof_is_current and (root["status"] != "proved" or not root.get("self_contained", True)
                                   or root.get("proof") != d.proof):
            meta = d.proofs[d.cur_proof].meta if d.proofs else {}
            st = "certified" if meta.get("strategy") == "certificate" else "proved"
            root["proof"] = (d.proof or "")[:G.MAX_PROOF_CHARS]
            root["tactics"] = G.tactics_of(d.proof or "")
            G.set_status(g, g["root"], st, "", self_contained=True, from_dossier=True)
            if meta.get("mathlib_lemma"):
                m = G.new_node("mathlib", meta["mathlib_lemma"], status="mathlib",
                               source={"kind": "mathlib", "name": meta["mathlib_lemma"]})
                G.add_node(g, m, parent=g["root"])
        elif not d.proof_is_current and cond.get("verdict") == "proved_modulo" and root["status"] == "open":
            root["proof"] = str(cond.get("code") or "")[:G.MAX_PROOF_CHARS]
            root["tactics"] = G.tactics_of(root["proof"])
            G.set_status(g, g["root"], "proved", "", self_contained=False)
        elif not d.proof_is_current and root["status"] in G.VERIFIED and root.get("from_dossier") and \
                cond.get("verdict") != "proved_modulo":
            G.set_status(g, g["root"], "open", "", from_dossier=False)   # a new statement: the old proof is gone

    def save(self, did: str) -> None:
        data = self.store.load(did)
        if data is None or "graph" not in data:
            return
        self.store.save(data)
        g = data["graph"]
        pid = g.get("project_id") or ""
        if pid:
            self._index.setdefault(pid, {})[did] = G.project_entries(g)

    def publish(self, did: str) -> None:
        g = self.get(did)
        if g is not None:
            self.ctx.publish("graph.updated", {"dossier_id": did, "rev": g.get("rev", 0),
                                               "run": self.run_state(did)})

    def project_rows(self, project_id: str, exclude: str = "") -> list[dict]:
        """Index rows of the other dossiers of the project (library reuse across dossiers), bounded."""
        if not project_id:
            return []
        idx = self._index.get(project_id)
        if idx is None:
            idx = {}
            for d in self.ctx.repo.list(project_id)[:200]:
                try:
                    g = self.get(d.id)
                except G.GraphError:
                    g = None
                if g is not None:
                    idx[d.id] = G.project_entries(g)
            self._index[project_id] = idx
        return [r for did, rows in idx.items() if did != exclude for r in rows][:600]

    def library_keys(self, ws_key: str) -> dict:
        lib = self.ctx.library
        stamp = (len(lib.entries), ws_key)
        if self._libkeys is None or self._libkeys[:2] != stamp:
            keys = {}
            for e in lib.entries:
                if e.workspace == ws_key and e.statement:
                    keys[G.statement_key(e.statement + " by sorry")] = e.name
            self._libkeys = (stamp[0], stamp[1], keys)
        return self._libkeys[2]

    # -- views
    def run_state(self, did: str) -> dict | None:
        r = self.runs.get(did)
        if r is None:
            return None
        s: ReasonedSearch = r["search"]
        return {"id": s.run_id, "running": not r["task"].done(), "steps": s.steps, "budgets": s.b.to_dict(),
                "spent": s.spent.to_dict(), "stopping": r["stop"]}

    def public(self, did: str, lang: str = "fr") -> dict:
        g = self.ensure(did)
        out = G.public(g, lang)
        out["run"] = self.run_state(did)
        out["budgets"] = Budgets.from_settings(self.ctx.settings).to_dict()
        d = self.ctx.repo.get(did)
        out["memory"] = {"digest_chars": len(G.digest(g, self.project_rows(d.project_id if d else "", did))),
                         "project_rows": len(self.project_rows(d.project_id if d else "", did))}
        return out

    # -- runs
    async def start(self, did: str, overrides: dict | None = None, mode: str | None = None) -> dict:
        d = self.ctx.repo.get(did)
        if d is None:
            raise G.GraphError("not_found", 404)
        if not d.statement:
            raise G.GraphError("no_statement", 409)
        if d.proof_is_current:
            raise G.GraphError("already_proved", 409)
        r = self.runs.get(did)
        if r is not None and not r["task"].done():
            raise G.GraphError("busy", 409)
        if self.ctx.orchestrator.active_for(did):
            raise G.GraphError("busy", 409)
        g = self.ensure(did)
        b = Budgets.from_settings(self.ctx.settings, overrides)
        mode = mode or self.ctx.settings.mode
        ops = LeanOps(self.ctx, self, did, mode)
        state = {"stop": False}
        search = ReasonedSearch(g, ops, b, save=lambda: self.save(did), publish=lambda: self.publish(did),
                                should_stop=lambda: state["stop"])
        state["search"] = search

        async def go():
            from ..brain import spend
            scope = f"graph:{did}:{search.run_id}"
            ledger = getattr(getattr(self.ctx.brain, "ledger", None), "scope_caps", None)
            if ledger is not None:
                ledger[scope] = b.usd
            tok = spend.SPEND_SCOPE.set(scope)
            try:
                summary = await search.run()
                if summary["reason"] == "solved":
                    await self._store_root(did, g)
                try:
                    self.learn_from_run(did, summary)
                except Exception:  # noqa: BLE001
                    log.exception("lessons from run")
                return summary
            except asyncio.CancelledError:
                search.g.setdefault("runs", []).append(search.summary("stopped"))
                self.save(did)
                raise
            except Exception:  # noqa: BLE001
                log.exception("reasoned search failed")
                g.setdefault("runs", []).append(search.summary("error"))
                self.save(did)
                return None
            finally:
                spend.SPEND_SCOPE.reset(tok)
                if ledger is not None:
                    ledger.pop(scope, None)
                try:
                    self.ctx.local.release_owner(f"graph-{did}")
                except Exception:  # noqa: BLE001
                    pass
                self.publish(did)
        state["task"] = asyncio.create_task(go())
        self.runs[did] = state
        G.touch(g, "run_start", g["root"], run=search.run_id)
        self.save(did)
        self.publish(did)
        return self.public(did)

    async def _store_root(self, did: str, g: dict) -> None:
        """The search proved the goal with a self-contained proof: it becomes the dossier's proof through the
        planner's strict path (fresh strict check, library)."""
        d = self.ctx.repo.get(did)
        root = g["nodes"][g["root"]]
        if d is None or d.proof_is_current or not root.get("proof") or not root.get("self_contained", True):
            return
        from .proofplan import body_of
        name = leancheck.theorem_name(d.statement)
        body = body_of(root["proof"], name)
        pre = root["proof"][:root["proof"].rfind(f"theorem {name}")] if f"theorem {name}" in root["proof"] else ""
        ok = await self.planner._store_proof(d, root["proof"] if pre.strip() else
                                             f"theorem {name} := by\n{indent(body)}", "graph",
                                             model="")
        if not ok and pre.strip():
            log.info("graph proof not stored (strict check refused)")

    def stop(self, did: str) -> dict:
        r = self.runs.get(did)
        if r is None or r["task"].done():
            raise G.GraphError("not_running", 409)
        r["stop"] = True
        self.publish(did)
        return {"stopping": True}

    async def wait(self, did: str, timeout: float = 600) -> dict | None:
        r = self.runs.get(did)
        if r is None:
            return None
        return await asyncio.wait_for(asyncio.shield(r["task"]), timeout)

    # -- user actions
    def abandon(self, did: str, nid: str, reason: str = "") -> dict:
        g = self.ensure(did)
        if nid not in g["nodes"]:
            raise G.GraphError("not_found", 404)
        if nid == g["root"]:
            r = self.runs.get(did)
            if r is not None and not r["task"].done():
                r["stop"] = True
        n = g["nodes"][nid]
        if n["status"] in G.VERIFIED:
            raise G.GraphError("already_proved", 409)
        G.set_status(g, nid, "abandoned", ("stopped by the user" + (f": {reason}" if reason else ""))[:500],
                     env=g.get("env"))
        n["by_user"] = True
        self.save(did)
        self.publish(did)
        return self.public(did)

    def resume(self, did: str, nid: str) -> dict:
        """« Reprendre »: an abandoned (or refuted by the user's choice: never) node is open again, its memory of
        errors cleared — the user decided something changed."""
        g = self.ensure(did)
        if nid not in g["nodes"]:
            raise G.GraphError("not_found", 404)
        n = g["nodes"][nid]
        if n["status"] != "abandoned":
            raise G.GraphError("not_abandoned", 409)
        G.set_status(g, nid, "open", "")
        n["errors_seen"], n["expand_first"], n["by_user"] = {}, False, False
        G.touch(g, "resumed", nid)
        self.save(did)
        self.publish(did)
        return self.public(did)

    def why(self, did: str, nid: str, lang: str = "fr") -> dict:
        g = self.ensure(did)
        if nid not in g["nodes"]:
            raise G.GraphError("not_found", 404)
        n = g["nodes"][nid]
        parents = G.users_of(g, nid)
        siblings = []
        for p in parents:
            for t in g["nodes"][p].get("tracks") or []:
                siblings.append({"parent": p, "idea": t.get("idea", ""), "active": t.get("active"),
                                 "abandoned": t.get("abandoned"), "why": t.get("why", ""),
                                 "lemmas": [{"node": x, "title": g["nodes"][x]["title"],
                                             "state": G.effective(g, x)["state"],
                                             "score": (g["nodes"][x].get("viability") or {}).get("score")}
                                            for x in t.get("lemmas") or [] if x in g["nodes"]]})
        return {"node": nid, "title": n["title"], "why": n.get("why", ""), "viability": n.get("viability"),
                "reason_text": G.reason_text(n.get("viability"), lang), "status": n["status"],
                "reason": n.get("reason", ""), "state": G.effective(g, nid), "alternatives": siblings,
                "attempts": n.get("attempts") or [], "attempts_n": n.get("attempts_n", 0),
                "source": n.get("source"), "sources": n.get("sources", []), "citation": n.get("citation")}

    def explain(self, did: str, nid: str | None = None, lang: str = "fr") -> dict:
        return G.explain(self.ensure(did), nid, lang)

    async def export(self, did: str, nid: str | None, fmt: str, lang: str = "fr", device: str = "") -> dict:
        e = self.explain(did, nid, lang)
        if fmt == "latex":
            return G.explanation_latex(e)
        if fmt == "bibtex":
            return {"bibtex": e["bibliography"]["bibtex"]}
        if fmt == "markdown":
            return {"markdown": e["text"]}
        if fmt == "note":
            d = self.ctx.repo.get(did)
            notes = getattr(getattr(self.ctx, "research", None), "notes", None)
            if d is None or notes is None:
                raise G.GraphError("no_notes", 409)
            body = e["text"]
            if e["bibliography"]["bibtex"]:
                body += "\n```bibtex\n" + e["bibliography"]["bibtex"] + "```\n"
            title = ("Explication — " if e["lang"] == "fr" else "Explanation — ") + e["title"]
            n = await asyncio.to_thread(notes.create, d.project_id, title[:180], body, ["explication"], "note", device)
            self.ctx.publish("note.updated", {"note": n.to_dict(), "device": device})
            return {"note": n.to_dict()}
        raise G.GraphError("bad_format")

    def add_cited(self, did: str, items: list, parent: str | None = None, edge: str = "uses") -> dict:
        """Cited lemmas from the literature (S-AX): new `cited` nodes (deduplicated by statement key), optionally
        « used » by `parent`. Never « proved »: a proof that uses them is conditional."""
        g = self.ensure(did)
        added = []
        for it in list(items or [])[:20]:
            node, created = G.add_node(g, G.cited_node(it), parent=parent if parent in g["nodes"] else None,
                                       edge=edge if edge in G.EDGE_KINDS else "uses")
            added.append({"node": node["id"], "created": created})
        self.save(did)
        self.publish(did)
        return {"added": added, "graph": self.public(did)}

    async def literature(self, did: str, nid: str | None = None, limit: int = 5) -> dict:
        """Ask the literature package (S-AX) for results related to a node; adds them as cited nodes. Without the
        package, says so (nothing invented)."""
        from . import literature_iface as LI
        g = self.ensure(did)
        nid = nid or g["root"]
        if nid not in g["nodes"]:
            raise G.GraphError("not_found", 404)
        n = g["nodes"][nid]
        items = await LI.search(self.ctx, n.get("statement_nl") or n["title"], lean=n.get("lean", ""), limit=limit)
        d = self.ctx.repo.get(did)
        provided = LI.provided(self.ctx, d) if d is not None else []
        if items is None and not provided:
            return {"available": False, "added": [], "graph": self.public(did)}
        res = self.add_cited(did, list(provided) + list(items or []), parent=None)
        return {"available": items is not None, **res}

    async def adapt(self, did: str, nid: str, mode: str | None = None) -> dict:
        """« Adapter la méthode »: from a node with a recorded method (its Lean proof, or the quoted text of a cited
        result), the model proposes a generalised statement and the adapted lemmas — added as PROPOSALS (open,
        labelled), whose Lean statements are checked by Lean before they are kept; only Lean will prove them."""
        g = self.ensure(did)
        if nid not in g["nodes"]:
            raise G.GraphError("not_found", 404)
        n = g["nodes"][nid]
        method = n.get("proof") or ((n.get("citation") or {}).get("quote") or "")
        if not method:
            raise G.GraphError("no_method", 409)
        ops = LeanOps(self.ctx, self, did, mode or self.ctx.settings.mode)
        root = g["nodes"][g["root"]]
        text, model, _tok, _usd = await ops._ask(adapt_messages(n["title"], n.get("lean", ""), method,
                                                               root.get("lean", "")), 4000, 0.4)
        idea, lemmas, _comb, gen = parse_lemmas(text)
        cand = []
        if gen and split_decl(str(gen.get("lean") or "")):
            gp = split_decl(str(gen["lean"]))
            cand.append({"name": "general", "title": str(gen.get("title") or "énoncé généralisé")[:200],
                         "statement_nl": str(gen.get("statement") or "")[:2000], "why": idea,
                         "lean": f"theorem {gp[1]} {gp[2]} := by sorry", "general": True})
        cand += [{**lm, "general": False} for lm in lemmas[:MAX_LEMMAS]]
        if not cand:
            return {"added": [], "refused": [], "graph": self.public(did)}
        # Lean checks the statements (with sorry) before anything is kept
        refused, ok = [], []
        if ops.ws is not None:
            code, spans = gate_file(ops.context, "adapt_target", "(x : True) : True",
                                    [{"lemmas": [{"name": f"adapt_{i}", "sig": split_decl(c["lean"])[2]}
                                                 for i, c in enumerate(cand)], "combination": ""}], equiv=False)
            r = await self.ctx.lean.check(code, ops.ws, max(120, self.ctx.settings.compile_timeout_s), None,
                                          owner=f"graph-adapt-{did}")
            gate = read_gate(spans, leancheck.parse_lean_json(r.stdout) if r.stdout else list(r.verdict.errors))
            for i, c in enumerate(cand):
                e = gate.get(("lemma", 0, i), {}).get("errors") or ([] if not (r.timed_out or r.infra_error)
                                                                     else ["Lean unavailable"])
                (refused if e else ok).append({**c, "err": "; ".join(e)[:300]})
        general_id = None
        added = []
        for c in ok:
            node = G.new_node("proposal", c["title"], lean=c["lean"], statement_nl=c["statement_nl"], why=c["why"],
                              source={"kind": "method", "from": nid, "model": model})
            node["proposal"] = True
            node, _ = G.add_node(g, node)
            if c["general"]:
                general_id = node["id"]
                G.add_edge(g, node["id"], "generalises", nid)
            added.append(node["id"])
        if general_id:
            for x in added:
                if x != general_id:
                    G.add_edge(g, general_id, "uses", x)
        G.touch(g, "adapt", nid, added=len(added))
        self.save(did)
        self.publish(did)
        return {"added": added, "refused": [{"title": c["title"], "reason": c["err"]} for c in refused],
                "idea": idea, "graph": self.public(did)}

    def adopt(self, did: str, nid: str) -> dict:
        """Use a proposal as a lemma of the goal (« uses » edge from the goal); it stays to be proved by Lean."""
        g = self.ensure(did)
        if nid not in g["nodes"]:
            raise G.GraphError("not_found", 404)
        if not G.add_edge(g, g["root"], "uses", nid):
            raise G.GraphError("cycle", 409)
        g["nodes"][nid]["depth"] = 1
        self.save(did)
        self.publish(did)
        return self.public(did)

    # -- sub-dossiers: a lemma node opened as a full dossier (a dossier with a parent, nothing more)
    def chain_depth(self, did: str) -> int:
        n, x, seen = 0, self.ctx.repo.get(did), set()
        while x is not None and x.parent_id and x.id not in seen and n < 50:
            seen.add(x.id)
            n += 1
            x = self.ctx.repo.get(x.parent_id)
        return n

    async def open_node(self, did: str, nid: str, device: str = "") -> dict:
        """« Ouvrir comme sous-dossier »: the lemma gets its own dossier (statement / proof thread, its own graph,
        Calcul, notes, certificates, literature), child of this one. Idempotent: an existing one is returned."""
        from ..server.routes_work import create_dossier
        g = self.ensure(did)
        if nid not in g["nodes"] or nid == g["root"]:
            raise G.GraphError("not_found", 404)
        n = g["nodes"][nid]
        if n.get("dossier_id") and self.ctx.repo.get(n["dossier_id"]) is not None:
            return {"dossier_id": n["dossier_id"], "created": False}
        d = self.ctx.repo.get(did)
        shared = self._family_dossier(did, n["key"], d.workspace)
        if shared is not None:
            # the same statement is already a sub-dossier of this family: one dossier, several users
            also = shared.extra.setdefault("graph_also", [])
            link = {"graph_dossier": did, "node": nid}
            if link not in also and shared.extra.get("graph") != link:
                also.append(link)
                del also[:-20]
                await self.ctx.repo.save(shared)
            n["dossier_id"] = shared.id
            G.touch(g, "sub_dossier_shared", nid, dossier=shared.id)
            self.save(did)
            self.rollup(shared)
            self.publish(did)
            return {"dossier_id": shared.id, "created": False, "shared": True}
        limit = max(1, int(getattr(self.ctx.settings, "plan_max_depth", 3) or 3))
        if self.chain_depth(did) + 1 > limit:
            raise G.GraphError("too_deep", 409, n=limit)
        parts = split_decl(d.statement or "") if d.statement else None
        context = parts[0] if parts else ""
        lean = (context + "\n\n" + n["lean"]).strip() if n.get("lean") else ""
        spec = {"title": n["title"], "problem": n.get("statement_nl") or n["title"], "statement": lean,
                "project_id": d.project_id, "workspace": d.workspace, "parent_id": d.id, "kind": "lemma",
                "start": False}
        try:
            child, _job = await create_dossier(self.ctx, spec, user_event=True)
        except leancheck.StatementError:
            spec["statement"] = ""
            child, _job = await create_dossier(self.ctx, spec, user_event=True)
        child.extra["graph"] = {"graph_dossier": did, "node": nid}
        await self.ctx.repo.save(child)
        n["dossier_id"] = child.id
        G.touch(g, "sub_dossier", nid, dossier=child.id)
        self.save(did)
        self.publish(did)
        return {"dossier_id": child.id, "created": True}

    def family(self, did: str) -> list:
        """The top-level dossier of `did` and all its sub-dossiers (bounded)."""
        from ..server.routes_work import descendants
        top, seen = self.ctx.repo.get(did), set()
        while top is not None and top.parent_id and top.id not in seen and len(seen) < 50:
            seen.add(top.id)
            up = self.ctx.repo.get(top.parent_id)
            if up is None:
                break
            top = up
        return [top] + descendants(self.ctx, top.id) if top is not None else []

    def _family_dossier(self, did: str, key: str, workspace: str):
        """A sub-dossier of the same top-level dossier and workspace whose statement has this key."""
        if not key:
            return None
        for x in self.family(did):
            if x.id == did or not x.parent_id or (x.workspace or "") != (workspace or ""):
                continue
            g = self.get(x.id)
            if g is not None and g["nodes"][g["root"]].get("key") == key:
                return x
            if g is None and x.statement and G.statement_key(x.statement) == key:
                return x
        return None

    def rollup(self, child) -> None:
        """A sub-dossier changed: its verdict rolls up into EVERY graph node that uses it (a shared sub-lemma has
        several users), then up each chain. Bounded and cycle-safe."""
        seen: set[str] = set()
        queue = [child]
        while queue and len(seen) < 40:
            child = queue.pop(0)
            if child is None or child.id in seen:
                continue
            seen.add(child.id)
            links = [child.extra.get("graph")] + list(child.extra.get("graph_also") or [])
            cg = self.get(child.id)
            if cg is not None:
                self._sync_dossier(cg, child)
            for link in links:
                if not isinstance(link, dict) or self.ctx.repo.get(link.get("graph_dossier", "")) is None:
                    continue
                pid = link["graph_dossier"]
                pg = self.ensure(pid)
                nid = link.get("node")
                if nid not in pg["nodes"]:
                    continue
                if child.proof_is_current and pg["nodes"][nid].get("proof") != child.proof:
                    pg["nodes"][nid]["proof"] = (child.proof or "")[:G.MAX_PROOF_CHARS]
                    pg["nodes"][nid]["tactics"] = G.tactics_of(child.proof or "")
                if G.rollup(pg, nid, cg, bool(child.proof_is_current)):
                    self.save(pid)
                    self.publish(pid)
                queue.append(self.ctx.repo.get(pid))

    # -- memory: recording finished jobs, the provers' digest
    def _graph_for(self, d) -> tuple[str, dict, str] | None:
        """(graph dossier, graph, node) for a dossier: its own graph's goal, or the node of its plan's graph."""
        link = d.extra.get("plan") if isinstance(d.extra.get("plan"), dict) else None
        if link and self.store.load(link.get("plan_dossier", "")) is not None:
            pid = link["plan_dossier"]
            g = self.ensure(pid)
            n = next((x for x in g["nodes"].values() if x.get("dossier_id") == d.id or
                      (link.get("node") and x.get("plan_node") == link.get("node"))), None)
            if n is not None:
                return pid, g, n["id"]
        if not d.statement:
            return None
        return d.id, self.ensure(d.id), self.ensure(d.id)["root"]

    async def on_job(self, job: dict) -> None:
        if not getattr(self.ctx.settings, "problem_graph", True):
            return
        if job.get("state") not in ("done", "failed"):
            return
        d = self.ctx.repo.get(job.get("dossier_id", ""))
        if d is None:
            return
        try:
            self.learn_from_job(job, d)
        except Exception:  # noqa: BLE001 (learning never breaks a job)
            log.exception("lessons")
        found = self._graph_for(d)
        if found is None:
            return
        did, g, nid = found
        n = g["nodes"][nid]
        proof_attempts = [a for a in job.get("attempts") or [] if a.get("stage") == "proof"]
        if d.proof_is_current:
            meta = d.proofs[d.cur_proof].meta if d.proofs else {}
            if nid == g["root"] and did == d.id:
                self._sync_dossier(g, d)
            elif n["status"] not in G.VERIFIED:
                n["proof"] = (d.proof or "")[:G.MAX_PROOF_CHARS]
                n["tactics"] = G.tactics_of(d.proof or "")
                G.set_status(g, nid, "certified" if meta.get("strategy") == "certificate" else "proved", "",
                             self_contained=True)
            if not any(a.get("job") == job.get("id") for a in n.get("attempts") or []):
                G.record_attempt(g, nid, how=str(meta.get("strategy") or "pipeline"), ok=True,
                                 model=str(d.proofs[d.cur_proof].model if d.proofs else ""), proof=d.proof or "",
                                 seconds=float(meta.get("seconds") or 0))
                n["attempts"][-1]["job"] = job.get("id")
        elif proof_attempts and job.get("state") == "failed":
            last = next((a for a in reversed(proof_attempts) if a.get("errors_text")), proof_attempts[-1])
            err = (last.get("errors_text") or job.get("error") or "no proof found")
            if not any(a.get("job") == job.get("id") for a in n.get("attempts") or []):
                G.record_attempt(g, nid, how="pipeline", ok=False, error=err, model=str(last.get("model") or ""))
                n["attempts"][-1]["job"] = job.get("id")
        else:
            self.rollup(d)
            return
        self.save(did)
        self.publish(did)
        self.rollup(d)

    def env_of(self, d) -> dict:
        from ..runtime.lean import workspace_info
        try:
            return workspace_info(self.ctx.workspace(d.workspace or self.ctx.settings.workspace)) or {}
        except Exception:  # noqa: BLE001
            return {}

    def learn_from_job(self, job: dict, d) -> None:
        """D57b: lessons from a finished job — only from a verified success (the fix after an error, renames, the
        strategy), never from a model's opinion."""
        from . import lessons
        st = lessons.store_of(self.ctx)
        if st is None or not d.statement or not d.proof_is_current or job.get("state") != "done":
            return
        env = self.env_of(d)
        proof = [a for a in job.get("attempts") or [] if a.get("stage") == "proof"]
        ok = next((a for a in reversed(proof) if a.get("status") == "accepted"), None)
        meta = d.proofs[d.cur_proof].meta if d.proofs else {}
        if ok is None:
            return
        bad = [a for a in proof if a.get("status") == "rejected" and a.get("errors_text") and a.get("code")
               and a["index"] < ok["index"]]
        if bad:
            st.learn_fix(bad[-1]["code"], bad[-1]["errors_text"], ok.get("code") or d.proof, d.statement, env, d.id)
        st.learn_strategy(d.statement, str(meta.get("strategy") or "pipeline"), G.tactics_of(d.proof or ""), env,
                          d.id)

    def learn_from_run(self, did: str, summary: dict) -> None:
        from . import lessons
        st = lessons.store_of(self.ctx)
        g = self.get(did)
        d = self.ctx.repo.get(did)
        if st is None or g is None or d is None:
            return
        env = self.env_of(d)
        for t in summary.get("tried") or []:
            n = g["nodes"].get(t.get("node", ""))
            if n is not None and n.get("lean") and t.get("reason") and not n.get("by_user"):
                st.learn_approach(n["lean"], n["title"], t["reason"], env, did)

    def prover_hint(self, d) -> str:
        """The compact memory digest for the provers of dossier `d` ("" when nothing useful is known)."""
        if not getattr(self.ctx.settings, "problem_graph", True) or d is None:
            return ""
        try:
            found = None
            link = d.extra.get("plan") if isinstance(d.extra.get("plan"), dict) else None
            gid = link.get("plan_dossier") if link and self.store.load(link.get("plan_dossier", "")) else d.id
            g = self.get(gid)
            if g is None:
                rows = self.project_rows(d.project_id, d.id)
                if not rows:
                    return ""
                found = {"v": 1, "root": "_", "nodes": {"_": G.new_node("goal", d.title)}, "edges": []}
                return G.digest(found, rows)
            return G.digest(g, self.project_rows(d.project_id, gid))
        except Exception:  # noqa: BLE001 (memory is a help, never a failure)
            log.exception("graph digest")
            return ""
