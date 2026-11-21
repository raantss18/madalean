"""« Vérifier l'énoncé » (S-K, TODO P0 #2): is the Lean statement what the user meant, and can it be true at all?

Three checks, run in parallel and all bounded:
 (a) fidelity — the general model compares the user's words with the Lean statement and lists discrepancies as
     JSON (wrong object, missing / extra hypothesis, wrong quantifier, wrong direction), each with a proposed fix;
 (b) truth — Lean, not the model: one compilation tries short proofs of the NEGATION (`decide`, `norm_num`, `simp`,
     `push_neg` + small witnesses) and of degenerate instances (∅ for sets, 0/1 for numbers, constant functions),
     plus quick proofs of the statement itself (`simp`, `norm_num`, `omega`, `aesop`, `exact?` in its own file);
 (c) degenerate cases — the model proposes counterexamples as tactic proofs of the PINNED negation
     `¬ (∀ BINDERS, CONCL)` (the server writes the proposition, the model only the tactics), checked by Lean.

A statement is « faux » only when Lean proves its negation (strict re-check, D28 gate). The model's opinion alone
can only make it « douteux ». The proof stage stops on « faux » / « douteux » and says why; the user can correct
the statement in one click or « Prouver quand même »."""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass, field

from .. import leancheck
from ..brain.api import BrainError
from ..logs import get
from . import probes as P

log = get("pipeline.verify")

AUTO_TIMEOUT = 90           # one compilation for all automatic probes
EXACT_TIMEOUT = 60          # `exact?` in its own file
CEX_TIMEOUT = 60            # model counterexamples, one compilation
STRICT_TIMEOUT = 60
MODEL_TIMEOUT = 150         # fidelity answer
MAX_CEX = 3
NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}

NEG_TACTICS = ["decide", "norm_num", "simp", "push_neg\nsimp", "push_neg\nnorm_num",
               "push_neg\nrefine ⟨0, ?_⟩\nnorm_num", "push_neg\nrefine ⟨1, ?_⟩\nnorm_num",
               "push_neg\nrefine ⟨0, 0, ?_⟩\nnorm_num"]
POS_TACTICS = ["decide", "norm_num", "simp", "omega", "aesop"]
CLOSE_HYP = ("first\n  | (simp at this; done)\n  | (norm_num at this; done)\n"
             "  | (simp at this; exact this (by first | fun_prop | continuity | simp | norm_num))\n"
             "  | (norm_num at this; exact this (by first | fun_prop | continuity | simp | norm_num))")


@dataclass
class CheckResult:
    verdict: str = "faithful"              # faithful | doubtful | false | unknown
    issues: list[dict] = field(default_factory=list)   # [{kind, severity, explanation, fix, checked}]
    fix: str = ""                          # best one-click correction (user's language)
    evidence: dict = field(default_factory=dict)       # {kind: negation|counterexample, code, idea}
    proof: str = ""                        # a quick proof of the statement found by Lean (tactic), if any
    proof_source: str = ""                 # e.g. "exact?" / "simp"
    model: str = ""
    model_verdict: str = ""
    summary: str = ""                      # model's one-line reading
    seconds: float = 0.0
    lean_seconds: float = 0.0
    probes: int = 0
    statement_index: int = -1
    t: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


