"""The problem graph (« graphe de lemmes raisonné », session S-AY, DECISIONS D57, docs/PROOF_GRAPH.md).

One graph per dossier, stored in the dossier's proof-plan file (`PlanStore`, key `graph`): it EXTENDS the proof plan
(S-L) instead of living beside it. The plan stays the user's editable tree of tracks; the graph is the memory of the
problem: every lemma met (planner, Mathlib, certificates, the literature, the library, the reasoned search), what
was tried on it, why a track was chosen or abandoned, and how the results combine.

Pure module (no server context): data model, statement keys, status propagation (« conditionnel »), cycle checks,
deterministic viability signals, the bounded memory digest given to provers, the migration from proof plans, and
the explanations (built from recorded facts only — no model writes them, so nothing can be invented).

Node statuses (`status`): proved (Lean, strict) · mathlib · certified · cited (from the literature, NOT proved in
Lean: conditional) · open · refuted · abandoned (with the reason). The status a user sees is `effective()`:
verified / conditional / open / refuted / abandoned — a node proved with an unproved cited lemma or a hole is
« conditionnel, repose sur … », never « vérifié »; it becomes verified when every lemma it rests on is verified.

Edges `[src, kind, dst]`: uses (src's proof uses dst) · generalises (src generalises dst) · special_case (src is a
special case of dst) · refutes (src, a counterexample, refutes dst). « uses » edges never form a cycle."""
from __future__ import annotations

import copy
import hashlib
import re
import time
import uuid

from .. import leancheck
from ..pipeline.stagecache import normalize_text

GRAPH_VERSION = 1
STATUSES = ("proved", "mathlib", "certified", "cited", "open", "refuted", "abandoned")
VERIFIED = ("proved", "mathlib", "certified")
KINDS = ("goal", "lemma", "mathlib", "certificate", "cited", "library", "proposal")
EDGE_KINDS = ("uses", "generalises", "special_case", "refutes")
MAX_GRAPH_NODES = 120          # stored nodes per dossier graph (oldest closed non-goal nodes dropped first)
MAX_ATTEMPTS_KEPT = 6          # attempt records kept per node (older ones folded into counters)
MAX_LOG = 200                  # change-log entries kept per graph
MAX_RUNS = 10                  # search-run records kept per graph
MAX_PROOF_CHARS = 20000
DIGEST_TOKENS = 600            # default budget of the prover digest (≈ 3.5 characters per token)
CHARS_PER_TOKEN = 3.5
MATHLIB_DOC = "https://leanprover-community.github.io/mathlib4_docs/find/?pattern={name}#doc"


class GraphError(Exception):
    def __init__(self, kind: str, status: int = 400, **data):
        super().__init__(kind)
        self.kind, self.status, self.data = kind, status, data
        self.params = {k: v for k, v in data.items() if isinstance(v, (str, int, float))}


# ---------------------------------------------------------------- keys
def statement_key(lean: str = "", nl: str = "") -> str:
    """Normalised statement key: the same Lean statement (whatever its name, comments, spacing) gives the same key in
    every run and every dossier of the project. Without a Lean statement, the normalised words (prefix `nl:`)."""
    if lean and lean.strip():
        from .proofplan import split_decl
        parts = split_decl(lean)
        # the last theorem's binders and type only: its name, comments, spacing, the header and the dossier's
        # context (shared inside one top-level dossier) are not part of what it says
        norm = re.sub(r"\s+", " ", parts[2]).strip() if parts else ""
        if norm:
            return "lean:" + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]
    words = normalize_text(nl)
    return ("nl:" + hashlib.sha256(words.encode("utf-8")).hexdigest()[:24]) if words else ""


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[A-Za-z][A-Za-z0-9_.']*|[ℕℤℚℝℂ∣≤≥≠√∑∏^%+*/<>=-]", text or "")
            if w not in {"theorem", "lemma", "by", "sorry", "fun"}}


def similarity(a: str, b: str) -> float:
    """Jaccard similarity of the statements' vocabularies (0..1); cheap, deterministic."""
    x, y = _words(a), _words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def error_fingerprint(error: str) -> str:
    """Two failures with the same fingerprint are the same failing state (no progress)."""
    first = next((ln for ln in (error or "").splitlines() if ln.strip()), "")
    first = re.sub(r"\d+", "#", first.lower())
    first = re.sub(r"\s+", " ", first).strip()[:160]
    return hashlib.sha1(first.encode("utf-8")).hexdigest()[:12] if first else ""


# ---------------------------------------------------------------- model
def _nid() -> str:
    return "gn-" + uuid.uuid4().hex[:8]


def new_node(kind: str, title: str, *, lean: str = "", statement_nl: str = "", status: str = "open",
             source: dict | None = None, why: str = "", plan_node: str = "", dossier_id: str = "") -> dict:
    if kind not in KINDS:
        raise GraphError("bad_kind")
    if status not in STATUSES:
        raise GraphError("bad_status")
    now = time.time()
    return {"id": _nid(), "key": statement_key(lean, statement_nl or title), "kind": kind, "title": (title or "")[:200],
            "statement_nl": (statement_nl or "")[:3000], "lean": (lean or "")[:8000], "status": status, "reason": "",
            "why": (why or "")[:1000], "source": dict(source or {"kind": "user"}), "citation": None,
            "plan_node": plan_node, "dossier_id": dossier_id, "depth": 0, "viability": None, "attempts": [],
            "attempts_n": 0, "errors_seen": {}, "proof": "", "tactics": [], "self_contained": True,
            "admitted": False, "proposal": False, "closed": None, "created": now, "updated": now}


def new_graph(dossier_id: str, project_id: str = "", title: str = "", lean: str = "", statement_nl: str = "") -> dict:
    root = new_node("goal", title or "Théorème", lean=lean, statement_nl=statement_nl,
                    source={"kind": "dossier"}, dossier_id=dossier_id)
    return {"v": GRAPH_VERSION, "rev": 1, "dossier_id": dossier_id, "project_id": project_id, "root": root["id"],
            "nodes": {root["id"]: root}, "edges": [], "log": [], "runs": [], "env": {}, "facts": "",
            "plan_rev": 0, "created": time.time(), "updated": time.time()}


def touch(g: dict, kind: str, node: str = "", **data) -> None:
    """Every change is a new revision with a log line (the graph's version history, bounded)."""
    g["rev"] = int(g.get("rev", 0)) + 1
    g["updated"] = time.time()
    g.setdefault("log", []).append({"rev": g["rev"], "t": g["updated"], "kind": kind, "node": node,
                                    **{k: v for k, v in data.items() if isinstance(v, (str, int, float, bool))}})
    del g["log"][:-MAX_LOG]


def find_key(g: dict, key: str) -> dict | None:
    if not key:
        return None
    return next((n for n in g["nodes"].values() if n["key"] == key), None)


