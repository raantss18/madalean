"""Leaderboard: which model really solves which kind of task here (session S-J, DECISIONS D30).

Per model and per task category (`prove`, `formalize`, `explain`) — and per coarse problem domain (`prove/algebra`,
`prove/number_theory`…) — it keeps time-decayed counts of tasks attempted, Lean-verified successes, attempts spent,
Lean errors, wall time and pauses (429 / quota / overload). The score is a Bayesian posterior mean of the success
rate (prior 0.3 with the weight of 4 tasks, so 1/1 does not beat 9/10), minus small penalties for many attempts per
success and for being often unavailable. The router adds `bonus()` to the score of the role's models, with a
human-readable reason (« a prouvé 7/9 problèmes d'algèbre linéaire ici »).

Persisted in `<config_dir>/brain-leaderboard.json` (mode 0600, no keys, bounded to MAX_ENTRIES rows)."""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from ._util import now, read_json, write_private

HALF_LIFE = 30 * 86400.0          # a result counts half after 30 days (models and providers change)
PRIOR_P = 0.3                      # prior success rate of an unknown model on a task
PRIOR_N = 4.0                      # weight of the prior, in tasks
WEIGHT = 1.0                       # router bonus = WEIGHT · (score − PRIOR_P) · confidence
MAX_ENTRIES = 600
TASKS = ("prove", "formalize", "explain")
ROLE_TASK = {"prove": "prove", "formalize": "formalize", "explain": "explain"}

DOMAINS = ("linear_algebra", "analysis", "combinatorics", "number_theory", "algebra", "geometry", "logic", "other")
DOMAIN_FR = {"linear_algebra": "d'algèbre linéaire", "analysis": "d'analyse", "combinatorics": "de combinatoire",
             "number_theory": "de théorie des nombres", "algebra": "d'algèbre", "geometry": "de géométrie",
             "logic": "de logique", "other": ""}
DOMAIN_EN = {"linear_algebra": "linear algebra", "analysis": "analysis", "combinatorics": "combinatorics",
             "number_theory": "number theory", "algebra": "algebra", "geometry": "geometry", "logic": "logic",
             "other": ""}
TASK_FR = {"prove": "prouvé {ok}/{n} problèmes", "formalize": "traduit {ok}/{n} énoncés",
           "explain": "expliqué {ok}/{n} preuves"}
TASK_EN = {"prove": "proved {ok}/{n} problems", "formalize": "formalized {ok}/{n} statements",
           "explain": "explained {ok}/{n} proofs"}

# first match wins (order matters: linear algebra before algebra, analysis before number theory)
_DOMAIN_RULES: list[tuple[str, re.Pattern]] = [(d, re.compile(p, re.I)) for d, p in [
    ("linear_algebra", r"\b(Matrix|LinearMap|Module\.|Submodule|FiniteDimensional|LinearIndependent|Basis|"
                       r"eigen\w*|Matrix\.det|det\b|span|rank)\b|matrice|vectoriel|lin[ée]aire|linear"),
    ("analysis", r"\b(Real\.(exp|log|sin|cos|sqrt|pi)|deriv|HasDerivAt|Continuous\w*|Differentiable\w*|Tendsto|"
                 r"Filter|atTop|∫|integral|MeasureTheory|Metric|Cauchy\w*|Summable|tsum|limit)\b|"
                 r"d[ée]riv|int[ée]grale|continu|limite|suite|s[ée]rie"),
    ("combinatorics", r"\b(Finset\.card|Fintype\.card|choose|Nat\.choose|SimpleGraph|Equiv\.Perm|card)\b|"
                      r"combinatoire|d[ée]nombr|permutation|graphe|coloriage"),
    ("number_theory", r"\b(Nat\.Prime|Prime|ZMod|Int\.gcd|Nat\.gcd|gcd|lcm|Even|Odd|Int\.emod|Nat\.ModEq|"
                      r"Int\.ModEq|padicValNat|Nat\.digits|totient)\b|∣|\s%\s|≡|premier|divis|pgcd|pair|impair|"
                      r"congru|modulo|entier"),
    ("algebra", r"\b(Polynomial|Ideal|Ring|Field|Group|Subgroup|MonoidHom|RingHom|IsUnit|roots|natDegree|"
                r"Complex)\b|polyn[ôo]me|cubique|cubic|quadratic|groupe|anneau|corps|racine|[ée]quation|x\s*\^\s*[23]"),
    ("geometry", r"\b(EuclideanGeometry|EuclideanSpace|Affine\w*|InnerProductSpace|angle|dist)\b|triangle|"
                 r"cercle|g[ée]om[ée]trie|orthogonal"),
    ("logic", r"\b(Set\.|Function\.Injective|Function\.Surjective|Bijective|Decidable|Classical)\b|"
              r"ensemble|injecti|surjecti|bijecti"),
]]


