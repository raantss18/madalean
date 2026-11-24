"""Is the Lean statement what the user asked? (S-BG, D65, docs/DOSSIER_FLOW.md). Deterministic checks, before any model.

- `parse_meaning`: the structured restatement written by a model (objects, hypotheses, claim, names, questions) —
  untrusted text: bounded, typed, and its literature claims stay `model_only` until a retrieved passage supports them;
- `refusals`: reasons to refuse a Lean statement (`False` / `True`, vacuous existential, empty type, objects or numbers
  of the problem absent from the statement and the definitions it reaches, conclusion that depends on nothing);
- `lean_refusals`: contradictory hypotheses, and a claim said to be open / false that `rfl` / `simp` closes (Lean,
  bounded, re-checked strictly);
- `agreement`: are two independent translations equivalent (Lean, bounded)? Never resolved silently;
- `review_fix` / `seen_before`: a suggested fix that changes the claim, a factual claim without source, oscillation;
- `status_of`: the known status, quoted verbatim from retrieved texts, else from the model and said so."""
from __future__ import annotations

import json
import re
import time
import unicodedata

from .. import leancheck
from ..i18n import msg
from ..logs import get
from . import probes as P

log = get("pipeline.faithful")
STATUSES = ("known", "open", "false", "unclear", "unknown")
MAX_OBJECTS, MAX_LIST, MAX_KNOWN, MAX_NAMES = 10, 8, 4, 4
PROBE_TIMEOUT, EQUIV_TIMEOUT = 60, 60


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _str(x, n: int = 400) -> str:
    return re.sub(r"\s+", " ", x).strip()[:n] if isinstance(x, str) else ""


def _strs(x, k: int = MAX_LIST, n: int = 400) -> list[str]:
    return [t for t in (_str(v, n) for v in (x if isinstance(x, list) else [])[:k]) if t]


def family(key: str) -> str:
    """Model family of a key (« groq:llama-3.3-70b » → llama): two candidates of one family are not independent."""
    n = key.rsplit("/", 1)[-1].split(":", 1)[-1].lower() if "/" in key else key.split(":", 1)[-1].lower()
    m = re.search(r"goedel|qwen|llama|deepseek|gemini|gemma|claude|gpt|mi[sx]tral|codestral|magistral|devstral|kimi|glm|"
                  r"nemotron|phi|command|kimina|minimax|grok|step", n)
    return m.group(0) if m else re.split(r"[-_.:\d]", n, maxsplit=1)[0] or n


# ---------------------------------------------------------------- the meaning
MEANING_PROMPT = (
    "\n\nThen, after these two lines, add one last line starting with MEANING: followed by ONE JSON object that "
    "analyses the same request (texts in {lang_name}, short):\n"
    "{{\"objects\": [{{\"name\": \"<object of the statement>\", \"meaning\": \"<its definition>\", \"lean\": "
    "[\"<Mathlib name, only if you are sure it exists>\"]}}], \"hypotheses\": [\"…\"], \"claim\": \"<the exact claim, "
    "with its numbers and relation, unchanged>\", \"names\": [\"<classical English name of the problem or theorem, "
    "e.g. Hadwiger–Nelson problem>\"], \"status\": \"known|open|false|unclear\", \"known_results\": [{{\"title\": "
    "\"…\", \"statement\": \"<a weaker or related PROVED result, stated completely and never stronger than what is "
    "proved>\"}}], \"questions\": [\"<only if the request is really ambiguous>\"]}}\n"
    "Never change the claim to make it true: an open or false claim is stated as asked and its status is \"open\" or "
    "\"false\". If you are not sure of the status write \"unclear\". known_results only for an open or false claim.")