def add_node(g: dict, node: dict, *, parent: str | None = None, edge: str = "uses") -> tuple[dict, bool]:
    """Insert `node` unless a node with the same statement key exists (then the sources are merged and the existing
    node is returned). `parent` (optional) gets an edge `parent --edge--> node`. Returns (node, created)."""
    same = find_key(g, node["key"])
    created = same is None
    if same is not None:
        src = node.get("source") or {}
        known = same.setdefault("sources", [])
        if src and src != same.get("source") and src not in known and len(known) < 8:
            known.append(src)
        if node.get("citation") and not same.get("citation"):
            same["citation"] = node["citation"]
        node = same
    else:
        if len(g["nodes"]) >= MAX_GRAPH_NODES:
            _prune(g)
        if len(g["nodes"]) >= MAX_GRAPH_NODES:
            raise GraphError("too_many_nodes", 409, n=MAX_GRAPH_NODES)
        g["nodes"][node["id"]] = node
    if parent:
        if parent not in g["nodes"]:
            raise GraphError("not_found", 404)
        if not add_edge(g, parent, edge, node["id"]):
            return node, created
        if created:
            node["depth"] = g["nodes"][parent].get("depth", 0) + 1
    if created:
        touch(g, "node", node["id"], title=node["title"][:80], source=(node.get("source") or {}).get("kind", ""))
    return node, created


def _prune(g: dict) -> None:
    """Keep the graph compact: drop the oldest abandoned / refuted non-goal leaves that nothing uses."""
    used = {e[2] for e in g["edges"] if e[1] == "uses"} | {e[0] for e in g["edges"]}
    victims = sorted((n for n in g["nodes"].values() if n["kind"] != "goal" and n["status"] in ("abandoned", "refuted")
                      and n["id"] not in used), key=lambda n: n["updated"])
    for n in victims[: max(1, len(g["nodes"]) - MAX_GRAPH_NODES + 10)]:
        g["nodes"].pop(n["id"], None)
        g["edges"] = [e for e in g["edges"] if n["id"] not in (e[0], e[2])]
        g.setdefault("forgotten", {})[n["key"]] = {"status": n["status"], "reason": n.get("reason", "")[:200],
                                                   "t": time.time()}
    if len(g.get("forgotten", {})) > 300:
        for k in sorted(g["forgotten"], key=lambda k: g["forgotten"][k]["t"])[:-300]:
            g["forgotten"].pop(k, None)


def uses_of(g: dict, nid: str) -> list[str]:
    return [e[2] for e in g["edges"] if e[0] == nid and e[1] == "uses" and e[2] in g["nodes"]]


def users_of(g: dict, nid: str) -> list[str]:
    return [e[0] for e in g["edges"] if e[2] == nid and e[1] == "uses" and e[0] in g["nodes"]]


def reaches(g: dict, src: str, dst: str, kind: str = "uses") -> bool:
    """Is there a path src → … → dst along `kind` edges? (iterative, cycle-safe)"""
    stack, seen = [src], set()
    while stack:
        x = stack.pop()
        if x == dst:
            return True
        if x in seen:
            continue
        seen.add(x)
        stack += [e[2] for e in g["edges"] if e[0] == x and e[1] == kind]
    return False


def add_edge(g: dict, src: str, kind: str, dst: str) -> bool:
    """Add an edge; a « uses » edge that would close a cycle (dst already uses src, or src == dst) is refused and
    logged. Returns False when refused."""
    if kind not in EDGE_KINDS:
        raise GraphError("bad_edge")
    if src not in g["nodes"] or dst not in g["nodes"]:
        raise GraphError("not_found", 404)
    if [src, kind, dst] in g["edges"]:
        return True
    if kind == "uses" and (src == dst or reaches(g, dst, src)):
        touch(g, "cycle_refused", src, target=dst)
        return False
    g["edges"].append([src, kind, dst])
    return True


def ancestors(g: dict, nid: str) -> list[str]:
    """Nodes that (transitively) use `nid`."""
    out, stack, seen = [], users_of(g, nid), set()
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
        stack += users_of(g, x)
    return out


# ---------------------------------------------------------------- statuses
def set_status(g: dict, nid: str, status: str, reason: str = "", env: dict | None = None, **extra) -> dict:
    if status not in STATUSES:
        raise GraphError("bad_status")
    n = g["nodes"][nid]
    n["status"], n["updated"] = status, time.time()
    n["reason"] = (reason or "")[:500]
    if status in ("abandoned", "refuted"):
        n["closed"] = {"t": time.time(), "reason": n["reason"], "env": dict(env or g.get("env") or {}),
                       "facts": facts_hash(g)}
    elif status == "open":
        n["closed"] = None
    for k, v in extra.items():
        n[k] = v
    touch(g, "status", nid, status=status, reason=n["reason"][:120])
    return n


def effective(g: dict, nid: str, _seen: frozenset = frozenset()) -> dict:
    """What the user is told: {state: verified|conditional|open|refuted|abandoned, rests_on: [node ids], composed}.

    - mathlib / certified, and a proved node whose own Lean proof is self-contained: verified.
    - a cited lemma (literature, not proved in Lean) or an admitted hole: conditional — it rests on itself.
    - a proved node whose proof used lemmas stated with `sorry` (self_contained False): verified when every lemma it
      uses is verified (composition of Lean-checked proofs of the same statements), else conditional and it rests
      on the unverified ones."""
    n = g["nodes"].get(nid)
    if n is None or nid in _seen:
        return {"state": "open", "rests_on": [], "composed": False}
    st = n["status"]
    if st in ("refuted", "abandoned"):
        return {"state": st, "rests_on": [], "composed": False}
    if st in ("mathlib", "certified") or (st == "proved" and n.get("self_contained", True)):
        return {"state": "verified", "rests_on": [], "composed": False}
    if st == "cited" or (st == "open" and n.get("admitted")):
        return {"state": "conditional", "rests_on": [nid], "composed": False}
    if st == "proved" and n.get("rests_external"):
        # rolled up from a sub-dossier whose own graph is conditional: it rests on that sub-dossier's results
        return {"state": "conditional", "rests_on": [nid], "composed": False}
    if st == "proved":
        rests: list[str] = []
        for u in uses_of(g, nid):
            e = effective(g, u, _seen | {nid})
            if e["state"] != "verified":
                rests += e["rests_on"] or [u]
        rests = list(dict.fromkeys(rests))
        return {"state": "conditional" if rests else "verified", "rests_on": rests, "composed": not rests}
    return {"state": "open", "rests_on": [], "composed": False}


def facts_hash(g: dict) -> str:
    """Changes when a new verified lemma enters the graph (an abandoned track may then be worth a new try)."""
    keys = sorted(n["key"] for n in g["nodes"].values() if n["status"] in VERIFIED)
    return hashlib.sha1("|".join(keys).encode()).hexdigest()[:12]


def env_changed(closed: dict | None, env: dict, facts: str) -> list[str]:
    """Why a closed (abandoned / refuted) node may be retried: [] when nothing changed."""
    if not closed:
        return ["never_closed"]
    out = []
    old = closed.get("env") or {}
    for k in ("lean", "mathlib", "workspace"):
        if env.get(k) and old.get(k) and env[k] != old[k]:
            out.append(k)
    if facts and closed.get("facts") and facts != closed["facts"]:
        out.append("new_lemma")
    return out


