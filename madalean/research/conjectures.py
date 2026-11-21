"""Conjecture workshop (ARCHITECTURE §14) — session S-G.

A conjecture is a dossier of kind `conjecture`; its workshop data live in `dossier.extra["conjecture"]` (round-
tripped by the dossier store): the precise natural-language statement, the motivation, where it came from, the
experiments (code drafted by a model, shown to the user, run only once approved), and an append-only, hash-chained
evidence log. Status, recomputed from the evidence and the dossier:

    proposed → tested-n-cases → lean-statement → proved            refuted (a re-verified counter-example)

`proved` only comes from the normal pipeline (the dossier's current proof, strict Lean verdict); promotion to a
theorem dossier keeps the whole history. Testing before believing:
 (a) experiments in Sage / Python through `sagebridge` (approval required unless the host enabled
     `experiments_auto`);
 (b) small cases in Lean: `example` instances of the statement closed by norm_num / decide / simp / omega, plus an
     optional bounded `decide` over `∀ n < K`;
 (c) counter-example search: a witness reported by an experiment is re-verified independently (the predicate alone
     in a FRESH kernel, and in Lean `¬ statement` closed at the witness when the statement is formalised) before
     the status becomes `refuted`;
 (d) literature check through the sources session's `litsearch` when it is importable."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid

from .. import leancheck
from ..i18n import msg

KEY = "conjecture"
STATUSES = ("proposed", "tested-n-cases", "lean-statement", "proved", "refuted")
TACTICS = "first | (norm_num; done) | decide | (simp; done) | omega"
MARK = "[madalean:conjectures]"
STOP = {"the", "a", "an", "of", "is", "are", "be", "for", "all", "every", "any", "and", "or", "then", "that", "if",
        "to", "in", "on", "with", "by", "let", "le", "la", "les", "de", "des", "du", "un", "une", "est", "sont",
        "pour", "tout", "tous", "et", "ou", "alors", "que", "si", "dans", "avec", "soit", "on", "it", "its",
        "number", "numbers", "elements", "element", "nombre", "nombres", "entier", "entiers", "integer", "integers"}


class ConjectureError(Exception):
    def __init__(self, kind: str, status: int = 400, key: str = "", **params):
        super().__init__(kind)
        self.kind, self.status, self.key, self.params = kind, status, key, params


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ0-9]+", (text or "").lower()) if w not in STOP and len(w) > 1}


def similarity(a: str, b: str) -> float:
    x, y = words(a), words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


# ---------------------------------------------------------------- data
def data_of(d) -> dict:
    c = d.extra.get(KEY)
    if not isinstance(c, dict):
        c = {}
        d.extra[KEY] = c
    c.setdefault("statement_nl", d.problem or d.title)
    c.setdefault("motivation", "")
    c.setdefault("origin", {})
    c.setdefault("evidence", [])
    c.setdefault("experiments", {})
    c.setdefault("counterexample", None)
    c.setdefault("promoted", None)
    c.setdefault("created", time.time())
    return c


def is_conjecture(d) -> bool:
    return d.kind == "conjecture" or isinstance(d.extra.get(KEY), dict)


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def add_evidence(d, kind: str, summary: dict, *, verdict: str = "", code: str = "", language: str = "",
                 output: str = "", data: dict | None = None, model: str = "", device: str = "") -> dict:
    """Append one immutable entry (timestamped, chained to the previous one by its hash)."""
    c = data_of(d)
    prev = c["evidence"][-1]["hash"] if c["evidence"] else ""
    e = {"id": "e-" + uuid.uuid4().hex[:10], "t": time.time(), "kind": kind, "summary": summary, "verdict": verdict,
         "code": code, "language": language, "output": output[-20000:], "data": data or {}, "model": model,
         "device": device, "prev": prev}
    e["hash"] = _hash(e)
    c["evidence"].append(e)
    d.touch()
    return e


def chain_ok(d) -> bool:
    prev = ""
    for e in data_of(d)["evidence"]:
        if e.get("prev") != prev or _hash(e) != e.get("hash"):
            return False
        prev = e["hash"]
    return True


def cases_tested(d) -> int:
    n = 0
    for e in data_of(d)["evidence"]:
        if e["kind"] == "lean_cases":
            n += int(e["data"].get("proved", 0))
        elif e["kind"] == "experiment" and e["verdict"] == "holds":
            n += int(e["data"].get("cases") or 0)
    return n


def status(d) -> str:
    c = data_of(d)
    if d.proof_is_current:
        return "proved"
    if c.get("counterexample") and c["counterexample"].get("verified"):
        return "refuted"
    if d.statement and d.statements[d.cur_statement].ok:
        return "lean-statement"
    if cases_tested(d) > 0:
        return "tested-n-cases"
    return "proposed"


def public(d) -> dict:
    c = data_of(d)
    exps = sorted(c["experiments"].values(), key=lambda e: e["created"])
    return {"id": d.id, "title": d.title, "project_id": d.project_id, "kind": d.kind, "status": status(d),
            "cases_tested": cases_tested(d), "statement_nl": c["statement_nl"], "motivation": c["motivation"],
            "origin": c["origin"], "lean_statement": d.statement, "statement_ok": bool(d.statement) and
            d.statements[d.cur_statement].ok, "proved": d.proof_is_current, "counterexample": c["counterexample"],
            "promoted": c["promoted"], "evidence": c["evidence"], "experiments": exps, "chain_ok": chain_ok(d),
            "dossier_status": d.status, "updated": d.updated}


# ---------------------------------------------------------------- Lean statement → Prop, instances, negation
def split_signature(statement: str) -> tuple[list[dict], str]:
    """Binders and conclusion of the target theorem of a prepared statement (`theorem n binders : concl := by sorry`)."""
    src = leancheck.remove_comments(statement)
    m = list(re.finditer(r"(?m)^\s*theorem\s+([^\s:({\[⦃]+)", src))
    if not m:
        raise ConjectureError("no_statement", 409)
    rest = src[m[-1].end():]
    rest = re.split(r":=\s*by\s+sorry|:=\s*sorry", rest)[0]
    rest = rest.rsplit(":=", 1)[0] if ":=" in rest and "by sorry" not in rest else rest
    binders, i, depth = [], 0, 0
    close = {"(": ")", "{": "}", "[": "]", "⦃": "⦄"}
    while i < len(rest):
        ch = rest[i]
        if ch.isspace():
            i += 1
            continue
        if ch in close:
            j, depth = i, 0
            while j < len(rest):
                if rest[j] in close:
                    depth += 1
                elif rest[j] in close.values():
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = rest[i + 1:j]
            kind = {"(": "explicit", "{": "implicit", "[": "inst", "⦃": "implicit"}[ch]
            names, _, typ = inner.partition(":")
            if kind == "inst" and not typ:
                names, typ = "", inner
            for nm in (names.split() or [""]):
                binders.append({"name": nm, "type": typ.strip(), "kind": kind, "text": ch + inner + close[ch]})
            i = j + 1
            continue
        if ch == ":":
            return binders, rest[i + 1:].strip()
        raise ConjectureError("unsupported_statement", 422)
    raise ConjectureError("unsupported_statement", 422)


def as_prop(statement: str) -> str:
    binders, concl = split_signature(statement)
    if not binders:
        return concl
    groups = " ".join(b["text"] for b in _dedupe(binders))
    return f"∀ {groups}, {concl}"


def _dedupe(binders: list[dict]) -> list[dict]:
    out, seen = [], set()
    for b in binders:
        if b["text"] not in seen:
            seen.add(b["text"])
            out.append(b)
    return out


def lean_value(v) -> str:
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return f"({v})" if v < 0 else str(v)
    s = str(v).strip()
    if not re.fullmatch(r"[\w\s+\-*/^().,\[\]#'⟨⟩]{1,200}", s):
        raise ConjectureError("bad_witness", 422)
    return f"({s})"


def value_binders(statement: str, witness: dict) -> list[dict]:
    binders, _ = split_signature(statement)
    return [b for b in binders if b["kind"] == "explicit" and b["name"] in witness]


def header_of(statement: str) -> str:
    src = statement
    m = list(re.finditer(r"(?m)^\s*theorem\s", src))
    return src[:m[-1].start()] if m else leancheck.GOEDEL_HEADER


def instance_file(statement: str, cases: list[dict], bounded: int = 0) -> tuple[str, list[dict]]:
    """Lean file with one `example` per case (and optionally a bounded `decide`). Returns (code, spans) where
    spans[i] = {case, start, end} (1-based line range of each example)."""
    binders, concl = split_signature(statement)
    lines = header_of(statement).rstrip("\n").split("\n") + [""]
    spans = []
    for case in cases:
        vals = [b for b in binders if b["kind"] == "explicit" and b["name"] in case]
        if not vals:
            continue
        rest = [b for b in binders if b not in vals]
        lam = " ".join(f"({b['name']} : {b['type']})" for b in vals)
        body = (f"∀ {' '.join(b['text'] for b in _dedupe(rest))}, {concl}" if rest else concl)
        args = " ".join(lean_value(case[b["name"]]) for b in vals)
        start = len(lines) + 1
        lines += [f"-- case {json.dumps(case, ensure_ascii=False)}",
                  f"example : (fun {lam} => {body}) {args} := by", f"  {TACTICS}", ""]
        spans.append({"case": case, "start": start, "end": len(lines)})
    if bounded > 0:
        vals = [b for b in binders if b["kind"] == "explicit" and b["type"] in ("ℕ", "Nat")]
        if len(vals) == 1 and all(b["kind"] != "explicit" or b is vals[0] for b in binders):
            v = vals[0]
            start = len(lines) + 1
            lines += [f"-- bounded: all {v['name']} < {bounded}",
                      f"example : ∀ {v['name']} : ℕ, {v['name']} < {int(bounded)} → {concl} := by", "  decide", ""]
            spans.append({"case": {"bounded": int(bounded)}, "start": start, "end": len(lines)})
    return "\n".join(lines) + "\n", spans


def negation_file(statement: str, witness: dict) -> str:
    """`example : ¬ (∀ binders, concl)` closed at the witness (Lean re-verification of a counter-example)."""
    binders, concl = split_signature(statement)
    prop = as_prop(statement)
    args = []
    for b in binders:
        if b["kind"] != "explicit":
            continue
        if b["name"] in witness:
            args.append(lean_value(witness[b["name"]]))
        else:
            args.append("(by first | norm_num | decide | omega)")
    head = header_of(statement).rstrip("\n")
    return (f"{head}\n\nexample : ¬ ({prop}) := by\n  intro h\n  have hw := h {' '.join(args)}\n  revert hw\n"
            f"  {TACTICS}\n")


def results_by_span(check: dict, spans: list[dict]) -> list[dict]:
    out = []
    for sp in spans:
        errs = [e for e in check.get("errors", []) if sp["start"] <= e["line"] <= sp["end"]]
        out.append({"case": sp["case"], "proved": not errs and not check.get("timed_out") and
                    not check.get("infra_error"), "errors": [e["text"][:400] for e in errs]})
    return out


# ---------------------------------------------------------------- prompts
def generation_messages(context: str, n: int, lang: str) -> list[dict]:
    language = "French" if lang == "fr" else "English"
    return [{"role": "user", "content": (
        f"{MARK} task=generate\nYou are a research mathematician. From the research context below (notes, results "
        f"already proved, sources), propose up to {n} NEW conjectures worth testing. For each one give:\n"
        "- statement: ONE precise, self-contained mathematical statement (every object with its type, every "
        "hypothesis, quantifiers explicit), in " + language + ";\n"
        "- motivation: why it is plausible and interesting (which item of the context suggests it), in " + language +
        ";\n- lean: an optional Lean 4 + Mathlib statement `theorem name … := by sorry` (omit when unsure);\n"
        "- test: how to test it numerically (which variables, which range).\n"
        "Do not restate results that are already in the context or are standard textbook theorems. Answer with a "
        "JSON array only: [{\"statement\":…, \"motivation\":…, \"lean\":…, \"test\":…}].\n\nCONTEXT:\n" + context)}]


def experiment_messages(c: dict, lean: str, kind: str, language: str) -> list[dict]:
    lang = "SageMath" if language == "sage" else "Python 3 (standard library only)"
    goal = ("search for a counter-example as efficiently as possible (enumerate small cases, then random cases)"
            if kind == "counterexample" else "test the statement on as many small cases as reasonable")
    return [{"role": "user", "content": (
        f"{MARK} task=experiment language={language}\nWrite {lang} code to {goal} for this conjecture:\n"
        f"{c['statement_nl']}\n" + (f"Lean statement:\n```lean\n{lean}\n```\n" if lean else "") +
        "Rules: two parts. First part starts with the line `# PREDICATE` and defines `holds(...)` returning True "
        "when the statement holds for the given values (keyword parameters named like the variables of the "
        "statement). Second part starts with `# SEARCH`, loops over cases calling holds, stops at the first "
        "failure and calls `report(\"counterexample\", witness={...}, cases=k)`; if no failure, calls "
        "`report(\"holds\", cases=k)`. `report` is provided. No file, network or shell access; at most 30 seconds. "
        "Answer with one fenced code block only.")}]


def parse_proposals(text: str) -> list[dict]:
    text = leancheck.clean_model_text(text)
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for it in arr if isinstance(arr, list) else []:
        if not isinstance(it, dict) or not str(it.get("statement", "")).strip():
            continue
        out.append({"statement": str(it["statement"]).strip()[:3000],
                    "motivation": str(it.get("motivation", "")).strip()[:3000],
                    "lean": str(it.get("lean") or "").strip()[:20000],
                    "test": str(it.get("test", "")).strip()[:1000]})
    return out


def parse_experiment(text: str) -> tuple[str, str] | None:
    """(predicate code, full code) from a model answer."""
    text = leancheck.clean_model_text(text)
    blocks = re.findall(r"```(?:[\w+-]*)\n(.*?)```", text, re.S)
    code = max(blocks, key=len) if blocks else text
    if "# PREDICATE" not in code or "# SEARCH" not in code or "def holds" not in code:
        return None
    pred = code.split("# SEARCH", 1)[0]
    return pred.strip() + "\n", code.strip() + "\n"


def context_text(ctx, project_id: str, note_ids: list[str], dossier_ids: list[str], library: list[str],
                 source_keys: list[str], notes_store) -> tuple[str, dict]:
    parts, origin = [], {"notes": [], "dossiers": [], "library": [], "sources": []}
    for nid in note_ids[:20]:
        n = notes_store.get(nid, include_deleted=False) if notes_store else None
        if n is not None:
            parts.append(f"## Note: {n.title}\n{n.body[:6000]}")
            origin["notes"].append(n.id)
    for did in dossier_ids[:20]:
        d = ctx.repo.get(did)
        if d is not None:
            st = "proved in Lean" if d.proof_is_current else ("conjecture" if d.kind == "conjecture" else "open")
            parts.append(f"## {d.kind} ({st}): {d.title}\n{d.understood or d.problem}\n```lean\n{d.statement}\n```")
            origin["dossiers"].append(d.id)
    for name in library[:20]:
        e = ctx.library.get(name)
        if e is not None:
            parts.append(f"## Proved result {e.name}: {e.title}\n{e.statement}")
            origin["library"].append(e.name)
    if source_keys:
        try:
            from . import sources as src_mod          # session S-E (optional)
            for k in source_keys[:10]:
                summ = None
                for fn in ("summary", "get_summary", "source_summary"):
                    f = getattr(src_mod, fn, None)
                    if callable(f):
                        try:
                            summ = f(ctx, project_id, k) if f.__code__.co_argcount >= 3 else f(k)
                        except Exception:  # noqa: BLE001
                            summ = None
                        break
                if summ:
                    parts.append(f"## Source [@{k}]\n{str(summ)[:4000]}")
                    origin["sources"].append(k)
        except Exception:  # noqa: BLE001 (S-E absent: sources are simply not used)
            pass
    return "\n\n".join(parts) or "(no context selected)", origin


async def filter_known(ctx, project_id: str, workspace: str, proposals: list[dict]) -> tuple[list[dict], list[dict]]:
    """Drop duplicates (other proposals, dossiers of the project, library) and restatements of known results
    (Mathlib retriever). Returns (kept, filtered with reason + match)."""
    kept, filtered = [], []
    existing = [(d.title + " " + (d.understood or d.problem or "") + " " + str(data_of(d)["statement_nl"]
                                                                              if is_conjecture(d) else ""), d)
                for d in ctx.repo.list(project_id)]
    for p in proposals:
        s = p["statement"]
        reason = None
        for k in kept:
            if similarity(s, k["statement"]) >= 0.7:
                reason = {"reason": "duplicate_proposal", "match": k["statement"][:200]}
        if reason is None:
            for text, d in existing:
                if similarity(s, text) >= 0.6:
                    reason = {"reason": "duplicate_dossier", "match": d.title, "dossier_id": d.id}
                    break
        if reason is None:
            for e in ctx.library.entries:
                if similarity(s, e.title + " " + e.statement) >= 0.6:
                    reason = {"reason": "known_library", "match": e.name}
                    break
        if reason is None and ctx.retriever is not None and workspace:
            try:
                hits = await ctx.retriever.search(workspace, s, 5)
            except Exception:  # noqa: BLE001
                hits = []
            for h in hits or []:
                if similarity(s, f"{h.get('doc', '')} {h.get('name', '')}".replace(".", " ").replace("_", " ")) >= 0.5:
                    reason = {"reason": "known_mathlib", "match": h.get("name", "")}
                    break
        if reason is None:
            kept.append(p)
        else:
            filtered.append({**p, **reason})
    return kept, filtered


# ---------------------------------------------------------------- workshop (server side)
class Workshop:
    def __init__(self, ctx, bridge, notes_store=None):
        self.ctx, self.bridge, self.notes = ctx, bridge, notes_store
        self.locks: dict[str, asyncio.Lock] = {}
        self.running: dict[str, asyncio.Task] = {}

    def lock(self, did: str) -> asyncio.Lock:
        return self.locks.setdefault(did, asyncio.Lock())

    def publish(self, d) -> None:
        self.ctx.publish("conjecture.updated", {"conjecture": public(d)})

    async def save(self, d) -> None:
        await self.ctx.repo.save(d)
        self.publish(d)

    def get(self, did: str):
        d = self.ctx.repo.get(did)
        if d is None or not is_conjecture(d):
            raise ConjectureError("not_found", 404)
        return d

    async def _complete(self, role: str, messages: list[dict], mode: str, owner: str, max_tokens: int = 3000):
        from ..server.helpers import complete_once
        return await complete_once(self.ctx, role, messages, mode, owner=owner, max_tokens=max_tokens, temperature=0.6)

    # -- generation
    async def generate(self, project_id: str, *, note_ids=(), dossier_ids=(), library=(), source_keys=(),
                       n: int = 5, mode: str | None = None) -> dict:
        from ..i18n import language
        mode = mode or self.ctx.settings.mode
        text, origin = context_text(self.ctx, project_id, list(note_ids), list(dossier_ids), list(library),
                                    list(source_keys), self.notes)
        c = await self._complete("assistant", generation_messages(text, max(1, min(int(n), 12)), language()), mode,
                                 owner=f"conj-gen-{project_id}", max_tokens=4000)
        props = parse_proposals(c.text)
        p = self.ctx.projects.get(project_id)
        ws = (p.workspace if p is not None else "") or self.ctx.settings.workspace
        kept, filtered = await filter_known(self.ctx, project_id, ws, props)
        for k in kept:
            k["origin"] = origin
        return {"proposals": kept, "filtered": filtered, "model": c.model.key}

    async def create(self, project_id: str, statement: str, *, motivation: str = "", lean: str = "",
                     title: str = "", origin: dict | None = None, model: str = "", device: str = "") -> object:
        statement = (statement or "").strip()
        if not statement:
            raise ConjectureError("empty")
        d = self.ctx.repo.new(statement, (self.ctx.projects.get(project_id).workspace
                                          if self.ctx.projects.get(project_id) else "") or self.ctx.settings.workspace,
                              title[:200] or "")
        d.kind = "conjecture"
        if project_id and self.ctx.projects.get(project_id) is not None:
            d.project_id = project_id
        c = data_of(d)
        c["statement_nl"], c["motivation"], c["origin"] = statement[:5000], motivation[:5000], origin or {}
        d.add_event("user", statement, stage="auto")
        add_evidence(d, "created", msg("Conjecture proposée."), data={"motivation": motivation[:2000]}, model=model,
                     device=device)
        if lean.strip():
            await self.set_lean(d, lean, save=False)
        await self.save(d)
        return d

    async def set_lean(self, d, lean: str, save: bool = True) -> dict | None:
        st = leancheck.prepare_statement(lean)
        old = leancheck.theorem_name(st)
        st = re.sub(rf"\btheorem\s+{re.escape(old)}\b", f"theorem {d.theorem}", st)
        ws = self.ctx.workspace(d.workspace or self.ctx.settings.workspace)
        result = None
        if ws is not None:
            r = await self.ctx.lean.check(st, ws, self.ctx.settings.compile_timeout_s, None, owner=f"conj-{d.id}")
            result = r.to_dict()
        idx = d.add_statement(st, source="user", ok=bool(result and result["statement_ok"]))
        m = msg("Énoncé Lean de la conjecture.")
        d.add_event("statement", m["text"], ref=idx, key=m["key"])
        add_evidence(d, "lean_statement", msg("Énoncé Lean accepté par Lean." if result and result["statement_ok"]
                                              else "Énoncé Lean refusé par Lean (ou non vérifié)."),
                     verdict="ok" if result and result["statement_ok"] else "rejected", code=st,
                     data={"check": result})
        if save:
            await self.save(d)
        return result

    # -- experiments
    async def draft_experiment(self, d, *, kind: str = "counterexample", language: str = "sage",
                               mode: str | None = None, code: str = "", device: str = "") -> dict:
        if kind not in ("counterexample", "test") or language not in ("sage", "python"):
            raise ConjectureError("bad_fields")
        c = data_of(d)
        model = ""
        if code.strip():
            parsed = parse_experiment(code)
            if parsed is None:
                raise ConjectureError("bad_code", 422, "Le code doit contenir « # PREDICATE » (avec def holds) puis "
                                                       "« # SEARCH ».")
            source = "user"
        else:
            ans = await self._complete("assistant", experiment_messages(c, d.statement, kind, language),
                                       mode or self.ctx.settings.mode, owner=f"conj-exp-{d.id}")
            parsed, model, source = parse_experiment(ans.text), ans.model.key, "ai"
            if parsed is None:
                raise ConjectureError("no_code", 422, "Le modèle n'a pas produit de code d'expérience utilisable.")
        pred, full = parsed
        eid = "x-" + uuid.uuid4().hex[:8]
        exp = {"id": eid, "kind": kind, "language": language, "code": full, "predicate": pred,
               "code_hash": hashlib.sha256(full.encode()).hexdigest(), "source": source, "model": model,
               "status": "awaiting_approval", "approved": None, "created": time.time(), "runs": [],
               "device": device}
        c["experiments"][eid] = exp
        d.touch()
        await self.save(d)
        return exp

    async def edit_experiment(self, d, eid: str, code: str) -> dict:
        exp = self._exp(d, eid)
        parsed = parse_experiment(code)
        if parsed is None:
            raise ConjectureError("bad_code", 422, "Le code doit contenir « # PREDICATE » (avec def holds) puis "
                                                   "« # SEARCH ».")
        if exp["status"] == "running":
            raise ConjectureError("busy", 409)
        exp["predicate"], exp["code"] = parsed
        exp["code_hash"] = hashlib.sha256(exp["code"].encode()).hexdigest()
        exp["approved"], exp["status"], exp["source"] = None, "awaiting_approval", "user"   # edits need a new approval
        await self.save(d)
        return exp

    def _exp(self, d, eid: str) -> dict:
        exp = data_of(d)["experiments"].get(eid)
        if exp is None:
            raise ConjectureError("not_found", 404)
        return exp

    async def approve(self, d, eid: str, code_hash: str, device: str) -> dict:
        exp = self._exp(d, eid)
        if code_hash != exp["code_hash"]:
            raise ConjectureError("stale_code", 409, "Le code a changé depuis que vous l'avez lu : relisez-le.")
        exp["approved"] = {"hash": code_hash, "t": time.time(), "device": device}
        exp["status"] = "approved"
        await self.save(d)
        return exp

    async def reject(self, d, eid: str) -> dict:
        exp = self._exp(d, eid)
        exp["status"], exp["approved"] = "rejected", None
        await self.save(d)
        return exp

    def may_run(self, exp: dict) -> bool:
        """Server-side approval check: approval of this exact code, or the host's « run automatically » switch."""
        appr = exp.get("approved") or {}
        return appr.get("hash") == exp["code_hash"] or bool(getattr(self.ctx.settings, "experiments_auto", False))

    async def run_experiment(self, d, eid: str, *, timeout: float = 60.0, device: str = "") -> dict:
        exp = self._exp(d, eid)
        if not self.may_run(exp):
            raise ConjectureError("not_approved", 403, "Cette expérience exécute du code sur l'ordinateur hôte : "
                                                       "relisez-la et approuvez-la d'abord.")
        lk = self.lock(d.id)
        if lk.locked():
            raise ConjectureError("busy", 409)
        async with lk:
            exp["status"] = "running"
            self.publish(d)

            def on_output(kind: str, text: str) -> None:
                self.ctx.publish("experiment.output", {"conjecture_id": d.id, "experiment_id": eid, "stream": kind,
                                                       "text": text})
            res = await self.bridge.run(d.id, exp["language"], exp["code"], timeout=timeout, on_output=on_output,
                                        workdir=d.id)
            rep = res.reports[-1] if res.reports else None
            verdict = rep["verdict"] if rep and res.status == "ok" else ("error" if res.status != "ok" else
                                                                       "inconclusive")
            exp["status"] = "done" if res.status == "ok" else "failed"
            run = {"t": time.time(), "status": res.status, "verdict": verdict, "seconds": round(res.seconds, 2)}
            exp["runs"].append(run)
            entry = add_evidence(
                d, "experiment", msg("Expérience ({lang}) : {verdict}.", lang=exp["language"], verdict=verdict),
                verdict=verdict, code=exp["code"], language=exp["language"],
                output=(res.stdout + ("\n[stderr]\n" + res.stderr if res.stderr else "") +
                        ("\n[error]\n" + res.error if res.error else "")),
                data={"experiment_id": eid, "status": res.status, "seconds": round(res.seconds, 2),
                      "killed": res.killed, "sandbox": res.sandbox, "witness": rep.get("witness") if rep else None,
                      "cases": rep.get("cases") if rep else None, "approved": exp.get("approved"),
                      "auto": not (exp.get("approved") or {}).get("hash")}, model=exp.get("model", ""), device=device)
            await self.save(d)
            if verdict == "counterexample" and rep and isinstance(rep.get("witness"), dict):
                await self._reverify(d, exp, rep["witness"], device)
            return entry

    async def _reverify(self, d, exp: dict, witness: dict, device: str) -> dict:
        """Independent re-verification of a counter-example: the predicate alone in a FRESH kernel, then Lean."""
        args = ", ".join(f"{k}={json.dumps(v)}" for k, v in witness.items() if re.fullmatch(r"[A-Za-z_]\w*", k))
        code = exp["predicate"] + f"\nprint('MADALEAN_CHECK', holds({args}))\n"
        res = await self.bridge.run(d.id, exp["language"], code, timeout=60, fresh=True)
        m = re.search(r"MADALEAN_CHECK (True|False)", res.stdout)
        sage_ok = bool(m) and m.group(1) == "False"
        lean_res = None
        if d.statement:
            lean_res = await self.lean_refute(d, witness)
        lean_ok = bool(lean_res and lean_res["ok"])
        verified = sage_ok and (lean_ok or not d.statement or bool(lean_res and lean_res.get("unsupported")))
        verdict = "refuted" if verified else "unconfirmed"
        entry = add_evidence(d, "counterexample_check",
                             msg("Contre-exemple {w} : {verdict}.", w=json.dumps(witness, ensure_ascii=False),
                                 verdict=verdict),
                             verdict=verdict, code=code, language=exp["language"], output=res.stdout + res.error,
                             data={"witness": witness, "kernel": {"fresh": True, "status": res.status,
                                                                  "predicate_false": sage_ok},
                                   "lean": lean_res, "experiment_id": exp["id"]}, device=device)
        if verified:
            data_of(d)["counterexample"] = {"witness": witness, "verified": True, "sage": sage_ok,
                                            "lean": lean_ok, "evidence": entry["id"], "t": time.time()}
            d.add_event("info", msg("Conjecture réfutée : contre-exemple {w} vérifié indépendamment.",
                                    w=json.dumps(witness, ensure_ascii=False))["text"],
                        key="Conjecture réfutée : contre-exemple {w} vérifié indépendamment.",
                        params={"w": json.dumps(witness, ensure_ascii=False)})
        await self.save(d)
        return entry

    async def lean_refute(self, d, witness: dict) -> dict:
        ws = self.ctx.workspace(d.workspace or self.ctx.settings.workspace)
        if ws is None:
            return {"ok": False, "error": "no_workspace"}
        try:
            code = negation_file(d.statement, witness)
        except ConjectureError as e:
            return {"ok": False, "unsupported": True, "error": e.kind}
        r = await self.ctx.lean.check(code, ws, self.ctx.settings.compile_timeout_s, None, owner=f"conj-{d.id}")
        res = r.to_dict()
        return {"ok": res["statement_ok"] and not res["has_sorry"], "code": code, "check": res}

    async def lean_cases(self, d, cases: list[dict] | None = None, bounded: int = 0, device: str = "") -> dict:
        if not d.statement:
            raise ConjectureError("no_statement", 409)
        binders, _ = split_signature(d.statement)
        if not cases:
            nat = [b for b in binders if b["kind"] == "explicit" and b["type"] in ("ℕ", "Nat", "ℤ", "Int")]
            if not nat:
                raise ConjectureError("no_cases", 422)
            cases = [{nat[0]["name"]: i} for i in range(10)]
        cases = [c for c in cases if isinstance(c, dict)][:50]
        code, spans = instance_file(d.statement, cases, max(0, min(int(bounded or 0), 10000)))
        if not spans:
            raise ConjectureError("no_cases", 422)
        ws = self.ctx.workspace(d.workspace or self.ctx.settings.workspace)
        if ws is None:
            raise ConjectureError("no_workspace", 409)
        lk = self.lock(d.id)
        if lk.locked():
            raise ConjectureError("busy", 409)
        async with lk:
            r = await self.ctx.lean.check(code, ws, self.ctx.settings.compile_timeout_s, None, owner=f"conj-{d.id}")
            res = r.to_dict()
            per = results_by_span(res, spans)
            proved = sum(1 for p in per if p["proved"])
            entry = add_evidence(d, "lean_cases", msg("Lean : {k} cas sur {n} vérifiés.", k=proved, n=len(per)),
                                 verdict="holds" if proved == len(per) else "partial", code=code, language="lean",
                                 output="\n".join(e["text"] for e in res["errors"])[:8000],
                                 data={"cases": per, "proved": proved, "total": len(per), "seconds": res["seconds"],
                                       "infra_error": res["infra_error"]}, device=device)
            await self.save(d)
            return entry

    async def literature(self, d, device: str = "") -> dict:
        c = data_of(d)
        try:
            from . import litsearch  # session S-E (optional)
        except Exception:  # noqa: BLE001
            return {"available": False}
        fn = None
        for name in ("is_known", "search", "search_all", "literature_search"):
            fn = getattr(litsearch, name, None)
            if callable(fn):
                break
        if fn is None:
            return {"available": False}
        try:
            out = fn(c["statement_nl"])
            if asyncio.iscoroutine(out):
                out = await asyncio.wait_for(out, 60)
        except Exception as e:  # noqa: BLE001
            return {"available": True, "error": str(e)[:300]}
        hits = out if isinstance(out, list) else (out.get("results") if isinstance(out, dict) else [])
        hits = [h for h in (hits or []) if isinstance(h, dict)][:10]
        entry = add_evidence(d, "literature", msg("Recherche bibliographique : {n} résultat(s).", n=len(hits)),
                             verdict="found" if hits else "none", data={"results": hits}, device=device)
        await self.save(d)
        return entry

    async def promote(self, d, device: str = "") -> object:
        if not d.proof_is_current:
            raise ConjectureError("not_proved", 409, "Seule une preuve acceptée par Lean permet la promotion.")
        c = data_of(d)
        c["promoted"] = {"t": time.time(), "device": device, "from": "conjecture"}
        d.kind = "theorem"
        add_evidence(d, "promoted", msg("Promue en théorème (preuve Lean)."), verdict="proved", device=device)
        await self.save(d)
        return d


