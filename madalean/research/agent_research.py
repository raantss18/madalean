"""« Consigne de recherche » (session S-Q, user decision 2026-11-21): in a project, the user gives a source (an article)
and an instruction in natural language — « vérifie les résultats avec Lean, ajoute des exemples et des graphiques avec
Sage, améliore la rédaction, généralise le théorème 2 ». Madalean plans and runs bounded steps with the EXISTING
features only, and PROPOSES; the user validates each change.

Steps (a fixed vocabulary; nothing else can run):
  blueprint   paper → blueprint (papers.extract), kept when it exists
  context     grounded summary of the source (qa.grounded over the source's passages: every claim cites a passage)
  import      only when « rédaction » is asked and the article has no text yet: the paper's sections are copied
              VERBATIM into the article (the user's text, unchanged; deleting the blocks undoes it)
  verify      draft dossiers for the targeted nodes (papers.create_dossiers) + normal pipeline jobs (statement check,
              Mathlib first, tournament, proof plans — whatever the settings say), waited for within the time budget
  examples    Sage code written by the model → Calcul cells (origin « assistant »: they run only once approved, or by
  figures     themselves when the host enabled `experiments_auto`) + a suggested paragraph citing the cell
  improve     wording suggestions on the article's text: an exact excerpt → its replacement (code-checked: the
              excerpt must exist; changed formulas are flagged)
  generalise  literature search (litsearch) for context, a generalised statement proposed by the model, created as a
              CONJECTURE (conjecture workshop) with a Sage counter-example experiment and a Lean job; it is written
              « Conjecture » in the suggestion until Lean proves it

Every change of the article is a SUGGESTION {type: correction | exemple | figure | generalisation | verification,
before, after, rationale, evidence: Lean dossiers, Calcul cells, citations} accepted or rejected one by one; accepting
re-checks that the text it replaces is still there (else « stale »). Nothing in the article is rewritten otherwise.

Bounded (max steps, minutes, cost; Claude stays inside the user's caps: the run is its own spend scope), cancellable,
resumable (state saved after each step; a run interrupted by a restart is shown « paused »), and every step is logged
in a research journal (a project note). Storage: `<project>/research/` (runs/<id>.json, suggestions.json,
basket.json)."""
from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import uuid
from pathlib import Path

from .. import config
from ..i18n import msg
from ..logs import get
from .safety import UNTRUSTED_RULE, wrap_untrusted

log = get("research.agent")
TYPES = ("correction", "exemple", "figure", "generalisation", "verification")
STEP_KINDS = ("blueprint", "context", "import", "verify", "examples", "figures", "improve", "generalise")
LIMITS = {"max_steps": (12, 1, 40), "max_minutes": (30, 1, 240), "max_cost_usd": (0.5, 0.0, 20.0),
          "max_targets": (3, 1, 10), "max_suggestions": (30, 1, 100)}
MAX_INSTRUCTION = 4000
VERIFY_SHARE = 0.5
CALL_TIMEOUT_S = 300.0
MAX_SUGGESTIONS_KEPT = 500
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
MATH_RE = re.compile(r"\$\$.+?\$\$|\$[^$\n]+\$", re.S)


class ResearchError(Exception):
    def __init__(self, kind: str, status: int = 400, **info):
        super().__init__(kind)
        self.kind, self.status, self.info = kind, status, info


def _now() -> float:
    return time.time()


# ================================================================ instruction → steps
STEP_PATTERNS = {
    "verify": r"v[ée]rifi|\blean\b|formalis|\bprouv|\bd[ée]montr|\bcheck|\bverif|\bprove",
    "examples": r"exemple|example|illustr|cas particulier|special case",
    "figures": r"graphique|figure|courbe|trac[ée]|\bplot|\bgraph|dessin|visualis|diagram",
    "improve": r"r[ée]daction|r[ée]dig|\bstyle|clart[ée]|relis|relecture|proofread|wording|writing|\btypo|"
               r"orthograph|grammaire|grammar|reformul|rephrase|polish",
    "generalise": r"g[ée]n[ée]ralis|generali[sz]|[ée]tend|extend|affaibli|weaken",
}
TARGET_RE = re.compile(r"(?i)\b(th[ée]or[èe]mes?|theorems?|lemmes?|lemmas?|propositions?|corollaires?|corollar(?:y|ies)|"
                       r"d[ée]finitions?|conjectures?)\s+((?:\d+(?:\.\d+)*)(?:\s*(?:,|et|and|&)\s*\d+(?:\.\d+)*)*)")
KIND_WORDS = {"th": "theorem", "le": "lemma", "pr": "proposition", "co": "corollary", "d": "definition"}


def _kind_of(word: str) -> str:
    w = word.lower()
    if w.startswith("conj"):
        return "conjecture"
    if w.startswith("cor"):
        return "corollary"
    if w.startswith("d"):
        return "definition"
    for k, v in KIND_WORDS.items():
        if w.startswith(k):
            return v
    return "theorem"


def parse_instruction(text: str) -> dict:
    """{steps: {kind: [targets]}, order: [kinds]} — deterministic (FR/EN). A clause's targets belong to the steps
    named in the same clause (« généralise le théorème 2 » targets only the generalisation)."""
    text = (text or "")[:MAX_INSTRUCTION]
    steps: dict[str, list[dict]] = {}
    order: list[str] = []
    for clause in re.split(r"[;\n!?]|\.(?!\d)|,(?!\s*\d)|\bpuis\b|\bthen\b|\bensuite\b", text):
        kinds = [k for k, pat in STEP_PATTERNS.items() if re.search(pat, clause, re.I)]
        targets = []
        for m in TARGET_RE.finditer(clause):
            for num in re.findall(r"\d+(?:\.\d+)*", m.group(2)):
                targets.append({"kind": _kind_of(m.group(1)), "number": num})
        for k in kinds:
            if k not in steps:
                steps[k] = []
                order.append(k)
            steps[k] += [t for t in targets if t not in steps[k]]
    return {"steps": steps, "order": order}


def plan(parsed: dict, *, has_blueprint: bool, article_has_text: bool, limits: dict) -> list[dict]:
    """The bounded list of steps shown to the user before anything runs."""
    want = parsed["steps"]
    out = [{"kind": "blueprint"}] if not has_blueprint else []
    out.append({"kind": "context"})
    if "improve" in want and not article_has_text:
        out.append({"kind": "import"})
    for k in ("verify", "examples", "figures", "improve", "generalise"):
        if k in want:
            out.append({"kind": k, "targets": want[k]})
    out = out[: limits["max_steps"]]
    for i, s in enumerate(out, 1):
        s.update(id=f"s{i}", status="todo", targets=s.get("targets", []), result={}, started=0.0, ended=0.0)
    return out