def rollup(g: dict, nid: str, child_graph: dict | None, child_proved: bool) -> bool:
    """A node opened as a sub-dossier takes the sub-dossier's verdict: its strictly proved theorem = proved;
    a conditional sub-graph = proved but conditional (« rests_external » lists what it rests on). Returns changed."""
    n = g["nodes"][nid]
    before = (n["status"], n.get("self_contained"), tuple(n.get("rests_external") or []))
    if child_proved:
        if n["status"] not in VERIFIED:
            set_status(g, nid, "proved", "", self_contained=True)
        n["rests_external"] = []
    elif child_graph is not None:
        e = effective(child_graph, child_graph["root"])
        if e["state"] == "conditional":
            titles = [child_graph["nodes"][x]["title"][:80] for x in e["rests_on"] if x in child_graph["nodes"]]
            if n["status"] != "proved":
                set_status(g, nid, "proved", "", self_contained=False)
            n["self_contained"] = False
            n["rests_external"] = titles or ["sub-dossier"]
    after = (n["status"], n.get("self_contained"), tuple(n.get("rests_external") or []))
    if after != before:
        touch(g, "rollup", nid, state=n["status"])
    return after != before


# ---------------------------------------------------------------- attempts and memory
def record_attempt(g: dict, nid: str, *, how: str, ok: bool, error: str = "", model: str = "", proof: str = "",
                   seconds: float = 0.0, tokens: int = 0, usd: float = 0.0, run: str = "") -> dict:
    """One try on a node (closers, certificate, a model proof, a pipeline job…). Returns {repeat: n} where n is how
    often this failing state was already seen (no-progress detection)."""
    n = g["nodes"][nid]
    fp = error_fingerprint(error) if not ok else ""
    seen = int(n["errors_seen"].get(fp, 0)) if fp else 0
    if fp:
        n["errors_seen"][fp] = seen + 1
        if len(n["errors_seen"]) > 30:
            for k in list(n["errors_seen"])[:-30]:
                n["errors_seen"].pop(k, None)
    rec = {"t": time.time(), "how": how[:40], "ok": bool(ok), "error": (error or "")[:600], "model": model[:120],
           "seconds": round(float(seconds), 2), "tokens": int(tokens), "usd": round(float(usd), 6), "fp": fp,
           "run": run, "tactics": tactics_of(proof) if ok and proof else []}
    n["attempts"].append(rec)
    n["attempts_n"] = int(n.get("attempts_n", 0)) + 1
    del n["attempts"][:-MAX_ATTEMPTS_KEPT]
    n["updated"] = time.time()
    touch(g, "attempt", nid, how=how[:40], ok=bool(ok))
    return {"repeat": seen, "fingerprint": fp}


_TACTIC_RE = re.compile(r"^\s*(?:[·.]\s*)?(?:<;>\s*)?([a-z_][A-Za-z_']*[?!]?)")
_NOT_TACTICS = {"theorem", "lemma", "def", "example", "import", "open", "set_option", "namespace", "end", "section",
                "variable", "noncomputable", "by", "at", "with", "fun", "then", "else", "if", "do", "from",
                "using", "only", "in", "let", "where", "match", "λ", "show_term", "private", "protected", "abbrev",
                "instance", "structure", "class", "attribute", "universe"}


def tactics_of(proof: str) -> list[str]:
    """Tactic names that appear at the start of a line of a Lean proof (recorded text; nothing is guessed)."""
    out: list[str] = []
    body = leancheck.remove_comments(proof or "")
    for ln in body.splitlines():
        s = ln.strip()
        if not s or s.startswith(("--", "import", "open ", "set_option", "theorem", "lemma", "def ", "example")):
            # a theorem line may carry `:= by tac`
            m = re.search(r":=\s*by\s+([a-z_][A-Za-z_']*[?!]?)", s)
            if m and m.group(1) not in _NOT_TACTICS:
                out.append(m.group(1))
            continue
        for part in re.split(r"\s*(?:<;>|;)\s*", s):
            m = _TACTIC_RE.match(part)
            if m and m.group(1) not in _NOT_TACTICS and not part.lstrip().startswith(("|", ")", "]", "⟩")):
                out.append(m.group(1))
    return list(dict.fromkeys(out))[:40]


def lean_constants(proof: str) -> list[str]:
    """Qualified constants written in a Lean proof (`Nat.add_comm`, `Even.add`, `Finset.sum_range_succ`): the
    proof's own words, offered as Mathlib references (links to the documentation search, not claims)."""
    body = leancheck.remove_comments(proof or "")
    body = re.sub(r'"(?:[^"\\]|\\.)*"', "", body)
    own = leancheck.declared_names(body)
    names = re.findall(r"(?<![\w.'])([A-Z][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)+)", body)
    return [x for x in dict.fromkeys(names) if x not in own and not x.startswith(("Mathlib.", "Aesop."))][:40]


# ---------------------------------------------------------------- viability (deterministic part)
def viability_signals(g: dict, nid: str, *, env: dict | None = None, project: list[dict] | None = None,
                      library_keys: dict | None = None) -> dict:
    """Signals computed WITHOUT a model: known result (graph / project / library), failed before (and whether
    something changed since), similarity to failed nodes, repeated Lean errors, cycles, depth. Returns
    {score, signals: [{code, params}], skip: bool}. `skip` = do not expand / attempt (already known or failed
    with nothing changed)."""
    n = g["nodes"][nid]
    env = env or g.get("env") or {}
    sig: list[dict] = []
    score, skip = 0.55, False
    facts = facts_hash(g)
    for other in g["nodes"].values():
        if other["id"] != nid and other["key"] == n["key"] and other["status"] in VERIFIED:
            sig.append({"code": "known", "params": {"title": other["title"][:80]}})
            return {"score": 1.0, "signals": sig, "skip": True, "known": other["id"]}
    for p in project or []:
        if p.get("key") == n["key"] and p.get("status") in VERIFIED:
            # offered for reuse (through the library, with its own Lean proof), never silently merged
            sig.append({"code": "known_project", "params": {"title": p.get("title", "")[:80],
                                                            "dossier": p.get("dossier_id", "")}})
            score += 0.2
            break
    if library_keys and n["key"] in library_keys:
        sig.append({"code": "in_library", "params": {"name": library_keys[n["key"]]}})
        return {"score": 1.0, "signals": sig, "skip": True, "library": library_keys[n["key"]]}
    if n["status"] in ("abandoned", "refuted") or n["key"] in (g.get("forgotten") or {}):
        closed = n.get("closed") if n["status"] in ("abandoned", "refuted") else {
            "reason": g["forgotten"][n["key"]]["reason"], "env": {}, "facts": ""}
        changed = env_changed(closed, env, facts)
        if n["status"] == "refuted":
            sig.append({"code": "refuted", "params": {"reason": n.get("reason", "")[:200]}})
            return {"score": 0.0, "signals": sig, "skip": True}
        if not changed:
            sig.append({"code": "failed_before", "params": {"reason": (closed or {}).get("reason", "")[:200]}})
            return {"score": 0.0, "signals": sig, "skip": True}
        sig.append({"code": "changed_since", "params": {"what": ", ".join(changed)}})
        score -= 0.15
    for p in project or []:
        if p.get("key") == n["key"] and p.get("status") in ("abandoned", "refuted") and p.get("dossier_id") != \
                g.get("dossier_id"):
            sig.append({"code": "failed_elsewhere", "params": {"title": p.get("title", "")[:80],
                                                               "reason": p.get("reason", "")[:160]}})
            score -= 0.25
            break
    text = n.get("lean") or n.get("statement_nl") or n["title"]
    worst, like = 0.0, None
    for o in g["nodes"].values():
        if o["id"] != nid and o["status"] in ("abandoned", "refuted"):
            s = similarity(text, o.get("lean") or o.get("statement_nl") or o["title"])
            if s > worst:
                worst, like = s, o
    if worst >= 0.8 and like is not None:
        sig.append({"code": "similar_failed", "params": {"title": like["title"][:80], "similarity": round(worst, 2),
                                                         "reason": like.get("reason", "")[:160]}})
        score -= 0.3 * worst
    repeats = sum(1 for v in n["errors_seen"].values() if v >= 2)
    if repeats:
        sig.append({"code": "same_error", "params": {"n": repeats}})
        score -= 0.25
    elif n["errors_seen"]:
        sig.append({"code": "lean_errors", "params": {"n": len(n["errors_seen"])}})
        score -= 0.05 * min(4, len(n["errors_seen"]))
    for a in ancestors(g, nid):
        if g["nodes"][a]["key"] == n["key"]:
            sig.append({"code": "cycle", "params": {"title": g["nodes"][a]["title"][:80]}})
            return {"score": 0.0, "signals": sig, "skip": True}
    d = int(n.get("depth", 0))
    if d:
        sig.append({"code": "depth", "params": {"n": d}})
        score -= 0.07 * d
    if n["kind"] == "cited":
        sig.append({"code": "cited", "params": {}})
    return {"score": round(max(0.0, min(1.0, score)), 3), "signals": sig, "skip": skip}