def split_meaning(text: str) -> tuple[str, dict]:
    """(answer without its MEANING part, the parsed JSON or {})."""
    m = re.search(r"(?m)^\W*MEANING\W*?:", text or "")
    if m is None:
        return text or "", {}
    raw = text[m.end():]
    a, b = raw.find("{"), raw.rfind("}")
    data: dict = {}
    if 0 <= a < b:
        # LaTeX commands written with one backslash (« \\frac » would be read as a form feed)
        js = re.sub(r"(?<!\\)\\(?=[A-Za-z]{2,})(?!u[0-9a-fA-F]{4})", r"\\\\", raw[a:b + 1])
        js = re.sub(r"(?<!\\)\\(?![\"\\/bfnrtu])", r"\\\\", js)
        for cand in (js, re.sub(r",\s*([}\]])", r"\1", js)):
            try:
                v = json.loads(cand)
                data = v if isinstance(v, dict) else {}
                break
            except ValueError:
                continue
    return text[: m.start()].rstrip(), data


def parse_meaning(data: dict, restated: str) -> dict:
    """The meaning shown at the gate, bounded and typed. The status is not decided here (`status_of`)."""
    objects = []
    for o in (data.get("objects") if isinstance(data.get("objects"), list) else [])[:MAX_OBJECTS]:
        if isinstance(o, dict) and _str(o.get("name"), 120):
            objects.append({"name": _str(o["name"], 120), "meaning": _str(o.get("meaning")),
                            "lean": [n for n in _strs(o.get("lean"), 4, 100) if re.fullmatch(r"[A-Za-z_][\w'.]*", n)]})
    known: list[dict] = []
    for r in (data.get("known_results") if isinstance(data.get("known_results"), list) else [])[:MAX_KNOWN]:
        if isinstance(r, dict) and _str(r.get("statement"), 1000):
            st = _str(r["statement"], 1000)
            if any(same_words(st, k["statement"]) for k in known):
                continue
            known.append({"id": f"k{len(known) + 1}", "title": _str(r.get("title"), 160) or st[:80], "statement": st})
    st = _str(data.get("status"), 20).lower()
    return {"restated": restated.strip(), "objects": objects, "hypotheses": _strs(data.get("hypotheses")),
            "claim": _str(data.get("claim"), 600), "known_status": st if st in STATUSES else "unknown",
            "status_sources": [], "status_confidence": "model_only", "known_results": known,
            "questions": _strs(data.get("questions"), 5), "names": _names(data.get("names"))}


def _names(x) -> list[str]:
    """Search names proposed by a model: plain words only (never a reference)."""
    from ..literature.query import clean_terms
    return clean_terms(x if isinstance(x, list) else [], MAX_NAMES, words=6)


def same_words(a: str, b: str) -> bool:
    from .stagecache import normalize_text
    return normalize_text(fold(a)) == normalize_text(fold(b))


# ---------------------------------------------------------------- concepts: words of the problem ↔ Lean names
_PROPER = r"(\w+) \S+ ≠ \1 \S+"            # `c x ≠ c y`: a proper colouring written out
# (key, words in the problem (folded French / English), how Lean may say it, Mathlib's own objects)
CONCEPTS = [
    ("chromatic", r"nombres? chromatiques?|chromatic numbers?",
     r"chromaticNumber|Colorable|Coloring|" + _PROPER,
     ["SimpleGraph.chromaticNumber", "SimpleGraph.Colorable", "SimpleGraph.Coloring"]),
    ("plane", r"\bplan\b(?! d[e'])|\bplans? euclid|\bplane\b",
     r"EuclideanSpace\s+ℝ\s+\(Fin 2\)|ℂ|Complex|ℝ\s*×\s*ℝ|Fin 2 → ℝ|WithLp|finrank", ["EuclideanSpace"]),
    ("graph", r"\bgraphes?\b(?! d'une? fonction)|\bgraphs?\b(?! of (a |the )?function)",
     r"[gG]raph|chromaticNumber|Colorable|\bAdj\b|" + _PROPER, ["SimpleGraph"]),
    ("prime", r"nombres? premiers?|entiers? premiers?|\bprimes?\b", r"[pP]rime|Irreducible", ["Nat.Prime"]),
    ("irrational", r"irrationne|irrational", r"Irrational|ℚ|Rat", ["Irrational"]),
    ("compact", r"\bcompacte?s?\b", r"Compact", ["IsCompact"]),
    ("continuous", r"\bcontinue?s?\b|continuous", r"Continuous|C\(|→L", ["Continuous"]),
    ("integral", r"integrale?s?\b", r"∫|[iI]ntegra", ["intervalIntegral"]),
    ("group", r"\bgroupes?\b|\bgroups?\b", r"Group|Subgroup|Perm|ZMod|Units", ["Group"]),
    ("eigenvalue", r"valeurs? propres?|eigenvalue", r"igenvalue|charpoly|spectrum|HasEigen|\*ᵥ",
     ["Module.End.HasEigenvalue"]),
]
# how a blind reading may name the object besides its own words
ALIASES = {"chromatic": r"colou?r|couleur", "plane": r"r\^?\{?2|\bplan|r²|ℝ|dimension 2|complex|euclid",
           "graph": r"sommet|vert(ex|ices)|arete|edge|adjacen|colou?r|couleur", "prime": r"premier|prime",
           "irrational": r"rationn|rational", "group": r"group", "continuous": r"continu", "compact": r"compact",
           "integral": r"integra", "eigenvalue": r"propre|eigen"}


