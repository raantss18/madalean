"""The Left to Solve checker's rules, re-implemented from join.txt (« THE RULES THE CHECKER ENFORCES », « PROBLEMS
THAT ASK FOR A VALUE », « REDUCTIONS », « FORMALIZE »; read 2026-11-28) — never copied from the site's code (no
licence). A file is « prête » only when `check_text` has no failure AND a fresh strict Lean in the pinned
workspace accepts it with axioms ⊆ {propext, Classical.choice, Quot.sound} (`local_check`).

Each rule has an id (shown to the user, tested one by one):
  import_first   a. the file starts with the single import line it was given (Mathlib imports may follow)
  target         b. exactly one `theorem OMA.solution : …` / `theorem OMA.disproof : ¬ (…)`, signature byte for byte
                    the skeleton's (`type_of% @<decl>` pins the upstream statement)
  commands       c. only theorem, lemma, def, abbrev, structure, inductive, instance, open, namespace, section, end,
                    variable, universe, `set_option <allowed> <number> in`, `@[simp]` / `@[local simp]`
  words          d. no sorry, admit, axiom, native_decide, decide := true, unsafe, partial, implemented_by, extern,
                    macro, syntax, elab, notation, initialize, run_cmd, #-commands, attribute, opaque
  quote          d. no double-quote character at all (anywhere, comments included)
  upstream       never the upstream declaration itself (or another of the module's `sorry` lemmas)
  answer         OMA.answer explicit: typed, not built from the problem's definitions, no choice / inf / sup / limit
  reduction      namespace OMA.R_<id>_R<n>, 2–4 `def Hk : Prop`, `theorem main : H1 → … → type_of% @<decl>`, the
                 hypotheses mention neither the target, main nor each other, no other def / structure / instance
  statement      formalize: one theorem, `main`, its body `sorry`, no other sorry
  axioms         (local check) axioms ⊆ {propext, Classical.choice, Quot.sound}; in the answer case only the
                 placeholder's `sorryAx` is tolerated, and only when the file names no other `sorry` declaration"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import leancheck

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
COMMANDS = {"theorem", "lemma", "def", "abbrev", "structure", "inductive", "instance", "open", "namespace", "section",
            "end", "variable", "universe", "set_option", "import"}
MODIFIERS = {"noncomputable", "private", "protected"}
CONTINUATIONS = {"termination_by", "decreasing_by", "where", "deriving", "with"}
SET_OPTIONS = {"maxHeartbeats", "maxRecDepth", "synthInstance.maxHeartbeats", "synthInstance.maxSize"}
WORDS = ["sorry", "admit", "axiom", "native_decide", "unsafe", "partial", "implemented_by", "extern", "macro",
         "syntax", "elab", "notation", "initialize", "run_cmd", "attribute", "opaque"]
HASH_COMMANDS = r"#(eval|check|print|reduce|exit|synth|guard\w*|help|find\w*|lint|min_imports|where|time|norm_num|simp|" \
                r"conv|leansearch|loogle|exact\?|explode|html|widget|test|sample|count_heartbeats|unfold|whnf)\b"
# « not built from the problem's own definitions, no choice / infimum / supremum / limit of the quantity asked for »
ANSWER_WORDS = ["choose", "choice", "epsilon", "sInf", "sSup", "iInf", "iSup", "⨅", "⨆", "limUnder", "lim", "limsup",
                "liminf", "Nat.find", "Nat.findGreatest", "Classical", "sorry", "Exists.choose", "Function.invFun",
                "Filter.Tendsto", "Tendsto", "inf", "sup", "csInf", "csSup", "ENat.toNat", "Set.ncard", "Nat.card"]
_IDENT_CH = r"[\w'!?₀-₉]"


@dataclass
class Target:
    """What the desk wrote for a problem (from `skeleton` / `disproofSkeleton` / `reductionSkeleton`)."""
    problem: str
    decl: str
    import_line: str
    solution_sig: str = ""            # text between `theorem OMA.solution :` and `:= by`, exactly
    disproof_sig: str = ""
    answer: bool = False              # the statement depends on a placeholder defined as sorry upstream
    placeholder: str = ""
    reduction_ns: str = ""
    sorry_decls: list[str] = field(default_factory=list)     # the module's declarations still `sorry` upstream
    module_defs: list[str] = field(default_factory=list)     # definitions of the upstream module (answer rule)


def _sig(skel: str, name: str) -> str:
    m = re.search(rf"(?ms)^theorem {re.escape(name)} :(.*?):= by", skel or "")
    return m.group(1) if m else ""


def target_of(problem: dict, brief: str = "") -> Target | None:
    skel = problem.get("skeleton") or ""
    first = next((l for l in skel.split("\n") if l.strip()), "")
    m = re.search(r"type_of% @([^\s)]+)", skel) or re.search(r"type_of% @([^\s)]+)", problem.get("disproofSkeleton") or "")
    if not first.startswith("import ") or m is None:
        return None
    t = Target(problem["id"], m.group(1), first, _sig(skel, "OMA.solution"),
               _sig(problem.get("disproofSkeleton") or "", "OMA.disproof"))
    ph = re.search(r"placeholder ([^\s;)]+) := sorry", skel)
    if ph or re.search(r"(?m)^\s*\S+ = OMA\.answer →", t.solution_sig):
        t.answer = True
        t.placeholder = ph.group(1) if ph else t.solution_sig.split("=", 1)[0].strip()
        t.disproof_sig = ""           # a value question: no refutation form
    rn = re.search(r"(?m)^namespace (OMA\.R_\S+)", problem.get("reductionSkeleton") or "")
    t.reduction_ns = rn.group(1) if rn else ""
    if brief:
        block = brief.split("Still sorry upstream", 1)
        if len(block) == 2:
            t.sorry_decls = re.findall(r"(?m)^\s{2}([A-Za-z0-9_.'«»]+)\s*$", block[1].split("==", 1)[0])
        upstream = brief.split("THE FULL UPSTREAM FILE", 1)[-1]
        t.module_defs = sorted(set(re.findall(r"(?m)^\s*(?:noncomputable\s+|private\s+|protected\s+)*"
                                              r"(?:def|abbrev|structure|inductive|class)\s+([^\s:({\[]+)", upstream)))
    return t


def reduction_namespace(problem_id: str, n: int) -> str:
    return "OMA.R_" + re.sub(r"[^A-Za-z0-9]", "_", problem_id) + f"_R{n}"


# ---------------------------------------------------------------- helpers
def code_only(text: str) -> str:
    """Comments removed, strings blanked (Lean's lexer, leancheck.lean_code_only)."""
    return leancheck.lean_code_only(text)


def has_word(text: str, word: str) -> bool:
    if not re.match(r"\w", word[0]):
        return word in text
    return re.search(rf"(?<!{_IDENT_CH}){re.escape(word)}(?!{_IDENT_CH})", text) is not None


def commands(code: str) -> list[tuple[int, str]]:
    """(line number, text) of each line that starts a top-level command (no indentation)."""
    return [(i + 1, l) for i, l in enumerate(code.split("\n")) if l.strip() and not l[0].isspace()]


def _head(line: str) -> tuple[list[str], str]:
    """Attributes and modifiers of a command line, then its keyword."""
    attrs = re.findall(r"@\[([^\]]*)\]", line)
    rest = re.sub(r"@\[[^\]]*\]\s*", "", line).strip()
    words = rest.split()
    while words and words[0] in MODIFIERS:
        words = words[1:]
    return attrs, (words[0] if words else "")


def _fail(out: list, rid: str, detail: str) -> None:
    out.append({"rule": rid, "ok": False, "detail": detail[:300]})


def _blocks(code: str) -> list[tuple[str, str, str]]:
    """(keyword, name, text) of each top-level declaration."""
    lines = code.split("\n")
    starts = [i for i, l in enumerate(lines) if l.strip() and not l[0].isspace()
              and _head(l)[1] not in CONTINUATIONS and re.match(r"[\w@]", l)]
    out = []
    for k, i in enumerate(starts):
        j = starts[k + 1] if k + 1 < len(starts) else len(lines)
        text = "\n".join(lines[i:j])
        _a, kw = _head(lines[i])
        rest = re.sub(r"@\[[^\]]*\]\s*", "", lines[i]).split()
        while rest and rest[0] in MODIFIERS:
            rest = rest[1:]
        name = rest[1] if len(rest) > 1 else ""
        out.append((kw, re.split(r"[\s:({\[⦃]", name)[0], text))
    return out


# ---------------------------------------------------------------- the text rules
def check_text(text: str, t: Target, kind: str = "proof") -> list[dict]:
    """Every failed rule (empty = the text rules pass). `kind`: proof | disproof | reduction | statement."""
    out: list[dict] = []
    if '"' in text:
        _fail(out, "quote", "le fichier contient un guillemet double")
    code = code_only(text)
    lines = [l for l in code.split("\n") if l.strip()]
    if not lines or lines[0].rstrip() != t.import_line.rstrip():
        _fail(out, "import_first", f"la première ligne doit être « {t.import_line} »")
    seen_decl = False
    for n, line in commands(code):
        attrs, kw = _head(line)
        for a in attrs:
            if a.strip() not in ("simp", "local simp"):
                _fail(out, "commands", f"ligne {n} : attribut @[{a.strip()}] non autorisé")
        if kw == "deriving" and re.match(r"\s*deriving\s+instance\b", line):
            _fail(out, "commands", f"ligne {n} : « deriving instance » non autorisé")
            continue
        if not kw or kw in CONTINUATIONS or not re.match(r"[A-Za-z_]", kw):
            continue                  # attributes alone, `termination_by`, `| pattern`, `⟨…⟩`: part of a declaration
        if kw == "import":
            if seen_decl or (line.rstrip() != t.import_line.rstrip() and not re.match(r"^import Mathlib(\.\S+)?\s*$", line)):
                _fail(out, "import_first", f"ligne {n} : import non autorisé « {line.strip()[:80]} »")
            continue
        seen_decl = True
        if kw not in COMMANDS:
            _fail(out, "commands", f"ligne {n} : commande « {kw[:40]} » non autorisée")
    for m in re.finditer(r"\bset_option\s+(\S+)\s+(\S+)(\s+in\b)?", code):
        if m.group(1) not in SET_OPTIONS or not m.group(2).isdigit() or not m.group(3):
            _fail(out, "commands", f"« set_option {m.group(1)} {m.group(2)} » : seulement set_option "
                                   f"<{'|'.join(sorted(SET_OPTIONS))}> <nombre> in")
    words = [w for w in WORDS if has_word(code, w)]
    if kind == "statement":
        words = [w for w in words if w != "sorry"]
    if words:
        _fail(out, "words", "mots interdits : " + ", ".join(words))
    if re.search(r"decide\s*:=\s*true", code):
        _fail(out, "words", "« decide := true » est interdit")
    if re.search(r"(?m)^\s*#[A-Za-z]", code) or re.search(HASH_COMMANDS, code):
        _fail(out, "words", "commande # interdite")
    if kind == "reduction":
        _reduction(code, t, out)
    elif kind == "statement":
        _statement(code, out)
    else:
        _target(code, t, kind, out)
    _upstream(code, t, out)
    if t.answer and kind == "proof":
        _answer(code, t, out)
    return out


def _target(code: str, t: Target, kind: str, out: list) -> None:
    sols = re.findall(r"(?m)^theorem OMA\.solution\b", code)
    dis = re.findall(r"(?m)^theorem OMA\.disproof\b", code)
    if len(sols) + len(dis) != 1:
        _fail(out, "target", "il faut exactement un « theorem OMA.solution » ou « theorem OMA.disproof »")
        return
    name, want = ("OMA.solution", t.solution_sig) if sols else ("OMA.disproof", t.disproof_sig)
    if (kind == "disproof") != bool(dis):
        _fail(out, "target", f"le fichier ne contient pas la forme attendue ({kind})")
        return
    if not want:
        _fail(out, "target", f"aucune forme {name} n'est proposée pour ce problème")
        return
    if _sig(code, name) != want:
        _fail(out, "target", f"l'énoncé de {name} doit être exactement « {want.strip()[:200]} »")


def _upstream(code: str, t: Target, out: list) -> None:
    """The upstream declaration (sorry inside) is never used: only inside `type_of% @<decl>`."""
    rest = code.replace(f"type_of% @{t.decl}", "")
    if t.placeholder:
        rest = rest.replace(t.placeholder, "")

    def used(d: str) -> bool:      # `X` itself, not a longer name `X.variants.y` (proved variants are fine)
        return re.search(rf"(?<![\w'!?₀-₉.]){re.escape(d)}(?![\w'!?₀-₉.])", rest) is not None
    banned = [t.decl] + [d for d in t.sorry_decls if d != t.placeholder]
    hit = [d for d in banned if used(d)]
    short = [d.split(".", 1)[1] for d in banned if "." in d]
    hit += [d for d in short if d and used(d) and d not in hit]
    if hit:
        _fail(out, "upstream", "le fichier utilise une déclaration encore « sorry » en amont : " + ", ".join(hit[:4]))


def _value_of(code: str, name: str) -> tuple[str, str] | None:
    for kw, n, text in _blocks(code):
        if kw in ("def", "abbrev") and n == name:
            head, sep, val = text.partition(":=")
            typ = head.split(name, 1)[1].strip() if name in head else ""
            return (typ, val) if sep else None
    return None


def _answer(code: str, t: Target, out: list) -> None:
    v = _value_of(code, "OMA.answer")
    if v is None:
        _fail(out, "answer", "il faut « def OMA.answer : <type> := <valeur> »")
        return
    typ, val = v
    if not typ.startswith(":"):
        _fail(out, "answer", "le type de OMA.answer doit être écrit (celui de l'espace réservé)")
    texts = [val]
    helpers = {n: tx for kw, n, tx in _blocks(code) if kw in ("def", "abbrev") and n != "OMA.answer"}
    for n, tx in helpers.items():                       # helpers the value uses, one level down
        if has_word(val, n) or has_word(val, n.rsplit(".", 1)[-1]):
            texts.append(tx.partition(":=")[2])
    root = t.decl.split(".", 1)[0]
    for tx in texts:
        bad = [w for w in ANSWER_WORDS if has_word(tx, w)]
        if has_word(tx, root) or f"{root}." in tx:
            bad.append(root + ".…")
        bad += [d for d in t.module_defs if has_word(tx, d)]
        if t.placeholder and has_word(tx, t.placeholder.rsplit(".", 1)[-1]):
            bad.append(t.placeholder)
        if bad:
            _fail(out, "answer", "valeur non explicite (" + ", ".join(dict.fromkeys(bad)) + ")")
            return


def _reduction(code: str, t: Target, out: list) -> None:
    m = re.search(r"(?m)^namespace (OMA\.R_\S+?)_R(\d+)\s*$", code)
    if not m or m.group(1) != reduction_namespace(t.problem, 1).rsplit("_R", 1)[0] or not 1 <= int(m.group(2)) <= 3:
        _fail(out, "reduction", "espace de noms attendu : " + reduction_namespace(t.problem, 1) + " (R1 à R3)")
        return
    hs, others = {}, []
    for kw, n, text in _blocks(code):
        if kw in ("def", "abbrev") and re.fullmatch(r"H\d", n):
            if not re.match(rf"(?s)\S+\s+H\d\s*:\s*Prop\s*:=", re.sub(r"@\[[^\]]*\]\s*", "", text).strip()):
                _fail(out, "reduction", f"{n} doit être « def {n} : Prop := … »")
            hs[n] = text.partition(":=")[2]
        elif kw in ("def", "abbrev", "structure", "inductive", "instance"):
            others.append(n or kw)
    if others:
        _fail(out, "reduction", "aucune autre def / structure / instance : " + ", ".join(others[:4]))
    names = sorted(hs, key=lambda x: int(x[1:]))
    if not 2 <= len(names) <= 4 or names != [f"H{i}" for i in range(1, len(names) + 1)]:
        _fail(out, "reduction", "il faut 2 à 4 hypothèses H1, H2, …")
        return
    for n, body in hs.items():
        bad = [w for w in ["main", "type_of%", t.decl] + [x for x in names if x != n] if has_word(body, w)]
        if bad:
            _fail(out, "reduction", f"{n} mentionne {', '.join(bad)}")
    want = " " + " → ".join(names + [f"type_of% @{t.decl}"]) + " "
    if _sig(code, "main") != want:
        _fail(out, "reduction", "il faut « theorem main :" + want + ":= by … »")


def _statement(code: str, out: list) -> None:
    thms = [(n, tx) for kw, n, tx in _blocks(code) if kw in ("theorem", "lemma")]
    if len(thms) != 1 or thms[0][0].rsplit(".", 1)[-1] != "main":
        _fail(out, "statement", "il faut un seul théorème, « main »")
        return
    body = thms[0][1].rsplit(":=", 1)[-1].strip()
    if body not in ("sorry", "by sorry", "by\n  sorry") and re.sub(r"\s+", " ", body) != "by sorry":
        _fail(out, "statement", "le corps de main reste « sorry »")
    if len(re.findall(rf"(?<!{_IDENT_CH})sorry(?!{_IDENT_CH})", code)) != 1:
        _fail(out, "statement", "aucun autre « sorry »")


# ---------------------------------------------------------------- the local check (fresh strict Lean)
def strict_name(text: str, kind: str, t: Target) -> str:
    if kind == "reduction":
        m = re.search(r"(?m)^namespace (\S+)", code_only(text))
        return f"{m.group(1)}.main" if m else "main"
    if kind == "statement":
        return ""
    return "OMA.disproof" if kind == "disproof" else "OMA.solution"


def axioms_ok(axioms: list[str] | None, text: str, t: Target) -> tuple[bool, str]:
    if axioms is None:
        return False, "axiomes non contrôlés"
    extra = [a for a in axioms if a not in ALLOWED_AXIOMS]
    if extra == ["sorryAx"] and t.answer and not has_word(code_only(text), "sorry"):
        # the placeholder `… := sorry` of the statement: tolerated like the site's checker does (join.txt); the
        # file itself names no sorry and no other upstream sorry declaration (rules words / upstream)
        return True, "sorryAx de l'espace réservé seulement (relu par une personne)"
    if extra:
        return False, "axiomes non standard : " + ", ".join(extra)
    return True, ""


async def local_check(ctx, ws, text: str, t: Target, kind: str = "proof", timeout_s: int = 1200) -> dict:
    """The text rules, then a fresh strict Lean (never the warm one, D37) in the pinned workspace.
    {rules: [...failures], local: ok|refused|error|not_run, axioms, summary, ready}."""
    fails = check_text(text, t, kind)
    res = {"rules": fails, "local": "not_run", "axioms": None, "summary": "", "ready": False}
    if fails:
        res["summary"] = "règles du vérificateur : " + "; ".join(f["detail"] for f in fails[:3])
        return res
    if ws is None:
        res["summary"] = "espace de travail Left to Solve absent"
        return res
    name = strict_name(text, kind, t)
    code = leancheck.with_axiom_probe(text, name) if name else text
    # the answer case tolerates the placeholder's sorryAx: verdict computed here from the messages; otherwise the
    # usual strict verdict (judge with the axiom probe)
    strict = name if (name and not t.answer) else None
    r = await ctx.lean.check(code, ws, timeout_s, strict)
    if r.infra_error:
        res.update(local="error", summary=str(r.infra_error)[:300])
        return res
    v = r.verdict
    axioms = v.axioms if strict else (_axioms_from(r.stdout, name) if name else None)
    res["axioms"] = axioms
    if r.timed_out or [e for e in v.errors if e.severity == "error"]:
        res.update(local="refused", summary=v.summary)
        return res
    if strict and not v.ok:
        res.update(local="refused", summary=v.summary)
        return res
    if name:
        ok_ax, why = axioms_ok(axioms, text, t)
        if not ok_ax:
            res.update(local="refused", summary=why)
            return res
        res["summary"] = why
    res.update(local="ok", ready=True,
               summary=res["summary"] or "Lean accepte le fichier (vérification stricte, nouveau processus)")
    return res


def _axioms_from(stdout: str, name: str) -> list[str] | None:
    for m in leancheck.parse_lean_json(stdout or ""):
        mm = leancheck.AXIOMS_RE.search(m.text)
        if mm and mm.group("name").split(".")[-1] == name.split(".")[-1]:
            return [a.strip() for a in mm.group("ax").split(",") if a.strip()]
        if leancheck.NO_AXIOMS_RE.search(m.text):
            return []
    return None