def combine_score(det: dict, model: dict | None) -> float:
    if not model or model.get("score") is None or det.get("skip"):
        return det["score"]
    return round(0.6 * det["score"] + 0.4 * max(0.0, min(1.0, float(model["score"]))), 3)


def priority(g: dict, nid: str) -> float:
    """Expected value per cost: viability score / (1 + attempts + half the depth)."""
    n = g["nodes"][nid]
    v = (n.get("viability") or {}).get("score", 0.5)
    return float(v) / (1.0 + int(n.get("attempts_n", 0)) + 0.5 * int(n.get("depth", 0)))


# ---------------------------------------------------------------- texts (FR / EN), from codes and recorded data
T = {
    "fr": {
        "known": "déjà prouvé dans ce graphe (« {title} »)",
        "known_project": "déjà prouvé dans un autre dossier du projet (« {title} ») : à réutiliser depuis la bibliothèque",
        "in_library": "déjà dans votre bibliothèque ({name})",
        "refuted": "réfuté : {reason}",
        "failed_before": "abandonné lors d'un essai précédent ({reason}) et rien n'a changé depuis",
        "changed_since": "abandonné auparavant, mais quelque chose a changé ({what}) : nouvel essai",
        "failed_elsewhere": "abandonné dans un autre dossier (« {title} » : {reason})",
        "similar_failed": "très proche d'une piste abandonnée (« {title} », similarité {similarity} : {reason})",
        "same_error": "la même erreur de Lean revient ({n} fois au moins deux fois)",
        "lean_errors": "{n} erreur(s) de Lean différente(s) déjà vues",
        "cycle": "boucle : ce lemme est l'énoncé d'un nœud qui l'utilise (« {title} »)",
        "depth": "profondeur {n}",
        "cited": "résultat cité, non prouvé en Lean : toute preuve qui l'utilise est conditionnelle",
        "model": "avis du modèle {model} : {reason}",
        "none": "aucun signal particulier",
        "score": "viabilité {score}",
        "verified": "vérifié par Lean", "conditional": "conditionnel", "open": "ouvert", "refuted": "réfuté",
        "abandoned": "abandonné", "composed": "vérifié par Lean (par composition de preuves vérifiées)",
    },
    "en": {
        "known": "already proved in this graph (“{title}”)",
        "known_project": "already proved in another dossier of the project (“{title}”): reuse it from the library",
        "in_library": "already in your library ({name})",
        "refuted": "refuted: {reason}",
        "failed_before": "abandoned in an earlier run ({reason}) and nothing has changed since",
        "changed_since": "abandoned before, but something changed ({what}): trying again",
        "failed_elsewhere": "abandoned in another dossier (“{title}”: {reason})",
        "similar_failed": "very close to an abandoned track (“{title}”, similarity {similarity}: {reason})",
        "same_error": "the same Lean error keeps coming back ({n} seen at least twice)",
        "lean_errors": "{n} different Lean error(s) already seen",
        "cycle": "loop: this lemma is the statement of a node that uses it (“{title}”)",
        "depth": "depth {n}",
        "cited": "cited result, not proved in Lean: any proof using it is conditional",
        "model": "opinion of the model {model}: {reason}",
        "none": "no particular signal",
        "score": "viability {score}",
        "verified": "verified by Lean", "conditional": "conditional", "open": "open", "refuted": "refuted",
        "abandoned": "abandoned", "composed": "verified by Lean (composition of verified proofs)",
    },
}


def _lang(lang: str) -> str:
    return "en" if str(lang or "").lower().startswith("en") else "fr"


def reason_text(v: dict | None, lang: str = "fr") -> str:
    """The written reason of a viability check, from its recorded signals (and the model's own words, labelled)."""
    if not v:
        return ""
    L = T[_lang(lang)]
    parts = []
    for s in v.get("signals") or []:
        tpl = L.get(s.get("code", ""))
        if tpl:
            try:
                parts.append(tpl.format(**(s.get("params") or {})))
            except (KeyError, IndexError):
                parts.append(tpl)
    m = v.get("model")
    if m and m.get("reason"):
        parts.append(L["model"].format(model=m.get("model", "?"), reason=str(m["reason"])[:200]))
    head = L["score"].format(score=f"{float(v.get('score', 0)):.2f}")
    return head + " — " + ("; ".join(parts) if parts else L["none"])


# ---------------------------------------------------------------- migration from a proof plan
PLAN_UI_STATUS = {"proved": "proved", "abandoned": "abandoned", "failed": "open", "hole": "open",
                  "conditional": "proved", "running": "open", "validated": "open", "to_validate": "open",
                  "alternative": "open"}