def concepts_of(text: str) -> list[tuple]:
    f = fold(text)
    return [c for c in CONCEPTS if re.search(c[1], f)]


def wanted_objects(meaning: dict, problem: str) -> list[tuple[str, list[tuple]]]:
    """[(name shown, concepts it must express)] — only what can be judged by rules."""
    out: list[tuple[str, list[tuple]]] = []
    for o in meaning.get("objects") or []:
        cs = concepts_of(o.get("name", ""))
        if cs:
            out.append((o["name"], cs))
    covered = {c[0] for _n, cs in out for c in cs}
    for c in concepts_of(problem):                     # the user's own words always count
        if c[0] not in covered:
            m = re.search(c[1], fold(problem))
            out.append((m.group(0) if m else c[0], [c]))
    return out


def mathlib_names(meaning: dict, problem: str) -> list[str]:
    """Mathlib names worth looking up in the workspace's own index (looked up, never trusted)."""
    names = [n for _n, cs in wanted_objects(meaning, problem) for c in cs for n in c[3]]
    for o in meaning.get("objects") or []:
        names += o.get("lean") or []
    return list(dict.fromkeys(names))[:10]


# ---------------------------------------------------------------- deterministic refusals
def reach(sig: P.Sig) -> str:
    """The target's signature and the local definitions it reaches (transitively)."""
    blocks: dict[str, str] = {}
    mods = r"(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+|private\s+)*"
    for b in re.split(r"(?m)^(?=" + mods + r"(?:def|abbrev|structure|class|inductive|theorem|lemma|instance)\s)",
                      sig.preamble):
        m = re.match(mods + r"(?:def|abbrev|structure|class|inductive)\s+([^\s:({\[]+)", b)
        if m:
            blocks[m.group(1)] = b
    text = f"{sig.binders} : {sig.concl}"
    seen: set[str] = set()
    grew = True
    while grew:
        grew = False
        for name, b in blocks.items():
            if name not in seen and _word(name, text):
                seen.add(name)
                text += "\n" + b
                grew = True
    return text


def _word(name: str, text: str) -> bool:
    return re.search(r"(?<![\w.'])" + re.escape(name) + r"(?![\w'])", text) is not None


_NUM = re.compile(r"(?<![\w.,])\d+(?![\w]|[.,]\d)")


def numbers(text: str) -> set[int]:
    """Integers ≥ 3 written in a text (0, 1, 2 are too often implicit: pair, carré, positif…)."""
    return {int(x) for x in _NUM.findall(text or "") if len(x) < 9 and int(x) >= 3}


def _strip_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        for i, ch in enumerate(s):
            depth += (ch == "(") - (ch == ")")
            if depth == 0 and i < len(s) - 1:
                return s
        s = s[1:-1].strip()
    return s


def vacuous_exists(concl: str) -> bool:
    """`∃ x, True`, `∃ x, x = t` (t without x): true whatever the problem says."""
    m = re.match(r"∃ \(?([^\W\d][\w']*)(?:\s*:\s*[^,()]+)?\)?\s*,\s*(.+)$", _strip_parens(concl), re.S)
    if not m:
        return False
    x, body = m.group(1), _strip_parens(m.group(2))
    if body == "True":
        return True
    e = re.fullmatch(r"([^=∧∨→↔∃∀≠≤≥<>]+)=([^=∧∨→↔∃∀≠≤≥<>]+)", body)
    if not e:
        return False
    a, b = _strip_parens(e.group(1)), _strip_parens(e.group(2))
    return (a == x and not _word(x, b)) or (b == x and not _word(x, a))


