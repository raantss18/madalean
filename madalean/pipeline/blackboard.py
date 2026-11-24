"""The blackboard of one target (S-BI, D67): what the attempts of any model left behind, as structured facts.

- `lemmas`: intermediate `have`s of REJECTED attempts that Lean accepted alone, afresh, strictly (`harvest`), and the
  proved parts of a split. They are offered to the next attempts (name + statement; the code is added when a proof
  uses the name) and become verified nodes of the problem graph. Nothing else here is ever called true.
- `goals`: goals Lean left open; `names`: names this Mathlib does not know; `approaches`: what failed and how often.
- progress: strong = a new accepted lemma; weak = a new kind of error or a new open goal. `sorry` and other forbidden
  constructs are no progress, whatever else the attempt contains.

Bounded everywhere, kept in the dossier (`extra.board`) for the same statement, workspace and Mathlib only."""
from __future__ import annotations

import hashlib
import re

from .. import leancheck, names as namesmod
from ..logs import get
from . import decompose as DC, probes as P

log = get("pipeline.blackboard")
MAX_LEMMAS, MAX_GOALS, MAX_NAMES, MAX_APPROACHES = 16, 8, 20, 16
MAX_NEW_PER_HARVEST = 4        # candidates checked strictly per harvest
MAX_CODES = 3                  # rejected codes read per harvest
MAX_LEMMA_CHARS = 2500
VIEW_CHARS = 2600
HARVEST_TIMEOUT = 120
_GOAL = re.compile(r"⊢\s*(.+?)(?=\n\S|\n\n|\Z)", re.S)
_HAVE = re.compile(r"have\b[ \t]*(?P<name>[^\W\d][\w'₀-₉]*)?(?P<rest>.*)", re.S)
_WORD = re.compile(r"[^\W\d][\w'₀-₉]*")
_CHEAT = re.compile(r"forbidden construct|uses ['`]?sorry|sorryAx")


def error_kind(feedback: str) -> str:
    from ..research.lessons import error_pattern
    m = re.search(r"Error Message:\s*(.+)", feedback or "")
    return error_pattern(m.group(1) if m else (feedback or ""))[:140]


def open_goals(feedback: str) -> list[str]:
    return list(dict.fromkeys(" ".join(g.split())[:240] for g in _GOAL.findall(feedback or "")))[:4]


# ---------------------------------------------------------------- reading a rejected proof
def _find(s: str, what: str) -> int:
    """First top-level `:` (not `:=`) or `:=`."""
    depth = 0
    for i, ch in enumerate(s):
        depth += (ch in DC._OPEN) - (ch in DC._CLOSE)
        if depth == 0 and ch == ":" and (s[i:i + 2] == ":=") == (what == ":="):
            return i
    return -1