def sync_from_plan(g: dict, plan_public: dict) -> int:
    """Bring the plan's tree into the graph (idempotent; keyed by plan node id): the plan's lemmas become lemma nodes,
    the active track's lemmas are « used » by their parent, alternative tracks are open nodes, abandoned tracks keep
    their reason, holes are admitted (→ conditional). Returns the number of changes."""
    nodes = plan_public.get("nodes") or {}
    root_pid = plan_public.get("root")
    by_plan = {n.get("plan_node"): n for n in g["nodes"].values() if n.get("plan_node")}
    changes = 0
    if root_pid and root_pid not in by_plan:
        g["nodes"][g["root"]]["plan_node"] = root_pid
        by_plan[root_pid] = g["nodes"][g["root"]]
    order = [root_pid] if root_pid else []
    i = 0
    while i < len(order):                 # breadth first over children and every track's lemmas
        pn = nodes.get(order[i]) or {}
        kids = list(pn.get("children") or [])
        for t in pn.get("tracks") or []:
            kids += [x for x in t.get("lemmas") or [] if x not in kids]
        order += [k for k in kids if k in nodes and k not in order]
        i += 1
    for pid in order:
        pn = nodes[pid]
        gn = by_plan.get(pid)
        ui = pn.get("ui") or ""
        if gn is None:
            gn = new_node("lemma", pn.get("title") or "lemme", lean=pn.get("lean") or "",
                          statement_nl=pn.get("statement_nl") or "", why=pn.get("why") or "",
                          source={"kind": "planner", "model": plan_public.get("model", "")}, plan_node=pid,
                          dossier_id=pn.get("dossier_id") or "")
            gn, created = add_node(g, gn)
            if not created and not gn.get("plan_node"):
                gn["plan_node"] = pid
            by_plan[pid] = gn
            changes += 1
        if pid != root_pid:
            par = by_plan.get(pn.get("parent") or "")
            if par is not None and pid in (nodes.get(pn.get("parent")) or {}).get("children", []):
                if [par["id"], "uses", gn["id"]] not in g["edges"] and add_edge(g, par["id"], "uses", gn["id"]):
                    changes += 1
                    gn["depth"] = par.get("depth", 0) + 1
        if pn.get("dossier_id") and not gn.get("dossier_id"):
            gn["dossier_id"] = pn["dossier_id"]
        if pn.get("why") and not gn.get("why"):
            gn["why"] = pn["why"][:1000]
        want = PLAN_UI_STATUS.get(ui, gn["status"])
        if pn.get("obvious") or (pn.get("proved") and ui != "conditional"):
            want = "proved"
        admitted = ui == "hole"
        if gn.get("admitted") != admitted:
            gn["admitted"] = admitted
            changes += 1
        if ui == "conditional":
            gn["self_contained"] = False
        elif want == "proved":
            gn["self_contained"] = True
        if want != gn["status"] and not (gn["status"] in VERIFIED and want == "open"):
            reason = ""
            if want == "abandoned":
                t = next((t for t in (nodes.get(pn.get("parent") or "") or {}).get("tracks") or []
                          if pid in (t.get("lemmas") or [])), None)
                reason = ((t or {}).get("refused") or ((t or {}).get("check") or {}).get("why") or
                          "track abandoned in the plan")
            set_status(g, gn["id"], want, reason)
            changes += 1
        if pn.get("obvious_proof") and not gn.get("proof"):
            gn["proof"] = pn["obvious_proof"][:MAX_PROOF_CHARS]
            gn["tactics"] = tactics_of(gn["proof"])
            gn.setdefault("how", "obvious")
    for pn in nodes.values():                   # chosen track: the parent's recorded reasons
        gn = by_plan.get(pn.get("id"))
        if gn is None:
            continue
        tracks = pn.get("tracks") or []
        if tracks:
            gn["tracks"] = [{"id": t.get("id"), "idea": (t.get("idea") or "")[:300],
                             "lemmas": [by_plan[x]["id"] for x in t.get("lemmas") or [] if x in by_plan],
                             "active": t.get("id") == pn.get("active_track"), "abandoned": bool(t.get("abandoned")),
                             "check": (t.get("check") or {}).get("state", ""),
                             "why": ((t.get("check") or {}).get("why") or t.get("refused") or "")[:300]}
                            for t in tracks]
    g["plan_rev"] = plan_public.get("rev", g.get("plan_rev", 0))
    if changes:
        touch(g, "plan_sync", g["root"], plan_rev=int(g["plan_rev"] or 0), changes=changes)
    return changes


# ---------------------------------------------------------------- cited lemmas (the literature, S-AX interface)
def cited_node(item) -> dict:
    """A cited lemma from the literature (S-AX `literature.search` item, a dict or an object with the same
    attributes): {title, statement_nl, lean, citation: CSL-JSON + {verified, quote, locator}, status}. A cited lemma
    is never « proved » here: its status is `cited` (conditional) unless Lean later proves it."""
    get = (lambda k, d=None: item.get(k, d)) if isinstance(item, dict) else (lambda k, d=None: getattr(item, k, d))
    cit = get("citation") or {}
    if not isinstance(cit, dict):
        cit = {k: getattr(cit, k) for k in dir(cit) if not k.startswith("_") and not callable(getattr(cit, k))}
    n = new_node("cited", str(get("title") or cit.get("title") or "résultat cité")[:200],
                 lean=str(get("lean") or ""), statement_nl=str(get("statement_nl") or get("statement") or ""),
                 status="cited", source={"kind": "literature", "id": str(get("id") or "")[:80]})
    n["citation"] = {k: cit[k] for k in ("type", "title", "author", "editor", "issued", "container-title", "volume",
                                         "issue", "page", "publisher", "DOI", "URL", "arxiv", "zbl", "mrnumber",
                                         "verified", "quote", "locator", "key") if k in cit}
    origin = str(get("origin") or "literature")
    if origin in ("provided", "attachment", "library", "literature", "mathlib"):
        n["source"]["kind"] = origin
    if get("mathlib_name"):
        n["source"]["name"] = str(get("mathlib_name"))[:200]
    claimed = str(get("status") or "")
    if claimed:
        n["claimed"] = claimed[:20]      # what the source says (« proved », « mathlib »…): only Lean decides here
    return n


# ---------------------------------------------------------------- digest for the provers (problem memory)
def digest(g: dict, project: list[dict] | None = None, max_tokens: int = DIGEST_TOKENS, lang: str = "en") -> str:
    """A compact, bounded summary of what is known about the problem, for the provers' prompt. Deterministic order
    (sorted by key) so that the same memory gives the same bytes (prompt caching): proved lemmas, cited results
    (conditional), failed approaches with their reasons, useful tactics, counterexamples. Empty when nothing useful
    is known."""
    budget = int(max_tokens * CHARS_PER_TOKEN)
    nodes = sorted((n for n in g["nodes"].values() if n["id"] != g["root"]), key=lambda n: n["key"])
    sections: list[tuple[str, list[str]]] = []

    def stmt(n):
        s = (n.get("lean") or "").strip() or (n.get("statement_nl") or n["title"])
        return re.sub(r"\s+", " ", re.sub(r":=\s*by\s+sorry\s*$", "", s))[:300]
    proved = [f"- {stmt(n)}" + (f"  (Mathlib: {n['source'].get('name')})" if n["status"] == "mathlib" and
                                 (n.get("source") or {}).get("name") else "")
              for n in nodes if n["status"] in VERIFIED]
    for p in sorted(project or [], key=lambda p: p.get("key", "")):
        if p.get("status") in VERIFIED and p.get("lean") and not any(n["key"] == p.get("key") for n in nodes):
            proved.append(f"- {stmt(p)}  (proved in another dossier of the project: reuse it from the library)")
    cited = [f"- {stmt(n)}  [{(n.get('source') or {}).get('kind', 'cited')}: "
             f"{_short_cite(n.get('citation') or {})}; NOT proved in Lean]"
             for n in nodes if n["status"] == "cited"]
    failed = [f"- {stmt(n)} — {n.get('reason') or 'abandoned'}"[:400]
              for n in nodes if n["status"] == "abandoned"]
    refuted = [f"- {stmt(n)} — {n.get('reason') or 'refuted'}"[:400] for n in nodes if n["status"] == "refuted"]
    tac: dict[str, int] = {}
    for n in nodes + [g["nodes"][g["root"]]]:
        for t in n.get("tactics") or []:
            tac[t] = tac.get(t, 0) + 1
    tactics = [", ".join(sorted(tac, key=lambda t: (-tac[t], t))[:12])] if tac else []
    root = g["nodes"][g["root"]]
    root_errors = sorted({a["error"].splitlines()[0][:160] for a in root.get("attempts") or [] if a.get("error")})
    reach, stack = set(), [g["root"]]
    while stack:
        x = stack.pop()
        if x not in reach:
            reach.add(x)
            stack += uses_of(g, x)
    todo = [f"- {stmt(n)}" for n in nodes if n["id"] in reach and n["status"] == "open" and not n.get("admitted")]
    sections += [("Connu / Known — proved in Lean (usable):", proved),
                 ("Connu / Known — cited or provided, NOT proved in Lean (a proof using them is conditional):",
                  cited),
                 ("À prouver / To prove (missing lemmas):", todo),
                 ("Approaches that failed (do not repeat them blindly):", failed),
                 ("Refuted (false) statements:", refuted),
                 ("Tactics that worked on this problem:", tactics),
                 ("Lean errors already seen on the main goal:", [f"- {e}" for e in root_errors[:4]])]
    if not any(lines for _h, lines in sections):
        return ""
    target = (root.get("lean") or "").strip() or root.get("statement_nl") or root["title"]
    target = re.sub(r"\s+", " ", re.sub(r":=\s*by\s+sorry\s*$", "", target))[:600]
    out = ["Problem memory (Madalean):", f"Cible / Target: {target}"]
    used = sum(len(x) + 1 for x in out)
    for head, lines in sections:
        if not lines:
            continue
        block = [head]
        for ln in lines:
            if used + sum(len(x) + 1 for x in block) + len(ln) + 1 > budget:
                break
            block.append(ln)
        if len(block) > 1:
            out += block
            used += sum(len(x) + 1 for x in block)
    return "\n".join(out) if len(out) > 2 else ""