EMPTY_TYPE = re.compile(r"Fin\s+0(?![\d\w])|\bP?Empty\b")


def refusals(code: str, meaning: dict | None, problem: str) -> dict:
    """{hard: [reason], soft: [reason], missing: [object]}: `hard` can never be approved as it is; `soft` refuses a
    translation but the user may still choose it. Without `meaning` (no meaning stage): the hard rules only."""
    hard: list[str] = []
    soft: list[str] = []
    missing: list[str] = []
    sig = P.split_statement(code)
    if sig is None:
        return {"hard": hard, "soft": soft, "missing": missing}
    bare = concl = _strip_parens(sig.concl)
    while (m := re.match(r"∀ [^,]+,\s*", bare)):       # `∀ x, False` says as little as `False`
        bare = _strip_parens(bare[m.end():])
    if bare == "False":
        hard.append(msg("La conclusion est « False » : l'énoncé ne dit rien du problème (une négation s'écrit "
                        "« ¬ … » ou « ≠ »).")["text"])
    elif bare == "True" or leancheck.vacuous(code):
        hard.append(msg("La conclusion est vraie par construction (« True », « x = x »).")["text"])
    elif vacuous_exists(concl):
        hard.append(msg("L'existence énoncée est vraie par construction : elle ne dit rien du problème.")["text"])
    text = reach(sig)
    if EMPTY_TYPE.search(text) and not re.search(r"\bvides?\b|\bempty\b|\b0\b|\bzero\b", fold(problem)):
        hard.append(msg("L'énoncé porte sur un type vide (« Fin 0 »…) : il est vrai ou faux pour une raison sans "
                        "rapport avec le problème.")["text"])
    if meaning is None:
        return {"hard": hard, "soft": soft, "missing": missing}
    wanted = wanted_objects(meaning, problem)
    missing = [name for name, cs in wanted if any(not re.search(c[2], text) for c in cs)]
    if missing:
        soft.append(msg("Objets du problème absents de l'énoncé Lean : {names}.", names=", ".join(missing))["text"])
    said = meaning.get("claim") or meaning.get("restated") or problem
    need = numbers(said) & numbers(problem) if numbers(problem) else numbers(said)
    lost = sorted(need - numbers(text))
    if lost:
        soft.append(msg("Nombres du problème absents de l'énoncé Lean : {names}.",
                        names=", ".join(map(str, lost)))["text"])
    extra = sorted(numbers(sig.concl) - numbers(" ".join([problem, said, meaning.get("restated") or ""])))
    if extra:
        soft.append(msg("Nombres ajoutés dans la conclusion, absents du problème : {names}.",
                        names=", ".join(map(str, extra)))["text"])
    data = [n for n, _t in P.explicit_binders(sig.binders)]
    if not hard and data and not any(_word(n, sig.concl) for n in data) \
            and not any(re.search(c[2], sig.concl) for _n, cs in wanted for c in cs) and not (need & numbers(sig.concl)):
        soft.append(msg("La conclusion ne dépend d'aucun objet ni d'aucun nombre du problème.")["text"])
    return {"hard": hard, "soft": soft, "missing": missing}


TRIVIAL = ("rfl", "trivial", "simp", "decide")
CONTRA = ("simp_all", "omega", "norm_num at *", "linarith")


