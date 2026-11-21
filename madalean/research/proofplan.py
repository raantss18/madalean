"""Guided proof decomposition (ARCHITECTURE §14, RESEARCH_WORKSHOP §3) — sessions S-G, then S-L (Madalean 2.0).

A proof plan is a tree attached to a dossier: the root is the dossier's theorem, below it lemmas. It is THE simple
way to prove a hard theorem, shown as a mind map:

1. **Analyse** (« Découper ce théorème »): the model writes a main track (2–6 lemmas, each with a natural-language
   statement, a Lean statement, its role, its dependencies, preferably independent) plus the **combination**: the
   Lean proof of the parent that uses the lemmas by name, and up to 2 ALTERNATIVE tracks (other strategies) kept as
   sibling branches. Mathlib candidates are given as hints.
2. **Gate** (before the user is asked): ONE Lean file states every lemma with `sorry` and the combination of each
   track; the parent must follow from its lemmas (combination compiles, no `sorry` in it). A failing plan is
   regenerated with Lean's errors (≤ 2 tries); a plan whose combination is not checked is shown « à vérifier ».
   The same pass applies the **obvious-stop rule** (cheap closers `omega`, `norm_num`, `linarith`, `simp_all`,
   `aesop`, `exact?` under a heartbeat cap: a lemma they close is proved immediately and never split) and the
   **loop guard** (a lemma equivalent to its parent — same normalized text, or `exact`/`simp` both ways — is
   refused, with its whole track).
3. The user validates (or edits) the PLAN; « Prouver le plan » then creates one sub-dossier per lemma (normal
   pipeline: Mathlib first, tournament), within the plan's concurrency limit; when every lemma of a node is proved,
   the stored combination is compiled with the REAL lemma proofs under the strict verdict → the node is proved,
   up to the root.
4. A lemma that fails → the app proposes, in order: (a) another track, (b) split it one level deeper, (c) leave it as
   a hole (`sorry`, admitted). A hole makes its ancestors CONDITIONAL (« Conditionnel — N trous »), never verified.

Hard limits: depth ≤ `plan_max_depth` (default 3), ≤ 6 lemmas per track, ≤ 2 alternatives per node, ≤ 30 live nodes
per tree, a total time budget (`plan_budget_minutes`). Plan content is versioned (every change = a version, manual
edits never overwritten without `force`); run progress (combinations, budget) lives beside it, unversioned.

Proved modulo admitted lemmas — the parent's proof is checked by Lean with the admitted lemmas stated with `sorry`.
That check never enters `dossier.proofs`: the strict verdict (leancheck.judge) rejects it (`sorry`, axiom
`sorryAx`), the dossier is NOT proved, and the conditional state is explicit in data:
`dossier.extra["conditional_proof"] = {verdict: "proved_modulo", admitted: [...], strict_ok: false, axioms}`."""
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

MAX_LEMMAS = 6           # per track
MAX_ALTS = 2             # alternative tracks per node (besides the main one)
MAX_NODES = 30           # live nodes per tree (root included; abandoned tracks without dossiers are pruned)
GATE_TRIES = 2           # plan generations per analysis when Lean rejects the plan
DEFAULT_DEPTH = 3
DEFAULT_BUDGET_MIN = 180
CLOSER_TACTICS = ["omega", "(norm_num; done)", "linarith", "(simp_all; done)", "(aesop; done)"]
CLOSERS = "first | " + " | ".join(CLOSER_TACTICS)
CLOSE_HEARTBEATS = 60000
EQUIV_HEARTBEATS = 20000
TRACK_LETTERS = "abcdefghijklmnopqrstuvwxyz"


class PlanError(Exception):
    def __init__(self, kind: str, status: int = 400, key: str = "", **data):
        super().__init__(kind)
        self.kind, self.status, self.key, self.data = kind, status, key, data
        self.params = {k: v for k, v in data.items() if isinstance(v, (str, int, float))}


def _nid() -> str:
    return "pn-" + uuid.uuid4().hex[:8]


def node(title: str, statement_nl: str = "", why: str = "", lean: str = "", parent: str | None = None) -> dict:
    return {"id": _nid(), "parent": parent, "children": [], "title": title[:200], "statement_nl": statement_nl[:5000],
            "why": why[:3000], "lean": lean[:20000], "status": "draft", "dossier_id": "", "admitted": False,
            "edited": False, "cancelled": False, "track": "", "tracks": [], "active_track": "", "uses": [],
            "lean_ok": None, "lean_error": "", "obvious": False, "obvious_proof": ""}


def track(tid: str, idea: str, lemmas: list[str], combination: str = "") -> dict:
    return {"id": tid, "idea": idea[:300], "lemmas": list(lemmas), "combination": combination[:20000],
            "check": {"state": "unchecked", "why": "", "t": 0.0}, "abandoned": False, "refused": ""}


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

    def runtime(self, did: str) -> dict:
        """Run progress (not versioned): {run: {...} | None, nodes: {nid: {combine…}}}."""
        data = self.load(did)
        if data is None:
            return {"run": None, "nodes": {}}
        return data.setdefault("runtime", {"run": None, "nodes": {}})

    def save_runtime(self, did: str) -> None:
        data = self.load(did)
        if data is not None:
            self.save(data)


# ---------------------------------------------------------------- tree helpers (pure)
def subtree(plan: dict, nid: str) -> list[str]:
    """`nid` and everything below it, alternative tracks included."""
    out, stack, seen = [], [nid], set()
    while stack:
        x = stack.pop()
        if x in plan["nodes"] and x not in seen:
            seen.add(x)
            out.append(x)
            n = plan["nodes"][x]
            stack += n["children"]
            for t in n.get("tracks") or []:
                stack += t["lemmas"]
    return out


def depth_first(plan: dict) -> list[str]:
    """The ACTIVE tree (active tracks only), parents first."""
    out = []

    def walk(x: str) -> None:
        out.append(x)
        for c in plan["nodes"][x]["children"]:
            if c in plan["nodes"]:
                walk(c)
    walk(plan["root"])
    return out


def depth_of(plan: dict, nid: str) -> int:
    d, x = 0, plan["nodes"][nid]["parent"]
    while x and d < 50:
        d, x = d + 1, plan["nodes"].get(x, {}).get("parent")
    return d


def live_nodes(plan: dict) -> int:
    return len(plan["nodes"])


def track_of(plan: dict, nid: str) -> dict | None:
    n = plan["nodes"].get(nid)
    par = plan["nodes"].get(n["parent"] or "") if n else None
    if not par:
        return None
    return next((t for t in par.get("tracks") or [] if nid in t["lemmas"]), None)


def off_track(plan: dict, nid: str) -> str:
    """"" when `nid` is on the active tree, else "alternative" (a sibling track not chosen yet) or "abandoned"."""
    x = nid
    while x and x in plan["nodes"]:
        n = plan["nodes"][x]
        par = plan["nodes"].get(n["parent"] or "")
        if par is None:
            return ""
        if x not in par["children"]:
            t = track_of(plan, x)
            return "abandoned" if (t is None or t.get("abandoned")) else "alternative"
        x = par["id"]
    return ""


def set_children(plan: dict, nid: str, kids: list[str]) -> None:
    """`children` is the active track's lemma list: keep both in sync."""
    n = plan["nodes"][nid]
    n["children"] = list(kids)
    t = next((t for t in n.get("tracks") or [] if t["id"] == n.get("active_track")), None)
    if t is None and kids:
        tid = _free_track_id(n)
        t = track(tid, "", kids)
        t["check"]["state"] = "unchecked"
        n.setdefault("tracks", []).append(t)
        n["active_track"] = tid
    if t is not None:
        t["lemmas"] = list(kids)


def _free_track_id(n: dict) -> str:
    used = {t["id"] for t in n.get("tracks") or []}
    return next(c for c in TRACK_LETTERS if c not in used)


# ---------------------------------------------------------------- Lean text helpers (pure)
def split_decl(lean: str) -> tuple[str, str, str] | None:
    """(context, name, signature) of the LAST `theorem`/`lemma` of `lean`; context = the declarations before it
    without header lines (import/set_option/open). signature = binders and type, without `:= …`."""
    text = leancheck.remove_comments(lean or "")
    starts = [m.start(1) for m in re.finditer(r"(?m)^\s*(?:@\[[^\]]*\]\s*)?(theorem|lemma)\s", text)]
    if not starts:
        return None
    before, tail = text[:starts[-1]], text[starts[-1]:]
    m = re.match(r"(?:theorem|lemma)\s+([^\s:({\[⦃]+)(.*)$", tail, re.S)
    if not m:
        return None
    name, rest = m.group(1), m.group(2)
    i = rest.find(":=")
    sig = (rest[:i] if i >= 0 else rest).strip()
    if not sig.startswith((":", "(", "{", "[", "⦃")) or ":" not in sig:
        return None
    context = "\n".join(line for line in before.split("\n")
                        if not re.match(r"\s*(import|set_option|open)\b", line)).strip()
    return context, name, sig


def norm_sig(sig: str) -> str:
    """Comparable form of a signature: whitespace collapsed, bound names kept (the text guard is only the cheap
    half of the loop guard; Lean checks equivalence modulo names)."""
    return re.sub(r"\s+", " ", sig).strip()


def body_of(code: str, name: str | None = None) -> str:
    """Tactic block after `theorem <name> … := by` (the named one if present, else the last theorem)."""
    text = leancheck.remove_comments(code or "")
    ms = list(re.finditer(r"(?:^|\s)theorem\s+([^\s:({\[⦃]+).*?:=\s*by\b", text, re.S))
    if not ms:
        t = text.strip()
        return t if t and not re.search(r"\btheorem\b", t) else ""
    m = next((x for x in ms if x.group(1) == name), ms[-1])
    return text[m.end():].strip("\n")