def _short_cite(c: dict) -> str:
    a = (c.get("author") or [{}])[0] if c.get("author") else {}
    who = a.get("family") or a.get("literal") or ""
    yr = ""
    dp = ((c.get("issued") or {}).get("date-parts") or [[None]]) if isinstance(c.get("issued"), dict) else [[None]]
    if dp and dp[0] and dp[0][0]:
        yr = str(dp[0][0])
    loc = c.get("locator") or ""
    return ", ".join(x for x in (who, yr, str(c.get("title") or "")[:80], loc) if x) or "reference"


def project_entries(g: dict) -> list[dict]:
    """What another dossier of the project may reuse from this graph (index rows, no proofs)."""
    return [{"key": n["key"], "status": n["status"], "title": n["title"], "lean": n.get("lean", ""),
             "reason": n.get("reason", "")[:200], "dossier_id": g.get("dossier_id", ""), "node": n["id"]}
            for n in g["nodes"].values() if n["key"] and n["status"] in VERIFIED + ("abandoned", "refuted", "cited")]


# ---------------------------------------------------------------- explanations (recorded facts only)
TACTICS = {
    "omega": ("décide l'arithmétique linéaire sur ℕ et ℤ (égalités, inégalités, divisibilité par des constantes)",
              "decides linear arithmetic over ℕ and ℤ (equalities, inequalities, divisibility by constants)"),
    "linarith": ("combine linéairement les hypothèses pour obtenir une inégalité",
                 "combines hypotheses linearly to obtain an inequality"),
    "nlinarith": ("comme linarith, en ajoutant des produits d'hypothèses (inégalités non linéaires)",
                  "like linarith, also multiplying hypotheses together (non-linear inequalities)"),
    "norm_num": ("calcule et simplifie des expressions numériques", "evaluates and simplifies numerical expressions"),
    "simp": ("réécrit avec des lemmes de simplification", "rewrites with simplification lemmas"),
    "simp_all": ("simplifie le but et toutes les hypothèses ensemble", "simplifies the goal and all hypotheses together"),
    "ring": ("prouve une égalité dans un anneau commutatif en développant", "proves an equality in a commutative "
                                                                            "ring by normalising both sides"),
    "ring_nf": ("met les expressions d'anneau sous forme normale", "puts ring expressions in normal form"),
    "field_simp": ("chasse les dénominateurs", "clears denominators"),
    "positivity": ("prouve qu'une expression est positive ou non nulle", "proves an expression is positive or nonzero"),
    "gcongr": ("compare deux expressions de même forme terme à terme", "compares two expressions of the same shape"),
    "exact": ("donne un terme qui a exactement le type du but", "gives a term whose type is exactly the goal"),
    "apply": ("applique un lemme et laisse ses hypothèses comme nouveaux buts",
              "applies a lemma, leaving its hypotheses as new goals"),
    "refine": ("applique un terme avec des trous qui deviennent des buts", "applies a term with holes that become goals"),
    "intro": ("introduit les variables et hypothèses du but", "introduces the goal's variables and hypotheses"),
    "intros": ("introduit toutes les variables et hypothèses", "introduces all variables and hypotheses"),
    "rintro": ("introduit et décompose en même temps", "introduces and destructures at once"),
    "rw": ("réécrit le but avec des égalités", "rewrites the goal with equalities"),
    "rewrite": ("réécrit le but avec des égalités", "rewrites the goal with equalities"),
    "nth_rewrite": ("réécrit une occurrence précise", "rewrites one chosen occurrence"),
    "induction": ("raisonne par récurrence", "reasons by induction"),
    "cases": ("distingue les cas d'une hypothèse ou d'un type inductif", "splits on the cases of a hypothesis or type"),
    "rcases": ("décompose une hypothèse (et, ou, il existe)", "destructures a hypothesis (and, or, exists)"),
    "obtain": ("extrait les composantes d'une hypothèse", "extracts the components of a hypothesis"),
    "use": ("fournit le témoin d'un « il existe »", "provides the witness of an existential"),
    "exists": ("fournit le témoin d'un « il existe »", "provides the witness of an existential"),
    "constructor": ("découpe le but selon son constructeur (et, ↔)", "splits the goal by its constructor (and, ↔)"),
    "calc": ("enchaîne des égalités ou inégalités pas à pas", "chains equalities or inequalities step by step"),
    "have": ("établit un résultat intermédiaire", "establishes an intermediate fact"),
    "show": ("précise la forme du but", "states the goal's form explicitly"),
    "aesop": ("recherche automatique de preuve par règles", "rule-based automatic proof search"),
    "decide": ("fait calculer la vérité de l'énoncé par le noyau de Lean", "lets Lean's kernel compute the truth of "
                                                                         "the statement"),
    "rfl": ("conclut par réflexivité (les deux côtés sont égaux par calcul)",
            "closes by reflexivity (both sides compute to the same value)"),
    "trivial": ("ferme les buts évidents", "closes trivial goals"),
    "unfold": ("déplie une définition", "unfolds a definition"),
    "subst": ("remplace une variable par sa valeur", "substitutes a variable by its value"),
    "by_contra": ("raisonne par l'absurde", "argues by contradiction"),
    "push_neg": ("pousse les négations vers l'intérieur", "pushes negations inwards"),
    "contradiction": ("trouve deux hypothèses contradictoires", "finds contradictory hypotheses"),
    "exfalso": ("remplace le but par False", "replaces the goal by False"),
    "specialize": ("applique une hypothèse générale à des valeurs", "instantiates a general hypothesis"),
    "ext": ("prouve une égalité de fonctions ou d'ensembles point par point",
            "proves an equality of functions or sets pointwise"),
    "funext": ("égalité de fonctions point par point", "equality of functions pointwise"),
    "congr": ("réduit une égalité à l'égalité des arguments", "reduces an equality to equal arguments"),
    "left": ("choisit le côté gauche d'un « ou »", "chooses the left side of an or"),
    "right": ("choisit le côté droit d'un « ou »", "chooses the right side of an or"),
    "split_ifs": ("distingue les cas des « si »", "splits on the if-then-else conditions"),
    "interval_cases": ("essaie toutes les valeurs d'une variable bornée", "tries every value of a bounded variable"),
    "fin_cases": ("essaie tous les éléments d'un type fini", "tries every element of a finite type"),
    "norm_cast": ("gère les conversions entre ℕ, ℤ, ℚ, ℝ", "handles casts between ℕ, ℤ, ℚ, ℝ"),
    "push_cast": ("pousse les conversions vers les feuilles", "pushes casts towards the leaves"),
    "exact_mod_cast": ("exact, aux conversions près", "exact, up to casts"),
    "tauto": ("logique propositionnelle", "propositional logic"),
    "symm": ("échange les deux côtés", "swaps both sides"),
    "convert": ("conclut avec un terme presque du bon type, laissant les différences",
                "closes with a term of nearly the right type, leaving the differences"),
    "first": ("essaie plusieurs tactiques dans l'ordre", "tries several tactics in order"),
    "all_goals": ("applique une tactique à tous les buts", "applies a tactic to every goal"),
    "repeat": ("répète une tactique tant qu'elle réussit", "repeats a tactic while it succeeds"),
    "native_decide": ("(refusé par Madalean)", "(refused by Madalean)"),
}