async def lean_refusals(io, ws, code: str, status: str) -> tuple[list[str], list[str]]:
    """(hard reasons, notes) from Lean: contradictory hypotheses; a claim closed at once by a trivial tactic — a refusal
    when the claim is said to be open or false, a note otherwise (an easy exercise may be easy)."""
    sig = P.split_statement(code)
    if sig is None:
        return [], []
    ps = [P.Probe(f"madalean_triv_{k}", P.decl(f"madalean_triv_{k}", f"{sig.binders} : {sig.concl}", t), "pos",
                  {"tactic": t}) for k, t in enumerate(TRIVIAL)]
    if P.explicit_binders(sig.binders):
        ps += [P.Probe(f"madalean_contra_{k}", P.decl(f"madalean_contra_{k}", f"{sig.binders} : False", t), "contra",
                       {"tactic": t}) for k, t in enumerate(CONTRA)]
    hard: list[str] = []
    notes: list[str] = []
    try:
        await P.run_batch(io, ws, sig.preamble, ps, PROBE_TIMEOUT)
        for kind in ("contra", "pos"):
            p = next((p for p in ps if p.ok and p.kind == kind), None)
            if p is None or not (await P.strict(io, ws, sig.preamble, p, PROBE_TIMEOUT)).verdict.ok:
                continue
            if kind == "contra":
                hard.append(msg("Les hypothèses se contredisent (Lean en déduit « False ») : l'énoncé est vrai à "
                                "vide.")["text"])
            elif status in ("open", "false"):
                hard.append(msg("Lean prouve l'énoncé d'un coup ({tactic}) alors que le problème est ouvert ou faux : "
                                "ce n'est pas le même énoncé.", tactic=p.meta["tactic"])["text"])
            else:
                notes.append(msg("Lean prouve l'énoncé d'un coup ({tactic}).", tactic=p.meta["tactic"])["text"])
    except Exception as e:  # noqa: BLE001 (a probe never breaks the translation)
        log.warning("faithfulness probes failed: %s", e)
    return hard, notes


async def agreement(io, ws, a: str, b: str, lean_real: bool) -> str:
    """equivalent | different | unchecked. « different »: Lean could not show in bounded time that they are equivalent."""
    from ..dossiers import strip_header
    from ..research.proofgraph import statement_key
    sa, sb = P.split_statement(a), P.split_statement(b)
    if sa is None or sb is None:
        return "unchecked"
    da, db = strip_header(sa.preamble), strip_header(sb.preamble)
    if statement_key(a) == statement_key(b) and da == db:
        return "equivalent"
    if not lean_real or (db and da != db):
        return "unchecked"

    def prop(s: P.Sig) -> str:
        return f"(∀ {s.binders}, {s.concl})" if s.binders.strip() else f"({s.concl})"
    head = f": {prop(sa)} ↔ {prop(sb)}"
    ps = [P.Probe(f"madalean_eqv_{k}", P.decl(f"madalean_eqv_{k}", head, t, 60000), "eqv") for k, t in enumerate((
        "exact Iff.rfl", "norm_num", "constructor <;> intro h <;> intros <;> simp_all", "aesop",
        "constructor <;> intro h <;> intros <;> first | (apply h <;> assumption) | linarith | omega"))]
    try:
        code, spans = P.batch_file(sa.preamble, ps)
        r = await io.check(code, ws, EQUIV_TIMEOUT, None)
        if r.timed_out or (r.infra_error and not r.verdict.errors):
            return "unchecked"
        P.read_batch(r.stdout, spans, r.timed_out)
        for p in [p for p in ps if p.ok][:2]:
            if (await P.strict(io, ws, sa.preamble, p, EQUIV_TIMEOUT)).verdict.ok:
                return "equivalent"
        return "different"
    except Exception as e:  # noqa: BLE001
        log.warning("agreement check failed: %s", e)
        return "unchecked"


# ---------------------------------------------------------------- blind back-translation
BACK_PROMPT = (
    "Read this Lean 4 (Mathlib) statement and say in {lang_name}, for a mathematician, exactly what it states: every "
    "object, every hypothesis, the quantifiers and the conclusion, with their numbers. Do not guess what was intended, "
    "do not correct it, do not prove it, do not comment on Lean. Plain sentences, at most 6 lines.\n\n"
    "```lean4\n{lean}\n```")


def back_messages(code: str, lang: str) -> list[dict]:
    """The problem is NOT given, and the theorem's name (which repeats it) is neutral: the reader only reads."""
    body = leancheck.remove_comments(code)
    try:
        name = leancheck.theorem_name(code)
        body = re.sub(r"(?<![\w.'])" + re.escape(name) + r"(?![\w'])", "statement", body)
    except leancheck.StatementError:
        pass
    body = "\n".join(ln for ln in body.split("\n") if not re.match(r"\s*(import|open|set_option)\b", ln))
    return [{"role": "user", "content": BACK_PROMPT.format(lang_name="English" if lang == "en" else "French",
                                                           lean=body.strip()[:6000])}]