def domain_of(text: str) -> str:
    """Coarse problem domain of a Lean statement and/or its natural-language problem (« other » when unsure)."""
    t = text or ""
    for d, rx in _DOMAIN_RULES:
        if rx.search(t):
            return d
    return "other"


@dataclass
class Entry:
    n: float = 0.0          # tasks where the model really ran (decayed)
    ok: float = 0.0         # Lean-verified successes (decayed)
    runs: float = 0.0       # attempts spent (agent runs / Goedel attempts, decayed)
    att_ok: float = 0.0     # attempts spent on the tasks it solved (decayed)
    lean_err: float = 0.0   # Lean rejections (decayed)
    pauses: float = 0.0     # times it could not run at all: 429, quota, overload, refused key (decayed)
    sec: float = 0.0        # wall seconds (decayed)
    t: float = 0.0          # last update (unix)
    last_ok: float = 0.0    # last success (unix)
    total: int = 0          # raw counts for display (not decayed)
    total_ok: int = 0

    def decayed(self, at: float) -> "Entry":
        f = 0.5 ** (max(0.0, at - self.t) / HALF_LIFE) if self.t else 1.0
        e = Entry(**asdict(self))
        for k in ("n", "ok", "runs", "att_ok", "lean_err", "pauses", "sec"):
            setattr(e, k, getattr(self, k) * f)
        return e


def score_of(e: Entry) -> float:
    """Posterior success rate minus penalties for inefficiency and unavailability, in [0, 1]."""
    p = (e.ok + PRIOR_P * PRIOR_N) / (e.n + PRIOR_N)
    mean_att = e.att_ok / e.ok if e.ok > 0.05 else 1.0
    eff = min(0.15, 0.03 * max(0.0, mean_att - 1.0))
    pause = 0.3 * e.pauses / (e.pauses + e.n + 2.0)
    # S-M: a model that ran several times, never succeeded and whose Lean is always rejected is demoted further
    # (summarisation or chat models that write text instead of Lean): up to -0.25
    junk = 0.0
    if e.ok < 0.05 and e.n >= 1.5 and e.runs > 0:
        junk = 0.25 * min(1.0, e.lean_err / e.runs) * (e.n / (e.n + 2.0))
    return max(0.0, min(1.0, p - eff - pause - junk))


def confidence(e: Entry) -> float:
    m = e.n + e.pauses
    return m / (m + 3.0)