def _chain(g: dict, nid: str) -> list[str]:
    """Goal → … → nid along « uses » edges (shortest), [nid] when not reachable."""
    root = g["root"]
    prev: dict[str, str | None] = {root: None}
    queue = [root]
    while queue:
        x = queue.pop(0)
        if x == nid:
            break
        for y in uses_of(g, x):
            if y not in prev:
                prev[y] = x
                queue.append(y)
    if nid not in prev:
        return [nid]
    out, x = [], nid
    while x is not None:
        out.append(x)
        x = prev[x]
    return list(reversed(out))


def _subtree_uses(g: dict, nid: str) -> list[str]:
    out, stack, seen = [], [nid], set()
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
        stack += uses_of(g, x)
    return out


def explain(g: dict, nid: str | None = None, lang: str = "fr") -> dict:
    """A structured account of a node (default: the goal), built ONLY from what the graph recorded: the chosen path
    and why (recorded viability reasons and planner's « why »), the alternatives considered, the lemmas used and
    their status, the tactics found in the recorded proofs and what each does (fixed glossary), what failed and why,
    the bibliography (Mathlib constants written in the proofs, cited works with their recorded references, BibTeX).
    No model is involved, so nothing can be invented. `text` is the same account as Markdown."""
    L = _lang(lang)
    W = T[L]
    nid = nid or g["root"]
    if nid not in g["nodes"]:
        raise GraphError("not_found", 404)
    n = g["nodes"][nid]
    eff = effective(g, nid)
    sub = _subtree_uses(g, nid)
    chain = _chain(g, nid)

    def brief(x: str) -> dict:
        m = g["nodes"][x]
        e = effective(g, x)
        return {"node": x, "title": m["title"], "lean": m.get("lean", ""), "status": m["status"], "state": e["state"],
                "kind": m["kind"], "source": (m.get("source") or {}).get("kind", ""),
                "why": m.get("why", ""), "reason": reason_text(m.get("viability"), L)}
    path = [brief(x) for x in chain]
    lemmas = [brief(x) for x in sub if x != nid]
    alternatives = []
    for x in chain + sub:
        for t in g["nodes"][x].get("tracks") or []:
            if not t.get("active"):
                alternatives.append({"parent": x, "idea": t.get("idea", ""), "abandoned": t.get("abandoned"),
                                     "why": t.get("why", ""),
                                     "lemmas": [g["nodes"][y]["title"] for y in t.get("lemmas") or []
                                                if y in g["nodes"]]})
    failures = []
    for m in g["nodes"].values():
        if m["status"] in ("abandoned", "refuted") and (m["id"] in sub or not users_of(g, m["id"]) or
                                                        any(p in sub for p in users_of(g, m["id"]))):
            failures.append({"node": m["id"], "title": m["title"], "status": m["status"],
                             "reason": m.get("reason", ""), "attempts": int(m.get("attempts_n", 0))})
    proofs = [(x, g["nodes"][x].get("proof") or "") for x in sub if g["nodes"][x].get("proof")]
    tac_count: dict[str, int] = {}
    for _x, p in proofs:
        for t in tactics_of(p):
            tac_count[t] = tac_count.get(t, 0) + 1
    tactics = [{"name": t, "count": c,
                "description": TACTICS[t][0 if L == "fr" else 1] if t in TACTICS else ""}
               for t, c in sorted(tac_count.items(), key=lambda kv: (-kv[1], kv[0]))]
    mathlib: list[dict] = []
    for x in sub:
        m = g["nodes"][x]
        if m["status"] == "mathlib" and (m.get("source") or {}).get("name"):
            nm = m["source"]["name"]
            mathlib.append({"name": nm, "url": MATHLIB_DOC.format(name=nm), "how": "mathlib"})
    for _x, p in proofs:
        for nm in lean_constants(p):
            if not any(e["name"] == nm for e in mathlib):
                mathlib.append({"name": nm, "url": MATHLIB_DOC.format(name=nm), "how": "proof"})
    works = bibliography(g, sub)
    attempts = [{"node": x, **{k: a[k] for k in ("how", "ok", "error", "model", "t") if k in a}}
                for x in sub for a in g["nodes"][x].get("attempts") or []]
    out = {"node": nid, "title": n["title"], "lean": n.get("lean", ""), "status": n["status"], "state": eff["state"],
           "composed": eff["composed"], "conditional": eff["state"] == "conditional",
           "rests_on": [brief(x) for x in eff["rests_on"] if x in g["nodes"]],
           "path": path, "lemmas": lemmas, "alternatives": alternatives, "failures": failures, "tactics": tactics,
           "attempts": attempts[-30:], "proof": n.get("proof", ""),
           "bibliography": {"mathlib": mathlib, "works": works["items"], "bibtex": works["bibtex"]},
           "lang": L, "rev": g.get("rev", 0)}
    out["text"] = explanation_markdown(out)
    return out


def bibliography(g: dict, among: list[str] | None = None) -> dict:
    """Cited works of the graph (or of `among`) with stable BibTeX keys; only recorded references."""
    from . import biblio
    items, keys, chunks = [], set(), []
    for x in among if among is not None else list(g["nodes"]):
        m = g["nodes"].get(x)
        c = (m or {}).get("citation")
        if not c:
            continue
        item = {k: v for k, v in c.items() if k not in ("verified", "quote", "locator", "key")}
        item.setdefault("type", "article-journal")
        key = biblio.safe_key(c.get("key") or biblio.make_key(item, keys))
        if key in keys:
            continue
        keys.add(key)
        items.append({"key": key, "node": m["id"], "title": str(c.get("title") or ""), "verified": bool(c.get("verified")),
                      "quote": str(c.get("quote") or "")[:600], "locator": str(c.get("locator") or ""),
                      "reference": _short_cite(c), "doi": str(c.get("DOI") or ""), "url": str(c.get("URL") or ""),
                      "status": m["status"]})
        chunks.append(biblio.item_to_bibtex(item, key))
    return {"items": items, "bibtex": "\n".join(chunks)}