FIDELITY_PROMPT = (
    "You check a formalization in Lean 4 (Mathlib) for a mathematics student. Compare what the user asked with the "
    "Lean statement below and look for discrepancies:\n"
    "- wrong_object: the Lean statement talks about another object or another theorem (e.g. the minimal polynomial "
    "instead of the characteristic polynomial, a field instead of a vector space);\n"
    "- missing_hypothesis: a hypothesis needed for the result to be TRUE or to match the user's text is absent "
    "(typical traps: a set that may be empty, division by zero, natural-number subtraction `a - b` that truncates "
    "at 0, a sequence whose two subsequences converge to DIFFERENT limits, a function that is only defined on part "
    "of the type, a zero vector space, n = 0);\n"
    "- extra_hypothesis: a hypothesis the user did not state that makes the result weaker or vacuous (e.g. "
    "contradictory hypotheses);\n"
    "- wrong_quantifier / wrong_direction: ∀ instead of ∃, the converse instead of the implication, ≤ instead of <;\n"
    "- false_statement: the statement as written is false (give a counterexample idea).\n"
    "Be precise and do not invent problems: a faithful statement must be reported as faithful. Lean syntax details "
    "(names of Mathlib definitions, coercions, implicit arguments) are NOT discrepancies.\n\n"
    "User's request (their own words):\n{problem}\n\n"
    "{understood}"
    "Lean statement:\n```lean4\n{lean}\n```\n\n"
    "If you think the statement is false, also give up to {max_cex} Lean 4 tactic proofs of its negation. The "
    "negation is EXACTLY this proposition (do not restate it, give only the tactic lines that prove it, as after "
    "`by`):\n```lean4\n{negation}\n```\n"
    "Typical proof: `intro h` then `have := h (x := …) …` with a concrete degenerate instance (∅, 0, a constant "
    "function, (-1)^n…), then `simp at this` / `norm_num at this`.\n\n"
    "Answer with ONE JSON object and nothing else:\n"
    "{{\"verdict\": \"faithful\" | \"doubtful\" | \"false\",\n"
    " \"summary\": \"<one sentence in {lang_name}: what the Lean statement says>\",\n"
    " \"issues\": [{{\"kind\": \"wrong_object|missing_hypothesis|extra_hypothesis|wrong_quantifier|wrong_direction|"
    "false_statement\", \"severity\": \"high|low\", \"explanation\": \"<in {lang_name}, {style}>\", "
    "\"fix\": \"<in {lang_name}: the corrected statement as ONE instruction for the translator, e.g. 'Ajouter "
    "l'hypothèse : K est non vide'>\"}}],\n"
    " \"counterexamples\": [{{\"idea\": \"<in {lang_name}>\", \"lean\": \"<tactic lines>\"}}]}}\n"
    "severity high = the Lean statement is false or is not the user's theorem; low = a detail worth knowing."
)

STYLE = {"plain": "2 sentences for a mathematician",
         "learn": "2–4 sentences for a student: name the trap, give the smallest example that shows it, and say "
                  "what hypothesis repairs it"}


def fidelity_messages(problem: str, understood: str, lean: str, negation: str, lang: str, learn: bool) -> list[dict]:
    name = "French" if lang != "en" else "English"
    und = f"How the assistant understood it:\n{understood.strip()}\n\n" if understood.strip() else ""
    body = lean[lean.rfind("theorem"):] if "theorem" in lean else lean
    return [{"role": "user", "content": FIDELITY_PROMPT.format(
        problem=problem.strip() or "(no text: the user wrote the Lean statement)", understood=und, lean=body.strip(),
        negation=negation, max_cex=MAX_CEX, lang_name=name, style=STYLE["learn" if learn else "plain"])}]


def parse_json_answer(text: str) -> dict | None:
    t = leancheck.clean_model_text(text)
    t = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", t.strip())
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    raw = t[a:b + 1]
    for cand in (raw, re.sub(r",\s*([}\]])", r"\1", raw)):
        try:
            v = json.loads(cand)
            return v if isinstance(v, dict) else None
        except ValueError:
            continue
    m = re.search(r'"verdict"\s*:\s*"(faithful|doubtful|false)"', raw)
    return {"verdict": m.group(1), "issues": []} if m else None


KINDS = {"wrong_object", "missing_hypothesis", "extra_hypothesis", "wrong_quantifier", "wrong_direction",
         "false_statement", "other"}


def clean_issues(v: dict) -> list[dict]:
    out = []
    for it in (v.get("issues") or [])[:6]:
        if not isinstance(it, dict):
            continue
        kind = str(it.get("kind") or "other").strip()
        out.append({"kind": kind if kind in KINDS else "other",
                    "severity": "high" if str(it.get("severity", "")).lower() == "high" else "low",
                    "explanation": str(it.get("explanation") or "")[:1200].strip(),
                    "fix": str(it.get("fix") or "")[:600].strip(), "checked": ""})
    return [i for i in out if i["explanation"] or i["fix"]]


def clean_tactics(s: str) -> str:
    s = leancheck.extract_code(s) or s
    s = re.sub(r"^\s*(?:theorem|lemma)\b.*?:=\s*by[ \t]*", "", s, flags=re.S)
    s = re.sub(r"^\s*by[ \t]*", "", s)
    lines = [l.rstrip() for l in s.split("\n") if l.strip()]
    if not lines:
        return ""
    ind = min(len(l) - len(l.lstrip(" ")) for l in lines)
    return "\n".join(l[ind:] for l in lines)[:3000]