def back_missing(back: str, meaning: dict, problem: str) -> list[str]:
    """Objects of the meaning that the blind reading does not mention (objects the rules can judge)."""
    if not back.strip():
        return []
    f = fold(back)
    return [name for name, cs in wanted_objects(meaning, problem)
            if any(not re.search(c[1], f) and not re.search(ALIASES.get(c[0], "$^"), f) for c in cs)]


# ---------------------------------------------------------------- suggested fixes: one target, no oscillation
_FACT = re.compile(r"conjectur|\bopen\b|\bouvert|unsolved|non resolu|(is|was|has been) (proved|proven|shown|known)|"
                   r"(est|a ete|fut) (prouve|demontre|etabli|connu)|on sait que|it is known|"
                   r"theoreme de [a-z]|\b(19|20)\d\d\b|\bde grey\b", re.I)
_WORDS = re.compile(r"[a-z]{4,}")
_IGNORE = set("ajouter hypothese add hypothesis enonce statement changer change remplacer replace corriger correct avec "
              "with dans that pour conclusion preciser objet object instead lieu donc comme prouver prove montrer show "
              "faut must should doit theorem theoreme lean mathlib utiliser".split())


def _rel(t: str) -> str:
    for a, b in (("\\leq", "≤"), ("\\le", "≤"), ("\\geq", "≥"), ("\\ge", "≥"), ("\\neq", "≠"), ("\\ne", "≠"),
                 ("<=", "≤"), (">=", "≥"), ("!=", "≠")):
        t = t.replace(a, b)
    return t


def claim_signature(text: str) -> str:
    """What a fix or a claim says, up to wording: its numbers with their relations, else its content words."""
    t = _rel(fold(text))
    rel = re.findall(r"\d+|[≤≥<>=≠]", t)
    if any(r.isdigit() for r in rel):
        return " ".join(rel)
    return " ".join(sorted(set(_WORDS.findall(t)) - _IGNORE)[:12])


def review_fix(fix: str, explanation: str, meaning: dict, problem: str, sources: list | None = None) -> dict:
    """{changes_claim, unsourced}: does this fix leave the user's claim, and does it assert a fact without a source?"""
    target = _rel(" ".join([problem, meaning.get("restated", ""), meaning.get("claim", ""),
                            " ".join(meaning.get("hypotheses") or [])]))
    f = _rel(fix)
    rels = set(re.findall(r"[≤≥<>≠]", f)) - set(re.findall(r"[≤≥<>≠]", target))
    lost = bool(numbers(f)) and bool(numbers(target)) and not numbers(f) & numbers(target)
    words = set(_WORDS.findall(fold(f))) - _IGNORE
    known = set(_WORDS.findall(fold(target)))
    foreign = [w for w in words if not any(w[:5] == k[:5] for k in known)]
    changes = bool(fix.strip()) and bool(numbers(f) - numbers(target) or lost or (rels and re.search(r"\d", f)) or
                                         len(foreign) * 2 > max(1, len(words)))
    quoted = any(_str(s.get("quote"), 2000) for s in sources or [])
    return {"changes_claim": changes, "unsourced": bool(_FACT.search(fold(fix + " " + explanation))) and not quoted}


def seen_before(d, statement: str, fix: str) -> bool:
    """Records (statement, fix) in the dossier's bounded history; True when it oscillates: a fix already suggested for
    ANOTHER statement, or a statement that comes back after having been left."""
    from ..research.proofgraph import statement_key
    hist = d.extra.setdefault("fix_history", [])
    skey, sig = statement_key(statement), claim_signature(fix) if fix.strip() else ""
    again = bool(hist) and hist[-1]["s"] != skey and any(h["s"] == skey for h in hist[:-1])
    again = again or (bool(sig) and any(h["f"] == sig and h["s"] != skey for h in hist))
    if not (hist and hist[-1]["s"] == skey and hist[-1]["f"] == sig):
        hist.append({"s": skey, "f": sig, "t": time.time()})
        del hist[:-20]
    return again