def indent(body: str) -> str:
    lines = [ln for ln in body.replace("\t", "  ").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return "  skip"
    pad = min((len(ln) - len(ln.lstrip(" ")) for ln in lines if ln.strip()), default=0)
    return "\n".join("  " + ln[pad:] if ln.strip() else "" for ln in lines)


def rename_refs(text: str, mapping: dict[str, str]) -> str:
    for old, new in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        if old != new:
            text = re.sub(rf"(?<![\w.']){re.escape(old)}(?![\w'])", new, text)
    return text


# ---------------------------------------------------------------- prompts / parsing
def draft_messages(goal_nl: str, lean: str, hint: str = "", sketch: str = "", max_depth: int = 2) -> list[dict]:
    """Legacy S-G prompt (nested claims). Kept for compatibility; analysis uses `analyse_messages`."""
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


def analyse_messages(goal_nl: str, name: str, lean: str, context: str = "", hint: str = "", sketch: str = "",
                     mathlib: list[dict] | None = None, alts: int = MAX_ALTS, feedback: str = "",
                     parent_nl: str = "", max_lemmas: int = MAX_LEMMAS, lang: str = "fr") -> list[dict]:
    hits = "".join(f"- {h.get('name')} : {str(h.get('signature') or '')[:240]}\n" for h in (mathlib or [])[:10])
    return [{"role": "user", "content": (
        f"{MARK} task=analyse\nYou plan the proof of a theorem as a few lemmas BEFORE anyone proves them. Lean 4 + "
        "Mathlib will check your plan: every lemma statement must compile, and the theorem must follow from the "
        "lemmas.\n"
        f"Theorem (natural language): {goal_nl or '(see the Lean statement)'}\n"
        + (f"It is itself a step of a larger proof: {parent_nl}\n" if parent_nl else "")
        + f"Lean statement:\n```lean\n{lean}\n```\n"
        + (f"Declarations available above it:\n```lean\n{context}\n```\n" if context else "")
        + (f"Mathlib declarations that may help (use them when they fit):\n{hits}" if hits else "")
        + (f"Proof sketch to follow (from a paper or the user):\n{sketch}\n" if sketch else "")
        + (f"Hint from the user: {hint}\n" if hint else "")
        + (f"Give ONE main track and up to {alts} alternative track(s) that use genuinely different strategies. "
           if alts else "Give ONE track. ")
        + f"Each track has 2 to {max_lemmas} lemmas. Rules:\n"
        "- each lemma is STRICTLY easier than the theorem and NOT a restatement of it;\n"
        "- prefer independent lemmas; when a lemma needs another one of the same track, list it in \"uses\";\n"
        "- a lemma that is a known Mathlib fact is welcome (it will be closed at once);\n"
        "- \"lean\": ONE self-contained `theorem <name> (binders) : <prop> := by sorry` (no import, no other "
        "declaration), with a snake_case name; only the namespaces BigOperators Real Nat Topology Rat are open, so "
        "write `Filter.Tendsto`, `Filter.atTop`, `Set.Icc`… in full;\n"
        "- the combination applies each lemma with arguments in the order of its binders;\n"
        f"- \"combination\": the Lean proof of `{name}` that uses the lemmas by name as if they were proved: "
        f"`theorem {name} … := by` followed by tactics, WITHOUT sorry.\n"
        + (f"Your previous plan was rejected by Lean:\n{feedback}\nFix it.\n" if feedback else "")
        + f"Write \"idea\", \"title\", \"statement\" and \"why\" in {'French' if lang == 'fr' else 'English'}.\n"
        + "Answer with JSON only:\n{\"tracks\": [{\"idea\": \"one-line strategy\", \"lemmas\": [{\"name\": …, "
          "\"title\": \"≤ 8 words\", \"statement\": \"precise natural language, LaTeX in $…$\", \"why\": \"how it "
          "helps\", \"lean\": \"theorem … := by sorry\", \"uses\": []}], \"combination\": \"theorem … := by\\n  …\"}]}")}]


def _json_obj(text: str):
    text = leancheck.clean_model_text(text or "")
    text = re.sub(r"```(?:json)?\s*", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def parse_claims(text: str) -> list[dict]:
    data = _json_obj(text)
    claims = data.get("claims") if isinstance(data, dict) else None
    return claims if isinstance(claims, list) else []


def parse_tracks(text: str) -> list[dict]:
    """[{idea, lemmas: [{name, title, statement, why, lean, uses}], combination}] — also accepts the legacy
    `{"claims": […]}` (one track, top level only, no combination)."""
    data = _json_obj(text)
    if not isinstance(data, dict):
        return []
    raw = data.get("tracks")
    if not isinstance(raw, list):
        claims = data.get("claims")
        raw = [{"idea": "", "lemmas": claims, "combination": ""}] if isinstance(claims, list) else []
    out = []
    for t in raw[: 1 + MAX_ALTS]:
        if not isinstance(t, dict) or not isinstance(t.get("lemmas"), list):
            continue
        lemmas = []
        for c in t["lemmas"][:MAX_LEMMAS]:
            if not isinstance(c, dict) or not (c.get("title") or c.get("statement") or c.get("lean")):
                continue
            uses = c.get("uses") if isinstance(c.get("uses"), list) else []
            lemmas.append({"name": str(c.get("name") or ""), "title": str(c.get("title") or c.get("statement") or
                                                                       c.get("name") or "?"),
                           "statement": str(c.get("statement") or ""), "why": str(c.get("why") or ""),
                           "lean": str(c.get("lean") or ""), "uses": [str(u) for u in uses][:MAX_LEMMAS]})
        if lemmas:
            out.append({"idea": str(t.get("idea") or ""), "lemmas": lemmas,
                        "combination": str(t.get("combination") or "")})
    return out


def claims_to_nodes(plan: dict, parent: str, claims: list, depth: int = 0) -> None:
    """Legacy (S-G): nested claims become the active track of `parent` (and of each claim, recursively)."""
    kids = []
    for c in claims[:12]:
        if not isinstance(c, dict) or not (c.get("title") or c.get("statement")):
            continue
        n = node(str(c.get("title") or c.get("statement"))[:200], str(c.get("statement", "")), str(c.get("why", "")),
                 str(c.get("lean") or ""), parent)
        plan["nodes"][n["id"]] = n
        kids.append(n["id"])
        if depth < 3 and isinstance(c.get("children"), list):
            claims_to_nodes(plan, n["id"], c["children"], depth + 1)
    if kids:
        set_children(plan, parent, plan["nodes"][parent]["children"] + kids)
        t = track_of(plan, kids[0])
        if t is not None:
            for k in kids:
                plan["nodes"][k]["track"] = t["id"]


def new_plan(d) -> dict:
    root = node(d.title, d.understood_display or d.understood or d.problem, "", d.statement, None)
    root["status"] = "accepted"
    root["dossier_id"] = d.id
    return {"root": root["id"], "nodes": {root["id"]: root}}


# ---------------------------------------------------------------- gate file (one Lean compile per analysis)
def gate_file(context: str, parent_name: str, parent_sig: str, tracks: list[dict], *, equiv: bool = True,
              closers: bool = False, exact: bool = False, statements: bool = True) -> tuple[str, list[tuple]]:
    """Lean file + spans [(kind, track_index, lemma_index, first_line, last_line)] (1-based, inclusive).
    kinds: lemma (stated with sorry), comb (combination), close (cheap closers), dn/up (equivalence probes)."""
    out = [leancheck.GOEDEL_HEADER.rstrip("\n") + "\n"]
    spans: list[tuple] = []
    line = out[0].count("\n") + 1

    def add(kind, ti, li, text):
        nonlocal line
        text = text.rstrip("\n") + "\n\n"
        spans.append((kind, ti, li, line, line + text.count("\n") - 2))
        out.append(text)
        line += text.count("\n")

    if context.strip():
        add("context", -1, -1, context.strip())
    pref = f"{parent_name}__mdl"
    if statements:          # (never for the closers: `exact?` would find the sorry'd statements themselves)
        add("parent", -1, -1, f"theorem {pref}_parent {parent_sig} := by sorry")
    for ti, t in enumerate(tracks):
        for li, lm in enumerate(t["lemmas"] if statements else []):
            add("lemma", ti, li, f"theorem {lm['name']} {lm['sig']} := by sorry")
        if t.get("combination"):
            add("comb", ti, -1, f"theorem {pref}_comb_{ti} {parent_sig} := by\n{indent(t['combination'])}")
        if equiv:
            for li, lm in enumerate(t["lemmas"]):
                h = f"{pref}_parent"
                add("dn", ti, li, f"set_option maxHeartbeats {EQUIV_HEARTBEATS} in\ntheorem {pref}_dn_{ti}_{li} "
                                  f"{lm['sig']} := by\n  {_equiv_tac(h)}")
                add("up", ti, li, f"set_option maxHeartbeats {EQUIV_HEARTBEATS} in\ntheorem {pref}_up_{ti}_{li} "
                                  f"{parent_sig} := by\n  {_equiv_tac(lm['name'])}")
        if closers:
            for li, lm in enumerate(t["lemmas"]):
                tac = CLOSERS + (" | exact?" if exact else "")
                add("close", ti, li, f"set_option maxHeartbeats {CLOSE_HEARTBEATS} in\ntheorem {pref}_close_{ti}_{li} "
                                     f"{lm['sig']} := by\n  {tac}")
    return "".join(out), spans


def _equiv_tac(h: str) -> str:
    return (f"first | exact {h} | (intros; exact {h} ‹_›) | (intros; apply {h} <;> assumption) | "
            f"(intros; simp_all only [{h}])")


def read_gate(spans: list[tuple], msgs: list) -> dict:
    """{(kind, ti, li): {"errors": [text], "try": str, "sorry": bool}} from Lean messages."""
    res: dict = {}
    for kind, ti, li, a, b in spans:
        res[(kind, ti, li)] = {"errors": [], "try": "", "sorry": False}
    for m in msgs:
        for kind, ti, li, a, b in spans:
            if a <= m.line <= b:
                r = res[(kind, ti, li)]
                if m.severity == "error":
                    r["errors"].append(m.text)
                elif "Try this:" in m.text:
                    r["try"] = m.text.split("Try this:", 1)[1].strip()
                elif leancheck.SORRY_RE.search(m.text):
                    r["sorry"] = True
                break
    return res


# ---------------------------------------------------------------- planner
class Planner:
    def __init__(self, ctx, store: PlanStore, limit: int | None = None):
        self.ctx, self.store = ctx, store
        caps = getattr(ctx.slots, "caps", {}) or {}
        self.limit = limit or max(1, min(4, int(caps.get("online", 3)) + int(caps.get("gpu", 1))))
        self.queues: dict[str, list[tuple[str, list[dict]]]] = {}     # plan dossier -> [(dossier id, job plan)]
        self.runners: dict[str, asyncio.Task] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.alocks: dict[str, asyncio.Lock] = {}                      # analyse / advance, per plan
        self.analysing: dict[str, str] = {}                            # plan dossier -> node being analysed

    # -- settings
    @property
    def max_depth(self) -> int:
        return max(1, min(5, int(getattr(self.ctx.settings, "plan_max_depth", DEFAULT_DEPTH) or DEFAULT_DEPTH)))

    @property
    def budget_s(self) -> float:
        return 60.0 * max(5, int(getattr(self.ctx.settings, "plan_budget_minutes", DEFAULT_BUDGET_MIN)
                                 or DEFAULT_BUDGET_MIN))

    def _lean_real(self) -> bool:
        from ..brain.fake import FakeLean
        return not isinstance(self.ctx.lean, FakeLean)

    # -- views
    def node_state(self, n: dict, plan: dict | None = None, rt: dict | None = None) -> dict:
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
        elif n.get("admitted"):
            st = "admitted"
        nrt = ((rt or {}).get("nodes") or {}).get(n["id"]) or {}
        if st in ("submitted", "accepted") and nrt.get("combining"):
            st = "combining"
        off = off_track(plan, n["id"]) if plan is not None else ""
        ui = self._ui(n, st, off, nrt)
        return {**n, "state": st, "ui": ui, "off": off, "proved": bool(d is not None and d.proof_is_current),
                "conditional": cond, "dossier_status": d.status if d is not None else "",
                "combine": {k: nrt[k] for k in ("state", "why", "t", "holes") if k in nrt} or None,
                "depth": depth_of(plan, n["id"]) if plan is not None else 0}

    @staticmethod
    def _ui(n: dict, st: str, off: str, nrt: dict) -> str:
        """The six user-facing statuses (+ conditional): to_validate, validated, running, proved, failed,
        abandoned, alternative, hole, conditional."""
        if off:
            return off
        if st == "proved":
            return "proved"
        if st == "admitted":
            return "hole"
        if st == "proved_modulo" or nrt.get("state") == "conditional":
            return "conditional"
        if st in ("proving", "queued", "submitted", "combining"):
            return "running"
        if st in ("failed", "stopped") or nrt.get("state") == "failed":
            return "failed"
        if n.get("obvious"):
            return "proved"
        if st == "draft":
            return "to_validate"
        if st == "rejected":
            return "abandoned"
        return "validated"

    def summary(self, plan: dict, nodes: dict, rt: dict) -> dict:
        """« Où en est-on » (no model): counts on the active tree + what to do next."""
        act = [x for x in depth_first(plan) if x != plan["root"]]
        by = {}
        for x in act:
            by[nodes[x]["ui"]] = by.get(nodes[x]["ui"], 0) + 1
        root = nodes[plan["root"]]
        holes = by.get("hole", 0)
        run = rt.get("run") or None
        failed = [x for x in act if nodes[x]["ui"] == "failed"]
        if root["ui"] == "proved":
            nxt = "done"
        elif not act:
            nxt = "split"
        elif failed:
            nxt = "fix"
        elif root["ui"] == "conditional":
            nxt = "conditional"
        elif by.get("to_validate"):
            nxt = "validate"
        elif not run:
            nxt = "prove"
        elif run and run.get("stopped"):
            nxt = "stopped"
        else:
            nxt = "wait"
        depth = max([depth_of(plan, x) for x in plan["nodes"]] or [0])
        return {"lemmas": len(act), "proved": by.get("proved", 0), "running": by.get("running", 0),
                "failed": len(failed), "holes": holes, "to_validate": by.get("to_validate", 0),
                "conditional": by.get("conditional", 0), "depth": depth, "max_depth": self.max_depth,
                "nodes": live_nodes(plan), "max_nodes": MAX_NODES, "next": nxt, "attention": failed[:6],
                "run": run, "analysing": self.analysing.get(plan.get("dossier_id", ""), "")}

    def public(self, did: str) -> dict | None:
        p = self.store.current(did)
        if p is None:
            return None
        rt = self.store.runtime(did)
        nodes = {k: self.node_state(v, p, rt) for k, v in p["nodes"].items()}
        root = nodes[p["root"]]
        if root["ui"] == "validated":           # the theorem itself: what the plan is waiting for
            run = rt.get("run") or {}
            kids = [nodes[x]["ui"] for x in depth_first(p) if x != p["root"]]
            root["ui"] = ("running" if run and not run.get("stopped") and not run.get("finished") else
                          "failed" if "failed" in kids else "to_validate" if "to_validate" in kids or not kids
                          else "validated")
        d = self.ctx.repo.get(did)
        cond = (d.extra.get("conditional_proof") if d is not None else None) or None
        admitted = [n for n in nodes.values() if n["state"] == "admitted" and not n["off"]]
        if d is not None and d.proof_is_current:
            verdict = {"state": "proved", "verified": True, "admitted": 0}
        elif cond and cond.get("verdict") == "proved_modulo":
            verdict = {"state": "proved_modulo", "verified": False, "admitted": len(cond.get("admitted", [])),
                       "admitted_names": cond.get("admitted", [])}
        else:
            verdict = {"state": "open", "verified": False, "admitted": len(admitted)}
        data = self.store.load(did) or {"versions": []}
        return {**p, "nodes": nodes, "root_state": root["state"], "verdict": verdict,
                "summary": self.summary(p, nodes, rt),
                "limits": {"depth": self.max_depth, "lemmas": MAX_LEMMAS, "alternatives": MAX_ALTS,
                           "nodes": MAX_NODES, "budget_minutes": int(self.budget_s // 60)},
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

    # -- model call
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
            try:
                await self.ctx.slots.acquire("online", owner)
                try:
                    res = await brain.run_agent("prove", "You plan proofs. Answer with the requested JSON only.",
                                                messages[0]["content"], tools, mode=mode, max_steps=6,
                                                max_seconds=180)
                finally:
                    self.ctx.slots.release("online", owner)
                if res.final_text and _json_obj(res.final_text):
                    return res.final_text, res.model.key
            except Exception:  # noqa: BLE001 (agent unavailable: one plain completion)
                pass
        from ..server.helpers import complete_once
        c = await complete_once(self.ctx, "prove", messages, mode, owner=owner, max_tokens=6000, temperature=0.4)
        return c.text, c.model.key

    async def _mathlib_hits(self, ws_key: str, statement: str, text: str) -> list[dict]:
        try:
            from ..pipeline.mathlib_first import candidates
            return (await asyncio.wait_for(candidates(self.ctx.retriever, ws_key, statement, [text], k=8), 45))[:10]
        except Exception:  # noqa: BLE001 (no index: no hints, never an error)
            return []

    # -- analysis: the model drafts tracks, Lean gates them
    def _node_decl(self, plan: dict, nid: str) -> tuple[str, str, str]:
        """(context, name, signature) of a node: the dossier's statement for the root (or a node with a
        dossier), else the node's Lean statement; context = the root's declarations above its theorem."""
        n = plan["nodes"][nid]
        root = plan["nodes"][plan["root"]]
        rd = self.ctx.repo.get(root.get("dossier_id") or "")
        root_stmt = (rd.statement if rd is not None and rd.statement else root.get("lean") or "")
        rparts = split_decl(root_stmt)
        context = rparts[0] if rparts else ""
        if nid == plan["root"]:
            if not rparts:
                raise PlanError("no_statement", 409, "Il faut d'abord un énoncé Lean accepté.")
            return context, rparts[1], rparts[2]
        dd = self.ctx.repo.get(n.get("dossier_id") or "")
        src = dd.statement if dd is not None and dd.statement else n.get("lean") or ""
        parts = split_decl(src)
        if not parts:
            raise PlanError("no_statement", 409, "Ce lemme n'a pas d'énoncé Lean : écrivez-le d'abord.")
        return context, parts[1], parts[2]

    def _guard_split(self, plan: dict, nid: str) -> None:
        n = plan["nodes"].get(nid)
        if n is None:
            raise PlanError("not_found", 404)
        if off_track(plan, nid):
            raise PlanError("off_track", 409, "Ce lemme appartient à une piste non choisie.")
        if n.get("obvious"):
            raise PlanError("obvious", 409, "Ce lemme est évident (fermé par une tactique simple) : il ne se découpe "
                                            "pas.")
        dd = self.ctx.repo.get(n.get("dossier_id") or "") if nid != plan["root"] else None
        if dd is not None and dd.proof_is_current:
            raise PlanError("already_proved", 409)
        if dd is not None and self.ctx.orchestrator.active_for(dd.id):
            raise PlanError("busy", 409)
        if depth_of(plan, nid) + 1 > self.max_depth:
            raise PlanError("too_deep", 409, "Profondeur maximale atteinte ({n} niveaux) : prouvez ce lemme, "
                                             "changez de piste ou laissez un trou.", n=self.max_depth)
        if live_nodes(plan) - len(self._prunable(plan, nid)) + 2 > MAX_NODES:
            raise PlanError("too_many_nodes", 409, "Le plan a atteint {n} nœuds : simplifiez-le avant de découper "
                                                   "encore.", n=MAX_NODES)

    def _prunable(self, plan: dict, nid: str) -> list[str]:
        """Nodes below `nid` that a new split replaces: everything without a dossier."""
        return [x for x in subtree(plan, nid) if x != nid and not plan["nodes"][x].get("dossier_id")]

    async def analyse(self, did: str, nid: str | None = None, *, hint: str = "", sketch: str = "",
                      mode: str | None = None, base_rev: int | None = None, force: bool = False,
                      device: str = "") -> dict:
        """« Découper ce théorème » / « Redécouper »: tracks for node `nid` (default: the root), gated by Lean."""
        d = self.ctx.repo.get(did)
        if d is None:
            raise PlanError("not_found", 404)
        link = d.extra.get("plan") if isinstance(d.extra.get("plan"), dict) else None
        if link and self.store.current(did) is None and self.store.current(link.get("plan_dossier", "")) is not None:
            # a lemma of a plan is split inside THAT plan (one tree, one set of limits), never in a new tree
            raise PlanError("in_plan", 409, "Ce lemme fait partie d'un plan : redécoupez-le depuis le plan du "
                                            "théorème.", plan_dossier=link["plan_dossier"], node=link.get("node", ""))
        plan = self._cur(did, base_rev) if self.store.current(did) is not None else new_plan(d)
        nid = nid or plan["root"]
        self._guard_split(plan, nid)
        n = plan["nodes"][nid]
        if not force and any(plan["nodes"][x].get("edited") for x in self._prunable(plan, nid)):
            raise PlanError("would_overwrite", 409, "Le plan contient des modifications manuelles : confirmez pour "
                                                    "créer une nouvelle version proposée par l'IA (l'ancienne reste "
                                                    "disponible).")
        context, pname, psig = self._node_decl(plan, nid)
        lk = self.alocks.setdefault(did, asyncio.Lock())
        if self.analysing.get(did):
            raise PlanError("busy", 409, "Une analyse est déjà en cours pour ce plan.")
        self.analysing[did] = nid
        self.publish(did)
        try:
            async with lk:
                await self._analyse(did, d, plan, nid, n, context, pname, psig, hint, sketch,
                                    mode or self.ctx.settings.mode, device)
        finally:
            self.analysing.pop(did, None)
            self.publish(did)
        return self.public(did)

    async def _analyse(self, did, d, plan, nid, n, context, pname, psig, hint, sketch, mode, device) -> dict:
        ws = self.ctx.workspace(d.workspace or self.ctx.settings.workspace)
        goal = n["statement_nl"] or n["title"] if nid != plan["root"] else (
            d.understood_display or d.understood or d.problem or n["statement_nl"])
        lean_text = f"theorem {pname} {psig} := by sorry"
        par = plan["nodes"].get(n["parent"] or "")
        parent_nl = (par["statement_nl"] or par["title"])[:600] if par else ""
        hits = await self._mathlib_hits(ws.key if ws else "", lean_text, goal or "") if ws else []
        budget = MAX_NODES - (live_nodes(plan) - len(self._prunable(plan, nid)))
        feedback, best, model = "", None, ""
        for attempt in range(GATE_TRIES):
            msgs = analyse_messages(goal, pname, lean_text, context, hint, sketch, hits,
                                    max(0, min(MAX_ALTS, budget // 3 - 1)), feedback, parent_nl,
                                    max_lemmas=max(2, min(MAX_LEMMAS, budget)),
                                    lang=getattr(self.ctx.settings, "language", "fr"))
            text, model = await self._ask(msgs, mode, f"plan-{did}")
            tracks = parse_tracks(text)
            if not tracks:
                feedback = "No usable JSON plan was found in your answer."
                continue
            tracks = self._prepare_tracks(tracks, pname, psig, budget)
            if not tracks:
                feedback = "Every lemma statement was malformed (`theorem name (binders) : prop := by sorry`)."
                continue
            await self._gate(ws, context, pname, psig, tracks)
            good = [t for t in tracks if t["ok"]]
            cand = good or [t for t in tracks if not t["refused"]]
            score = (len(good), sum(1 for t in cand if all(lm["sig"] and not lm["err"] for lm in t["lemmas"])),
                     len(cand))
            if best is None or score > best["score"]:
                best = {"tracks": cand or tracks, "good": bool(good), "model": model, "score": score,
                        "refused": [t for t in tracks if t["refused"]]}
            if good:
                break
            feedback = self._feedback(tracks)
        if best is None:
            raise PlanError("no_plan_proposed", 422, "Le modèle n'a proposé aucun plan utilisable.")
        tracks = sorted(best["tracks"], key=lambda t: (not t["ok"], t["refused"] != ""))
        live = [t for t in tracks if not t["refused"]]
        refused = [{"idea": t["idea"][:300], "reason": t["refused"],
                    "lemmas": [lm["lean"][:500] for lm in t["lemmas"] if lm["err"].startswith("equivalent")
                               or norm_sig(lm["sig"]) == norm_sig(psig)]} for t in best.get("refused", [])]
        candidates = live
        live = [t for t in live if all(lm["sig"] and not lm["err"] for lm in t["lemmas"])]
        if not live and candidates:
            raise PlanError("lean_rejected", 422, "Lean a refusé chaque découpage proposé (énoncés de lemmes "
                                                  "invalides) : réessayez, donnez une piste ou changez de modèle.",
                            why=self._feedback(tracks)[:1500])
        if not live:
            raise PlanError("loop_refused", 422, "Chaque piste proposée redisait le théorème lui-même : refusée "
                                                 "(garde-fou contre les boucles).")
        # cheap closers on every installed track (the obvious-stop rule), when Lean is real
        if ws is not None and self._lean_real():
            await self._closers(ws, context, live)
        self._install(plan, nid, live, pname)
        plan["nodes"][nid]["refused_tracks"] = refused       # the loop guard's refusals, shown, never installed
        src = "sketch" if sketch else "ai"
        return self._push(did, plan, src, device, best["model"], note=f"analyse {nid}" + (f" — {hint[:120]}"
                                                                                         if hint else ""))

    def _prepare_tracks(self, tracks: list[dict], pname: str, psig: str, budget: int) -> list[dict]:
        """Rename lemmas `<parent>_<track letter><k>` (unique, no Mathlib clash), parse signatures, apply the
        limits (lemmas per track, alternatives, node budget) and the text half of the loop guard."""
        out, used = [], 0
        for ti, t in enumerate(tracks[: 1 + MAX_ALTS]):
            letter = TRACK_LETTERS[ti]
            mapping, lemmas = {}, []
            cap = min(MAX_LEMMAS, budget - used)
            if cap < 1 or (ti > 0 and cap < len(t["lemmas"][:MAX_LEMMAS])):
                break                                 # alternatives only when they fit whole
            for k, lm in enumerate(t["lemmas"][:cap]):
                parts = split_decl(lm["lean"]) if lm["lean"] else None
                new = f"{pname}_{letter}{k + 1}"
                if parts:
                    mapping[parts[1]] = new
                if lm.get("name"):
                    mapping.setdefault(lm["name"], new)
                lemmas.append({**lm, "name": new, "sig": parts[2] if parts else "",
                               "lean": f"theorem {new} {parts[2]} := by sorry" if parts else lm["lean"],
                               "err": "" if parts else "malformed"})
            used += len(lemmas)
            for lm in lemmas:
                lm["uses"] = [mapping.get(u, u) for u in lm.get("uses") or [] if mapping.get(u, u) != lm["name"]]
            comb = body_of(rename_refs(t.get("combination") or "", mapping), pname)
            refused = ""
            if any(lm["sig"] and norm_sig(lm["sig"]) == norm_sig(psig) for lm in lemmas):
                refused = "same_text"
            out.append({"idea": t["idea"], "lemmas": lemmas, "combination": comb, "refused": refused,
                        "ok": False, "check": {"state": "unchecked", "why": "", "t": 0.0}})
        return out

    async def _gate(self, ws, context: str, pname: str, psig: str, tracks: list[dict]) -> None:
        """One Lean compile: lemma statements (sorry), combinations, equivalence probes. Sets lemma `err`, track
        `check` / `ok` / `refused`. Without a workspace or with an infra failure, tracks stay « unchecked »."""
        for t in tracks:
            for lm in t["lemmas"]:
                if lm["sig"] and leancheck.exec_risks(lm["lean"]):
                    lm["err"] = "refused: " + ", ".join(leancheck.exec_risks(lm["lean"]))
            if t["combination"] and (leancheck.exec_risks(t["combination"]) or
                                     leancheck.forbidden_reasons(t["combination"])):
                t["check"] = {"state": "failed", "why": "forbidden: " + ", ".join(
                    leancheck.exec_risks(t["combination"]) + leancheck.forbidden_reasons(t["combination"])),
                    "t": time.time()}
                t["combination_bad"] = True
        if ws is None:
            return
        real = self._lean_real()
        gt = [{"lemmas": [lm for lm in t["lemmas"] if lm["sig"] and not lm["err"]],
               "combination": "" if t.get("combination_bad") or t["refused"] else t["combination"]}
              for t in tracks]
        code, spans = gate_file(context, pname, psig, gt, equiv=real)
        r = await self.ctx.lean.check(code, ws, max(120, self.ctx.settings.compile_timeout_s), None,
                                      owner=f"plan-gate-{pname}")
        if r.timed_out or r.infra_error:
            for t in tracks:
                if t["check"]["state"] == "unchecked":
                    t["check"] = {"state": "unchecked", "why": r.verdict.summary, "t": time.time()}
            return
        msgs = leancheck.parse_lean_json(r.stdout) if r.stdout else list(r.verdict.errors)
        res = read_gate(spans, msgs)
        ctx_err = res.get(("context", -1, -1), {}).get("errors") or res.get(("parent", -1, -1), {}).get("errors")
        for ti, t in enumerate(tracks):
            g = gt[ti]
            for li, lm in enumerate(g["lemmas"]):
                e = res.get(("lemma", ti, li), {}).get("errors") or []
                if e:
                    lm["err"] = "; ".join(x[:300] for x in e[:3])
                if real and not e:
                    dn = res.get(("dn", ti, li), {"errors": ["?"]})
                    up = res.get(("up", ti, li), {"errors": ["?"]})
                    if not dn["errors"] and not up["errors"]:
                        lm["err"] = "equivalent to the theorem itself"
                        t["refused"] = t["refused"] or "equivalent"
            lemma_ok = all(lm["sig"] and not lm["err"] for lm in t["lemmas"])
            if t["refused"]:
                t["check"] = {"state": "failed", "why": "loop: " + t["refused"], "t": time.time()}
            elif t["check"]["state"] == "failed":
                pass
            elif not t["combination"]:
                t["check"] = {"state": "unchecked", "why": "no combination", "t": time.time()}
            else:
                ce = res.get(("comb", ti, -1), {}).get("errors") or []
                if ctx_err:
                    t["check"] = {"state": "failed", "why": "; ".join(ctx_err[:2])[:400], "t": time.time()}
                elif ce:
                    t["check"] = {"state": "failed", "why": "; ".join(x[:300] for x in ce[:3]), "t": time.time()}
                else:
                    t["check"] = {"state": "ok", "why": "", "t": time.time()}
            t["ok"] = lemma_ok and t["check"]["state"] == "ok"

    @staticmethod
    def _feedback(tracks: list[dict]) -> str:
        lines = []
        for t in tracks:
            for lm in t["lemmas"]:
                if lm["err"]:
                    lines.append(f"- lemma `{lm['name']}`: {lm['err'][:300]}")
            if t["check"]["state"] == "failed":
                lines.append(f"- combination of track « {t['idea'][:60]} »: {t['check']['why'][:400]}")
            elif t["check"]["state"] == "unchecked" and not t["combination"]:
                lines.append(f"- track « {t['idea'][:60]} » has no combination proof")
        return "\n".join(lines[:12]) or "The theorem does not follow from the lemmas."

    async def _closers(self, ws, context: str, tracks: list[dict]) -> None:
        """Obvious-stop rule: a lemma closed by cheap closers (or `exact?`, under a heartbeat cap) is proved now.
        One compile for all the tracks."""
        groups = [{"lemmas": [lm for lm in t["lemmas"] if lm["sig"] and not lm["err"]], "combination": ""}
                  for t in tracks]
        if not any(g["lemmas"] for g in groups):
            return
        code, spans = gate_file(context, "obvious", "(x : True) : True", groups, equiv=False, closers=True,
                                exact=True, statements=False)
        r = await self.ctx.lean.check(code, ws, max(180, self.ctx.settings.compile_timeout_s), None,
                                      owner="plan-closers")
        if r.timed_out or r.infra_error:
            return
        res = read_gate(spans, leancheck.parse_lean_json(r.stdout) if r.stdout else list(r.verdict.errors))
        for ti, g0 in enumerate(groups):
            for li, lm in enumerate(g0["lemmas"]):
                g = res.get(("close", ti, li))
                if g is None or g["errors"] or g["sorry"]:
                    continue
                sugg = g["try"]
                if sugg and (leancheck.forbidden_reasons(sugg) or re.search(
                        r"__mdl|(?<![\w.'])" + re.escape(lm["name"]) + r"(?![\w'])", sugg)):
                    continue                          # never a proof that cites itself or a probe
                body = sugg or CLOSERS
                lm["obvious_proof"] = f"theorem {lm['name']} {lm['sig']} := by\n  {body}\n"

    def _install(self, plan: dict, nid: str, tracks: list[dict], pname: str) -> None:
        """Replace the split of `nid`: prune undossiered nodes below it, keep started ones as abandoned tracks."""
        n = plan["nodes"][nid]
        for x in self._prunable(plan, nid):
            plan["nodes"].pop(x, None)
        kept = []
        for t in n.get("tracks") or []:
            t["lemmas"] = [x for x in t["lemmas"] if x in plan["nodes"]]
            if t["lemmas"]:
                t["abandoned"] = True
                kept.append(t)
        n["tracks"], n["children"], n["active_track"] = kept, [], ""
        first = ""
        for t in tracks:
            tid = _free_track_id(n)
            ids = []
            by_name = {}
            for lm in t["lemmas"]:
                c = node(lm["title"], lm["statement"], lm["why"], lm["lean"], nid)
                c["track"], c["lean_ok"] = tid, (None if t["check"]["state"] == "unchecked" and not lm["err"]
                                                 else not lm["err"])
                c["lean_error"] = lm["err"][:1000]
                c["name"] = lm["name"]
                c["uses_names"] = lm.get("uses") or []
                if lm.get("obvious_proof"):
                    c["obvious"], c["obvious_proof"] = True, lm["obvious_proof"]
                plan["nodes"][c["id"]] = c
                ids.append(c["id"])
                by_name[lm["name"]] = c["id"]
            for x in ids:
                c = plan["nodes"][x]
                c["uses"] = [by_name[u] for u in c.pop("uses_names") if u in by_name]
            tr = track(tid, t["idea"], ids, t["combination"])
            tr["check"], tr["refused"] = t["check"], t["refused"]
            tr["name"] = pname
            if t["refused"]:
                tr["abandoned"] = True
            n["tracks"].append(tr)
            if not first and not t["refused"]:
                first = tid
        n["active_track"] = first
        act = next((t for t in n["tracks"] if t["id"] == first), None)
        n["children"] = list(act["lemmas"]) if act else []
        n["admitted"] = False

    # -- legacy entry points (S-G API), now on top of the analysis
    async def draft(self, d, *, hint: str = "", sketch: str = "", mode: str | None = None, force: bool = False,
                    device: str = "") -> dict:
        cur = self.store.current(d.id)
        if cur is not None and not force and any(n.get("edited") for n in cur["nodes"].values()):
            raise PlanError("would_overwrite", 409, "Le plan contient des modifications manuelles : confirmez pour "
                                                    "créer une nouvelle version proposée par l'IA (l'ancienne reste "
                                                    "disponible).")
        return await self.analyse(d.id, None, hint=hint, sketch=sketch, mode=mode, force=True, device=device)

    async def replan(self, did: str, nid: str, *, hint: str = "", mode: str | None = None, base_rev: int | None = None,
                     device: str = "") -> dict:
        return await self.analyse(did, nid, hint=hint, mode=mode, base_rev=base_rev, force=True, device=device)

    # -- manual edits
    def create_empty(self, d, device: str = "") -> dict:
        if self.store.current(d.id) is not None:
            return self.public(d.id)
        return self._push(d.id, new_plan(d), "user", device)

    def _stale(self, plan: dict, nid: str) -> None:
        """A manual change under `nid`'s active track: its combination must be checked again."""
        n = plan["nodes"].get(nid)
        t = next((t for t in (n or {}).get("tracks") or [] if t["id"] == (n or {}).get("active_track")), None)
        if t is not None and t["check"]["state"] != "unchecked":
            t["check"] = {"state": "unchecked", "why": "edited", "t": time.time()}

    def edit_node(self, did: str, nid: str, fields: dict, base_rev: int | None, device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        n = plan["nodes"].get(nid)
        if n is None:
            raise PlanError("not_found", 404)
        combination = fields.pop("combination", None) if isinstance(fields, dict) else None
        bad = [k for k in fields if k not in EDITABLE or not isinstance(fields[k], str)]
        if bad or (combination is not None and not isinstance(combination, str)):
            raise PlanError("bad_fields", 400, fields=bad or ["combination"])
        if n.get("dossier_id") and nid != plan["root"] and "lean" in fields and fields["lean"] != n["lean"]:
            raise PlanError("submitted", 409, "Ce nœud a déjà son dossier : modifiez l'énoncé dans le dossier.")
        for k, v in fields.items():
            n[k] = v[:20000]
        if "lean" in fields:
            n["lean_ok"], n["lean_error"], n["obvious"], n["obvious_proof"] = None, "", False, ""
            parts = split_decl(n["lean"])
            if parts:
                n["name"] = parts[1]
            if n["parent"]:
                self._stale(plan, n["parent"])
        if combination is not None:
            t = next((t for t in n.get("tracks") or [] if t["id"] == n.get("active_track")), None)
            if t is None:
                raise PlanError("no_track", 409)
            t["combination"] = body_of(combination, n.get("name")) or combination[:20000]
            t["check"] = {"state": "unchecked", "why": "edited", "t": time.time()}
        n["edited"] = True
        return self._push(did, plan, "user", device, note=f"edit {nid}")

    def add_node(self, did: str, parent: str, fields: dict, index: int | None, base_rev: int | None,
                 device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        if parent not in plan["nodes"]:
            raise PlanError("not_found", 404)
        if live_nodes(plan) + 1 > MAX_NODES:
            raise PlanError("too_many_nodes", 409, "Le plan a atteint {n} nœuds : simplifiez-le avant de découper "
                                                   "encore.", n=MAX_NODES)
        if depth_of(plan, parent) + 1 > self.max_depth:
            raise PlanError("too_deep", 409, "Profondeur maximale atteinte ({n} niveaux) : prouvez ce lemme, "
                                             "changez de piste ou laissez un trou.", n=self.max_depth)
        kids = plan["nodes"][parent]["children"]
        if len(kids) + 1 > MAX_LEMMAS:
            raise PlanError("too_many_lemmas", 409, "Au plus {n} lemmes par piste.", n=MAX_LEMMAS)
        n = node(str(fields.get("title") or fields.get("statement_nl") or "?"), str(fields.get("statement_nl", "")),
                 str(fields.get("why", "")), str(fields.get("lean", "")), parent)
        n["edited"] = True
        parts = split_decl(n["lean"])
        if parts:
            n["name"] = parts[1]
        plan["nodes"][n["id"]] = n
        kids = list(kids)
        kids.insert(len(kids) if index is None else max(0, min(int(index), len(kids))), n["id"])
        set_children(plan, parent, kids)
        n["track"] = plan["nodes"][parent]["active_track"]
        self._stale(plan, parent)
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
        par = plan["nodes"][plan["nodes"][nid]["parent"]]
        if nid in par["children"]:
            set_children(plan, par["id"], [x for x in par["children"] if x != nid])
        for t in par.get("tracks") or []:
            t["lemmas"] = [x for x in t["lemmas"] if x != nid]
        for x in plan["nodes"].values():
            x["uses"] = [u for u in x.get("uses") or [] if u != nid]
        for x in sub:
            del plan["nodes"][x]
        self._stale(plan, par["id"])
        return self._push(did, plan, "user", device, note=f"delete {nid}")

    def move_node(self, did: str, nid: str, parent: str, index: int | None, base_rev: int | None,
                  device: str = "") -> dict:
        plan = self._cur(did, base_rev)
        if nid == plan["root"] or nid not in plan["nodes"] or parent not in plan["nodes"]:
            raise PlanError("not_found", 404)
        if parent in subtree(plan, nid):
            raise PlanError("cycle", 400)
        old = plan["nodes"][nid]["parent"]
        set_children(plan, old, [x for x in plan["nodes"][old]["children"] if x != nid])
        for t in plan["nodes"][old].get("tracks") or []:
            t["lemmas"] = [x for x in t["lemmas"] if x != nid]
        kids = [x for x in plan["nodes"][parent]["children"] if x != nid]
        kids.insert(len(kids) if index is None else max(0, min(int(index), len(kids))), nid)
        set_children(plan, parent, kids)
        plan["nodes"][nid]["parent"] = parent
        plan["nodes"][nid]["track"] = plan["nodes"][parent]["active_track"]
        plan["nodes"][nid]["edited"] = True
        if old != parent:
            self._stale(plan, old)
        self._stale(plan, parent)
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

    # -- tracks
    async def switch_track(self, did: str, nid: str, tid: str | None, base_rev: int | None, device: str = "") -> dict:
        """« Autre piste »: node `nid` uses track `tid` (default: the next one not abandoned); the current track is
        abandoned (its running lemmas are stopped). The run continues with the new lemmas."""
        plan = self._cur(did, base_rev)
        n = plan["nodes"].get(nid)
        if n is None:
            raise PlanError("not_found", 404)
        cur = next((t for t in n.get("tracks") or [] if t["id"] == n.get("active_track")), None)
        options = [t for t in n.get("tracks") or [] if t["id"] != n.get("active_track") and not t.get("refused")
                   and (not t.get("abandoned") or t["id"] == tid)]
        new = next((t for t in options if t["id"] == tid), None) if tid else (options[0] if options else None)
        if new is None:
            raise PlanError("no_alternative", 409, "Aucune autre piste pour ce nœud : redécoupez-le ou laissez un "
                                                   "trou.")
        stop = []
        if cur is not None:
            cur["abandoned"] = True
            stop = [plan["nodes"][x]["dossier_id"] for y in cur["lemmas"] for x in subtree(plan, y)
                    if plan["nodes"].get(x, {}).get("dossier_id")]
        new["abandoned"] = False
        n["active_track"], n["children"] = new["id"], list(new["lemmas"])
        for x in new["lemmas"]:
            if plan["nodes"][x]["status"] == "draft" and plan.get("validated"):
                plan["nodes"][x]["status"] = "accepted"
        self.queues[did] = [(x, jp) for x, jp in self.queues.get(did, []) if x not in stop]
        for x in stop:
            await self.ctx.orchestrator.cancel_dossier(x)
        rt = self.store.runtime(did)
        rt["nodes"].pop(nid, None)
        pub = self._push(did, plan, "user", device, note=f"track {nid} → {new['id']}")
        if rt.get("run"):
            self.ctx.spawn(self.advance(did))
        return pub

    async def recheck(self, did: str, nid: str, base_rev: int | None = None, device: str = "") -> dict:
        """Run the Lean gate again on the active track of `nid` (after manual edits)."""
        plan = self._cur(did, base_rev)
        n = plan["nodes"].get(nid)
        if n is None:
            raise PlanError("not_found", 404)
        t = next((t for t in n.get("tracks") or [] if t["id"] == n.get("active_track")), None)
        if t is None:
            raise PlanError("no_track", 409)
        d = self.ctx.repo.get(did)
        ws = self.ctx.workspace(d.workspace or self.ctx.settings.workspace)
        context, pname, psig = self._node_decl(plan, nid)
        lemmas = []
        for x in t["lemmas"]:
            c = plan["nodes"][x]
            parts = split_decl(c["lean"]) if c["lean"] else None
            lemmas.append({"name": parts[1] if parts else c.get("name", ""), "sig": parts[2] if parts else "",
                           "lean": c["lean"], "err": "" if parts else "malformed", "id": x})
        tt = {"idea": t["idea"], "lemmas": lemmas, "combination": t["combination"], "refused": "", "ok": False,
              "check": {"state": "unchecked", "why": "", "t": 0.0}}
        await self._gate(ws, context, pname, psig, [tt])
        if ws is not None and self._lean_real() and not tt["refused"]:
            await self._closers(ws, context, [tt])
        for lm in lemmas:
            c = plan["nodes"][lm["id"]]
            c["lean_ok"] = None if tt["check"]["state"] == "unchecked" and not lm["err"] else not lm["err"]
            c["lean_error"] = lm["err"][:1000]
            if lm.get("obvious_proof") and not c.get("dossier_id"):
                c["obvious"], c["obvious_proof"] = True, lm["obvious_proof"]
        t["check"] = tt["check"]
        if tt["refused"]:
            t["refused"] = tt["refused"]
        return self._push(did, plan, "user", device, note=f"recheck {nid}")

    # -- validation and the automatic run
    def validate(self, did: str, base_rev: int | None, device: str = "") -> dict:
        """« Valider le plan »: every lemma of the active tree becomes accepted."""
        plan = self._cur(did, base_rev)
        acts = [x for x in depth_first(plan) if x != plan["root"]]
        if not acts:
            raise PlanError("nothing_to_submit", 422, "Découpez d'abord le théorème en lemmes.")
        for x in acts:
            if plan["nodes"][x]["status"] in ("draft", "rejected"):
                plan["nodes"][x]["status"] = "accepted"
        plan["validated"] = time.time()
        return self._push(did, plan, "user", device, note="validate")

    async def prove(self, did: str, base_rev: int | None, device: str = "", mode: str | None = None) -> dict:
        """« Prouver le plan »: validates if needed, then proves every lemma automatically (sub-dossiers within the
        concurrency limit), combines bottom-up, and only stops to ask when a lemma fails."""
        plan = self._cur(did, base_rev)
        if not plan.get("validated") or any(plan["nodes"][x]["status"] == "draft"
                                            for x in depth_first(plan) if x != plan["root"]):
            self.validate(did, plan["rev"], device)
        rt = self.store.runtime(did)
        now = time.time()
        rt["run"] = {"started": now, "deadline": now + self.budget_s, "mode": mode or "", "stopped": ""}
        self.store.save_runtime(did)
        await self.advance(did)
        return {"plan": self.public(did)}

    def stop_run(self, did: str, reason: str = "user") -> None:
        rt = self.store.runtime(did)
        if rt.get("run"):
            rt["run"]["stopped"] = reason
            self.store.save_runtime(did)

    async def _materialize(self, did: str, plan: dict, mode: str | None) -> list[str]:
        """Sub-dossiers for every lemma of the active tree that has none yet; obvious lemmas get their proof at
        once (strict re-check), leaves are queued. Returns created node ids."""
        from ..server.routes_work import create_dossier
        root_d = self.ctx.repo.get(did)
        created = []
        q = self.queues.setdefault(did, [])
        for x in depth_first(plan):
            if x == plan["root"]:
                continue
            n = plan["nodes"][x]
            if n.get("dossier_id") or n["status"] == "rejected":
                continue
            par = plan["nodes"][n["parent"]]
            parent_d = self.ctx.repo.get(par.get("dossier_id") or "")
            if parent_d is None:
                continue
            context = split_decl(root_d.statement)[0] if root_d.statement and split_decl(root_d.statement) else ""
            lean = (context + "\n\n" + n["lean"]).strip() if n["lean"] and n.get("lean_ok") is not False else ""
            spec = {"title": n["title"], "problem": n["statement_nl"] or n["title"], "statement": lean,
                    "project_id": root_d.project_id, "workspace": root_d.workspace, "parent_id": parent_d.id,
                    "kind": "lemma", "start": False}
            try:
                child, _job = await create_dossier(self.ctx, spec, user_event=False)
            except leancheck.StatementError:
                spec["statement"] = ""
                child, _job = await create_dossier(self.ctx, spec, user_event=False)
            child.extra["plan"] = {"plan_dossier": did, "node": x}
            await self.ctx.repo.save(child)
            n["dossier_id"], n["status"] = child.id, "submitted"
            if child.id not in parent_d.uses:
                parent_d.uses.append(child.id)
            parent_d.retry_parent = False                 # the plan combines; the orchestrator does not retry
            await self.ctx.repo.save(parent_d)
            created.append(x)
        for x in created:
            n = plan["nodes"][x]
            if n["children"] or n.get("admitted"):
                continue                                  # internal node: combined when its lemmas are proved
            dd = self.ctx.repo.get(n["dossier_id"])
            if n.get("obvious") and n.get("obvious_proof") and dd.statement:
                if await self._store_proof(dd, n["obvious_proof"], "obvious"):
                    continue
            jp = ([{"stage": "proof"}] if dd.statement else
                  [{"stage": "understand"}, {"stage": "statement"}, {"stage": "proof"}])
            q.append((dd.id, jp))
        return created

    async def _store_proof(self, dd, code: str, strategy: str, used: list[str] | None = None,
                           model: str = "") -> bool:
        """Strict check (D28 gate inside lean.check) of `code` against the dossier's statement; on success the proof
        is the dossier's and enters the library."""
        ws = self.ctx.workspace(dd.workspace or self.ctx.settings.workspace)
        if ws is None or not dd.statement:
            return False
        try:
            full = leancheck.assemble_proof(dd.statement, code)
            name = leancheck.theorem_name(dd.statement)
        except leancheck.StatementError:
            return False
        r = await self.ctx.lean.check(leancheck.with_axiom_probe(full, name), ws, self.ctx.settings.compile_timeout_s,
                                      name, owner=f"plan-store-{dd.id}")
        if not r.verdict.ok:
            return False
        from ..runtime.lean import workspace_info
        info = workspace_info(ws)
        meta = {"axioms": r.verdict.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
                "workspace": ws.key, "seconds": round(r.seconds, 1), "strategy": strategy, "attempts": 1,
                "checked": time.time()}
        idx = dd.add_proof(full, note=f"proof plan ({strategy})", model=model, meta=meta)
        dd.status = "proved"
        dd.lemmas_used = list(used or [])
        m = (msg("Lemme évident : fermé par une tactique simple, vérifié par Lean.") if strategy == "obvious" else
             msg("Plan de preuve : les lemmes sont prouvés, la combinaison est vérifiée par Lean (verdict strict)."))
        dd.add_event("proof", m["text"], ref=idx, key=m["key"])
        await self.ctx.repo.save(dd)
        entry = await asyncio.to_thread(self.ctx.library.add_proof, full, dd.title, ws.key, dd.id, list(used or []))
        if entry:
            self.ctx.publish("library.updated", {"added": entry.name})
        return True

    async def advance(self, did: str) -> None:
        """Move the run forward (idempotent): create missing sub-dossiers, combine every node whose lemmas are all
        proved (or holes), respect the budget, then schedule."""
        rt = self.store.runtime(did)
        run = rt.get("run")
        if not run or run.get("stopped"):
            return
        lk = self.alocks.setdefault(did, asyncio.Lock())
        async with lk:
            if time.time() > run.get("deadline", 0):
                run["stopped"] = "budget"
                self.queues[did] = []
                self.store.save_runtime(did)
                self.publish(did)
                return
            plan = self._cur(did)
            created = await self._materialize(did, plan, run.get("mode") or None)
            if created:
                self.store.push(did, plan, source="auto", note=f"run: {len(created)} lemma(s)")
            plan = self._cur(did)
            for x in reversed(depth_first(plan)):
                n = plan["nodes"][x]
                if not n["children"] or n.get("admitted"):
                    continue
                dd = self.ctx.repo.get(n.get("dossier_id") or "")
                if dd is None or dd.proof_is_current or self.ctx.orchestrator.active_for(dd.id):
                    continue
                kids = [plan["nodes"][c] for c in n["children"]]
                states = [self._kid_state(c) for c in kids]
                if not all(s in ("proved", "hole", "conditional") for s in states):
                    continue
                key = json.dumps([[c["id"], c.get("dossier_id"), s,
                                   (self.ctx.repo.get(c.get("dossier_id") or "").cur_proof
                                    if self.ctx.repo.get(c.get("dossier_id") or "") else -1)]
                                  for c, s in zip(kids, states)])
                nrt = rt["nodes"].setdefault(x, {})
                if nrt.get("key") == key:
                    continue
                nrt.update({"key": key, "combining": True})
                self.publish(did)
                try:
                    await self._combine(did, plan, x, kids, states, nrt, run.get("mode") or None)
                finally:
                    nrt["combining"] = False
                    self.store.save_runtime(did)
            root_d = self.ctx.repo.get(did)
            if root_d is not None and root_d.proof_is_current:
                run["finished"] = time.time()
                self.store.save_runtime(did)
        self._kick(did, run.get("mode") or None)
        self.publish(did)

    def _kid_state(self, n: dict) -> str:
        if n.get("admitted"):
            return "hole"
        dd = self.ctx.repo.get(n.get("dossier_id") or "")
        if dd is None:
            return "missing"
        if dd.proof_is_current:
            return "proved"
        if ((dd.extra.get("conditional_proof") or {}).get("verdict") == "proved_modulo"):
            return "conditional"
        return dd.status

    async def _combine(self, did: str, plan: dict, nid: str, kids: list[dict], states: list[str], nrt: dict,
                       mode: str | None) -> None:
        """Compile node `nid`'s combination with the REAL proofs of its lemmas (library entries) and holes /
        conditional lemmas stated with `sorry`. No hole → strict verdict → the node's proof. Holes → conditional
        (never verified). A combination that fails → the normal proof stage of the node, with its lemmas forced in
        as library results (only without holes)."""
        from ..dossiers import closure
        n = plan["nodes"][nid]
        dd = self.ctx.repo.get(n["dossier_id"])
        t = next((t for t in n.get("tracks") or [] if t["id"] == n.get("active_track")), None)
        ws = self.ctx.workspace(dd.workspace or self.ctx.settings.workspace)
        entries, holes, mapping, hole_names = [], [], {}, []
        for c, s in zip(kids, states):
            cd = self.ctx.repo.get(c.get("dossier_id") or "")
            plan_name = c.get("name") or (split_decl(c["lean"])[1] if split_decl(c["lean"]) else "")
            if s == "proved" and cd is not None:
                e = next((e for e in self.ctx.library.entries if e.dossier == cd.id), None)
                if e is None:
                    nrt.update({"state": "failed", "why": "lemma proof missing from the library", "t": time.time()})
                    return
                entries.append(e)
                if plan_name:
                    mapping[plan_name] = e.name
            else:
                src = cd.statement if cd is not None and cd.statement else c["lean"]
                parts = split_decl(src)
                if not parts:
                    nrt.update({"state": "failed", "why": "hole without a Lean statement", "t": time.time()})
                    return
                holes.append(f"-- hole (admitted, plan): {c['title'][:80]}\ntheorem {parts[1]} {parts[2]} := by sorry")
                hole_names.append(parts[1])
                if plan_name:
                    mapping[plan_name] = parts[1]
        body = rename_refs(t["combination"], mapping) if t and t.get("combination") else ""
        if not body or ws is None or not dd.statement:
            nrt.update({"state": "fallback" if not holes else "failed",
                        "why": "no combination" if not body else "no workspace", "t": time.time()})
            if not holes:
                self._fallback(did, dd, mode)
            return
        entries = closure(self.ctx.library, entries)
        statement = leancheck.prepare_statement(self.conditional_statement(dd.statement, entries, holes))
        name = leancheck.theorem_name(statement)
        try:
            full = leancheck.assemble_proof(statement, f"theorem {name} := by\n{indent(body)}")
        except leancheck.StatementError as e:
            nrt.update({"state": "failed", "why": str(e)[:300], "t": time.time()})
            return
        if not holes:
            ok = await self._store_proof(dd, full, "plan", used=[e.name for e in entries],
                                         model=(t or {}).get("model", ""))
            if ok:
                nrt.update({"state": "proved", "why": "", "t": time.time(), "holes": 0})
                return
            nrt.update({"state": "fallback", "why": "combination rejected with the real lemmas", "t": time.time()})
            self._fallback(did, dd, mode)
            return
        res = await self.check_conditional(full, name, ws, hole_names)
        if res["ok"]:
            n_holes = self._holes_below(plan, nid)
            cond = {"verdict": "proved_modulo", "admitted": hole_names, "code": full, "theorem": name,
                    "axioms": res["axioms"], "strict_ok": res["strict_ok"], "strict_summary": res["strict_summary"],
                    "checked": time.time(), "model": "", "plan_node": nid, "workspace": ws.key, "holes": n_holes}
            dd.extra["conditional_proof"] = cond
            m = msg("Conditionnel — {n} trou(s) : la combinaison est vérifiée par Lean avec des lemmes admis "
                    "(sorry). Ce n'est PAS une preuve vérifiée.", n=n_holes)
            dd.add_event("info", m["text"], key=m["key"], params=m["params"])
            await self.ctx.repo.save(dd)
            nrt.update({"state": "conditional", "why": "", "t": time.time(), "holes": n_holes})
        else:
            nrt.update({"state": "failed", "why": res.get("why", "")[:400], "t": time.time()})

    def _holes_below(self, plan: dict, nid: str) -> int:
        n = 0
        for x in depth_first(plan):
            if x == nid:
                continue
            y, below = x, False
            while y:
                y = plan["nodes"][y]["parent"]
                if y == nid:
                    below = True
                    break
            if below and plan["nodes"][x].get("admitted"):
                n += 1
        return n

    def _fallback(self, did: str, dd, mode: str | None) -> None:
        """The combination did not go through: the node is proved by the normal proof stage, its proven lemmas
        forced in as library results (runner: children's entries are always given)."""
        if dd.id == did or not any(x == dd.id for x, _p in self.queues.get(did, [])):
            self.queues.setdefault(did, []).append((dd.id, [{"stage": "proof"}]))

    # -- legacy submission (S-G API): accepted nodes → sub-dossiers, parent retried by the orchestrator
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
        self._push(did, plan, "user", device, note=f"submit {len(created)}")
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
        if (t is None or t.done()) and self.queues.get(did):
            self.runners[did] = self.ctx.spawn(self._schedule(did, mode))

    async def _schedule(self, did: str, mode: str | None) -> None:
        """Keep at most `limit` jobs of this plan in the orchestrator; the slots still decide what really runs."""
        from ..orchestrator import DossierBusy
        started: set[str] = set()
        while self.queues.get(did):
            run = self.store.runtime(did).get("run") or {}
            if run and not run.get("stopped") and time.time() > run.get("deadline", float("inf")):
                run["stopped"] = "budget"
                self.store.save_runtime(did)
                self.queues[did] = []
                break
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
            self.stop_run(did)
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

    # -- holes (admitted lemmas): conditional proofs, never verified
    def admit(self, did: str, nid: str, base_rev: int | None, device: str = "") -> dict:
        """« Laisser un trou »: the lemma is admitted (`sorry`); its ancestors can only become CONDITIONAL."""
        plan = self._cur(did, base_rev)
        n = plan["nodes"].get(nid)
        if n is None or nid == plan["root"]:
            raise PlanError("not_found", 404)
        dd = self.ctx.repo.get(n.get("dossier_id") or "")
        if dd is not None and dd.proof_is_current:
            raise PlanError("already_proved", 409)
        stmt = dd.statement if dd is not None and dd.statement else n.get("lean") or ""
        if not split_decl(stmt) or n.get("lean_ok") is False and not (dd is not None and dd.statement):
            raise PlanError("no_statement", 409, "Un lemme admis doit avoir un énoncé Lean accepté.")
        n["admitted"], n["cancelled"] = True, False
        pub = self._push(did, plan, "user", device, note=f"admit {nid}")
        if dd is not None and self.ctx.orchestrator.active_for(dd.id):
            self.ctx.spawn(self.ctx.orchestrator.cancel_dossier(dd.id))
        self.queues[did] = [(x, jp) for x, jp in self.queues.get(did, []) if x != (dd.id if dd else "")]
        if self.store.runtime(did).get("run"):
            self.ctx.spawn(self.advance(did))
        return pub

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
            code = re.sub(r"-- (admitted for now|hole \(admitted, plan\)):[^\n]*\n", "", code)
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
        if (self.store.runtime(plan_id).get("run") or {}) and not self.store.runtime(plan_id)["run"].get("stopped"):
            self.ctx.spawn(self.advance(plan_id))
        self.publish(plan_id)


# ---------------------------------------------------------------- demo answer (scripted brain)
DEMO_TRACKS = {"tracks": [
    {"idea": "Écrire $a$ et $b$ comme des doubles, puis additionner.",
     "lemmas": [
         {"name": "a_double", "title": "a est un double", "statement": "Si $a$ est pair, il existe $k$ tel que "
          "$a = k + k$.", "why": "Définition de la parité.", "uses": [],
          "lean": "theorem a_double (a : ℕ) (ha : Even a) : ∃ k, a = k + k := by sorry"},
         {"name": "sum_doubles", "title": "Somme de deux doubles", "statement": "$(k + k) + (l + l)$ est pair.",
          "why": "Conclut une fois $a$ et $b$ écrits comme des doubles.", "uses": [],
          "lean": "theorem sum_doubles (k l : ℕ) : Even ((k + k) + (l + l)) := by sorry"}],
     "combination": "theorem T (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n"
                    "  obtain ⟨k, hk⟩ := a_double a ha\n  obtain ⟨l, hl⟩ := a_double b hb\n"
                    "  subst hk hl\n  exact sum_doubles k l"},
    {"idea": "Passer par la divisibilité par 2.",
     "lemmas": [
         {"name": "even_iff_two_dvd'", "title": "Pair = divisible par 2", "statement": "Un entier naturel est pair "
          "si et seulement s'il est divisible par $2$.", "why": "Traduit la parité en divisibilité.", "uses": [],
          "lean": "theorem even_iff_two_dvd' (n : ℕ) : Even n ↔ 2 ∣ n := by sorry"},
         {"name": "dvd_sum", "title": "2 divise la somme", "statement": "Si $2 \\mid a$ et $2 \\mid b$, alors "
          "$2 \\mid a + b$.", "why": "La divisibilité passe à la somme.", "uses": [],
          "lean": "theorem dvd_sum (a b : ℕ) (ha : 2 ∣ a) (hb : 2 ∣ b) : 2 ∣ a + b := by sorry"}],
     "combination": "theorem T (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n"
                    "  rw [even_iff_two_dvd'] at *\n  exact dvd_sum a b ha hb"}]}


def demo_answer(first: str) -> str | None:
    if not first.startswith(MARK):
        return None
    if "task=analyse" in first:
        return json.dumps(DEMO_TRACKS, ensure_ascii=False)
    return json.dumps({"claims": [
        {"title": "a pair", "statement": "Il existe $k$ tel que $a = 2k$.", "why": "Définition de la parité.",
         "lean": "theorem plan_a_even (a : ℕ) (ha : Even a) : ∃ k, a = k + k := by sorry", "children": []},
        {"title": "b pair", "statement": "Il existe $l$ tel que $b = 2l$.", "why": "Idem pour $b$.",
         "lean": "theorem plan_b_even (b : ℕ) (hb : Even b) : ∃ l, b = l + l := by sorry", "children": []},
        {"title": "Somme", "statement": "$a + b = 2(k + l)$ est pair.", "why": "Conclut la preuve.",
         "lean": "theorem plan_sum (k l : ℕ) : Even ((k + k) + (l + l)) := by sorry", "children": []}]},
        ensure_ascii=False)


def demo_plan(d) -> dict:
    """`--demo`: a small decomposition of « the square of an even integer is even » (map with a split lemma, an
    obvious lemma, an alternative track) — checked by Lean in a real run, scripted here."""
    plan = new_plan(d)
    r = plan["root"]
    stmt = "theorem carre_pair (n : ℕ) (hn : Even n) : Even (n ^ 2) := by sorry"
    plan["nodes"][r]["lean"] = plan["nodes"][r]["lean"] or stmt

    def lem(parent, title, nl, why, lean, obvious=""):
        c = node(title, nl, why, lean, parent)
        c["name"] = split_decl(lean)[1]
        c["lean_ok"] = True
        if obvious:
            c["obvious"], c["obvious_proof"] = True, obvious
        plan["nodes"][c["id"]] = c
        return c["id"]
    a1 = lem(r, "n est un double", "Si $n$ est pair, il existe $k$ tel que $n = k + k$.", "Rend la parité calculable.",
             "theorem carre_pair_a1 (n : ℕ) (hn : Even n) : ∃ k, n = k + k := by sorry",
             "theorem carre_pair_a1 (n : ℕ) (hn : Even n) : ∃ k, n = k + k := by\n  exact hn\n")
    a2 = lem(r, "Carré d'un double", "$(k + k)^2 = 2 \\cdot (2k^2)$.", "Fait apparaître le facteur 2.",
             "theorem carre_pair_a2 (k : ℕ) : (k + k) ^ 2 = 2 * (2 * k ^ 2) := by sorry")
    a3 = lem(r, "Un double est pair", "Pour tout $m$, $2m$ est pair.", "Conclut.",
             "theorem carre_pair_a3 (m : ℕ) : Even (2 * m) := by sorry",
             "theorem carre_pair_a3 (m : ℕ) : Even (2 * m) := by\n  exact even_two_mul m\n")
    b1 = lem(r, "Pair fois entier", "Si $n$ est pair, $n \\cdot m$ est pair.", "Le carré est $n \\cdot n$.",
             "theorem carre_pair_b1 (n m : ℕ) (hn : Even n) : Even (n * m) := by sorry")
    c1 = lem(a2, "Double = 2k", "$k + k = 2k$.", "Réécrit le double.", "theorem carre_pair_a2_a1 (k : ℕ) : k + k = 2 * k := "
             "by sorry", "theorem carre_pair_a2_a1 (k : ℕ) : k + k = 2 * k := by\n  omega\n")
    c2 = lem(a2, "Carré de 2k", "$(2k)^2 = 4k^2$.", "Développe le carré.",
             "theorem carre_pair_a2_a2 (k : ℕ) : (2 * k) ^ 2 = 2 * (2 * k ^ 2) := by sorry")
    ta = track("a", "Écrire $n = k + k$, développer le carré, factoriser par $2$.", [a1, a2, a3],
               "obtain ⟨k, rfl⟩ := carre_pair_a1 n hn\nrw [carre_pair_a2 k]\nexact carre_pair_a3 _")
    ta["check"] = {"state": "ok", "why": "", "t": time.time()}
    tb = track("b", "Le produit d'un pair par un entier est pair.", [b1], "rw [pow_two]\nexact carre_pair_b1 n n hn")
    tb["check"] = {"state": "ok", "why": "", "t": time.time()}
    tc = track("a", "Passer par $2k$ puis développer.", [c1, c2], "rw [carre_pair_a2_a1]\nexact carre_pair_a2_a2 k")
    tc["check"] = {"state": "unchecked", "why": "", "t": 0.0}
    for x, t in ((a1, "a"), (a2, "a"), (a3, "a"), (b1, "b"), (c1, "a"), (c2, "a")):
        plan["nodes"][x]["track"] = t
    plan["nodes"][r].update(tracks=[ta, tb], active_track="a", children=[a1, a2, a3])
    plan["nodes"][a2].update(tracks=[tc], active_track="a", children=[c1, c2])
    return plan