class StatementChecker:
    """`io`: the job's StageIO (complete + check). `lean_real`: False with the demo's fake Lean (no Lean probes:
    a fake checker would « prove » every negation)."""

    def __init__(self, io, mode: str, lean_real: bool = True, use_model: bool = True):
        self.io, self.mode, self.lean_real, self.use_model = io, mode, lean_real, use_model

    async def run(self, problem: str, understood: str, statement: str, ws, *, lang: str = "fr",
                  learn: bool = False) -> CheckResult:
        t0 = time.monotonic()
        res = CheckResult()
        sig = P.split_statement(statement)
        lean_tasks: list[asyncio.Task] = []
        auto: list[P.Probe] = []
        exq: list[P.Probe] = []
        if sig is not None and self.lean_real:
            auto = self._auto_probes(sig)
            exq = [P.Probe("madalean_exact", P.decl("madalean_exact", f"{sig.binders} : {sig.concl}", "exact?",
                                                    60000), "pos", {"tactic": "exact?"})]
            lean_tasks = [asyncio.create_task(P.run_batch(self.io, ws, sig.preamble, auto, AUTO_TIMEOUT)),
                          asyncio.create_task(P.run_batch(self.io, ws, sig.preamble, exq, EXACT_TIMEOUT))]
        fid: dict | None = None
        try:
            if self.use_model:
                try:
                    fid = await asyncio.wait_for(self._fidelity(problem, understood, statement, sig, lang, learn),
                                                 MODEL_TIMEOUT)
                except (asyncio.TimeoutError, BrainError) as e:
                    log.info("fidelity check skipped: %s", e)
            for t in lean_tasks:
                try:
                    res.lean_seconds += await t
                except Exception as e:  # noqa: BLE001 (a probe batch never breaks the job)
                    log.warning("probe batch failed: %s", e)
        finally:
            for t in lean_tasks:
                if not t.done():
                    t.cancel()
        res.probes = len(auto) + len(exq)
        if fid is not None:
            res.model = fid.get("_model", "")
            res.model_verdict = str(fid.get("verdict") or "")
            res.summary = str(fid.get("summary") or "")[:600]
            res.issues = clean_issues(fid)
        # (c) the model's counterexamples, as proofs of the pinned negation
        cex: list[P.Probe] = []
        if sig is not None and self.lean_real and fid is not None and not any(p.ok and p.kind != "pos" for p in auto):
            for k, c in enumerate((fid.get("counterexamples") or [])[:MAX_CEX]):
                if not isinstance(c, dict):
                    continue
                tac = clean_tactics(str(c.get("lean") or ""))
                if tac:
                    cex.append(P.Probe(f"madalean_cex_{k}", P.decl(f"madalean_cex_{k}", ": " + sig.negation(), tac,
                                                                     60000), "cex", {"idea": str(c.get("idea") or "")[:400]}))
            if cex:
                res.lean_seconds += await P.run_batch(self.io, ws, sig.preamble, cex, CEX_TIMEOUT)
                res.probes += len(cex)
        # strict re-checks: the first negation that holds decides
        if sig is not None and self.lean_real:
            for p in [p for p in auto + cex if p.ok and p.kind in ("neg", "cex")][:3]:
                r = await P.strict(self.io, ws, sig.preamble, p, STRICT_TIMEOUT)
                res.lean_seconds += r.seconds
                if r.verdict.ok:
                    res.evidence = {"kind": "counterexample" if p.kind == "cex" or p.meta.get("subst") else "negation",
                                    "code": _shown(p.code), "idea": p.meta.get("idea") or p.meta.get("subst") or ""}
                    break
            if not res.evidence:
                for p in [p for p in exq + auto if p.kind == "pos" and (p.ok or p.suggestion)][:3]:
                    tac = p.suggestion if p.meta.get("tactic") == "exact?" else p.meta.get("tactic", "")
                    if not tac or "?" in tac:
                        continue
                    q = P.Probe(p.name + "_ok", P.decl(p.name + "_ok", f"{sig.binders} : {sig.concl}", tac, 200000),
                                "pos")
                    r = await P.strict(self.io, ws, sig.preamble, q, STRICT_TIMEOUT)
                    res.lean_seconds += r.seconds
                    if r.verdict.ok:
                        res.proof, res.proof_source = tac, p.meta.get("tactic", "")
                        break
        res.verdict = self._verdict(res)
        if fid is None and not res.evidence and not res.proof:
            res.verdict = "unknown"           # nothing could be checked (no model answer, no Lean result)
        res.fix = next((i["fix"] for i in res.issues if i["severity"] == "high" and i["fix"]), "") or \
            next((i["fix"] for i in res.issues if i["fix"]), "")
        if res.evidence and not res.fix:
            res.fix = degenerate_fix(res.evidence.get("idea", ""), lang)
        if res.evidence:
            for i in res.issues:
                if i["kind"] in ("missing_hypothesis", "false_statement"):
                    i["checked"] = "lean"
        res.seconds = time.monotonic() - t0
        return res

    @staticmethod
    def _verdict(res: CheckResult) -> str:
        if res.evidence:
            return "false"
        high = [i for i in res.issues if i["severity"] == "high"]
        if res.proof:
            # Lean proved the statement: « missing hypothesis » / « false » claims are refuted; a wrong object is not
            return "doubtful" if any(i["kind"] in ("wrong_object", "wrong_direction", "wrong_quantifier",
                                                   "extra_hypothesis") for i in high) else "faithful"
        if high or res.model_verdict == "false":
            return "doubtful"
        return "faithful"

    def _auto_probes(self, sig: P.Sig) -> list[P.Probe]:
        out: list[P.Probe] = []
        neg = ": " + sig.negation()
        for k, tac in enumerate(NEG_TACTICS):
            out.append(P.Probe(f"madalean_neg_{k}", P.decl(f"madalean_neg_{k}", neg, tac), "neg", {"tactic": tac}))
        # degenerate instances: every binder at once, then one binder at a time
        subs = [(n, v[0]) for n, t in P.explicit_binders(sig.binders) for v in [P.degenerate_value(t)] if v]
        combos: list[list[tuple[str, str]]] = []
        if subs:
            combos.append(subs)
            combos += [[s] for s in subs if len(subs) > 1]
            for n, t in P.explicit_binders(sig.binders):
                vals = P.degenerate_value(t)
                if len(vals) > 1:
                    combos.append([(n, vals[1])])
        for k, combo in enumerate(combos[:8]):
            args = " ".join(f"({n} := {v})" for n, v in combo)
            tac = f"intro h\nhave := h {args}\n{CLOSE_HYP}"
            out.append(P.Probe(f"madalean_deg_{k}", P.decl(f"madalean_deg_{k}", neg, tac), "neg",
                               {"tactic": tac, "subst": ", ".join(f"{n} = {v}" for n, v in combo)}))
        head = f"{sig.binders} : {sig.concl}"
        for k, tac in enumerate(POS_TACTICS):
            out.append(P.Probe(f"madalean_pos_{k}", P.decl(f"madalean_pos_{k}", head, tac), "pos", {"tactic": tac}))
        return out

    async def _fidelity(self, problem: str, understood: str, statement: str, sig, lang: str, learn: bool) -> dict | None:
        negation = sig.negation() if sig is not None else "¬ (the statement)"
        c = await self.io.complete("understand", fidelity_messages(problem, understood, statement, negation, lang,
                                                                     learn),
                                   None, temperature=0.2, max_tokens=3000, extra={"top_p": 0.9, **NO_THINK},
                                   mode=self.mode, stage="verify")
        v = parse_json_answer(c.text)
        if v is None:
            return None
        v["_model"] = c.model.key
        return v


def degenerate_fix(idea: str, lang: str = "fr") -> str:
    """A correction derived from the degenerate instance Lean used (« K = ∅ » → K non vide), when the model gave none."""
    parts = []
    for name, val in re.findall(r"([^\s,=]+) = (∅|0)(?=,|$)", idea):
        if val == "∅":
            parts.append(f"{name} est non vide ({name}.Nonempty)" if lang != "en" else f"{name} is nonempty ({name}.Nonempty)")
        else:
            parts.append(f"{name} ≠ 0")
    if not parts:
        return ""
    return ("Ajouter l'hypothèse : " if lang != "en" else "Add the hypothesis: ") + " ; ".join(parts)


def _shown(code: str) -> str:
    """The probe as the user should read it: without the `set_option … in` lines."""
    return "\n".join(l for l in code.split("\n") if not l.startswith("set_option ")).strip()
