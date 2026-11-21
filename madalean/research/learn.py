"""Learning support for the UI's « Apprendre » mode (ARCHITECTURE §13) — session S-G.

Grounded in Lean's verdict, no gamification. Pedagogy (installed skills `education-agent-skills:*`):
- retrieve-first gate: before the first hint the learner writes an attempt (and a 0–100 confidence);
- progressive hint ladder, 5 levels: 1 nudge → 2 strategy → 3 key lemma → 4 next step → 5 full proof. Generated
  lazily, cached per proof version, levels revealed in order; from level 3 on the learner first says what the last
  hint told them (reflection requirement). Each generated level goes through a leak detector built from the verified
  proof (level k must not give away level k+1); a leaking answer is regenerated once, then redacted. Level 5 is the
  Lean-verified proof itself (never model text). Deviation from the skill, by the architecture's decision: the ladder
  ends with the full proof (the skill never gives it).
- tactic / declaration explanations: tactics from a curated table; declarations only through the retriever
  (signature + docstring); an unknown name is reported unknown, with close names, never invented;
- « explain it back » (self-explanation): the brain grades the learner's explanation against the verified proof with
  a rubric and names the precise gap without revealing the rest (leak-checked);
- faded exercises (worked-example fading, from the end of the proof backwards): k tactic blocks removed; generation
  verifies with Lean that the proof with the original blocks compiles (strict) and that each blank is non-trivial
  (a battery of automatic tactics does not fill it); the learner's answer is checked by Lean for real;
- erroneous examples: one plausible wrong step (lemma swap, argument swap, tactic swap, dropped step) that Lean
  really rejects; Lean's error is the ground truth, shown after the learner's diagnosis;
- per-device progress log on the server, published as `learn.progress`."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from .. import config, leancheck
from ..i18n import language, msg

MARK = "[madalean:learn]"
LEVELS = {1: "nudge", 2: "strategy", 3: "key_lemma", 4: "next_step", 5: "full_proof"}
TRIVIAL = "first | rfl | trivial | decide | assumption | (simp; done) | omega | (norm_num; done) | linarith | aesop"

TACTICS = {
    "omega": ("Arithmétique linéaire sur ℕ et ℤ (avec +, −, constantes, ≤, <, =, %, / par une constante) : décide "
              "complètement ces buts.", "Linear arithmetic over ℕ and ℤ (+, −, constants, ≤, <, =, % and / by a "
              "constant): decides such goals completely."),
    "rcases": ("Déstructure une hypothèse (∃, ∧, ∨, égalités) selon un motif : `rcases h with ⟨k, hk⟩` extrait un "
               "témoin.", "Destructures a hypothesis (∃, ∧, ∨, equalities) by a pattern: `rcases h with ⟨k, hk⟩` "
               "extracts a witness."),
    "obtain": ("Comme rcases, mais écrit « obtain ⟨k, hk⟩ := h ».", "Like rcases, written « obtain ⟨k, hk⟩ := h »."),
    "simp": ("Réécrit le but avec les lemmes marqués @[simp] (et ceux donnés entre crochets) jusqu'à simplification.",
             "Rewrites the goal with the @[simp] lemmas (and those given in brackets) until it is simplified."),
    "norm_num": ("Calcule et décide des égalités/inégalités numériques (et la primalité de petits nombres).",
                 "Evaluates and decides numeric (in)equalities (and primality of small numbers)."),
    "linarith": ("Prouve un but linéaire (≤, <, =) à partir d'hypothèses linéaires, sur un corps ordonné.",
                 "Proves a linear goal (≤, <, =) from linear hypotheses over an ordered field."),
    "nlinarith": ("linarith avec des produits d'hypothèses : inégalités polynomiales simples.",
                  "linarith with products of hypotheses: simple polynomial inequalities."),
    "ring": ("Prouve une égalité dans un anneau commutatif en normalisant les deux côtés.",
             "Proves an equality in a commutative ring by normalising both sides."),
    "exact": ("Ferme le but avec un terme qui a exactement le type demandé.",
              "Closes the goal with a term of exactly the required type."),
    "apply": ("Applique un lemme dont la conclusion correspond au but ; ses hypothèses deviennent de nouveaux buts.",
              "Applies a lemma whose conclusion matches the goal; its hypotheses become new goals."),
    "intro": ("Introduit une hypothèse ou une variable (pour un but ∀ ou →).",
              "Introduces a hypothesis or variable (for a ∀ or → goal)."),
    "intros": ("Introduit toutes les variables et hypothèses possibles.", "Introduces all variables and hypotheses."),
    "induction": ("Raisonnement par récurrence sur une variable (cas de base, puis hérédité).",
                  "Proof by induction on a variable (base case, then inductive step)."),
    "cases": ("Distinction de cas sur une donnée inductive (ℕ : 0 ou n+1 ; ∨ : gauche ou droite).",
              "Case analysis on inductive data (ℕ: 0 or n+1; ∨: left or right)."),
    "rw": ("Réécrit le but avec une égalité (ou équivalence) : `rw [h]` remplace le côté gauche par le droit.",
           "Rewrites the goal with an equality (or iff): `rw [h]` replaces the left side by the right side."),
    "use": ("Donne le témoin d'un but ∃.", "Provides the witness of an ∃ goal."),
    "constructor": ("Découpe un but ∧ ou ↔ en ses deux parties.", "Splits an ∧ or ↔ goal into its two parts."),
    "refine": ("Comme exact, avec des trous `?_` qui deviennent de nouveaux buts.",
               "Like exact, with holes `?_` that become new goals."),
    "have": ("Prouve un résultat intermédiaire et l'ajoute aux hypothèses.",
             "Proves an intermediate result and adds it to the hypotheses."),
    "show": ("Précise (sous une forme équivalente) le but courant.", "Restates the current goal in an equivalent form."),
    "calc": ("Chaîne d'égalités/inégalités justifiées pas à pas.", "A chain of (in)equalities justified step by step."),
    "decide": ("Évalue une proposition décidable (calcul exécuté par le noyau).",
               "Evaluates a decidable proposition (computation run by the kernel)."),
    "field_simp": ("Chasse les dénominateurs (avec des hypothèses de non-nullité).",
                   "Clears denominators (given non-zero hypotheses)."),
    "positivity": ("Prouve qu'une expression est positive / strictement positive / non nulle.",
                   "Proves that an expression is non-negative / positive / non-zero."),
    "aesop": ("Recherche automatique de preuve (règles simp, constructeurs, hypothèses).",
              "Automatic proof search (simp rules, constructors, hypotheses)."),
    "simpa": ("simp sur le but et sur l'hypothèse donnée, puis les fait coïncider.",
              "simp on the goal and on the given term, then closes the goal with it."),
    "exact?": ("Cherche un lemme de la bibliothèque qui ferme le but (interdit dans une preuve finale).",
               "Searches the library for a lemma closing the goal (not allowed in a final proof)."),
    "push_neg": ("Pousse les négations vers l'intérieur (¬∀ devient ∃¬…).", "Pushes negations inwards (¬∀ becomes ∃¬…)."),
    "by_contra": ("Raisonnement par l'absurde : suppose la négation du but.", "Proof by contradiction: assumes the "
                  "negation of the goal."),
    "contradiction": ("Ferme le but quand les hypothèses sont contradictoires.",
                      "Closes the goal when the hypotheses are contradictory."),
    "gcongr": ("Prouve une inégalité « par congruence » (même forme des deux côtés).",
               "Proves an inequality « by congruence » (same shape on both sides)."),
    "subst": ("Remplace une variable par sa valeur grâce à une égalité `x = e`.",
              "Substitutes a variable using an equality `x = e`."),
    "unfold": ("Déplie une définition.", "Unfolds a definition."),
    "exfalso": ("Remplace le but par False.", "Replaces the goal by False."),
    "trivial": ("Essaie quelques tactiques simples (rfl, assumption, True.intro…).",
                "Tries a few simple tactics (rfl, assumption, True.intro…)."),
    "rfl": ("Ferme un but `a = a` (égalité par définition).", "Closes a goal `a = a` (definitional equality)."),
}


class LearnError(Exception):
    def __init__(self, kind: str, status: int = 400, key: str = "", **data):
        super().__init__(kind)
        self.kind, self.status, self.key, self.data = kind, status, key, data


# ---------------------------------------------------------------- proof anatomy
def split_proof(proof: str) -> tuple[str, str, list[str]]:
    """(prefix up to and including `:= by`, target signature line(s), tactic body lines) of the LAST theorem."""
    starts = [m.start() for m in re.finditer(r"(?m)^theorem\s", proof)]
    if not starts:
        raise LearnError("no_proof", 409)
    head, tail = proof[:starts[-1]], proof[starts[-1]:]
    m = re.search(r":=\s*by\b", tail)
    if not m:
        raise LearnError("term_proof", 422, "Preuve sans « by » : pas d'exercice possible.")
    sig, body = tail[:m.end()], tail[m.end():]
    lines = body.split("\n")
    if lines and not lines[0].strip():
        lines = lines[1:]
    elif lines:                                         # `:= by tac` on one line
        lines[0] = "  " + lines[0].strip()
    while lines and not lines[-1].strip():
        lines.pop()
    return head, sig, lines


def tactic_blocks(lines: list[str]) -> list[list[int]]:
    """Top-level tactic blocks: a line at the minimal indentation starts a block, deeper lines continue it."""
    idx = [i for i, ln in enumerate(lines) if ln.strip() and not ln.strip().startswith("--")]
    if not idx:
        return []
    base = min(len(lines[i]) - len(lines[i].lstrip()) for i in idx)
    blocks: list[list[int]] = []
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        ind = len(ln) - len(ln.lstrip())
        if ind == base or not blocks:
            blocks.append([i])
        else:
            blocks[-1].append(i)
    return blocks


IDENT_RE = re.compile(r"(?<![\w.'])([A-Za-z_][\w']*(?:\.[A-Za-z_][\w']*)+)")


def answer_key(proof: str) -> dict:
    """What a hint must not give away too early, from the verified proof."""
    _h, _s, lines = split_proof(proof)
    body = "\n".join(lines)
    clean = leancheck.remove_comments(body)
    lemmas = sorted(set(IDENT_RE.findall(clean)))
    tactics = sorted({w for w in re.findall(r"(?<![\w.])([a-z_][\w?!]*)", clean) if w in TACTICS})
    norm = [re.sub(r"\s+", " ", ln.strip().lstrip("·").strip()) for ln in clean.split("\n") if ln.strip()]
    return {"lemmas": lemmas, "tactics": tactics, "lines": [ln for ln in norm if len(ln) >= 6]}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def leaks(level: int, text: str, key: dict, allowed: str = "") -> list[str]:
    """Items of the answer key that `text` reveals although level `level` must not (allowed: text the learner
    already wrote, e.g. their explanation, whose content may be repeated)."""
    t, ok = _norm(text), _norm(allowed)
    found = []
    nlines = len(key["lines"])
    proof_lines = [ln for ln in key["lines"] if ln in t and ln not in ok]
    if level <= 3 and proof_lines:
        found += [f"line:{ln}" for ln in proof_lines]
    if level == 4:
        cap = max(0, (nlines + 1) // 2) if nlines >= 2 else 0
        if len(proof_lines) > cap:
            found += [f"line:{ln}" for ln in proof_lines[cap:]]
    if level <= 2:
        found += [f"lemma:{x}" for x in key["lemmas"] if re.search(rf"(?<![\w.]){re.escape(x)}(?![\w'])", t)
                  and x not in ok]
    if level == 3:
        named = [x for x in key["lemmas"] if re.search(rf"(?<![\w.]){re.escape(x)}(?![\w'])", t) and x not in ok]
        if len(named) > 1:
            found += [f"lemma:{x}" for x in named[1:]]
    if level <= 1:
        found += [f"tactic:{x}" for x in key["tactics"] if re.search(rf"`{re.escape(x)}\b", t)]
    return found


def redact(text: str, items: list[str]) -> str:
    for it in sorted(items, key=len, reverse=True):
        val = it.split(":", 1)[1]
        text = text.replace(val, "…")
        text = re.sub(r"\s+".join(re.escape(p) for p in val.split(" ")), "…", text)
    return text


# ---------------------------------------------------------------- prompts
LEVEL_RULES = {
    1: "Level 1 — NUDGE: one or two sentences, a question that points toward the key idea without naming any lemma, "
       "tactic or step. No Lean code.",
    2: "Level 2 — STRATEGY: the overall approach in plain mathematics (e.g. induction on n, case analysis, unfold a "
       "definition, a known identity), without naming any Mathlib lemma and without any Lean line.",
    3: "Level 3 — KEY LEMMA: name the ONE key lemma or fact (Mathlib name allowed, only one) and ask how it connects "
       "to the goal. Do not show how to apply it, no Lean line of the proof.",
    4: "Level 4 — NEXT STEP: the very next step only (at most the first tactic line, or a skeleton with `_` holes). "
       "Do not write the rest of the proof.",
}


def hint_messages(d, level: int, previous: list[str], lang: str) -> list[dict]:
    lg = "French" if lang == "fr" else "English"
    prev = "\n".join(f"Level {i + 1}: {h}" for i, h in enumerate(previous)) or "(none)"
    return [{"role": "user", "content": (
        f"{MARK} task=hint level={level}\nYou are a patient mathematics and Lean tutor. A learner tries to prove the "
        f"theorem below. A verified Lean proof exists (given to you only so that your hint is correct). Write ONLY "
        f"the hint of the requested level, in {lg}, formulas in LaTeX between $...$.\n{LEVEL_RULES[level]}\n"
        f"Never reveal the content of a later level.\nTheorem: {d.understood_display or d.problem or d.title}\n"
        f"Lean statement:\n```lean\n{d.statement}\n```\nVerified proof (SECRET, do not copy it):\n```lean\n{d.proof}\n"
        f"```\nHints already given:\n{prev}")}]


def explain_back_messages(d, text: str, lang: str, target: str = "proof", previous: list[str] | None = None) -> list[dict]:
    lg = "French" if lang == "fr" else "English"
    prev = ("\nPrevious exchanges:\n" + "\n".join(str(x)[:2000] for x in previous[-6:])) if previous else ""
    if target == "statement":
        return [{"role": "user", "content": (
            f"{MARK} task=explain_back target=statement\nA learner explains in their own words what the Lean statement "
            "below says. Grade it with a rubric of 3 to 5 criteria (objects and their types, hypotheses, conclusion, "
            "quantifiers). For each criterion: met (true/false) and the learner's words that show it. Then name the "
            "single most important GAP and ask ONE question that leads to it, without rewriting the explanation. "
            f"Write in {lg}. Answer with JSON only: {{\"criteria\": [{{\"criterion\": …, \"met\": …, \"evidence\": …}}], "
            f"\"gap\": …, \"question\": …}}\nLean statement:\n```lean\n{d.statement}\n```{prev}\n\n"
            f"Learner's explanation:\n{text}")}]
    return [{"role": "user", "content": (
        f"{MARK} task=explain_back\nA learner explains in their own words why the theorem below is true. Grade the "
        "explanation against the verified proof with a rubric of 3 to 5 criteria (the essential ideas of the proof). "
        "For each criterion: met (true/false) and the learner's words that show it. Then name the single most "
        "important GAP precisely (what is missing or wrong) WITHOUT giving the missing idea away: ask a question "
        f"that leads to it. Write in {lg}. Answer with JSON only: {{\"criteria\": [{{\"criterion\": …, \"met\": …, "
        "\"evidence\": …}], \"gap\": …, \"question\": …}}\n"
        f"Theorem: {d.understood_display or d.problem or d.title}\nVerified proof (SECRET):\n```lean\n{d.proof}\n```\n"
        f"Natural-language proof (SECRET): {d.informal_proof or d.explanation}{prev}\n\nLearner's explanation:\n{text}")}]


# ---------------------------------------------------------------- store
class LearnStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.root / "progress.json"
        self._progress = config.read_json(self.progress_file)[0] or {}
        self._docs: dict[str, dict] = {}

    def doc(self, did: str) -> dict:
        if did not in self._docs:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", did):
                raise LearnError("bad_id")
            self._docs[did] = config.read_json(self.root / f"{did}.json")[0] or {"hints": {}, "exercises": {}}
        return self._docs[did]

    def save_doc(self, did: str) -> None:
        config.atomic_write_text(self.root / f"{did}.json", json.dumps(self.doc(did), ensure_ascii=False, indent=1))

    def log(self, device: str, entry: dict) -> dict:
        entry = {"t": time.time(), **entry}
        self._progress.setdefault(device, []).append(entry)
        self._progress[device] = self._progress[device][-5000:]
        config.atomic_write_text(self.progress_file, json.dumps(self._progress, ensure_ascii=False))
        return entry

    def progress(self, device: str, dossier: str | None = None) -> list[dict]:
        out = self._progress.get(device, [])
        return [e for e in out if dossier is None or e.get("dossier") == dossier]


# ---------------------------------------------------------------- tutor
class Tutor:
    def __init__(self, ctx, store: LearnStore):
        self.ctx, self.store = ctx, store
        self.locks: dict[str, asyncio.Lock] = {}

    def _proved(self, did: str):
        d = self.ctx.repo.get(did)
        if d is None:
            raise LearnError("not_found", 404)
        if not d.proof_is_current:
            raise LearnError("not_proved", 409, "Le mode Apprendre demande une preuve vérifiée par Lean.")
        return d

    def _log(self, device: str, entry: dict) -> dict:
        e = self.store.log(device, entry)
        self.ctx.publish("learn.progress", {"device": device, "entry": e})
        return e

    async def _complete(self, messages, owner: str, max_tokens: int = 1200):
        from ..server.helpers import complete_once
        return await complete_once(self.ctx, "explain", messages, self.ctx.settings.mode, owner=owner,
                                   max_tokens=max_tokens, temperature=0.4)

    # -- retrieve-first gate + hint ladder
    def attempt(self, did: str, device: str, text: str, confidence: int | None) -> dict:
        self._proved(did)
        if len((text or "").strip()) < 3:
            raise LearnError("empty", 400, "Écrivez d'abord ce que vous avez essayé, même partiel.")
        conf = None if confidence is None else max(0, min(100, int(confidence)))
        return self._log(device, {"dossier": did, "kind": "attempt", "text": text[:4000], "confidence": conf})

    def ladder_state(self, did: str, device: str) -> dict:
        d = self._proved(did)
        prog = self.store.progress(device, did)
        cur = d.cur_proof
        revealed = sorted({e["level"] for e in prog if e["kind"] == "hint" and e.get("proof") == cur})
        attempted = any(e["kind"] == "attempt" for e in prog)
        cached = self.store.doc(did)["hints"].get(str(cur), {})
        return {"dossier": did, "proof": cur, "attempted": attempted, "revealed": revealed,
                "levels": {lv: name for lv, name in LEVELS.items()},
                "hints": {str(lv): cached[str(lv)] for lv in revealed if str(lv) in cached},
                "next": (max(revealed) + 1 if revealed else 1) if (not revealed or max(revealed) < 5) else None}

    async def hint(self, did: str, level: int, device: str, reflection: str = "") -> dict:
        d = self._proved(did)
        if level not in LEVELS:
            raise LearnError("bad_level")
        st = self.ladder_state(did, device)
        if not st["attempted"]:
            raise LearnError("attempt_first", 409, "Avant le premier indice : écrivez ce que vous avez essayé "
                                                   "(et votre confiance de 0 à 100).")
        if level > 1 and (level - 1) not in st["revealed"]:
            raise LearnError("in_order", 409, "Les indices se débloquent dans l'ordre.")
        if level >= 3 and level not in st["revealed"] and len((reflection or "").strip()) < 3:
            raise LearnError("reflect_first", 409, "Dites d'abord ce que l'indice précédent vous a appris.")
        cur = str(d.cur_proof)
        doc = self.store.doc(did)
        cache = doc["hints"].setdefault(cur, {})
        lk = self.locks.setdefault(did, asyncio.Lock())
        async with lk:
            for lv in range(1, level + 1):
                if str(lv) in cache:
                    continue
                cache[str(lv)] = await self._make_hint(d, lv, [cache[str(i)]["text"] for i in range(1, lv)])
                self.store.save_doc(did)
        if reflection.strip():
            self._log(device, {"dossier": did, "kind": "reflection", "level": level - 1, "text": reflection[:2000]})
        if level not in st["revealed"]:
            self._log(device, {"dossier": did, "kind": "hint", "level": level, "proof": d.cur_proof})
        return {"level": level, "name": LEVELS[level], **cache[str(level)]}

    async def _make_hint(self, d, level: int, previous: list[str]) -> dict:
        if level == 5:
            return {"text": "```lean\n" + d.proof.strip() + "\n```", "model": "", "source": "lean", "redacted": False,
                    "t": time.time()}
        key = answer_key(d.proof)
        found, text, model = [], "", ""
        for attempt in range(2):
            msgs = hint_messages(d, level, previous, language())
            if found:
                msgs.append({"role": "assistant", "content": text})
                msgs.append({"role": "user", "content": "Your hint reveals too much (" + ", ".join(
                    f.split(":", 1)[1] for f in found[:5]) + "). Rewrite it within the level's rules."})
            c = await self._complete(msgs, f"learn-{d.id}")
            text, model = leancheck.clean_model_text(c.text), c.model.key
            found = leaks(level, text, key)
            if not found:
                return {"text": text, "model": model, "source": "ai", "redacted": False, "t": time.time()}
        return {"text": redact(text, found), "model": model, "source": "ai", "redacted": True,
                "leaks": len(found), "t": time.time()}

    # -- tokens and declarations
    async def explain_token(self, name: str, workspace: str | None) -> dict:
        name = (name or "").strip()
        if not name or len(name) > 200:
            raise LearnError("empty")
        lang = 0 if language() == "fr" else 1
        if name in TACTICS:
            return {"name": name, "kind": "tactic", "known": True, "text": TACTICS[name][lang], "source": "madalean"}
        ws = workspace or self.ctx.settings.workspace
        r = self.ctx.retriever
        decl = None
        if r is not None:
            try:
                decl = await r.declaration(ws, name)
            except Exception:  # noqa: BLE001
                decl = None
        if decl:
            return {"name": decl.get("name", name), "kind": "declaration", "known": True,
                    "signature": decl.get("signature", ""), "doc": decl.get("doc", ""),
                    "module": decl.get("module", ""), "source": "retriever"}
        sugg = []
        if r is not None:
            try:
                sugg = [h.get("name") for h in (await r.search(ws, name.replace(".", " ").replace("_", " "), 5) or [])]
            except Exception:  # noqa: BLE001
                sugg = []
        return {"name": name, "kind": "unknown", "known": False, "suggestions": [s for s in sugg if s],
                **msg("« {name} » est inconnu de l'index des déclarations de cet espace de travail : aucune "
                      "explication n'est inventée.", name=name)}

    # -- explain it back
    async def explain_back(self, did: str, device: str, text: str, confidence: int | None = None,
                           target: str = "proof", previous: list[str] | None = None) -> dict:
        if target == "statement":
            d = self.ctx.repo.get(did)
            if d is None:
                raise LearnError("not_found", 404)
            if not d.statement:
                raise LearnError("no_statement", 409)
        else:
            d = self._proved(did)
        if len((text or "").strip()) < 10:
            raise LearnError("empty", 400, "Expliquez la preuve en quelques phrases.")
        msgs = explain_back_messages(d, text[:6000], language(), target, previous or [])
        c = await self._complete(msgs, f"learn-eb-{did}", 1500)
        raw = leancheck.clean_model_text(c.text)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except ValueError:
            data = {}
        crit = [x for x in (data.get("criteria") or []) if isinstance(x, dict)][:6]
        gap, question = str(data.get("gap", "")), str(data.get("question", ""))
        key = answer_key(d.proof) if d.proof_is_current else {"lemmas": [], "tactics": [], "lines": []}
        found = leaks(2, gap + "\n" + question, key, allowed=text)
        if found:
            gap, question = redact(gap, found), redact(question, found)
        met = sum(1 for x in crit if x.get("met") is True)
        res = {"criteria": [{"criterion": str(x.get("criterion", ""))[:300], "met": x.get("met") is True,
                             "evidence": str(x.get("evidence", ""))[:300]} for x in crit],
               "met": met, "total": len(crit), "gap": gap, "question": question, "model": c.model.key,
               "redacted": bool(found), "target": target,
               "graded_against": "lean_verified_proof" if target != "statement" else "lean_statement",
               "text": "\n\n".join(x for x in (gap, question) if x)}
        self._log(device, {"dossier": did, "kind": "explain_back", "met": met, "total": len(crit),
                           "confidence": confidence})
        return res

    # -- faded exercises
    def _copies(self, d, variants: list[tuple[str, list[str]]]) -> tuple[str, list[dict]]:
        """One Lean file with renamed copies of the target theorem (one per variant body). Returns (code, spans)."""
        head, sig, _lines = split_proof(d.proof)
        name = leancheck.theorem_name(d.proof)
        parts, spans = [head.rstrip("\n"), ""], []
        line = head.rstrip("\n").count("\n") + 3
        for tag, body in variants:
            s = re.sub(rf"\btheorem\s+{re.escape(name)}\b", f"theorem {name}_{tag}", sig, count=1)
            block = s + "\n" + "\n".join(body) + "\n"
            parts.append(block)
            n = block.count("\n")
            spans.append({"tag": tag, "start": line, "end": line + n, "name": f"{name}_{tag}"})
            line += n + 1
        return "\n".join(parts) + "\n", spans

    async def _compile(self, d, code: str, strict_name: str | None = None) -> dict:
        ws = self.ctx.workspace(d.workspace or self.ctx.settings.workspace)
        if ws is None:
            raise LearnError("no_workspace", 409)
        if strict_name:
            code = leancheck.with_axiom_probe(code, strict_name)
        r = await self.ctx.lean.check(code, ws, self.ctx.settings.compile_timeout_s, strict_name,
                                      owner=f"learn-{d.id}")
        return r.to_dict() | {"_stdout": r.stdout}

    @staticmethod
    def _span_errors(check: dict, sp: dict) -> list[dict]:
        return [e for e in check["errors"] if sp["start"] <= e["line"] <= sp["end"]]

    @staticmethod
    def _span_sorry(stdout: str, sp: dict) -> bool:
        for m in leancheck.parse_lean_json(stdout):
            if sp["start"] <= m.line <= sp["end"] and leancheck.SORRY_RE.search(m.text):
                return True
        return False

    async def faded(self, did: str, k: int = 1, device: str = "") -> dict:
        d = self._proved(did)
        _h, _s, lines = split_proof(d.proof)
        blocks = tactic_blocks(lines)
        if not blocks:
            raise LearnError("no_blocks", 422)
        k = max(1, min(int(k), len(blocks)))
        cands = list(range(len(blocks)))[::-1]           # fade from the end of the proof backwards
        variants = [("orig", lines), ("holes", self._fill(lines, blocks, {i: None for i in cands[:k]}))]
        for i in cands:
            variants.append((f"t{i}", self._fill(lines, blocks, {i: [TRIVIAL]})))
        code, spans = self._copies(d, variants)
        check = await self._compile(d, code)
        sp = {s["tag"]: s for s in spans}
        orig_ok = not self._span_errors(check, sp["orig"]) and not self._span_sorry(check["_stdout"], sp["orig"]) \
            and not check["timed_out"] and not check["infra_error"]
        if not orig_ok:
            raise LearnError("orig_failed", 409, "La preuve d'origine ne compile plus dans cet espace : à revérifier.")
        nontrivial = [i for i in cands if self._span_errors(check, sp[f"t{i}"])]
        chosen = nontrivial[:k]
        if not chosen:
            raise LearnError("all_trivial", 422, "Chaque étape de cette preuve se règle automatiquement : pas "
                                                 "d'exercice utile.")
        holes_lines = self._fill(lines, blocks, {i: None for i in chosen})
        # the structure with sorry blanks must compile (only sorry warnings)
        code2, spans2 = self._copies(d, [("holes", holes_lines)])
        c2 = await self._compile(d, code2)
        if self._span_errors(c2, spans2[0]):
            raise LearnError("holes_failed", 422)
        eid = "fx-" + uuid.uuid4().hex[:10]
        blanks = sorted(chosen)
        template = self._template(d, lines, blocks, blanks)
        ex = {"id": eid, "kind": "faded", "dossier": did, "proof": d.cur_proof, "k": len(blanks), "blanks": blanks,
              "solutions": {str(i): "\n".join(lines[j] for j in blocks[i]) for i in blanks},
              "template": template, "verified": {"original_compiles": True, "holes_compile": True,
                                                  "nontrivial": blanks, "trivial_blocks":
                                                      [i for i in cands if i not in nontrivial],
                                                  "battery": TRIVIAL, "seconds": check["seconds"] + c2["seconds"]},
              "created": time.time()}
        self.store.doc(did)["exercises"][eid] = ex
        self.store.save_doc(did)
        self._log(device, {"dossier": did, "kind": "exercise_created", "exercise": eid, "type": "faded"})
        return self.public_exercise(ex)

    @staticmethod
    def _fill(lines: list[str], blocks: list[list[int]], repl: dict[int, list[str] | None]) -> list[str]:
        out = []
        for bi, blk in enumerate(blocks):
            ind = lines[blk[0]][: len(lines[blk[0]]) - len(lines[blk[0]].lstrip())]
            if bi in repl:
                body = repl[bi]
                out += [ind + "sorry"] if body is None else [ind + b for b in body]
            else:
                out += [lines[j] for j in blk]
        return out

    def _template(self, d, lines, blocks, blanks) -> str:
        head, sig, _l = split_proof(d.proof)
        out = []
        for bi, blk in enumerate(blocks):
            ind = lines[blk[0]][: len(lines[blk[0]]) - len(lines[blk[0]].lstrip())]
            if bi in blanks:
                out.append(f"{ind}sorry -- ⟨{blanks.index(bi) + 1}⟩")
            else:
                out += [lines[j] for j in blk]
        return (sig + "\n" + "\n".join(out)).strip() + "\n"

    @staticmethod
    def public_exercise(ex: dict) -> dict:
        return {k: v for k, v in ex.items() if k not in ("solutions", "error", "lean_error")}

    def exercise(self, did: str, eid: str) -> dict:
        ex = self.store.doc(did)["exercises"].get(eid)
        if ex is None:
            raise LearnError("not_found", 404)
        return ex

    async def submit(self, did: str, eid: str, device: str, fills: list[str] | None = None, code: str = "",
                     diagnosis: str = "") -> dict:
        d = self._proved(did)
        ex = self.exercise(did, eid)
        _h, _s, lines = split_proof(d.proof)
        blocks = tactic_blocks(lines)
        name = leancheck.theorem_name(d.proof)
        if ex["kind"] == "faded":
            if not isinstance(fills, list) or len(fills) != len(ex["blanks"]):
                raise LearnError("bad_fills")
            repl = {}
            for bi, text in zip(ex["blanks"], fills):
                tl = [t for t in str(text).replace("\r", "").split("\n")]
                if not any(t.strip() for t in tl):
                    raise LearnError("bad_fills")
                base = min(len(t) - len(t.lstrip()) for t in tl if t.strip())
                repl[bi] = [t[base:] for t in tl]
            body = self._fill(lines, blocks, repl)
        else:
            if len((diagnosis or "").strip()) < 3 and not code.strip():
                raise LearnError("diagnose_first", 409, "Dites d'abord où est l'erreur et pourquoi.")
            if not code.strip():
                self._log(device, {"dossier": did, "kind": "exercise_diagnosis", "exercise": eid,
                                   "text": diagnosis[:2000]})
                return {"checked": False, "lean_error": ex["lean_error"], "wrong_block": ex["block"]}
            if re.search(r"(?m)^theorem\s", code):
                _hh, _ss, body = split_proof(code)       # only the body is taken: the statement stays pinned
            else:
                body = [ln if ln.startswith((" ", "\t")) or not ln.strip() else "  " + ln
                        for ln in code.replace("\r", "").split("\n")]
        head, sig, _l = split_proof(d.proof)
        full = head + sig + "\n" + "\n".join(body) + "\n"
        if leancheck.forbidden_reasons(full):
            check = {"ok": False, "summary": msg("Refusé : {why}.", why=", ".join(leancheck.forbidden_reasons(full)))
                     ["text"], "errors": [], "reasons": leancheck.forbidden_reasons(full)}
        else:
            check = await self._compile(d, full, name)
            check.pop("_stdout", None)
        ok = bool(check["ok"])
        self._log(device, {"dossier": did, "kind": "exercise_submit", "exercise": eid, "type": ex["kind"], "ok": ok})
        out = {"checked": True, "ok": ok, "check": check}
        if ex["kind"] == "erroneous":
            out["lean_error"] = ex["lean_error"]
        return out

    # -- erroneous examples
    async def erroneous(self, did: str, device: str = "") -> dict:
        d = self._proved(did)
        _h, _s, lines = split_proof(d.proof)
        blocks = tactic_blocks(lines)
        cands = await self._mutations(d, lines, blocks)
        if not cands:
            raise LearnError("no_mutation", 422, "Aucune variante plausible de cette preuve n'a été trouvée.")
        variants = [(f"m{i}", m["body"]) for i, m in enumerate(cands)]
        code, spans = self._copies(d, variants)
        check = await self._compile(d, code)
        chosen = None
        for i, sp in enumerate(spans):
            errs = self._span_errors(check, sp)
            if errs:
                chosen = (cands[i], errs)
                break
        if chosen is None:
            raise LearnError("no_mutation", 422, "Aucune variante plausible de cette preuve n'a été trouvée.")
        m, errs = chosen
        head, sig, _l = split_proof(d.proof)
        eid = "ex-" + uuid.uuid4().hex[:10]
        ex = {"id": eid, "kind": "erroneous", "dossier": did, "proof": d.cur_proof, "block": m["block"],
              "mutation": m["kind"], "wrong_proof": (sig + "\n" + "\n".join(m["body"])).strip() + "\n",
              "lean_error": [{"line": e["line"] - spans[cands.index(m)]["start"] + 1, "text": e["text"][:1500]}
                             for e in errs],
              "prompts": [msg("Lisez la preuve : chaque étape est-elle juste ?")["text"],
                          msg("Quelle étape est fausse ? Expliquez pourquoi.")["text"],
                          msg("Corrigez-la : Lean vérifiera votre correction.")["text"]],
              "created": time.time()}
        self.store.doc(did)["exercises"][eid] = ex
        self.store.save_doc(did)
        self._log(device, {"dossier": did, "kind": "exercise_created", "exercise": eid, "type": "erroneous"})
        return self.public_exercise(ex)

    async def _mutations(self, d, lines: list[str], blocks: list[list[int]]) -> list[dict]:
        out = []
        ws = d.workspace or self.ctx.settings.workspace
        swaps = [("omega", "linarith"), ("linarith", "omega"), ("norm_num", "simp"), ("nlinarith", "linarith"),
                 ("ring", "simp"), ("exact", "apply")]
        for bi, blk in enumerate(blocks):
            text = "\n".join(lines[j] for j in blk)
            for lemma in IDENT_RE.findall(leancheck.remove_comments(text)):
                alts = []
                if self.ctx.retriever is not None:
                    try:
                        hits = await self.ctx.retriever.search(ws, lemma.replace(".", " ").replace("_", " "), 6)
                        alts = [h["name"] for h in hits or [] if h.get("name") and h["name"] != lemma]
                    except Exception:  # noqa: BLE001
                        alts = []
                for alt in alts[:2]:
                    out.append({"block": bi, "kind": "lemma_swap", "body": self._replace(lines, blk, lemma, alt)})
            m = re.search(r"(\b[\w.']+)\s+(\w+)\s+(\w+)(\s*)$", text)
            if m and m.group(2) != m.group(3):
                new = text[:m.start(2)] + m.group(3) + " " + m.group(2) + m.group(4)
                out.append({"block": bi, "kind": "argument_swap", "body": self._sub_block(lines, blk, new)})
            for a, b in swaps:
                if re.search(rf"\b{a}\b", text):
                    out.append({"block": bi, "kind": "tactic_swap",
                                "body": self._sub_block(lines, blk, re.sub(rf"\b{a}\b", b, text, count=1))})
        if len(blocks) > 1:
            out.append({"block": len(blocks) - 1, "kind": "dropped_step",
                        "body": [lines[j] for blk in blocks[:-1] for j in blk]})
        return out[:12]

    @staticmethod
    def _replace(lines, blk, old, new) -> list[str]:
        text = "\n".join(lines[j] for j in blk).replace(old, new, 1)
        return Tutor._sub_block(lines, blk, text)

    @staticmethod
    def _sub_block(lines, blk, text) -> list[str]:
        out = []
        for i, ln in enumerate(lines):
            if i == blk[0]:
                out += text.split("\n")
            elif i in blk:
                continue
            else:
                out.append(ln)
        return out


# ---------------------------------------------------------------- demo answers (scripted brain)
def demo_answer(first: str) -> str | None:
    if not first.startswith(MARK):
        return None
    if "task=hint" in first:
        lv = int(re.search(r"level=(\d)", first).group(1))
        return {1: "Que signifie « être pair » pour $a$ et pour $b$ ? Que devient la somme ?",
                2: "Écrivez $a$ et $b$ comme des doubles, puis regroupez : la somme est encore un double.",
                3: "Le lemme clé de Mathlib est `Even.add` : comment s'applique-t-il ici ?",
                4: "Commencez par `exact Even.add _ _` : quels arguments manquent ?"}[lv]
    if "task=explain_back" in first:
        return json.dumps({"criteria": [
            {"criterion": "a et b s'écrivent comme des doubles", "met": True, "evidence": "a = 2k"},
            {"criterion": "la somme se factorise par 2", "met": False, "evidence": ""}],
            "gap": "Vous n'expliquez pas pourquoi la somme est un double.",
            "question": "Que vaut $2k + 2l$ ?"}, ensure_ascii=False)
    return None


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]
