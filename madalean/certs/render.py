"""From a witness to a Lean proof that only checks it (session S-AT, DECISIONS D52).

Every value that comes back from the sandbox is read strictly (integers, rationals, polynomials with bounded sizes)
and only numbers are written into the proof; names are those of the statement. The mathematics of a witness is NOT
checked here: a wrong witness gives a proof that Lean refuses, and that refusal is what gets reported.

Tactics used, all checked by Lean's kernel: `norm_num`, `decide`, `ring`, `linear_combination`, `linarith`,
`nlinarith` (fallback only), `positivity`, `interval_cases`, `omega`. `native_decide` is never used (it would add the
compiler to what has to be trusted, and Madalean refuses it before compilation, D28)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

from ..i18n import msg
from . import expr as E
from . import poly as Y
from . import pratt
from .problem import Problem, Task

EVAL = "first | (norm_num; done) | (set_option exponentiation.threshold 100000 in norm_num; done) | decide | rfl"
CLOSE = ("first | (norm_num [Nat.ModEq, Int.ModEq]; done) | decide "
         "| (norm_num [Nat.ModEq, Int.ModEq, Nat.factorial, Nat.choose]; done) "
         "| (set_option exponentiation.threshold 100000 in norm_num [Nat.ModEq, Int.ModEq]; done) "
         "| (set_option maxRecDepth 100000 in decide) | (simp; done)")
DECIDE = "set_option maxRecDepth 100000 in decide"
# Mathlib names of the numerical bounds, per generation of Mathlib (old: Lean ≤ 4.19, new: later)
PI_DIGITS = {"old": 6, "new": 20}
BOUNDS = {
    "pi": (("Real.pi_gt_3141592", "Real.pi_gt_d6", "Real.pi_gt_d20"), ("Real.pi_lt_3141593", "Real.pi_lt_d6",
                                                                       "Real.pi_lt_d20")),
    "exp1": (("Real.exp_one_gt_d9",), ("Real.exp_one_lt_d9",)),
    "log2": (("Real.log_two_gt_d9",), ("Real.log_two_lt_d9",)),
}


class BadWitness(ValueError):
    pass


@dataclass
class Rendered:
    helpers: str = ""                    # declarations placed before the theorem
    tactics: list[str] = field(default_factory=list)
    witness: list[dict] = field(default_factory=list)     # i18n messages shown to the user
    checker: str = ""                    # the Lean tactic that checks the witness (shown, measured)

    def proof(self, name: str) -> str:
        body = "\n".join("  " + ln for ln in self.tactics)
        return (self.helpers.rstrip() + "\n\n" if self.helpers.strip() else "") + f"theorem {name} := by\n{body}\n"


def flavor(ws) -> str:
    m = re.search(r"v4\.(\d+)", getattr(ws, "toolchain", "") or "")
    return "old" if m and int(m.group(1)) < 20 else "new"


def digits(fl: str) -> dict:
    return {"pi": PI_DIGITS.get(fl, 6), "sqrt": 9, "exp1": 9, "log2": 9}


def _value(v: Fraction) -> str:
    if v.denominator == 1:
        return str(v.numerator) if v >= 0 else f"({v.numerator})"
    return f"({v.numerator} / {v.denominator})"


def _plain(v: Fraction) -> str:
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def _cert(c, depth: int = 0) -> dict:
    """A Pratt tree from untrusted JSON: integers only."""
    if not isinstance(c, dict) or depth > 14:
        raise BadWitness("bad certificate")
    out: dict = {"p": Y.integer(c.get("p"), 200)}
    if "e" in c:
        out["e"] = Y.integer(c["e"], 5)
    if "a" in c or "factors" in c:
        fs = c.get("factors")
        if not isinstance(fs, list) or len(fs) > 40:
            raise BadWitness("bad certificate")
        out["a"] = Y.integer(c.get("a"), 200)
        out["factors"] = [_cert(f, depth + 1) for f in fs]
    return out


def render(pb: Problem, task: Task, ans: dict | None, fl: str = "new") -> Rendered:
    """The Lean proof for this task and this witness (`ans`: the producer's answer, None for the direct kinds).
    Raises BadWitness when the answer does not even have the shape of a witness."""
    try:
        r = _RENDER[task.kind](pb, task, ans or {}, fl)
    except (E.Unsupported, pratt.BadCertificate, KeyError, TypeError, IndexError, AttributeError) as e:
        raise BadWitness(str(e) or type(e).__name__) from e
    if pb.intros and task.kind in ("identity", "ideal", "linear", "sos"):
        r.tactics.insert(0, "intro " + " ".join(pb.intros))
    return r


# ---------------------------------------------------------------- number theory
def _prime(pb, task, ans, fl) -> Rendered:
    n, ex = task.data["n"], task.data["expr"]
    lit = ex[0] == "num"
    if task.request is None:
        return Rendered(tactics=["norm_num"], checker="norm_num",
                        witness=[msg("Petit nombre : Lean essaie lui-même tous les diviseurs possibles.")])
    cert = _cert(ans.get("cert"))
    if cert["p"] != n:
        raise BadWitness("certificate for another number")
    helpers, term = pratt.proof(cert)
    tac = [f"exact {term}"] if lit else [
        f"have hv : {E.lean(ex)} = {n} := by {EVAL}", "rw [hv]", f"exact {term}"]
    fs = cert.get("factors") or []
    return Rendered(helpers, tac, checker="lucas_primality + decide", witness=[
        msg("Témoin de primalité (Pratt) : a = {a} est d'ordre p − 1 modulo p, avec p − 1 = {fact}.", a=cert.get("a", ""),
            fact=" · ".join(f"{f['p']}^{f['e']}" if f.get("e", 1) > 1 else str(f["p"]) for f in fs)),
        msg("{n} nombres premiers intermédiaires certifiés de la même façon.", n=max(0, len(pratt.nodes(cert)) - 1))])


def _composite(pb, task, ans, fl) -> Rendered:
    d, q, ex = Y.integer(ans.get("d"), 4000), Y.integer(ans.get("q"), 4000), task.data["expr"]
    if d < 0 or q < 0:
        raise BadWitness("negative factor")
    return Rendered(tactics=["intro h",
                             f"have h1 := (Nat.dvd_prime h).mp (show {d} ∣ {E.lean(ex)} from ⟨{q}, by norm_num⟩)",
                             "norm_num at h1"], checker="norm_num",
                    witness=[msg("Diviseur trouvé : {n} = {d} × {q}.", n=task.data["n"], d=d, q=q)])


def _arith(pb, task, ans, fl) -> Rendered:
    return Rendered(tactics=[CLOSE], checker="norm_num / decide", witness=[msg("Calcul direct sur des nombres.")])


def _powmod(pb, task, ans, fl) -> Rendered:
    d = task.data
    a, n, r, ev = d["a"], d["n"], d["r"], d["ev"]
    et = E.lean(d["e"], False)
    fuel = max(1, ev.bit_length())
    term = (f"(madalean_cert_powmod_eq {fuel} {a} {et} {n} (by {EVAL})).symm.trans "
            f"(by {DECIDE} : madalean_cert_powmod {fuel} {a} {et} {n} = {r})")
    tac = [f"have hp : {a} ^ {et} % {n} = {r} := {term}"]
    if d["form"] == "modeq":
        tac.append(f"show {a} ^ {et} % {n} = _ % {n}")
    tac += ["rw [hp]", "all_goals norm_num"]
    return Rendered(pratt.POW_HELPERS, tac, checker="decide",
                    witness=[msg("Puissance modulaire par carrés successifs ({k} étapes) : reste {r}.", k=fuel, r=r)])


# ---------------------------------------------------------------- witnesses
def _values(task, ans) -> list[Fraction]:
    vals = ans.get("values")
    groups = task.data["vars"]
    if not isinstance(vals, list) or len(vals) != len(groups):
        raise BadWitness("bad witness")
    out = [Y.fraction(v, 2000) for v in vals]
    dom = task.data["dom"]
    if dom in ("N", "Z") and any(v.denominator != 1 for v in out) or dom == "N" and any(v < 0 for v in out):
        raise BadWitness("witness outside the number type")
    return out


def _exists(pb, task, ans, fl) -> Rendered:
    vals = _values(task, ans)
    names = [n for n, _t in task.data["vars"]]
    return Rendered(tactics=["exact ⟨" + ", ".join(_value(v) for v in vals) + f", by {CLOSE}⟩"], checker="norm_num",
                    witness=[msg("Témoin : {w}.", w=", ".join(f"{n} = {_plain(v)}" for n, v in zip(names, vals)))])


def _counterexample(pb, task, ans, fl) -> Rendered:
    vals = _values(task, ans)
    names = [n for n, _t in task.data["vars"]]
    args = " ".join(_value(v) for v in vals)
    return Rendered(tactics=["intro h", f"exact absurd (h {args}) (by {CLOSE})"], checker="norm_num",
                    witness=[msg("Contre-exemple : {w}.", w=", ".join(f"{n} = {_plain(v)}" for n, v in zip(names, vals)))])


def _finite(pb, task, ans, fl) -> Rendered:
    bounds, form = task.data["bounds"], task.data["form"]
    names = [n for n, _hi in bounds]
    if form == "ball":
        intro = " ".join(f"{n} h{n}" for n in names)
    else:
        intro = " ".join(names) + " " + " ".join(f"h{n}" for n in names)
    cases = " <;> ".join(f"interval_cases {n}" for n in names)
    return Rendered(tactics=["first", f"  | ({DECIDE})",
                             f"  | (intro {intro}; {cases} <;> (first | norm_num | decide | omega))"],
                    checker="decide",
                    witness=[msg("Vérification exhaustive : {n} cas.", n=task.data["points"])])


# ---------------------------------------------------------------- algebra
def _identity(pb, task, ans, fl) -> Rendered:
    return Rendered(tactics=["ring"], checker="ring",
                    witness=[msg("Identité polynomiale : les deux membres ont le même développement.")])


def _ideal(pb, task, ans, fl) -> Rendered:
    names, dom, hyps = task.data["names"], task.data["dom"], task.data["hyps"]
    k = Y.integer(ans.get("exp"), 1)
    cof = ans.get("cof")
    if not isinstance(cof, list) or len(cof) != len(hyps) or not 1 <= k <= 3:
        raise BadWitness("bad cofactors")
    polys = [Y.from_wire(c, len(names)) for c in cof]
    terms = [f"({Y.lean(p, names, dom)}) * {h}" for p, h in zip(polys, hyps) if p]
    tac = "linear_combination" + (f" (exp := {k})" if k > 1 else "") + " " + (" + ".join(terms) if terms else "0")
    shown = [msg("{h} multipliée par {c}", h=h, c=Y.text(p, names)) for p, h in zip(polys, hyps) if p]
    head = msg("Combinaison des hypothèses trouvée (base de Gröbner){pw} :",
               pw=msg(", pour la puissance {k} du but", k=k)["text"] if k > 1 else "")
    return Rendered(tactics=[tac], checker="linear_combination", witness=[head] + shown)


def _linear(pb, task, ans, fl) -> Rendered:
    hyps = task.data["hyps"]
    runs = ans.get("multipliers")
    if not isinstance(runs, list) or not runs or len(runs) > 2:
        raise BadWitness("bad multipliers")
    lam = []
    for run in runs:
        if not isinstance(run, list) or len(run) != len(hyps):
            raise BadWitness("bad multipliers")
        lam.append([Y.fraction(v) for v in run])
    used = [h for i, h in enumerate(hyps) if any(run[i] for run in lam)]
    only = f"linarith only [{', '.join(used)}]"
    shown = [msg("{h} multipliée par {c}", h=h, c=_plain(lam[0][i])) for i, h in enumerate(hyps) if lam[0][i]]
    return Rendered(tactics=[f"first | {only} | linarith"], checker="linarith",
                    witness=[msg("Combinaison linéaire des hypothèses qui donne le résultat (certificat de Farkas) :")]
                    + (shown or [msg("aucune hypothèse nécessaire")]))


def _gap(prop) -> str:
    """The expression that the relation says is ≥ 0 (or > 0), as Lean text."""
    a, b = E.lean(prop[2], False), E.lean(prop[3], False)
    return f"{b} - {a}" if prop[1] in ("<", "<=") else f"{a} - {b}"


def _sos(pb, task, ans, fl) -> Rendered:
    names, dom, hyps, goal = task.data["names"], task.data["dom"], task.data["hyps"], task.data["goal"]
    t = E.LEAN_TYPE[dom]
    c = Y.fraction(ans.get("c"))
    mults, blocks = ans.get("mults"), ans.get("blocks")
    if not isinstance(mults, list) or not isinstance(blocks, list) or len(mults) > 40 or len(blocks) > 12 or c < 0:
        raise BadWitness("bad certificate")
    tac, facts, rhs, shown = [], [], [], []
    if c:
        rhs.append(Y.lean_const(c, dom))
    need: set[int] = set()
    prods = []
    for m in mults:
        idx, lam = m[0], Y.fraction(m[1])
        if not (isinstance(idx, list) and 1 <= len(idx) <= 2 and all(isinstance(i, int) and 0 <= i < len(hyps)
                                                                     for i in idx)) or lam < 0:
            raise BadWitness("bad multiplier")
        need.update(idx)
        prods.append((idx, lam))
    for i in sorted(need):
        tac.append(f"have hn{i} : (0 : {t}) ≤ {_gap(hyps[i][1])} := by linarith [{hyps[i][0]}]")
        facts.append(f"hn{i}")
    for k, (idx, lam) in enumerate(prods):
        g = " * ".join(f"({_gap(hyps[i][1])})" for i in idx)
        if len(idx) == 2:
            tac.append(f"have hm{k} : (0 : {t}) ≤ {g} := mul_nonneg hn{idx[0]} hn{idx[1]}")
            facts.append(f"hm{k}")
        rhs.append(f"{Y.lean_const(lam, dom)} * ({g})")
        shown.append(msg("{c} × {h}", c=_plain(lam), h=" × ".join(hyps[i][0] for i in idx)))
    for bk, blk in enumerate(blocks):
        i, forms = blk[0], blk[1]
        if not isinstance(i, int) or not -1 <= i < len(hyps) or not isinstance(forms, list) or len(forms) > 40:
            raise BadWitness("bad block")
        sq = []
        for s in forms:
            d, f = Y.fraction(s[0]), Y.from_wire(s[1], len(names))
            if d < 0:
                raise BadWitness("negative weight")
            if d and f:
                sq.append(f"{Y.lean_const(d, dom)} * ({Y.lean(f, names, dom)}) ^ 2")
                shown.append(msg("{c} × ({f})²", c=_plain(d), f=Y.text(f, names)) if i < 0 else
                             msg("{h} × {c} × ({f})²", h=hyps[i][0], c=_plain(d), f=Y.text(f, names)))
        if not sq:
            continue
        if i < 0:
            tac.append(f"have hs : (0 : {t}) ≤ {' + '.join(sq)} := by positivity")
            facts.append("hs")
            rhs += sq
        else:
            if i not in need:
                need.add(i)
                tac.append(f"have hn{i} : (0 : {t}) ≤ {_gap(hyps[i][1])} := by linarith [{hyps[i][0]}]")
                facts.append(f"hn{i}")
            term = f"({_gap(hyps[i][1])}) * ({' + '.join(sq)})"
            tac.append(f"have hb{bk} : (0 : {t}) ≤ {term} := mul_nonneg hn{i} (by positivity)")
            facts.append(f"hb{bk}")
            rhs.append(term)
    tac.append(f"have he : {_gap(goal)} = {' + '.join(rhs) if rhs else f'(0 : {t})'} := by ring")
    facts.append("he")
    tac.append(f"first | linarith | nlinarith [{', '.join(facts)}]")
    head = msg("Écriture comme somme de carrés{c} :", c=msg(" plus la constante {c}", c=_plain(c))["text"] if c else "")
    return Rendered(tactics=tac, checker="ring + positivity + linarith", witness=[head] + shown)


def _numeric(pb, task, ans, fl) -> Rendered:
    atoms = task.data["atoms"]
    bounds = ans.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != len(atoms):
        raise BadWitness("bad bounds")
    tac, facts, shown = [], [], []
    for i, (a, b) in enumerate(zip(atoms, bounds)):
        lo, hi = Y.fraction(b[0], 60), Y.fraction(b[1], 60)
        text = E.lean(a, False)
        lo_t, hi_t = Y.lean_const(abs(lo), "R"), Y.lean_const(abs(hi), "R")
        if a[1] == "sqrt":
            if lo < 0 or hi <= 0:
                tac.append(f"have hl{i} : (0 : ℝ) ≤ {text} := Real.sqrt_nonneg _")
            else:
                tac += [f"have hl{i} : {lo_t} < {text} := by", "  rw [Real.lt_sqrt (by norm_num)]", "  norm_num"]
            tac += [f"have hu{i} : {text} < {hi_t} := by", "  rw [Real.sqrt_lt' (by norm_num)]", "  norm_num"]
        else:
            key = "pi" if a[1] == "pi" else ("exp1" if a[1] == "exp" else "log2")
            if lo <= 0 or hi <= 0:
                raise BadWitness("bad bounds")
            for side, names, stmt in (("l", BOUNDS[key][0], f"{lo_t} < {text}"), ("u", BOUNDS[key][1],
                                                                                  f"{text} < {hi_t}")):
                alts = " | ".join(f"(have h := {nm}; first | linarith [h] | (norm_num at h ⊢; linarith) "
                                  f"| (norm_num at h; linarith))" for nm in reversed(names))
                tac += [f"have h{side}{i} : {stmt} := by", f"  first | {alts}"]
        facts += [f"hl{i}", f"hu{i}"]
        shown.append(msg("{lo} < {x} < {hi}", lo=f"{float(lo):.12g}", x=text, hi=f"{float(hi):.12g}"))
    tac.append(f"first | linarith | (norm_num at *; linarith) | nlinarith [{', '.join(facts)}] "
               f"| (norm_num at *; nlinarith [{', '.join(facts)}])")
    return Rendered(tactics=tac, checker="norm_num + linarith",
                    witness=[msg("Encadrements calculés par Sage, vérifiés par Lean :")] + shown)


_RENDER = {"prime": _prime, "composite": _composite, "arith": _arith, "powmod": _powmod, "exists": _exists,
           "counterexample": _counterexample, "finite": _finite, "identity": _identity, "ideal": _ideal,
           "linear": _linear, "sos": _sos, "numeric": _numeric}
