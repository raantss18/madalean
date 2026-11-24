"""« Ce que Madalean a appris » — learning from mistakes without training any model (session S-AY, D57b).

A small local store of lessons, fed automatically by verified work and keyed by normalised signatures (never by
model), so that whichever model runs next profits from them:

- `rename`   — a Mathlib name Lean did not know (« unknown identifier / constant ») → the name the verified proof
               used instead, per Lean / Mathlib version. Exact lessons are applied WITHOUT a model (the code is
               rewritten and Lean re-checks it).
- `fix`      — a Lean error pattern (normalised message) on a statement shape → what the verified proof did
               differently (the tactics added), learned only from a verified success after that error.
- `approach` — an approach that failed on a statement shape → the reason (from the problem graph).
- `interpretation` — a « mal compris » report of the user (D65): the words of the problem, what was wrong and the user's
               words; given as data to the understand / translate prompts for similar problems.
- `split`    — a decomposition whose parts and combination Lean accepted, by statement shape (D67).
- `strategy` — which strategy / tactic family succeeded on a statement shape (counts).

Hygiene: every lesson carries evidence (dossier, date, workspace, Lean / Mathlib versions), success / failure
counters; a lesson that stops helping (failures ≫ successes) or whose Mathlib version is gone decays and is dropped;
the store is bounded (`MAX_LESSONS`); it is visible, deletable, exportable and importable (Réglages). Retrieval is a
cheap lexical / shape match with a bounded, deterministic text (stable prefix for prompt caching)."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

from .. import config, leancheck

KINDS = ("rename", "fix", "approach", "strategy", "interpretation", "split")
FADE_AFTER = 6                 # times given to a model without one success: the lesson leaves the hints
MAX_INTERPRETATIONS = 80
MAX_LESSONS = 400
MAX_EVIDENCE = 5
HINT_CHARS = 900
DECAY_DAYS = 120
_IDENT = r"[A-Za-z_][A-Za-z0-9_'.]*"
UNKNOWN_RE = re.compile(r"unknown (?:identifier|constant)\s+(['‘`«]?)(" + _IDENT + r")")


def unknown_names(error: str) -> list[str]:
    """Names Lean did not know, from its messages (the closing quote is not part of the name)."""
    out = []
    for q, name in UNKNOWN_RE.findall(error or ""):
        if q and name.endswith(("'", "’")):
            name = name[:-1]
        out.append(name.rstrip("."))
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- signatures
def shape_of(statement: str) -> str:
    """A statement's shape: its conclusion with names → `x`, numbers → `#` (model- and name-independent)."""
    text = leancheck.remove_comments(statement or "")
    text = re.sub(r":=\s*by\b.*$", "", text, flags=re.S)
    m = list(re.finditer(r"\)\s*:\s*|\}\s*:\s*|^\s*theorem\s+\S+\s*:\s*", text, re.M))
    concl = text[m[-1].end():] if m else text
    concl = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_']*\b", lambda k: k.group(0) if "." in k.group(0) or k.group(0)[0].isupper()
                   else "x", concl)
    concl = re.sub(r"\d+", "#", concl)
    return re.sub(r"\s+", " ", concl).strip()[:200]


def domain_of(statement: str) -> list[str]:
    s = statement or ""
    out = [t for t, pat in (("nat", "ℕ|Nat"), ("int", "ℤ|Int"), ("rat", "ℚ"), ("real", "ℝ|Real"), ("complex", "ℂ"),
                            ("set", r"\bSet\b|Finset"), ("sum", "∑|∏"), ("div", "∣|%"), ("ineq", "≤|<|≥|>"),
                            ("prime", "Prime"), ("poly", "Polynomial"), ("func", "→")) if re.search(pat, s)]
    return out or ["other"]