def clamp_limits(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for k, (dflt, lo, hi) in LIMITS.items():
        try:
            v = float(raw.get(k, dflt))
        except (TypeError, ValueError):
            v = dflt
        v = max(lo, min(hi, v))
        out[k] = int(v) if isinstance(dflt, int) else round(v, 2)
    return out


# ================================================================ storage
class Store:
    """Per project: runs/<rid>.json, suggestions.json, basket.json (atomic writes, one lock)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._lock = threading.RLock()

    def dir(self, pid: str) -> Path:
        d = self.ctx.projects.store.dir(pid) / "research"
        (d / "runs").mkdir(parents=True, exist_ok=True)
        return d

    def _read(self, path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write(self, path: Path, data) -> None:
        config.atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1))

    # ---- runs
    def save_run(self, run: dict) -> None:
        run["updated"] = _now()
        with self._lock:
            self._write(self.dir(run["project_id"]) / "runs" / f"{run['id']}.json", run)

    def run(self, pid: str, rid: str) -> dict | None:
        if not ID_RE.match(rid or ""):
            return None
        return self._read(self.dir(pid) / "runs" / f"{rid}.json", None)

    def runs(self, pid: str) -> list[dict]:
        out = [self._read(p, None) for p in (self.dir(pid) / "runs").glob("*.json")]
        return sorted([r for r in out if isinstance(r, dict)], key=lambda r: -r.get("created", 0))

    # ---- suggestions
    def suggestions(self, pid: str) -> list[dict]:
        data = self._read(self.dir(pid) / "suggestions.json", [])
        return data if isinstance(data, list) else []

    def add_suggestion(self, pid: str, s: dict) -> dict:
        with self._lock:
            lst = self.suggestions(pid)
            lst.append(s)
            if len(lst) > MAX_SUGGESTIONS_KEPT:      # oldest decided ones go first
                decided = [x for x in lst if x["status"] != "proposed"]
                for x in decided[: len(lst) - MAX_SUGGESTIONS_KEPT]:
                    lst.remove(x)
            self._write(self.dir(pid) / "suggestions.json", lst)
        return s

    def update_suggestion(self, pid: str, sid: str, fn) -> dict:
        with self._lock:
            lst = self.suggestions(pid)
            s = next((x for x in lst if x["id"] == sid), None)
            if s is None:
                raise ResearchError("not_found", 404)
            fn(s)
            self._write(self.dir(pid) / "suggestions.json", lst)
            return s

    # ---- « send to Publier » basket
    def basket(self, pid: str) -> dict:
        b = self._read(self.dir(pid) / "basket.json", {})
        return {k: [x for x in b.get(k, []) if isinstance(x, str)] for k in ("dossiers", "notes", "calcul")}

    def basket_add(self, pid: str, kind: str, item: str, remove: bool = False) -> dict:
        with self._lock:
            b = self.basket(pid)
            lst = b[kind]
            if remove:
                b[kind] = [x for x in lst if x != item]
            elif item not in lst:
                lst.append(item)
            self._write(self.dir(pid) / "basket.json", b)
            return b


# ================================================================ helpers
def new_suggestion(run: dict, type_: str, *, title: str, before: str, after: str, rationale: str, target: dict,
                   evidence: dict | None = None, **extra) -> dict:
    assert type_ in TYPES
    touches = sorted(set(MATH_RE.findall(before))) != sorted(set(MATH_RE.findall(after))) and bool(before)
    return {"id": "sg-" + uuid.uuid4().hex[:10], "run_id": run["id"], "project_id": run["project_id"], "type": type_,
            "title": title[:300], "before": before, "after": after, "rationale": rationale[:3000], "target": target,
            "evidence": evidence or {}, "touches_math": touches, "status": "proposed", "created": _now(),
            "decided": 0.0, "model": extra.pop("model", ""), **extra}


def json_block(text: str):
    """The first JSON object / array in a model answer (code fences tolerated)."""
    t = re.sub(r"<think>.*?(</think>|$)", "", text or "", flags=re.S)
    m = re.search(r"```(?:json)?\s*(.+?)```", t, re.S)
    if m:
        t = m.group(1)
    for opener, closer in (("[", "]"), ("{", "}")):
        i, j = t.find(opener), t.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except ValueError:
                continue
    return None


def extract_code(text: str) -> str:
    m = re.search(r"```(?:sage|python|py)?\s*\n(.+?)```", text or "", re.S)
    return (m.group(1) if m else "").strip()


def paragraph_of(text: str, excerpt: str) -> str:
    """The paragraph of `text` that contains `excerpt` (for a readable « before »)."""
    for p in re.split(r"\n\s*\n", text):
        if excerpt in p:
            return p
    return excerpt


def vacuous(lean: str) -> bool:
    from .. import leancheck
    return leancheck.vacuous(lean)


def node_label(n: dict) -> str:
    return (f"{n.get('name') or n.get('kind', '').title()} {n.get('number', '')}".strip() +
            (f" ({n['title']})" if n.get("title") else ""))


def select_nodes(bp: dict | None, targets: list[dict], limit: int, kinds=("theorem", "proposition", "corollary",
                                                                          "lemma")) -> list[dict]:
    if not bp:
        return []
    nodes = bp.get("nodes", [])
    if targets:
        out = []
        for t in targets:
            num, same = t["number"], [n for n in nodes if n.get("kind") == t["kind"]]
            pick = ([n for n in same if str(n.get("number")) == num] or
                    # « théorème 1 » in a paper numbered 1.1, 1.2, …
                    [n for n in same if str(n.get("number", "")).startswith(num + ".")] or
                    # else the n-th result of that kind, else any result with that number
                    (same[int(num) - 1: int(num)] if num.isdigit() and 0 < int(num) <= len(same) else []) or
                    [n for n in nodes if str(n.get("number")) == num])
            out += [n for n in pick[:1] if n not in out]
        return out[:limit]
    return [n for n in nodes if n.get("kind") in kinds][:limit]


# ================================================================ the agent
class Agent:
    """One per server. `calc` is the Calcul adapter given by the plugin (add_cell / run_allowed / cell / cells)."""

    def __init__(self, ctx, calc=None, notes=None, workshop=None, art_lock=None):
        self.ctx = ctx
        self.store = Store(ctx)
        self.calc = calc
        self._notes, self._workshop = notes, workshop
        self.art_lock = art_lock or (lambda pid: self._locks.setdefault(pid, asyncio.Lock()))
        self._locks: dict[str, asyncio.Lock] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self._left = CALL_TIMEOUT_S

    # the research workshop (notes, conjectures) is resolved when used: plugins register in any order
    @property
    def notes(self):
        return self._notes if self._notes is not None else getattr(getattr(self.ctx, "research", None), "notes", None)

    @property
    def workshop(self):
        return self._workshop if self._workshop is not None else \
            getattr(getattr(self.ctx, "research", None), "workshop", None)

    # ------------------------------------------------------------ public state
    def public_run(self, run: dict) -> dict:
        r = dict(run)
        if r.get("status") == "running" and r["id"] not in self.tasks:
            r["status"] = "paused"                       # interrupted by a restart: resumable
            r["paused_reason"] = "interrupted"
        return r

    def runs(self, pid: str) -> list[dict]:
        return [self.public_run(r) for r in self.store.runs(pid)]

    def publish_run(self, run: dict) -> None:
        self.ctx.publish("research.run", {"project_id": run["project_id"], "run": self.public_run(run)})

    def publish_suggestion(self, s: dict) -> None:
        self.ctx.publish("research.suggestion", {"project_id": s["project_id"], "suggestion": self.resolve(s)})

    # ------------------------------------------------------------ start / cancel / resume
    def prepare(self, pid: str, source: dict, instruction: str, limits: dict | None, mode: str) -> dict:
        from . import article as art_mod
        from . import papers
        from .sources import library
        instruction = (instruction or "").strip()
        if not instruction:
            raise ResearchError("empty_instruction")
        lib = library(self.ctx)
        shelf, sid = str(source.get("shelf") or pid), str(source.get("id") or "")
        src = lib.get(shelf, sid)                         # raises SourceError not_found
        lim = clamp_limits(limits)
        parsed = parse_instruction(instruction)
        if not parsed["order"]:
            raise ResearchError("nothing_understood", 422)
        bp = papers.load(self.ctx, pid, src["id"])
        art = art_mod.load(self.ctx, pid)
        has_text = any((b.get("text") or "").strip() for b in art["blocks"] if b["kind"] != "dossier")
        steps = plan(parsed, has_blueprint=bool(bp and bp.get("nodes")), article_has_text=has_text, limits=lim)
        return {"id": "rr-" + uuid.uuid4().hex[:10], "project_id": pid, "instruction": instruction[:MAX_INSTRUCTION],
                "source": {"shelf": shelf, "id": src["id"], "key": src["key"],
                           "title": str((src.get("csl") or {}).get("title", ""))[:300]},
                "limits": lim, "mode": mode, "steps": steps, "parsed": parsed, "status": "planned",
                "spent": {"seconds": 0.0, "cost_usd": 0.0, "model_calls": 0, "steps": 0},
                "journal_note": "", "suggestions": [], "jobs": [], "dossiers": [], "conjectures": [], "cells": [],
                "context": "", "citations": [], "created": _now(), "updated": _now(), "error": ""}

    def start(self, run: dict) -> dict:
        if run["id"] in self.tasks:
            raise ResearchError("busy", 409)
        busy = [r for r in self.store.runs(run["project_id"]) if r["id"] in self.tasks]
        if busy:
            raise ResearchError("busy", 409, run_id=busy[0]["id"])
        run["status"] = "running"
        run.pop("paused_reason", None)
        self.store.save_run(run)
        spawn = getattr(self.ctx, "spawn", None) or asyncio.ensure_future
        t = spawn(self._run(run))
        self.tasks[run["id"]] = t
        t.add_done_callback(lambda _t, rid=run["id"]: self.tasks.pop(rid, None))
        self.publish_run(run)
        return run

    def resume(self, pid: str, rid: str, limits: dict | None = None) -> dict:
        """Continue a run (steps done are kept). `limits` may raise a limit that stopped it (time, cost…)."""
        run = self.store.run(pid, rid)
        if run is None:
            raise ResearchError("not_found", 404)
        if run["status"] in ("done",):
            raise ResearchError("finished", 409)
        if isinstance(limits, dict):
            run["limits"] = clamp_limits({**run["limits"], **limits})
        run.pop("stopped_by", None)
        return self.start(run)

    async def cancel(self, pid: str, rid: str) -> dict:
        t = self.tasks.get(rid)
        if t is not None:
            t.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(t), 15)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass
        run = self.store.run(pid, rid)
        if run is None:
            raise ResearchError("not_found", 404)
        if run["status"] in ("running", "planned", "paused"):
            run["status"] = "cancelled"
            self.store.save_run(run)
        self.publish_run(run)
        return self.public_run(run)

    async def shutdown(self) -> None:
        for t in list(self.tasks.values()):
            t.cancel()

    # ------------------------------------------------------------ the loop
    def _cost(self, run: dict) -> float:
        led = getattr(getattr(self.ctx, "brain", None), "ledger", None)
        try:
            return float(led.scope_total(f"research:{run['id']}")) if led is not None else 0.0
        except Exception:  # noqa: BLE001
            return 0.0

    def _over(self, run: dict, t0: float) -> str:
        lim, sp = run["limits"], run["spent"]
        if sp["seconds"] + (time.monotonic() - t0) >= lim["max_minutes"] * 60:
            return "time"
        if lim["max_cost_usd"] > 0 and self._cost(run) >= lim["max_cost_usd"]:
            return "cost"
        if sp["steps"] >= lim["max_steps"]:
            return "steps"
        if len(run["suggestions"]) >= lim["max_suggestions"]:
            return "suggestions"
        return ""

    def remaining(self, run: dict, t0: float) -> float:
        self._left = max(0.0, run["limits"]["max_minutes"] * 60 - run["spent"]["seconds"] - (time.monotonic() - t0))
        return self._left

    async def _run(self, run: dict) -> None:
        from ..brain.spend import SPEND_SCOPE
        SPEND_SCOPE.set(f"research:{run['id']}")       # Claude stays inside the per-run (= per-proof) cap
        t0 = time.monotonic()
        try:
            resumed = any(st["status"] == "done" for st in run["steps"])
            await self._journal(run, (msg("Reprise de la consigne.")["text"] if resumed else
                                      msg("Consigne : {text}", text=run["instruction"][:500])["text"]), header=True)
            for step in run["steps"]:
                if step["status"] == "done":
                    continue
                self.remaining(run, t0)
                why = self._over(run, t0)
                if why:
                    run["status"], run["stopped_by"] = "stopped", why
                    await self._journal(run, msg("Arrêt : limite atteinte ({why}).", why=why)["text"])
                    break
                step["status"], step["started"] = "running", _now()
                self.store.save_run(run)
                self.publish_run(run)
                try:
                    res = await getattr(self, f"_s_{step['kind']}")(run, step, t0)
                    step["status"], step["result"] = "done", res or {}
                except asyncio.CancelledError:
                    step["status"] = "todo"
                    raise
                except ResearchError as e:
                    step["status"], step["result"] = "failed", {"error": e.kind, **{k: v for k, v in e.info.items()
                                                                                    if isinstance(v, (str, int))}}
                except Exception as e:  # noqa: BLE001
                    log.exception("research step %s failed", step["kind"])
                    step["status"], step["result"] = "failed", {"error": "internal", "text": str(e)[:300]}
                step["ended"] = _now()
                run["spent"]["steps"] += 1
                run["spent"]["cost_usd"] = round(self._cost(run), 4)
                await self._journal(run, self._step_line(step))
                self.store.save_run(run)
                self.publish_run(run)
            else:
                run["status"] = "done"
            if run["status"] == "running":
                run["status"] = "done"
            await self._journal(run, msg("Fin : {n} suggestion(s) à relire dans Article → Suggestions.",
                                         n=len(run["suggestions"]))["text"])
        except asyncio.CancelledError:
            run["status"] = "cancelled"
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("research run failed")
            run["status"], run["error"] = "failed", str(e)[:300]
        finally:
            run["spent"]["seconds"] = round(run["spent"]["seconds"] + time.monotonic() - t0, 1)
            run["spent"]["cost_usd"] = round(self._cost(run), 4)
            self.store.save_run(run)
            self.publish_run(run)

    def _step_line(self, step: dict) -> str:
        res = step.get("result") or {}
        detail = ", ".join(f"{k}={v}" for k, v in res.items() if isinstance(v, (int, float, str)) and k != "text")[:400]
        state = {"done": "✓", "failed": "✗"}.get(step["status"], "·")
        return f"{state} {step['kind']}" + (f" — {detail}" if detail else "")

    # ------------------------------------------------------------ model calls
    async def _ask(self, run: dict, role: str, content: str, max_tokens: int = 2500) -> tuple[str, str]:
        from ..server.helpers import complete_once
        run["spent"]["model_calls"] += 1
        try:      # one slow free provider must not eat the whole budget (real run: a call hung > 13 min)
            c = await asyncio.wait_for(complete_once(self.ctx, role, [{"role": "user", "content": content}],
                                                     run["mode"], owner=f"research-{run['id']}",
                                                     max_tokens=max_tokens, temperature=0.2),
                                       min(CALL_TIMEOUT_S, max(30.0, self._left)))
        except asyncio.TimeoutError:
            await self._journal(run, msg("Modèle trop lent : appel abandonné ({role}).", role=role)["text"])
            return "", ""
        return c.text or "", getattr(c.model, "key", "") or ""

    # ------------------------------------------------------------ journal (a project note)
    async def _journal(self, run: dict, line: str, header: bool = False) -> None:
        if self.notes is None:
            return
        stamp = time.strftime("%H:%M")
        try:
            n = self.notes.get(run["journal_note"]) if run.get("journal_note") else None
            if n is None or n.deleted is not None:
                title = msg("Journal de recherche — {date} ({id})", date=time.strftime("%d/%m/%Y"),
                            id=run["id"][3:])["text"]
                src = run["source"]
                body = (f"[[@{src['key']}]] — {src.get('title', '')}\n\n" if src.get("key") else "")
                n = await asyncio.to_thread(self.notes.create, run["project_id"], title, body, ["recherche"], "note",
                                            "consigne")
                run["journal_note"] = n.id
            entry = (f"\n**{stamp}** {line}\n" if header else f"- {stamp} {line}\n")
            n2, _m, _old = await asyncio.to_thread(self.notes.update, n.id, n.rev, body=(n.body or "") + entry,
                                                   device="consigne", reason="journal")
            self.ctx.publish("note.updated", {"note": n2.to_dict(), "device": "consigne"})
        except Exception as e:  # noqa: BLE001 (the journal never stops the run)
            log.warning("research journal: %s", e)

    def _suggest(self, run: dict, s: dict) -> dict:
        self.store.add_suggestion(run["project_id"], s)
        run["suggestions"].append(s["id"])
        self.publish_suggestion(s)
        return s

    # ------------------------------------------------------------ steps
    def _lib(self):
        from .sources import library
        return library(self.ctx)

    def _bp(self, run: dict) -> dict | None:
        from . import papers
        return papers.load(self.ctx, run["project_id"], run["source"]["id"])

    async def _s_blueprint(self, run: dict, step: dict, t0: float) -> dict:
        from . import papers
        lib = self._lib()
        src = lib.get(run["source"]["shelf"], run["source"]["id"])
        bp = await asyncio.to_thread(papers.extract, lib.shelf(run["source"]["shelf"]), src)
        bp["shelf"] = run["source"]["shelf"]
        await asyncio.to_thread(papers.save, self.ctx, run["project_id"], bp)
        self.ctx.publish("blueprint.updated", {"project": run["project_id"], "source_id": src["id"], "blueprint": bp})
        if not bp["nodes"]:
            raise ResearchError("no_results_found", warnings=",".join(bp.get("warnings", []))[:200])
        return {"nodes": len(bp["nodes"]), "method": bp.get("method", "")}

    async def _source_hits(self, run: dict, query: str, k: int = 8) -> list[dict]:
        lib = self._lib()
        try:
            hits = await lib.search([run["source"]["shelf"]], query, k, [run["source"]["id"]], semantic=False)
        except Exception:  # noqa: BLE001
            hits = []
        if not hits:                                      # no lexical hit: the source's overview passages
            from . import qa
            chunks = await asyncio.to_thread(lib.chunks_of, run["source"]["shelf"], run["source"]["id"])
            for c in chunks:
                c["shelf"], c["source_key"] = run["source"]["shelf"], run["source"]["key"]
            hits = qa.source_overview_hits(chunks, budget=9000)
        return hits

    async def _s_context(self, run: dict, step: dict, t0: float) -> dict:
        from . import qa
        from ..i18n import language
        q = ("Quels sont les résultats principaux de ce texte, avec leurs hypothèses exactes ?" if language() != "en"
             else "What are the main results of this text, with their exact hypotheses?")
        hits = await self._source_hits(run, run["instruction"][:300] + " " + q, 10)

        async def complete(role, messages, phase):
            from ..server.helpers import complete_once
            run["spent"]["model_calls"] += 1
            return await complete_once(self.ctx, role, messages, run["mode"], owner=f"research-{run['id']}",
                                       max_tokens=1800, temperature=0.2)
        res = await qa.grounded(complete, q, hits, lang=language())
        # only the sentences the checker found in the passages; each keeps its citation marks
        sents = [x for x in res.get("sentences", []) if x.get("supported") and not x.get("notice")]
        run["context"] = " ".join(x["text"] for x in sents)[:6000]
        cited = {c for x in sents for c in x.get("citations", []) if isinstance(c, (int, str))}
        pas = res.get("passages") or []
        run["citations"] = [{"key": h.get("source_key", run["source"]["key"]), "locator": h.get("locator", ""),
                             "quote": (h.get("text") or "")[:300]}
                            for i, h in enumerate(pas, 1) if isinstance(h, dict) and (not cited or i in cited
                                                                                     or str(i) in cited)][:8]
        await self._journal(run, msg("Contexte (réponse sourcée) : {text}",
                                     text=run["context"][:1200] or res.get("status", ""))["text"])
        return {"passages": len(hits), "sentences": len(sents), "status": res.get("status", "")}

    async def _s_import(self, run: dict, step: dict, t0: float) -> dict:
        """The paper's text, verbatim, as the article's blocks (only when the article has no text)."""
        from . import article as art_mod
        lib = self._lib()
        art = art_mod.load(self.ctx, run["project_id"])
        if any((b.get("text") or "").strip() for b in art["blocks"] if b["kind"] != "dossier"):
            return {"skipped": "article_has_text"}
        chunks = await asyncio.to_thread(lib.chunks_of, run["source"]["shelf"], run["source"]["id"])
        sections: list[list] = []                       # [[title, [texts]]] in reading order
        for c in chunks:
            text = (c.get("text") or "").strip()
            if c.get("kind") == "heading":
                sections.append([text[:200], []])
                continue
            sec = (c.get("section") or "").strip()
            if not sections or (sec and sec != sections[-1][0]):
                sections.append([sec or run["source"]["key"], []])
            sections[-1][1].append(text)
        blocks, total = [], 0
        for title, texts in sections[:40]:
            text = "\n\n".join(t for t in texts if t)[:30000]
            total += len(text)
            if not text or total > 400_000:
                continue
            b = art_mod.new_block("section", title, text, "user")
            b["versions"][-1]["note"] = f"importé depuis [@{run['source']['key']}] (texte inchangé)"
            b["imported_from"] = run["source"]["key"]
            blocks.append(b)
        if blocks:
            async with self.art_lock(run["project_id"]):
                art = art_mod.load(self.ctx, run["project_id"])
                art["blocks"] = blocks + art["blocks"]
                await asyncio.to_thread(art_mod.save, self.ctx, run["project_id"], art)
            self.ctx.publish("article.updated", {"project": run["project_id"], "article": art})
        return {"blocks": len(blocks)}

    async def _s_verify(self, run: dict, step: dict, t0: float) -> dict:
        from . import papers
        from ..orchestrator import DossierBusy
        pid = run["project_id"]
        bp = self._bp(run)
        nodes = select_nodes(bp, step["targets"], run["limits"]["max_targets"])
        if not nodes:
            raise ResearchError("no_target")
        known = self._lib().all_entries(pid)
        await papers.create_dossiers(self.ctx, pid, bp, [n["id"] for n in nodes], known)
        bp = self._bp(run)
        ids = [n.get("dossier_id") for n in bp["nodes"] if n["id"] in {x["id"] for x in nodes} and n.get("dossier_id")]
        run["dossiers"] = list(dict.fromkeys(run["dossiers"] + ids))
        opts = {"mode": run["mode"]} if run["mode"] in ("local", "auto", "online") else {}
        tasks = []
        for did, plan_, strategy in papers.formalise_plans(bp, self.ctx, ids, True):
            d = self.ctx.repo.get(did)
            if not plan_ or (d is not None and d.proof_is_current):
                continue
            try:
                job = self.ctx.orchestrator.submit(did, plan_, gates=False, **opts, **({"strategy": strategy} if strategy else {}))
            except DossierBusy as e:
                job = e.job
            run["jobs"].append(job.id)
            t = self.ctx.orchestrator.tasks.get(job.id)
            if t is not None:
                tasks.append(t)
        self.store.save_run(run)
        # Lean may take the whole budget: wait for at most half of what is left (≤ 20 min), the later steps still
        # run; the jobs go on, and the verification suggestions read their status live (real run 2026-11-21: the
        # three Hölder/AM-GM jobs used all 40 minutes and nothing else was proposed)
        budget = min(self.remaining(run, t0) * VERIFY_SHARE, 20 * 60)
        if tasks and budget > 0:
            await asyncio.wait(tasks, timeout=budget)       # the jobs keep running after this if time is up
        verified = 0
        for n in nodes:
            n2 = next((x for x in bp["nodes"] if x["id"] == n["id"]), n)
            did = n2.get("dossier_id")
            d = self.ctx.repo.get(did) if did else None
            if d is None:
                continue
            ok_ = bool(d.proof_is_current) and not vacuous(d.statement or "")
            verified += ok_
            self._suggest(run, new_suggestion(
                run, "verification", title=node_label(n2), before="",
                after=(msg("{what} : preuve vérifiée par Lean (dossier « {title} »).", what=node_label(n2),
                           title=d.title)["text"] if ok_ else
                       msg("{what} : pas encore vérifié par Lean (dossier « {title} »).", what=node_label(n2),
                           title=d.title)["text"]),
                rationale=msg("Ajoute le résultat à l'article avec son statut Lean (énoncé et preuve vérifiés par le "
                              "pipeline normal).")["text"],
                target={"mode": "add_dossier", "dossier_id": d.id},
                evidence={"lean": [{"dossier_id": d.id}], "citations": [{"key": run["source"]["key"],
                                                                         "locator": n2.get("locator", "")}]}))
        return {"targets": len(nodes), "jobs": len(tasks), "verified": verified}

    def _calc_ready(self) -> bool:
        return self.calc is not None

    async def _sage_step(self, run: dict, step: dict, t0: float, kind: str) -> dict:
        """examples / figures: Sage cells in Calcul + one suggested paragraph per targeted result."""
        if not self._calc_ready():
            raise ResearchError("calcul_unavailable")
        bp = self._bp(run)
        nodes = select_nodes(bp, step["targets"], min(2, run["limits"]["max_targets"]))
        if not nodes:
            raise ResearchError("no_target")
        made = 0
        for n in nodes:
            if self._over(run, t0):
                break
            want = ("Write SageMath code that computes 2 or 3 small, concrete EXAMPLES illustrating the result below "
                    "(print the values with clear labels)." if kind == "examples" else
                    "Write SageMath code that draws ONE clear FIGURE (plot / list_plot / points / implicit_plot) "
                    "illustrating the result below; the last line must display the graphics object (e.g. `show(g)` or "
                    "just `g`).")
            content = (f"{want}\nThen, after the code block, write a short paragraph (2-4 sentences, LaTeX between "
                       f"$...$, in the language of the result) presenting this {'example' if kind == 'examples' else 'figure'} "
                       f"for the article. Answer with exactly one ```sage code block followed by the paragraph.\n"
                       f"{UNTRUSTED_RULE}\n\n" + wrap_untrusted(f"{node_label(n)}. {n.get('text', '')[:3000]}",
                                                                run["source"]["key"]))
            text, model = await self._ask(run, "assistant", content, 2500)
            code = extract_code(text)
            if not code:
                continue
            para = re.sub(r"```.*?```", "", text, flags=re.S).strip()
            para = re.sub(r"<think>.*?(</think>|$)", "", para, flags=re.S).strip()[:3000]
            cell = await self.calc.add_cell(run["project_id"], code, "sage",
                                            note=f"{'Exemple' if kind == 'examples' else 'Figure'} — {node_label(n)}",
                                            model=model)
            run["cells"].append(cell["id"])
            ran = await self.calc.run_allowed(run["project_id"], cell["id"], run.get("allow_exec", True))
            label = msg("Exemple ({what})", what=node_label(n))["text"] if kind == "examples" else \
                msg("Figure ({what})", what=node_label(n))["text"]
            after = (f"**{label}.** {para}\n\n" if para else f"**{label}.**\n\n") + \
                f"[[calcul:{cell['id']}]]"
            self._suggest(run, new_suggestion(
                run, "exemple" if kind == "examples" else "figure", title=label, before="", after=after,
                rationale=msg("Calcul Sage proposé ; le résultat affiché est celui du carnet Calcul.")["text"],
                target={"mode": "insert_after", "near": n.get("dossier_id") or "", "node": n["id"]},
                evidence={"calcul": [{"cell_id": cell["id"]}], "citations": [{"key": run["source"]["key"],
                                                                              "locator": n.get("locator", "")}]},
                model=model, ran=bool(ran)))
            made += 1
        return {"cells": made}

    async def _s_examples(self, run, step, t0):
        return await self._sage_step(run, step, t0, "examples")

    async def _s_figures(self, run, step, t0):
        return await self._sage_step(run, step, t0, "figures")

    async def _s_improve(self, run: dict, step: dict, t0: float) -> dict:
        from . import article as art_mod
        art = art_mod.load(self.ctx, run["project_id"])
        blocks = [b for b in art["blocks"] if b["kind"] != "dossier" and len((b.get("text") or "").strip()) > 80]
        if art["abstract"].get("text", "").strip():
            blocks.insert(0, dict(art["abstract"], id="abstract"))
        made = 0
        for b in blocks[:6]:
            if self._over(run, t0):
                break
            content = ("You are a careful mathematical copy-editor. Propose at most 4 LOCAL improvements of the "
                       "wording of the text below (clarity, grammar, typography, precision). Never change the "
                       "mathematics: keep every formula between $...$ identical unless it contains an obvious typo, "
                       "and say so in the reason. Answer ONLY with JSON: [{\"excerpt\": \"<exact substring of the "
                       "text>\", \"replacement\": \"<new text>\", \"reason\": \"<short reason>\"}]. Write the "
                       f"replacement in the language of the text.\n{UNTRUSTED_RULE}\n\n" +
                       wrap_untrusted(b["text"][:7000], "article"))
            text, model = await self._ask(run, "explain", content, 2000)
            edits = json_block(text)
            if not isinstance(edits, list):
                continue
            for e in edits[:4]:
                if not isinstance(e, dict):
                    continue
                ex, rep = str(e.get("excerpt", "")), str(e.get("replacement", ""))
                if not ex or ex == rep or ex not in b["text"] or len(ex) > 2000:
                    continue                              # code-checked: the excerpt must exist verbatim
                para = paragraph_of(b["text"], ex)
                self._suggest(run, new_suggestion(
                    run, "correction", title=b.get("title") or msg("Résumé")["text"], before=para,
                    after=para.replace(ex, rep, 1), rationale=str(e.get("reason", ""))[:500],
                    target={"mode": "replace_excerpt", "block_id": b["id"]}, model=model))
                made += 1
        return {"suggestions": made, "blocks": len(blocks[:6])}

    async def _s_generalise(self, run: dict, step: dict, t0: float) -> dict:
        from . import litsearch
        pid = run["project_id"]
        bp = self._bp(run)
        nodes = select_nodes(bp, step["targets"], 1 if not step["targets"] else run["limits"]["max_targets"],
                             kinds=("theorem", "proposition", "corollary"))
        if not nodes:
            raise ResearchError("no_target")
        made = 0
        for n in nodes:
            if self._over(run, t0):
                break
            lit = []
            if run["mode"] != "local":
                try:
                    q = " ".join(re.findall(r"[A-Za-zÀ-ÿ]{4,}", f"{n.get('title', '')} {n.get('text', '')}")[:10])
                    res = await litsearch.search(self._lib().fetcher, q, run["mode"], ["arxiv", "openalex"], 5)
                    lit = [r for r in (res.get("results") or [])[:5] if isinstance(r, dict)]
                except Exception as e:  # noqa: BLE001
                    log.info("litsearch for generalisation: %s", e)
            lit_txt = "\n".join(f"- {r.get('title', '')} ({r.get('year', '')})" for r in lit)
            content = ("Propose ONE natural generalisation of the result below (weaker hypotheses or a larger class "
                       "of objects), which might be true. It is a CONJECTURE until proved. Answer ONLY with JSON: "
                       "{\"statement\": \"<the generalised statement, LaTeX between $...$>\", \"why\": \"<why it is "
                       "plausible, what changes>\", \"sage\": \"<optional SageMath code testing it on small cases, "
                       "printing a counter-example if one is found>\"}.\n"
                       f"{UNTRUSTED_RULE}\n\n" + wrap_untrusted(f"{node_label(n)}. {n.get('text', '')[:3000]}",
                                                                run["source"]["key"]) +
                       (f"\n\nRelated literature (titles only, data):\n{lit_txt}" if lit_txt else "") +
                       (f"\n\nContext from the source (data):\n{wrap_untrusted(run['context'][:2000], 'context')}"
                        if run.get("context") else ""))
            text, model = await self._ask(run, "explain", content, 2000)
            prop = json_block(text)
            if not isinstance(prop, dict) or not str(prop.get("statement", "")).strip():
                continue
            statement = str(prop["statement"]).strip()[:4000]
            why = str(prop.get("why", "")).strip()[:2000]
            conj_id, job_id = "", ""
            if self.workshop is not None:
                try:
                    d = await self.workshop.create(pid, statement, motivation=why,
                                                   title=msg("Généralisation de {what}", what=node_label(n))["text"],
                                                   origin={"kind": "consigne", "run_id": run["id"], "node": n["id"]},
                                                   device="consigne")
                    conj_id = d.id
                    run["conjectures"].append(d.id)
                    if prop.get("sage") and self.calc is not None:
                        cell = await self.calc.add_cell(pid, str(prop["sage"])[:20000], "sage",
                                                        note=msg("Test de la conjecture « {t} »",
                                                                 t=statement[:80])["text"], model=model)
                        run["cells"].append(cell["id"])
                        await self.calc.run_allowed(pid, cell["id"], run.get("allow_exec", True))
                    from ..pipeline.runner import full_plan
                    from ..orchestrator import DossierBusy
                    try:
                        job = self.ctx.orchestrator.submit(d.id, full_plan(), gates=False,
                                                               mode=run["mode"])
                        job_id = job.id
                        run["jobs"].append(job.id)
                    except DossierBusy:
                        pass
                except Exception as e:  # noqa: BLE001
                    log.info("conjecture creation: %s", e)
            head = msg("Conjecture (généralisation de {what})", what=node_label(n))["text"]
            head_proved = msg("Théorème (généralisation de {what}, vérifiée par Lean)", what=node_label(n))["text"]
            ev = {"lean": [{"dossier_id": conj_id}] if conj_id else [],
                  "citations": [{"key": run["source"]["key"], "locator": n.get("locator", "")}] +
                  [{"key": "", "title": r.get("title", ""), "url": r.get("url") or r.get("doi", ""), "year":
                    r.get("year", "")} for r in lit[:3]],
                  "calcul": [{"cell_id": c} for c in run["cells"][-1:]] if prop.get("sage") else []}
            self._suggest(run, new_suggestion(
                run, "generalisation", title=head, before="", after=f"**{head}.** {statement}",
                rationale=why, target={"mode": "insert_after", "near": n.get("dossier_id") or "", "node": n["id"]},
                evidence=ev, model=model, conjecture=True, after_if_proved=f"**{head_proved}.** {statement}",
                job_id=job_id))
            made += 1
        return {"proposed": made}

    # ------------------------------------------------------------ suggestions: live evidence, accept, reject
    def resolve(self, s: dict) -> dict:
        """The suggestion with its evidence brought up to date (Lean status, Calcul run, conjecture state)."""
        out = json.loads(json.dumps(s))
        for e in out.get("evidence", {}).get("lean", []):
            d = self.ctx.repo.get(e.get("dossier_id", "")) if e.get("dossier_id") else None
            if d is not None:
                job = self.ctx.orchestrator.active_for(d.id) if hasattr(self.ctx.orchestrator, "active_for") else None
                vac = vacuous(d.statement or "")
                e.update(title=d.title, kind=d.kind, statement_ok=bool(d.statement and d.statements[d.cur_statement].ok),
                         proved=bool(d.proof_is_current) and not vac, vacuous=vac, running=bool(job),
                         lean=(d.statement or "")[-1500:])
        for e in out.get("evidence", {}).get("calcul", []):
            cell = self.calc.cell(out["project_id"], e.get("cell_id", "")) if self.calc is not None else None
            if cell is not None:
                last = (cell.get("runs") or [None])[-1]
                e.update(code=cell.get("code", "")[:4000],
                         approved=bool(cell.get("origin") != "assistant" or
                                       (cell.get("approved") or {}).get("hash") == cell.get("code_hash")),
                         run=None if not last else {"ok": last.get("status") == "ok" and not last.get("error"),
                                                    "text": self.calc.output_text(last)[:3000],
                                                    "error": (last.get("error") or "")[:1000],
                                                    "assets": [r.get("asset") for r in last.get("rich", [])
                                                               if r.get("asset")][:4]})
        if out.get("conjecture"):
            ev = out["evidence"].get("lean") or [{}]
            out["proved"] = bool(ev[0].get("proved"))
        return out

    def _render_calcul(self, s: dict, text: str) -> str:
        """`[[calcul:ID]]` → the cell's printed result (examples) or a figure reference; the article stays text."""
        runs = {e.get("cell_id"): e.get("run") for e in s.get("evidence", {}).get("calcul", [])}

        def one(m):
            r = runs.get(m.group(1))
            if r and r.get("assets"):
                return msg("(Figure : carnet Calcul, cellule {id})", id=m.group(1))["text"]
            if r and r.get("ok") and r.get("text"):
                return "```\n" + r["text"][:3000] + "\n```"
            return msg("(Calcul : cellule {id}, pas encore exécutée)", id=m.group(1))["text"]
        return re.sub(r"\[\[calcul:([A-Za-z0-9._-]{1,80})\]\]", one, text)

    def suggestions(self, pid: str, type_: str = "", status: str = "") -> list[dict]:
        out = [self.resolve(s) for s in self.store.suggestions(pid)
               if (not type_ or s["type"] == type_) and (not status or s["status"] == status)]
        return sorted(out, key=lambda s: (s["status"] != "proposed", -s["created"]))

    def accept(self, pid: str, sid: str, edited: str | None = None) -> tuple[dict, dict]:
        """Apply ONE suggestion to the article (called under the article lock). Returns (suggestion, article)."""
        from . import article as art_mod
        cur = next((x for x in self.store.suggestions(pid) if x["id"] == sid), None)
        if cur is None:
            raise ResearchError("not_found", 404)
        if cur["status"] != "proposed":
            raise ResearchError("already_decided", 409, current=cur["status"])
        s = self.resolve(cur)
        after = edited if isinstance(edited, str) and edited.strip() else \
            (s.get("after_if_proved") if s.get("conjecture") and s.get("proved") else s["after"])
        after = self._render_calcul(s, after)
        art = art_mod.load(self.ctx, pid)
        tgt = s.get("target") or {}
        note = f"suggestion {sid} ({s['type']}) acceptée"
        mode = tgt.get("mode")
        if mode == "replace_excerpt":
            b = art_mod.find_block(art, tgt.get("block_id", ""))
            if s["before"] not in (b.get("text") or ""):
                self.store.update_suggestion(pid, sid, lambda x: x.update(status="stale", decided=_now()))
                raise ResearchError("stale", 409)
            art_mod.set_text(b, b["text"].replace(s["before"], after, 1), "user", model=s.get("model", ""),
                             note=note)
        elif mode == "add_dossier":
            did = tgt.get("dossier_id", "")
            if self.ctx.repo.get(did) is None:
                raise ResearchError("not_found", 404)
            if not any(b["kind"] == "dossier" and b.get("dossier_id") == did for b in art["blocks"]):
                art["blocks"].append(art_mod.new_block("dossier", "", "", "dossier", did))
        else:                                             # insert_after: a new block after the related result
            nb = art_mod.new_block("prose", s.get("title", ""), after, "user", model=s.get("model", ""))
            nb["versions"][-1]["note"] = note
            idx = next((i for i, b in enumerate(art["blocks"]) if tgt.get("near") and b["kind"] == "dossier"
                        and b.get("dossier_id") == tgt.get("near")), None)
            if idx is None and tgt.get("block_id"):
                idx = next((i for i, b in enumerate(art["blocks"]) if b["id"] == tgt["block_id"]), None)
            if idx is None:
                art["blocks"].append(nb)
            else:
                art["blocks"].insert(idx + 1, nb)
        art_mod.save(self.ctx, pid, art)
        res = self.store.update_suggestion(pid, sid, lambda x: x.update(status="accepted", decided=_now(),
                                                                        applied=after))
        return res, art

    def reject(self, pid: str, sid: str) -> dict:
        def f(x):
            if x["status"] != "proposed":
                raise ResearchError("already_decided", 409, current=x["status"])
            x.update(status="rejected", decided=_now())
        return self.store.update_suggestion(pid, sid, f)

    # ------------------------------------------------------------ one search across the project
    async def search(self, pid: str, q: str, k: int = 40) -> list[dict]:
        q = (q or "").strip()[:300]
        if not q:
            return []
        low = q.lower()
        out: list[dict] = []

        def snip(text: str, n: int = 200) -> str:
            text = re.sub(r"\s+", " ", text or "")
            i = text.lower().find(low)
            return (("…" if i > 60 else "") + text[max(0, i - 60): max(0, i - 60) + n]) if i >= 0 else text[:n]
        for d in self.ctx.repo.list(pid, include_archived=False):
            hay = f"{d.title}\n{d.problem or ''}\n{d.statement or ''}"
            if low in hay.lower():
                out.append({"kind": "dossier", "id": d.id, "title": d.title, "snippet": snip(hay),
                            "status": "proved" if d.proof_is_current else ("conjecture" if d.kind == "conjecture"
                                                                           else "statement")})
        if self.notes is not None:
            try:
                for h in await asyncio.to_thread(self.notes.search, q, pid, 20):
                    out.append({"kind": "note", "id": h.get("id", ""), "title": h.get("title", ""),
                                "snippet": re.sub(r"<[^>]+>", "", str(h.get("snippet") or h.get("context") or ""))})
            except Exception:  # noqa: BLE001
                pass
        if self.calc is not None:
            for c in self.calc.cells(pid):
                last = (c.get("runs") or [{}])[-1] or {}
                hay = f"{c.get('code', '')}\n{c.get('note', '')}\n{last.get('stdout', '')}"
                if low in hay.lower():
                    assets = [r.get("asset") for r in last.get("rich", []) if r.get("asset")]
                    out.append({"kind": "figure" if assets else "calcul", "id": c["id"],
                                "title": c.get("note") or c.get("code", "").split("\n")[0][:80],
                                "snippet": snip(hay), "assets": assets[:2]})
        try:
            lib = self._lib()
            hits = await lib.search([pid], q, 10, semantic=False)
            for h in hits:
                out.append({"kind": "passage", "id": h.get("chunk_id") or h.get("id", ""), "source_id":
                            h.get("source_id", ""), "source_key": h.get("source_key", ""),
                            "title": f"{h.get('source_key', '')} {h.get('locator', '')}".strip(),
                            "snippet": re.sub(r"\s+", " ", str(h.get("text", "")))[:240],
                            "page": h.get("page")})
        except Exception:  # noqa: BLE001
            pass
        for s in self.store.suggestions(pid):
            if low in (s.get("after", "") + s.get("title", "")).lower():
                out.append({"kind": "suggestion", "id": s["id"], "title": s.get("title", ""), "snippet":
                            snip(s.get("after", "")), "status": s["status"], "type": s["type"]})
        return out[:k]

    def to_article(self, pid: str, kind: str, item: str, extra: dict) -> dict:
        """Insert a search result into the article — the user's explicit action (no suggestion needed)."""
        from . import article as art_mod
        art = art_mod.load(self.ctx, pid)
        if kind == "dossier":
            if self.ctx.repo.get(item) is None:
                raise ResearchError("not_found", 404)
            if any(b["kind"] == "dossier" and b.get("dossier_id") == item for b in art["blocks"]):
                raise ResearchError("already_there", 409)
            nb = art_mod.new_block("dossier", "", "", "dossier", item)
        elif kind == "note":
            n = self.notes.get(item, include_deleted=False) if self.notes is not None else None
            if n is None or n.project_id not in (pid, "", None):
                raise ResearchError("not_found", 404)
            nb = art_mod.new_block("prose", n.title, n.body[:30000], "user")
        elif kind in ("calcul", "figure"):
            if self.calc is None or self.calc.cell(pid, item) is None:
                raise ResearchError("not_found", 404)
            nb = art_mod.new_block("prose", str(extra.get("title", ""))[:200], f"[[calcul:{item}]]", "user")
        elif kind == "passage":
            key, text = str(extra.get("source_key", "")), str(extra.get("text", ""))[:3000]
            loc = str(extra.get("locator", ""))[:80]
            if not key or not text:
                raise ResearchError("bad_fields")
            nb = art_mod.new_block("prose", "", f"> {text}\n\n[@{key}{', ' + loc if loc else ''}]", "user")
        else:
            raise ResearchError("bad_fields")
        art["blocks"].append(nb)
        art_mod.save(self.ctx, pid, art)
        return {"block": nb, "article": art}