class Leaderboard:
    """Thread-safe, persisted after each change. Keys: "<model key>|<task>" and "<model key>|<task>/<domain>"."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.entries: dict[str, Entry] = {}
        raw = read_json(self.path) or {}
        names = {f.name for f in fields(Entry)}
        for k, v in (raw.get("entries") or {}).items() if isinstance(raw, dict) else []:
            if not isinstance(k, str) or "|" not in k or not isinstance(v, dict):
                continue
            try:
                self.entries[k] = Entry(**{f: type(getattr(Entry(), f))(v[f]) for f in names if f in v})
            except (TypeError, ValueError):
                pass

    # ------------------------------------------------------------ write
    def _save(self) -> None:
        if len(self.entries) > MAX_ENTRIES:
            for k in sorted(self.entries, key=lambda k: self.entries[k].t)[: len(self.entries) - MAX_ENTRIES]:
                del self.entries[k]
        try:
            write_private(self.path, json.dumps({"version": 1, "entries": {k: asdict(v) for k, v in
                                                                            self.entries.items()}}))
        except OSError:
            pass

    def record(self, model: str, task: str, domain: str | None = None, *, ok: bool, attempts: int = 1,
               lean_errors: int = 0, seconds: float = 0.0, unavailable: bool = False) -> None:
        """One task outcome for one model. `unavailable`: the model could not run at all (429, quota, pause…):
        counted as a pause, not as a failure of its mathematics."""
        if not model or not task:
            return
        t = now()
        keys = [f"{model}|{task}"] + ([f"{model}|{task}/{domain}"] if domain and domain != "other" else [])
        with self._lock:
            for k in keys:
                e = self.entries.get(k, Entry()).decayed(t)
                e.t = t
                if unavailable:
                    e.pauses += 1
                else:
                    a = max(1, int(attempts))
                    e.n += 1
                    e.total += 1
                    e.runs += a
                    e.lean_err += max(0, int(lean_errors))
                    e.sec += max(0.0, float(seconds))
                    if ok:
                        e.ok += 1
                        e.total_ok += 1
                        e.att_ok += a
                        e.last_ok = t
                self.entries[k] = e
            self._save()

    def reset(self) -> None:
        with self._lock:
            self.entries.clear()
            self._save()

    # ------------------------------------------------------------ read
    def entry(self, model: str, task: str, domain: str | None = None) -> Entry | None:
        k = f"{model}|{task}" + (f"/{domain}" if domain else "")
        e = self.entries.get(k)
        return e.decayed(now()) if e else None

    def score(self, model: str, task: str, domain: str | None = None) -> float:
        e = self.entry(model, task, domain)
        return score_of(e) if e else PRIOR_P

    def bonus(self, model: str, task: str | None, domain: str | None = None, lang: str = "fr") -> tuple[float, str]:
        """Router bonus for `model` on `task` (and `domain` when it has enough evidence), with its reason."""
        if not task:
            return 0.0, ""
        gen = self.entry(model, task)
        dom = self.entry(model, task, domain) if domain and domain != "other" else None
        e, d = (dom, domain) if dom is not None and dom.n + dom.pauses >= 2 else (gen, None)
        if e is None or e.n + e.pauses <= 0:
            return 0.0, ""
        b = WEIGHT * (score_of(e) - PRIOR_P) * confidence(e)
        return b, explain(e, task, d, lang) + f" ({b:+.2f})"

    def table(self, task: str | None = None) -> list[dict]:
        """Rows for GET /api/models/leaderboard, best first within each (task, domain)."""
        t = now()
        rows = []
        for k, raw in self.entries.items():
            model, cat = k.split("|", 1)
            tk, _, dom = cat.partition("/")
            if task and tk != task:
                continue
            e = raw.decayed(t)
            rows.append({"model": model, "task": tk, "domain": dom or "", "tasks": raw.total, "solved": raw.total_ok,
                         "score": round(score_of(e), 3),
                         "mean_attempts": round(e.att_ok / e.ok, 2) if e.ok > 0.05 else None,
                         "mean_seconds": round(e.sec / e.n, 1) if e.n > 0.05 else None,
                         "lean_errors": round(e.lean_err, 1), "pauses": round(e.pauses, 1),
                         "last_success": raw.last_ok or None, "updated": raw.t or None})
        rows.sort(key=lambda r: (r["task"], r["domain"], -r["score"], -r["solved"]))
        return rows

    def top(self, task: str, domain: str | None = None, k: int = 2, among: list[str] | None = None) -> list[str]:
        keys = among if among is not None else sorted({x.split("|", 1)[0] for x in self.entries})
        return sorted(keys, key=lambda m: -self.score(m, task, domain))[:k]


def explain(e: Entry, task: str, domain: str | None, lang: str = "fr") -> str:
    ok, n = e.total_ok, e.total
    if lang == "en":
        s = TASK_EN.get(task, "solved {ok}/{n} tasks").format(ok=ok, n=n)
        if domain and DOMAIN_EN.get(domain):
            s = s.replace(" problems", f" {DOMAIN_EN[domain]} problems")
        s += " here"
        if e.ok > 0.05:
            s += f", {e.att_ok / e.ok:.1f} attempts on average"
        if e.pauses >= 1:
            s += f", unavailable {e.pauses:.0f}×"
        return s
    s = TASK_FR.get(task, "réussi {ok}/{n} tâches").format(ok=ok, n=n)
    if domain and DOMAIN_FR.get(domain):
        s += " " + DOMAIN_FR[domain]
    s = "a " + s + " ici"
    if e.ok > 0.05:
        s += f", {e.att_ok / e.ok:.1f} essais en moyenne"
    if e.pauses >= 1:
        s += f", indisponible {e.pauses:.0f}×"
    return s