def explanation_markdown(e: dict) -> str:
    L = e["lang"]
    W = T[L]
    fr = L == "fr"
    lines = [f"## {'Explication' if fr else 'Explanation'} — {e['title']}", ""]
    state = W["composed"] if e["state"] == "verified" and e["composed"] else W.get(e["state"], e["state"])
    lines.append(f"**{'Statut' if fr else 'Status'} :** {state}" if fr else f"**Status:** {state}")
    if e["conditional"]:
        names = ", ".join(f"« {r['title']} »" if fr else f"“{r['title']}”" for r in e["rests_on"])
        lines += ["", ("**Conditionnel** — repose sur des résultats non prouvés en Lean : " if fr else
                       "**Conditional** — rests on results not proved in Lean: ") + names]
    if e["lean"]:
        lines += ["", "```lean", e["lean"].strip(), "```"]
    if len(e["path"]) > 1 or any(p["why"] or p["reason"] for p in e["path"]):
        lines += ["", f"### {'Piste choisie et pourquoi' if fr else 'Chosen path and why'}"]
        for p in e["path"]:
            why = "; ".join(x for x in (p["why"], p["reason"]) if x)
            lines.append(f"- {p['title']} ({W.get(p['state'], p['state'])})" + (f" — {why}" if why else ""))
    if e["alternatives"]:
        lines += ["", f"### {'Autres pistes envisagées' if fr else 'Alternatives considered'}"]
        for a in e["alternatives"]:
            tag = (" (abandonnée)" if fr else " (abandoned)") if a.get("abandoned") else ""
            lines.append(f"- {a['idea'] or '—'}{tag}" + (f" — {a['why']}" if a.get("why") else ""))
    if e["lemmas"]:
        lines += ["", f"### {'Lemmes' if fr else 'Lemmas'}"]
        for m in e["lemmas"]:
            src = {"mathlib": "Mathlib", "literature": "littérature" if fr else "literature",
                   "certificate": "certificat" if fr else "certificate"}.get(m["source"], "")
            lines.append(f"- {m['title']} — {W.get(m['state'], m['state'])}" + (f" ({src})" if src else ""))
    if e["tactics"]:
        lines += ["", f"### {'Tactiques employées' if fr else 'Tactics used'}"]
        for t in e["tactics"]:
            desc = t["description"] or ("(pas de description dans le glossaire de Madalean)" if fr else
                                        "(no description in Madalean's glossary)")
            lines.append(f"- `{t['name']}` — {desc}")
    if e["failures"]:
        lines += ["", f"### {'Ce qui a échoué' if fr else 'What failed'}"]
        for f in e["failures"]:
            lines.append(f"- {f['title']} — {W.get(f['status'], f['status'])}" + (f" : {f['reason']}" if fr and
                         f["reason"] else f": {f['reason']}" if f["reason"] else ""))
    bib = e["bibliography"]
    if bib["mathlib"] or bib["works"]:
        lines += ["", f"### {'Bibliographie' if fr else 'Bibliography'}"]
        for m in bib["mathlib"]:
            lines.append(f"- Mathlib : [`{m['name']}`]({m['url']})" if fr else f"- Mathlib: [`{m['name']}`]({m['url']})")
        for w in bib["works"]:
            ver = ("référence vérifiée" if w["verified"] else "référence NON vérifiée") if fr else \
                  ("verified reference" if w["verified"] else "UNVERIFIED reference")
            lines.append(f"- [{w['key']}] {w['reference']} ({ver})")
            if w["quote"]:
                lines.append(f"  > {w['quote']}")
    return "\n".join(lines).strip() + "\n"


def explanation_latex(e: dict) -> dict:
    """The account for the article: LaTeX with \\cite{key} for cited works, and the matching BibTeX."""
    def esc(s: str) -> str:
        return re.sub(r"([#$%&_{}~^\\])", lambda m: {"\\": r"\textbackslash{}", "~": r"\textasciitilde{}",
                                                    "^": r"\textasciicircum{}"}.get(m.group(1), "\\" + m.group(1)),
                      s or "")
    fr = e["lang"] == "fr"
    W = T[e["lang"]]
    out = [f"\\subsection*{{{esc(('Explication — ' if fr else 'Explanation — ') + e['title'])}}}"]
    state = W["composed"] if e["state"] == "verified" and e["composed"] else W.get(e["state"], e["state"])
    out.append(esc(("Statut : " if fr else "Status: ") + state) + ".")
    keys = {w["node"]: w["key"] for w in e["bibliography"]["works"]}
    if e["conditional"]:
        refs = ", ".join(esc(r["title"]) + (f"~\\cite{{{keys[r['node']]}}}" if r["node"] in keys else "")
                         for r in e["rests_on"])
        out.append(("\\textbf{Conditionnel} : repose sur " if fr else "\\textbf{Conditional}: rests on ") + refs + ".")
    if e["lemmas"]:
        out.append("\\begin{itemize}")
        for m in e["lemmas"]:
            cite = f"~\\cite{{{keys[m['node']]}}}" if m["node"] in keys else ""
            out.append(f"  \\item {esc(m['title'])}{cite} ({esc(W.get(m['state'], m['state']))})")
        out.append("\\end{itemize}")
    if e["tactics"]:
        out.append(("Tactiques : " if fr else "Tactics: ") + ", ".join(f"\\texttt{{{esc(t['name'])}}}"
                                                                     for t in e["tactics"]) + ".")
    if e["bibliography"]["mathlib"]:
        out.append("Mathlib : " + ", ".join(f"\\texttt{{{esc(m['name'])}}}" for m in e["bibliography"]["mathlib"]) +
                   ".")
    return {"latex": "\n".join(out) + "\n", "bibtex": e["bibliography"]["bibtex"]}


def record_text_tokens(e: dict) -> set[str]:
    """Every name the account may legitimately mention (for tests and audits): node titles, tactic names found in
    recorded proofs, constants in recorded proofs, recorded Mathlib names, citation keys."""
    toks: set[str] = set()
    for grp in ("path", "lemmas", "rests_on"):
        toks |= {x["title"] for x in e[grp]}
    toks |= {t["name"] for t in e["tactics"]}
    toks |= {m["name"] for m in e["bibliography"]["mathlib"]}
    toks |= {w["key"] for w in e["bibliography"]["works"]}
    return toks


# ---------------------------------------------------------------- public view
def public(g: dict, lang: str = "fr") -> dict:
    out = copy.deepcopy(g)
    out.pop("forgotten", None)
    for nid, n in out["nodes"].items():
        e = effective(g, nid)
        n["state"] = e["state"]
        n["composed"] = e["composed"]
        n["rests_on"] = e["rests_on"]
        n["reason_text"] = reason_text(n.get("viability"), lang)
        n["uses"] = uses_of(g, nid)
        n["used_by"] = users_of(g, nid)
        n["proof"] = (n.get("proof") or "")[:4000]
    counts: dict[str, int] = {}
    for n in out["nodes"].values():
        counts[n["state"]] = counts.get(n["state"], 0) + 1
    out["counts"] = counts
    out["log"] = out.get("log", [])[-40:]
    return out