def error_pattern(error: str) -> str:
    """Normalised first error message (names, numbers and positions removed)."""
    first = next((ln for ln in (error or "").splitlines() if ln.strip() and "error" in ln.lower()), "") or \
        next((ln for ln in (error or "").splitlines() if ln.strip()), "")
    first = re.sub(r"^.*?error:\s*", "", first)
    first = re.sub(r"['‘`«][^'’`»]*['’`»]", "'_'", first)
    first = re.sub(r"\d+", "#", first)
    return re.sub(r"\s+", " ", first).strip().lower()[:160]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z][A-Za-z0-9_.']+|[ℕℤℚℝℂ∑∏∣≤≥<>%^]", text or ""))


def _id(*parts: str) -> str:
    return "ls-" + hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:14]


# ---------------------------------------------------------------- store
class Lessons:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.items: dict[str, dict] = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for x in data.get("lessons", []):
                if isinstance(x, dict) and x.get("kind") in KINDS and x.get("id"):
                    self.items[x["id"]] = x
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        with self._lock:
            self._gc()
            config.atomic_write_text(self.path, json.dumps({"v": 1, "lessons": list(self.items.values())},
                                                           ensure_ascii=False, indent=1))

    def _gc(self) -> None:
        now = time.time()
        for k, x in list(self.items.items()):
            stale = now - float(x.get("updated", now)) > DECAY_DAYS * 86400 and int(x.get("ok", 0)) <= 1
            useless = int(x.get("bad", 0)) >= 3 and int(x.get("bad", 0)) > 2 * int(x.get("ok", 0))
            idle = int(x.get("shown", 0)) >= 2 * FADE_AFTER and not int(x.get("shown_ok", 0))
            if stale or useless or idle:
                self.items.pop(k, None)
        if len(self.items) > MAX_LESSONS:
            keep = sorted(self.items.values(), key=lambda x: (self.value(x), x.get("updated", 0)), reverse=True)
            self.items = {x["id"]: x for x in keep[:MAX_LESSONS]}

    @staticmethod
    def value(x: dict) -> float:
        v = (int(x.get("ok", 0)) + 1) / (int(x.get("bad", 0)) + 2)
        shown, won = int(x.get("shown", 0)), int(x.get("shown_ok", 0))
        return v * (2 + won) / (2 + shown) if shown > won else v      # given often, rarely with a success: fades

    @staticmethod
    def faded(x: dict) -> bool:
        return int(x.get("shown", 0)) >= FADE_AFTER and not int(x.get("shown_ok", 0))

    def outcome(self, ids: list[str], ok: bool) -> None:
        """D67: these lessons were in a prover's context; the search succeeded or not. An association, not a proof of
        usefulness: it only makes lessons that never go with a success fade."""
        hit = [self.items[i] for i in dict.fromkeys(ids) if i in self.items]
        for x in hit:
            x["shown"] = min(10_000, int(x.get("shown", 0)) + 1)
            x["shown_ok"] = min(10_000, int(x.get("shown_ok", 0)) + bool(ok))
        if hit:
            self.save()

    def _upsert(self, lid: str, base: dict, evidence: dict) -> dict:
        x = self.items.get(lid)
        now = time.time()
        if x is None:
            x = {**base, "id": lid, "ok": 0, "bad": 0, "used": 0, "evidence": [], "created": now}
            self.items[lid] = x
        x["ok"] = int(x.get("ok", 0)) + 1
        x["updated"] = now
        ev = {k: str(v)[:120] for k, v in evidence.items() if v}
        ev["t"] = now
        x["evidence"] = ([e for e in x["evidence"] if e.get("dossier") != ev.get("dossier")] + [ev])[-MAX_EVIDENCE:]
        return x

    # -- learning (only from verified results, or recorded failure reasons)
    def learn_fix(self, failing_code: str, error: str, passing_code: str, statement: str, env: dict,
                  dossier: str = "") -> list[dict]:
        """A proof that Lean accepted after `error` on `failing_code`: renames (unknown names replaced by the
        name the verified proof used) and the tactics that made the difference."""
        out = []
        ev = {"dossier": dossier, "workspace": env.get("workspace", ""), "lean": env.get("lean", ""),
              "mathlib": env.get("mathlib", "")}
        good = _tokens(passing_code)
        for bad in unknown_names(error):
            if bad in good:
                continue
            new = _closest(bad, (good - _tokens(failing_code)) or good)
            if new:
                out.append(self._upsert(_id("rename", bad, env.get("mathlib", "")), {
                    "kind": "rename", "old": bad, "new": new, "mathlib": env.get("mathlib", ""),
                    "lean": env.get("lean", ""), "workspace": env.get("workspace", "")}, ev))
        pat = error_pattern(error)
        if pat and not out:
            from .proofgraph import tactics_of
            added = [t for t in tactics_of(passing_code) if t not in set(tactics_of(failing_code))][:6]
            if added:
                out.append(self._upsert(_id("fix", pat, shape_of(statement)), {
                    "kind": "fix", "pattern": pat, "shape": shape_of(statement), "domain": domain_of(statement),
                    "tactics": added}, ev))
        if out:
            self.save()
        return out

    def learn_strategy(self, statement: str, strategy: str, tactics: list[str], env: dict, dossier: str = "") -> dict:
        ev = {"dossier": dossier, "workspace": env.get("workspace", ""), "mathlib": env.get("mathlib", "")}
        fam = sorted(set(tactics))[:6]
        x = self._upsert(_id("strategy", shape_of(statement), strategy), {
            "kind": "strategy", "shape": shape_of(statement), "domain": domain_of(statement), "strategy": strategy,
            "tactics": fam}, ev)
        x["tactics"] = sorted(set(x.get("tactics", [])) | set(fam))[:10]
        self.save()
        return x

    def learn_approach(self, statement: str, approach: str, reason: str, env: dict, dossier: str = "") -> dict:
        ev = {"dossier": dossier, "workspace": env.get("workspace", ""), "mathlib": env.get("mathlib", "")}
        x = self._upsert(_id("approach", shape_of(statement), approach[:120]), {
            "kind": "approach", "shape": shape_of(statement), "domain": domain_of(statement),
            "approach": approach[:200], "reason": reason[:300]}, ev)
        self.save()
        return x

    def learn_split(self, statement: str, pattern: str, parts: list[str], env: dict, dossier: str = "") -> dict:
        """A decomposition that led to a verified proof."""
        ev = {"dossier": dossier, "workspace": env.get("workspace", ""), "mathlib": env.get("mathlib", "")}
        x = self._upsert(_id("split", shape_of(statement), pattern), {
            "kind": "split", "shape": shape_of(statement), "domain": domain_of(statement), "pattern": pattern[:20],
            "parts": [shape_of(p)[:120] for p in parts[:6]]}, ev)
        self.save()
        return x

    def learn_interpretation(self, problem: str, target: str, reason: str, text: str, dossier: str = "") -> dict:
        """What the user reported as misunderstood. His words are data (never instructions)."""
        words = sorted(_problem_words(problem))[:24]
        x = self._upsert(_id("interpretation", " ".join(words), target, reason, text[:200]), {
            "kind": "interpretation", "problem": re.sub(r"\s+", " ", problem).strip()[:300], "words": words,
            "target": target[:20], "reason": reason[:40], "text": re.sub(r"\s+", " ", text).strip()[:400]},
            {"dossier": dossier})
        mine = sorted((y for y in self.items.values() if y["kind"] == "interpretation"),
                      key=lambda y: float(y.get("updated", 0)))
        for y in mine[:max(0, len(mine) - MAX_INTERPRETATIONS)]:
            self.items.pop(y["id"], None)
        self.save()
        return x

    def interpretation_hint(self, problem: str, k: int = 3) -> str:
        """Reports on similar problems, for the understand / translate prompts ("" when none)."""
        from .safety import UNTRUSTED_RULE, wrap_untrusted
        mine = _problem_words(problem)
        scored = []
        for x in self.items.values():
            if x["kind"] != "interpretation":
                continue
            ws = {str(w) for w in x.get("words") or []}
            s = len(mine & ws) / max(1, len(mine | ws))
            if mine and (mine == ws or len(mine & ws) >= 2 and s >= 0.5):
                scored.append((-round(s, 3), x["id"], x))
        if not scored:
            return ""
        lines = [f"- problem « {str(x.get('problem', ''))[:160]} »: {x.get('target')} was wrong ({x.get('reason')})"
                 + (f"; the user said: {str(x['text'])[:240]}" if x.get("text") else "")
                 for _s, _i, x in sorted(scored, key=lambda t: t[:2])[:k]]
        return ("Earlier misunderstandings on similar problems, reported by the user; do not repeat them. "
                + UNTRUSTED_RULE + "\n" + wrap_untrusted("\n".join(lines)[:HINT_CHARS], "reports"))

    def feedback(self, lid: str, helped: bool) -> None:
        x = self.items.get(lid)
        if x is None:
            return
        x["used"] = int(x.get("used", 0)) + 1
        if helped:
            x["ok"] = int(x.get("ok", 0)) + 1
        else:
            x["bad"] = int(x.get("bad", 0)) + 1
        x["updated"] = time.time()
        self.save()

    # -- use
    def renames(self, env: dict) -> dict[str, tuple[str, str]]:
        """Exact rename lessons for this Mathlib version: {old: (new, lesson id)}."""
        out = {}
        for x in self.items.values():
            if x["kind"] == "rename" and x.get("mathlib", "") == env.get("mathlib", "") and \
                    self.value(x) >= 0.5:
                out[x["old"]] = (x["new"], x["id"])
        return out

    def apply_renames(self, code: str, env: dict) -> tuple[str, list[str]]:
        """Rewrite known-bad names (whole identifiers only). Returns (code, lesson ids used)."""
        used = []
        for old, (new, lid) in sorted(self.renames(env).items()):
            pat = re.compile(r"(?<![\w.'])" + re.escape(old) + r"(?![\w'])")
            if pat.search(code):
                code = pat.sub(new, code)
                used.append(lid)
        return code, used

    def relevant(self, statement: str, env: dict, k: int = 5) -> list[dict]:
        shape, dom, toks = shape_of(statement), set(domain_of(statement)), _tokens(statement)
        scored = []
        for x in self.items.values():
            if x["kind"] == "interpretation" or self.faded(x):
                continue                      # about words, not about Lean: `interpretation_hint`
            if x["kind"] == "rename":
                if x.get("mathlib", "") != env.get("mathlib", ""):
                    continue
                s = 0.6
            else:
                s = 0.0
                if x.get("shape") == shape:
                    s += 1.0
                s += 0.3 * len(dom & set(x.get("domain") or [])) / max(1, len(dom))
                s += 0.4 * len(_tokens(x.get("shape", "")) & toks) / max(1, len(toks))
            s *= self.value(x)
            if s >= 0.25:
                scored.append((round(s, 3), x["id"], x))
        return [x for _s, _i, x in sorted(scored, key=lambda t: (-t[0], t[1]))[:k]]

    def hint(self, statement: str, env: dict, max_chars: int = HINT_CHARS, ids: list | None = None) -> str:
        rel = sorted(self.relevant(statement, env), key=lambda x: x["id"])      # stable order (prompt caching)
        lines, of = [], []
        for x in rel:
            before = len(lines)
            if x["kind"] == "rename":
                lines.append(f"- `{x['old']}` does not exist in this Mathlib; use `{x['new']}`.")
            elif x["kind"] == "fix":
                lines.append(f"- After the Lean error « {x['pattern'][:100]} » on this shape, a verified proof used: "
                             + ", ".join(x.get("tactics") or []) + ".")
            elif x["kind"] == "approach":
                lines.append(f"- Failed before on this shape: {x['approach'][:100]} — {x['reason'][:140]}.")
            elif x["kind"] == "strategy":
                lines.append(f"- Worked on this shape: {x['strategy']} ({', '.join(x.get('tactics') or [])}).")
            elif x["kind"] == "split":
                lines.append(f"- This shape was proved by a split ({x.get('pattern', '')}): "
                             + "; ".join(x.get("parts") or ["lemmas"])[:200] + ".")
            of += [x["id"]] * (len(lines) - before)
        out, used = [], 0
        for ln in lines:
            if used + len(ln) > max_chars:
                break
            out.append(ln)
            used += len(ln) + 1
        if ids is not None:
            ids += of[:len(out)]
        return ("Lessons from earlier verified work (Madalean):\n" + "\n".join(out)) if out else ""

    def error_hint(self, feedback: str, env: dict) -> str:
        """Extra line for a Lean error the store already knows (« use X instead of Y »)."""
        rn = self.renames(env)
        tips = [f"`{b}` → `{rn[b][0]}`" for b in unknown_names(feedback) if b in rn]
        return ("\nKnown renames (Madalean lessons): " + ", ".join(tips)) if tips else ""

    # -- settings screen
    def list(self) -> list[dict]:
        return sorted(self.items.values(), key=lambda x: -float(x.get("updated", 0)))

    def delete(self, lid: str) -> bool:
        ok = self.items.pop(lid, None) is not None
        if ok:
            self.save()
        return ok

    def clear(self) -> int:
        n = len(self.items)
        self.items = {}
        self.save()
        return n

    def export(self) -> dict:
        return {"v": 1, "kind": "madalean-lessons", "exported": time.time(), "lessons": self.list()}

    def import_(self, data: dict) -> int:
        if not isinstance(data, dict) or data.get("kind") != "madalean-lessons":
            raise ValueError("not a Madalean lessons file")
        n = 0
        for x in data.get("lessons") or []:
            if not isinstance(x, dict) or x.get("kind") not in KINDS:
                continue
            clean = {k: v for k, v in x.items() if isinstance(v, (str, int, float, list, dict)) and len(str(v)) < 4000}
            if x["kind"] == "rename" and not (re.fullmatch(_IDENT, str(clean.get("old", ""))) and
                                              re.fullmatch(_IDENT, str(clean.get("new", "")))):
                continue                      # a rename rewrites code: only plain identifiers are accepted
            lid = str(clean.get("id") or _id(json.dumps(clean, sort_keys=True)))[:40]
            if lid not in self.items:
                clean["id"] = lid
                clean.setdefault("ok", 1)
                clean.setdefault("bad", 0)
                clean["imported"] = time.time()
                self.items[lid] = clean
                n += 1
        self.save()
        return n


_COMMON = set("que les des une est sont dans pour par sur avec tout tous toute alors soit montrer prouver demontrer the "
              "that for all and with then prove show let are its this from such".split())


def _problem_words(problem: str) -> set[str]:
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFKD", (problem or "").lower()) if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z]{3,}|\d+", t) if w not in _COMMON}


def _closest(bad: str, candidates: set[str]) -> str:
    import difflib
    tail = bad.rsplit(".", 1)[-1]
    best, score = "", 0.0
    for c in candidates:
        if "." not in c and "." in bad:
            continue
        s = max(difflib.SequenceMatcher(None, bad, c).ratio(),
                difflib.SequenceMatcher(None, tail, c.rsplit(".", 1)[-1]).ratio())
        if s > score:
            best, score = c, s
    return best if score >= 0.6 else ""


def store_of(ctx) -> Lessons | None:
    """The host's lesson store (created on first use), or None when learning is off."""
    if not getattr(ctx.settings, "lessons", True):
        return None
    st = getattr(ctx, "_lessons", None)
    if st is None:
        st = Lessons(ctx.paths.config / "research" / "lessons.json")
        ctx._lessons = st
    return st