def blocks_of(body: str) -> list[str]:
    """Top-level tactic blocks of a proof body (a line of the base indentation and its deeper lines)."""
    lines = [ln.rstrip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return []
    base = min(len(ln) - len(ln.lstrip()) for ln in lines)
    out: list[list[str]] = []
    for ln in lines:
        if len(ln) - len(ln.lstrip()) == base or not out:
            out.append([])
        out[-1].append(ln[base:])
    return ["\n".join(b) for b in out]


def candidates(statement: str, code: str) -> list[dict]:
    """Standalone declarations to try for the `have`s of `code`: [{name, head, tactic}] (unchecked text)."""
    sig = P.split_statement(statement)
    if sig is None:
        return []
    text = leancheck.remove_comments(code)
    at = [m for m in re.finditer(r"(?:^|\s)theorem\s+([^\s:({\[⦃]+).*?:=\s*by\b", text, re.S) if m.group(1) == sig.name]
    if not at:
        return []
    blocks = blocks_of(text[at[-1].end():])
    binders = sig.binders
    m = re.fullmatch(r"intros?\s+((?:[^\W\d][\w'₀-₉]*\s*)+)", blocks[0].strip()) if blocks else None
    if m:
        names = m.group(1).split()
        binders, _c, got = DC.peel(sig.binders, sig.concl, names)
        if got != names:
            return []
    hyps = {" ".join(t.split()) for _n, t in P.explicit_binders(binders)}
    out: list[dict] = []
    prev: list[tuple[str, str]] = []
    for b in blocks:
        m = _HAVE.fullmatch(b)
        if not m or len(b) > MAX_LEMMA_CHARS:
            continue
        rest, hname = m.group("rest"), m.group("name") or "this"
        j, k = _find(rest, ":"), _find(rest, ":=")
        if j < 0 or k < j:
            continue
        local, typ = rest[:j].strip(), " ".join(rest[j + 1:k].split())
        if not typ or typ in hyps or typ == "True" or leancheck.forbidden_reasons(b) or leancheck.exec_risks(b):
            continue
        need: list[str] = []
        words = set(_WORD.findall(b))
        for pn, pb in reversed(prev):               # the earlier `have`s it really mentions
            if pn in words:
                need.insert(0, pb)
                words |= set(_WORD.findall(pb))
        head = f"{binders} : {f'∀ {local}, {typ}' if local else typ}".strip()
        out.append({"name": "mad_" + hashlib.sha1(" ".join(head.split()).encode()).hexdigest()[:8], "head": head,
                    "tactic": "\n".join(need + [b, f"exact {hname}"])})
        prev.append((hname, b))
    return out


# ---------------------------------------------------------------- the board
class Board:
    def __init__(self, statement: str, env: dict | None = None):
        self.statement = statement
        self.env = {k: str((env or {}).get(k, "")) for k in ("workspace", "lean", "mathlib")}
        self.lemmas: dict[str, dict] = {}          # name → {name, head, code, model}
        self.goals: list[str] = []
        self.names: list[str] = []
        self.approaches: dict[str, dict] = {}      # key → {how, why, n, models}
        self.kinds: set[str] = set()
        self.strong = self.weak = 0
        self.cheats = 0
        self.cut = ""                              # the split tried on this target (and | iff | cases | search)
        self._told: set[str] = set()
        self._cheated: set[str] = set()
        self._codes: list[tuple[str, str]] = []
        self._tried: set[str] = set()

    # -- persistence
    @staticmethod
    def key_of(statement: str) -> str:
        return hashlib.sha1(" ".join(leancheck.remove_comments(statement).split()).encode()).hexdigest()[:20]

    @classmethod
    def load(cls, d, statement: str, env: dict | None) -> "Board":
        b = cls(statement, env)
        x = d.extra.get("board") if isinstance(d.extra, dict) else None
        try:
            if isinstance(x, dict) and x.get("key") == cls.key_of(statement) and x.get("env") == b.env:
                b.lemmas = {str(m["name"]): {k: str(m.get(k, "")) for k in ("name", "head", "code", "model")}
                            for m in (x.get("lemmas") or [])[:MAX_LEMMAS]}
                b.goals = [str(g) for g in x.get("goals") or []][-MAX_GOALS:]
                b.names = [str(g) for g in x.get("names") or []][-MAX_NAMES:]
                b.approaches = {str(k): {"how": str(v.get("how", "")), "why": str(v.get("why", "")),
                                         "n": int(v.get("n", 1)), "models": [str(y) for y in v.get("models") or []][:6]}
                                for k, v in list((x.get("approaches") or {}).items())[-MAX_APPROACHES:]}
                b.kinds = {v["why"] for v in b.approaches.values()}
        except (TypeError, ValueError, KeyError, AttributeError):
            return cls(statement, env)
        return b

    def store(self, d) -> None:
        if self.lemmas or self.goals or self.names or self.approaches:
            d.extra["board"] = {"key": self.key_of(self.statement), "env": self.env,
                                "lemmas": list(self.lemmas.values()), "goals": list(self.goals),
                                "names": list(self.names), "approaches": self.approaches}

    # -- writing
    def record(self, code: str, feedback: str, model: str = "") -> None:
        """A proof Lean rejected."""
        if leancheck.forbidden_reasons(code or "") or _CHEAT.search(feedback or ""):
            self.cheat(model)
            return
        kind = error_kind(feedback)
        if not kind:
            return
        from ..research.proofgraph import tactics_of
        goals = open_goals(feedback)
        if kind not in self.kinds or any(g not in self.goals for g in goals):
            self.weak += 1
        self.kinds.add(kind)
        for g in goals:
            if g in self.goals:
                self.goals.remove(g)
            self.goals.append(g)
        del self.goals[:-MAX_GOALS]
        self.names += [n for n in namesmod.missing_names(feedback) if n not in self.names]
        del self.names[:-MAX_NAMES]
        how = ", ".join(tactics_of(code)[:5])
        k = f"{kind}|{how}"
        a = self.approaches.setdefault(k, {"how": how, "why": kind, "n": 0, "models": []})
        a["n"] += 1
        if model and model not in a["models"]:
            a["models"] = (a["models"] + [model])[-6:]
        if len(self.approaches) > MAX_APPROACHES:     # the least repeated of the others goes
            self.approaches.pop(min((x for x in self.approaches if x != k), key=lambda x: self.approaches[x]["n"]))
        if code and all(code != c for c, _m in self._codes):
            self._codes = (self._codes + [(code, model)])[-12:]

    def cheat(self, model: str = "") -> None:
        self.cheats += 1
        self._cheated.add(model)

    def add_lemma(self, name: str, head: str, code: str, model: str = "") -> bool:
        """`code`: a declaration that a FRESH strict Lean check has just accepted."""
        if name in self.lemmas or len(self.lemmas) >= MAX_LEMMAS:
            return False
        self.lemmas[name] = {"name": name, "head": head, "code": code.strip(), "model": model}
        self.strong += 1
        return True

    def mark(self) -> tuple[int, int]:
        return self.strong, self.weak

    async def harvest(self, io, ws, timeout_s: int = HARVEST_TIMEOUT) -> list[dict]:
        """Read the rejected proofs, let Lean judge their `have`s alone (one batch, then each survivor strictly)."""
        codes, self._codes = self._codes[-MAX_CODES:], []
        sig = P.split_statement(self.statement)
        if sig is None or not codes or len(self.lemmas) >= MAX_LEMMAS:
            return []
        probes: list[P.Probe] = []
        for code, model in reversed(codes):
            for c in candidates(self.statement, code):
                if c["name"] in self._tried or c["name"] in self.lemmas or len(probes) >= 2 * MAX_NEW_PER_HARVEST:
                    continue
                probes.append(P.Probe(c["name"], P.decl(c["name"], c["head"], c["tactic"], 200000), "have",
                                      {"head": c["head"], "model": model}))
                self._tried.add(c["name"])
        new: list[dict] = []
        try:
            await P.run_batch(io, ws, sig.preamble, probes, timeout_s)
            for p in [x for x in probes if x.ok][:MAX_NEW_PER_HARVEST]:
                r = await P.strict(io, ws, sig.preamble, p, timeout_s)
                if r.verdict.ok and self.add_lemma(p.name, p.meta["head"], p.code, p.meta["model"]):
                    new.append(self.lemmas[p.name])
        except Exception as e:  # noqa: BLE001 (a help, never a failure of the proof stage)
            log.warning("harvest: %s", e)
        return new

    # -- use
    def include(self, code: str) -> str:
        """`code` with the accepted lemmas it names (and does not declare) written above it."""
        have = leancheck.declared_names(code)
        need = [m["code"] for n, m in self.lemmas.items()
                if n not in have and re.search(rf"(?<![\w.']){re.escape(n)}(?![\w'])", code)]
        m = re.search(r"(?m)^\s*(?:theorem|lemma)\s", code) if need else None
        if m is None:
            return code
        i = m.start()
        return code[:i] + "\n" + "\n\n".join(need) + "\n\n" + code[i:].lstrip("\n")

    def assemble(self, statement: str, code: str) -> str:
        """`leancheck.assemble_proof`, with the accepted lemmas the proof uses."""
        full = leancheck.assemble_proof(statement, code)
        more = self.include(full)
        return full if more == full else leancheck.assemble_proof(statement, more)

    def view(self, model: str = "") -> str:
        """The compact, deduplicated record for the next attempt ("" when there is nothing)."""
        out: list[str] = []
        if self.lemmas:
            out.append("Lemmas about this theorem already ACCEPTED by Lean (in scope of your proof, use them by name):")
            out += [f"theorem {m['name']} {m['head']}" for m in list(self.lemmas.values())[-8:]]
        if self.goals:
            out.append("Goals on which earlier attempts stopped: " + "; ".join(f"⊢ {g}" for g in self.goals[-3:]))
        if self.names:
            out.append("Names that do not exist here: " + ", ".join(f"`{n}`" for n in self.names[-10:]))
        bad = sorted(self.approaches.values(), key=lambda a: -a["n"])[:4]
        if bad:
            out.append("Already failed (do something else): " + "; ".join(
                f"{a['how'] or 'proof'} — {a['why'][:100]}" + (f" (×{a['n']})" if a["n"] > 1 else "") for a in bad))
        if model in self._cheated and model not in self._told:
            self._told.add(model)
            out.append("An earlier answer contained `sorry` or another forbidden construct: it counts for nothing.")
        return ("Shared record of the earlier attempts on this exact theorem:\n" + "\n".join(out))[:VIEW_CHARS] \
            if out else ""


def mirror(graphs, did: str, board: Board) -> dict[str, str]:
    """Accepted lemmas as verified nodes of the dossier's problem graph; {lemma name: node id}. Never raises."""
    out: dict[str, str] = {}
    if graphs is None or not board.lemmas:
        return out
    try:
        from ..research import proofgraph as G
        g = graphs.ensure(did)
        for m in board.lemmas.values():
            node, _c = G.add_node(g, G.new_node(
                "lemma", m["head"].rsplit(" : ", 1)[-1][:120], lean=f"theorem {m['name']} {m['head']} := by sorry",
                source={"kind": "attempt", "model": m["model"]}))
            if node["status"] == "open" and not node.get("proof"):
                node["proof"], node["tactics"] = m["code"][:G.MAX_PROOF_CHARS], G.tactics_of(m["code"])
                G.set_status(g, node["id"], "proved", "", self_contained=True)
            out[m["name"]] = node["id"]
        graphs.save(did)
        graphs.publish(did)
    except Exception:  # noqa: BLE001
        log.exception("mirror")
    return out