# ---------------------------------------------------------------- known status from retrieved texts
STATUS_RE = {
    "open": re.compile(r"\b(open (problem|question)|unsolved|still open|remains? open|is open|not known whether|"
                       r"unknown whether|unresolved|long-?standing (open )?(problem|conjecture))\b|"
                       r"exact value[^.]{0,40}unknown", re.I),
    "false": re.compile(r"\b(disprov\w+|counter-?examples? to|refut\w+|is false|fails in general)\b", re.I),
    "known": re.compile(r"\b(we (prove|show|establish|confirm)|is (proved|proven|shown|established)|was (proved|proven)|"
                        r"has been (proved|proven|solved)|proof of the)\b", re.I),
}


def _anchored(sentence: str, meaning: dict) -> bool:
    """The sentence is about this problem: one of its classical names, or all the concepts of its claim."""
    low = fold(sentence)
    for n in meaning.get("names") or []:
        ws = [w for w in re.findall(r"[a-z]{3,}", fold(n)) if w not in ("problem", "theorem", "conjecture", "the")]
        if ws and all(w in low for w in ws):
            return True
    cs = concepts_of(" ".join([meaning.get("claim", ""), meaning.get("restated", "")]))
    return len(cs) >= 2 and all(re.search(c[1], low) for c in cs)


def status_of(meaning: dict, items: list) -> dict:
    """known_status, status_sources, status_confidence from retrieved items (verbatim, string-matched) and the model's
    opinion. Sources that contradict the model → « unclear » with the sources shown; nothing → the model's word."""
    from ..literature import quotes as Q
    found: dict[str, list[dict]] = {}
    for it in items or []:
        url = it.reference.url or (f"https://doi.org/{it.reference.doi}" if it.reference.doi else "")
        for t in it.texts:
            if t.suspect:
                continue
            for a, b in Q.sentences(t.text):
                s = t.text[a:b].strip()
                if not Q.MIN_QUOTE <= len(s) <= Q.MAX_QUOTE or not _anchored(s, meaning):
                    continue
                kind = next((k for k, rx in STATUS_RE.items() if rx.search(s)), "")
                span = Q.verify(s, t.text) if kind else None
                if span is None:
                    continue
                q = t.text[span[0]:span[1]]
                if not any(r["quote"] == q for r in found.get(kind, [])):
                    found.setdefault(kind, []).append({"title": it.reference.title, "url": url, "quote": q})
    opinion = meaning.get("known_status", "unknown")
    strong = [k for k in ("open", "false") if k in found]
    if opinion in ("open", "false") and opinion in found or opinion == "known" and "known" in found and not strong:
        return {"known_status": opinion, "status_sources": found[opinion][:3], "status_confidence": "cited"}
    if strong:
        # « we prove » in a paper about the problem is often a partial result: alone it never makes a claim « known »
        k = strong[0] if len(strong) == 1 and opinion in ("unknown", "unclear") else "unclear"
        return {"known_status": k, "status_sources": [r for x in strong for r in found[x]][:3],
                "status_confidence": "cited"}
    return {"known_status": opinion, "status_sources": [], "status_confidence": "model_only"}


def source_known(meaning: dict, items: list) -> None:
    """A known result gets a `source` only from a retrieved passage holding all its numbers and most of its words."""
    from ..literature import quotes as Q
    for r in meaning.get("known_results") or []:
        nums = numbers(r["statement"])
        words = {w for w in _WORDS.findall(fold(r["statement"] + " " + r["title"])) if len(w) > 5} - _IGNORE
        for it in items or []:
            for q in it.quotes:
                low = fold(q.text)
                hit = sum(1 for w in words if w[:6] in low)
                if nums and nums <= numbers(q.text) and words and hit * 2 >= len(words) and \
                        Q.verify(q.text, it.texts[q.text_index].text):
                    r["source"] = {"title": it.reference.title, "url": it.reference.url, "quote": q.text}
                    break
            if "source" in r:
                break