# ---------------------------------------------------------------- demo answers (scripted brain)
def demo_answer(first: str) -> str | None:
    if not first.startswith(MARK):
        return None
    if "task=generate" in first:
        return json.dumps([
            {"statement": "Pour tout entier naturel $n$, $n^2 + n + 41$ est premier.",
             "motivation": "Polynôme d'Euler : premier pour $n = 0, \\dots, 39$ (à tester !).",
             "lean": "theorem euler_poly (n : ℕ) : Nat.Prime (n ^ 2 + n + 41) := by sorry", "test": "n de 0 à 100"},
            {"statement": "Pour tout entier naturel $n$, $n^2 + n$ est pair.",
             "motivation": "Produit de deux entiers consécutifs.",
             "lean": "theorem consec_even (n : ℕ) : Even (n ^ 2 + n) := by sorry", "test": "n de 0 à 1000"}],
            ensure_ascii=False)
    if "task=experiment" in first:
        return ("```python\n# PREDICATE\ndef holds(n):\n    m = n * n + n + 41\n    return m > 1 and all(m % p for p in "
                "range(2, int(m ** 0.5) + 1))\n\n# SEARCH\nk = 0\nfor n in range(0, 200):\n    k += 1\n    if not "
                "holds(n=n):\n        report(\"counterexample\", witness={\"n\": n}, cases=k)\n        break\nelse:\n"
                "    report(\"holds\", cases=k)\n```")
    return None
