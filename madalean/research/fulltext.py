"""Full text of sources, with anchors, and the per-shelf search index.

TeX (preferred, from arXiv sources): main file found and `\\input`/`\\include` inlined (inside the extracted archive
only), comments removed, user macros expanded conservatively (simple `\\newcommand`/`\\def`/`\\DeclareMathOperator`
bodies, bounded), sections numbered like LaTeX does, theorem-like environments recognised from the document's own
`\\newtheorem` / `\\declaretheorem` declarations (numbering emulated: shared counters, `[section]` reset), labels,
proofs attached to their statements, `\\ref`/`\\eqref`/`\\cref`/`\\cite` collected, `\\bibitem` keys. The paper's TeX
is NEVER compiled, only parsed.

PDF: `pdftotext -bbox-layout` (poppler, run with time and memory limits) → pages → flows → blocks → lines; running
headers / footers removed (lines repeated in the top / bottom band of many pages, page numbers), end-of-line
hyphenation undone, two-column pages follow poppler's reading order (detected and reported). Each chunk keeps its
page and bounding box (PDF points, origin top-left as pdftotext gives it). No text layer → reported honestly; OCR
with tesseract when installed (maths from OCR flagged unreliable).

Chunks: one per paragraph / theorem / proof (merged up to ~1 200 characters, never across pages or sections), with
a stable id `c-<sha1>` derived from the source, its anchor and its text. Index: SQLite FTS5 (`index.sqlite` of the
shelf); optional semantic re-ranking through `madalean.brain.rag.Embedder` (local Ollama only, same policy as the
declaration index)."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .safety import run_tool, safe_join

MAX_TEX = 8 * 1024 * 1024
CHUNK_CHARS = 1200

# ================================================================ TeX helpers
def strip_comments(tex: str) -> str:
    out = []
    for line in tex.split("\n"):
        m = re.search(r"(?<!\\)(?:\\\\)*%", line)
        out.append(line[:m.start() + (len(m.group(0)) - 1)] if m else line)
    return "\n".join(out)


def braced_at(text: str, i: int) -> tuple[str, int] | None:
    """`text[i]` is '{' → (content, index after the closing brace)."""
    if i >= len(text) or text[i] != "{":
        return None
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return None


def bracket_at(text: str, i: int) -> tuple[str, int] | None:
    """Optional argument `[...]` (nested braces respected)."""
    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i >= len(text) or text[i] != "[":
        return None
    depth = 0
    j = i + 1
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "]" and depth == 0:
            return text[i + 1:j], j + 1
        j += 1
    return None


def braced_after(text: str, cmd: str) -> str:
    k = text.find(cmd + "{")
    if k < 0:
        m = re.search(re.escape(cmd) + r"\s*(\[[^\]]*\])?\s*\{", text)
        if not m:
            return ""
        k = m.end() - 1 - len(cmd)
        r = braced_at(text, m.end() - 1)
        return r[0].strip() if r else ""
    r = braced_at(text, k + len(cmd))
    return r[0].strip() if r else ""


def decode_tex(data: bytes) -> str:
    """UTF-8, else Latin-1 (older papers / LyX exports declare latin1/latin9 input encodings)."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def read_tex(path: Path) -> str:
    return decode_tex(Path(path).read_bytes()[:MAX_TEX])


def find_main_tex(root: Path) -> Path | None:
    cands = []
    for p in sorted(Path(root).rglob("*.tex")):
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_TEX:
            continue
        try:
            head = read_tex(p)
        except OSError:
            continue
        s = strip_comments(head)
        score = (2 if "\\documentclass" in s else 0) + (2 if "\\begin{document}" in s else 0) + \
            (1 if p.parent == Path(root) else 0)
        if score:
            cands.append((score, p.stat().st_size, p))
    if not cands:
        return None
    cands.sort(key=lambda x: (-x[0], -x[1]))
    return cands[0][2]


def inline_inputs(text: str, root: Path | None, depth: int = 0, budget: list | None = None) -> str:
    """Replace `\\input{x}` / `\\include{x}` / `\\subfile{x}` by the file's text — only files inside `root`."""
    budget = budget if budget is not None else [MAX_TEX]
    if root is None or depth > 8:
        return text

    def repl(m: re.Match) -> str:
        name = m.group(2).strip()
        for cand in (name, name + ".tex"):
            try:
                p = safe_join(root, cand)
            except ValueError:
                return ""
            if p.is_file() and not p.is_symlink():
                data = read_tex(p)
                budget[0] -= len(data)
                if budget[0] < 0:
                    return ""
                return "\n" + inline_inputs(strip_comments(data), root, depth + 1, budget) + "\n"
        return ""
    return re.sub(r"\\(input|include|subfile)\s*\{([^{}\n]{1,200})\}", repl, text)


# ---------------------------------------------------------------- macros
FORBIDDEN_IN_MACRO = re.compile(r"\\(def|gdef|edef|xdef|newcommand|renewcommand|input|include|write|immediate|openin|"
                                r"openout|read|catcode|csname|expandafter|loop|let|futurelet|makeatletter|"
                                r"usepackage|special|directlua)\b")


def collect_macros(tex: str) -> dict[str, tuple[int, str]]:
    """name → (number of arguments, body) for simple user macros."""
    out: dict[str, tuple[int, str]] = {}
    for m in re.finditer(r"\\(?:(?:re)?newcommand|providecommand)\*?\s*\{?\\([A-Za-z]+)\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*\{",
                         tex):
        r = braced_at(tex, m.end() - 1)
        if r:
            out[m.group(1)] = (int(m.group(2) or 0), r[0])
    for m in re.finditer(r"\\def\s*\\([A-Za-z]+)\s*((?:#\d)*)\s*\{", tex):
        r = braced_at(tex, m.end() - 1)
        if r:
            out[m.group(1)] = (len(m.group(2)) // 2, r[0])
    for m in re.finditer(r"\\DeclareMathOperator(\*?)\s*\{?\\([A-Za-z]+)\}?\s*\{", tex):
        r = braced_at(tex, m.end() - 1)
        if r:
            out[m.group(2)] = (0, ("\\operatorname*{" if m.group(1) else "\\operatorname{") + r[0] + "}")
    safe = {}
    for k, (n, body) in out.items():
        if len(body) <= 400 and not FORBIDDEN_IN_MACRO.search(body) and k not in ("begin", "end", "label", "ref", "cite",
                                                                                  "section", "item"):
            safe[k] = (n, body)
    return safe


def expand_macros(text: str, macros: dict, max_steps: int = 3000) -> str:
    if not macros:
        return text
    names = sorted(macros, key=len, reverse=True)
    pat = re.compile(r"\\(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z])")
    steps = 0
    for _round in range(4):
        changed = False
        out, i = [], 0
        for m in pat.finditer(text):
            if m.start() < i:
                continue
            n, body = macros[m.group(1)]
            j = m.end()
            args = []
            ok = True
            for _k in range(n):
                while j < len(text) and text[j] in " \t":
                    j += 1
                r = braced_at(text, j)
                if r is None:
                    if j < len(text) and n:
                        args.append(text[j])
                        j += 1
                        continue
                    ok = False
                    break
                args.append(r[0])
                j = r[1]
            if not ok:
                continue
            rep = body
            for k, a in enumerate(args, 1):
                rep = rep.replace(f"#{k}", a)
            out.append(text[i:m.start()])
            out.append(rep if not rep[-1:].isalpha() or not text[j:j + 1].isalpha() else rep + " ")
            i = j
            changed = True
            steps += 1
            if steps > max_steps:
                break
        out.append(text[i:])
        text = "".join(out)
        if not changed or steps > max_steps:
            break
    return text


# ---------------------------------------------------------------- theorem-like environments
KIND_WORDS = [("theorem", ("theorem", "théorème", "satz", "teorema", "thm")),
              ("lemma", ("lemma", "lemme", "lem", "hilfssatz")),
              ("proposition", ("proposition", "prop")),
              ("corollary", ("corollary", "corollaire", "cor", "folgerung", "korollar")),
              ("definition", ("definition", "définition", "defn", "def", "notation")),
              ("conjecture", ("conjecture", "conj", "vermutung")),
              ("claim", ("claim", "fact", "observation", "assertion", "affirmation")),
              ("question", ("question", "problem", "problème", "open problem")),
              ("remark", ("remark", "remarque", "note", "bemerkung", "rem")),
              ("example", ("example", "exemple", "ex", "beispiel")),
              ("hypothesis", ("hypothesis", "assumption", "condition", "hypothèse")),
              ("exercise", ("exercise", "exercice"))]
STATEMENT_KINDS = ("theorem", "lemma", "proposition", "corollary", "definition", "conjecture", "claim", "question")


def kind_of(name: str) -> str:
    n = re.sub(r"[^a-zàâçéèêëîïôûùüÿœ ]", "", (name or "").lower()).strip()
    for kind, words in KIND_WORDS:
        if n in words:
            return kind
    for kind, words in KIND_WORDS:
        if any(n.startswith(w) for w in words if len(w) > 3):
            return kind
    return ""


DEFAULT_ENVS = {"theorem": "Theorem", "thm": "Theorem", "lemma": "Lemma", "lem": "Lemma",
                "proposition": "Proposition", "prop": "Proposition", "corollary": "Corollary", "cor": "Corollary",
                "definition": "Definition", "defn": "Definition", "conjecture": "Conjecture", "claim": "Claim",
                "remark": "Remark", "example": "Example", "question": "Question", "problem": "Problem",
                "fact": "Fact", "observation": "Observation", "exercise": "Exercise"}


@dataclass
class EnvDecl:
    name: str
    title: str
    counter: str          # counter name (own name, or the sibling's)
    within: str = ""      # section | subsection | chapter | ''
    starred: bool = False
    kind: str = ""


def theorem_decls(tex: str, macros: dict | None = None) -> dict[str, EnvDecl]:
    decls: dict[str, EnvDecl] = {}
    for m in re.finditer(r"\\(?:new|sp)theorem(\*?)\s*\{([^{}]+)\}", tex):
        star, name = m.group(1), m.group(2).strip()
        j = m.end()
        shared = bracket_at(tex, j)
        if shared:
            j = shared[1]
        while j < len(tex) and tex[j] in " \t\n":
            j += 1
        title = braced_at(tex, j)
        if not title:
            continue
        j = title[1]
        within = bracket_at(tex, j)
        ttl = expand_macros(title[0].replace("\\protect", ""), macros or {})
        d = EnvDecl(name, re.sub(r"\\[A-Za-z]+\s*", "", ttl).replace("{", "").replace("}", "").strip(), name,
                    (within[0].strip() if within else ""), bool(star))
        if shared:
            d.counter = shared[0].strip()
        d.kind = kind_of(d.title) or kind_of(name)
        decls[name] = d
    for m in re.finditer(r"\\declaretheorem\s*(\[[^\]]*\])?\s*\{([^{}]+)\}", tex):
        opts = (m.group(1) or "").strip("[]")
        name = m.group(2).strip()
        o = dict((k.strip(), v.strip()) for k, _, v in (p.partition("=") for p in opts.split(",")) if k.strip())
        title = o.get("name") or o.get("title") or name.capitalize()
        d = EnvDecl(name, title, o.get("sibling") or o.get("sharenumber") or o.get("numberlike") or name,
                    o.get("numberwithin") or o.get("parent") or "", "numbered" in o and o["numbered"] == "no")
        d.kind = kind_of(title) or kind_of(name)
        decls[name] = d
    for m in re.finditer(r"\\numberwithin\s*\{([^{}]+)\}\s*\{([^{}]+)\}", tex):
        for d in decls.values():
            if d.counter == m.group(1).strip():
                d.within = m.group(2).strip()
    # counters shared with a sibling inherit its `within`
    for d in decls.values():
        if d.counter != d.name and d.counter in decls and not d.within:
            d.within = decls[d.counter].within
    return decls


# ---------------------------------------------------------------- document model
REF_RE = re.compile(r"\\(?:ref|eqref|cref|Cref|autoref|thref|vref|crefrange|cpageref|pageref)\*?\s*\{([^{}]+)\}")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|cites|parencite|textcite|autocite|footcite|citeauthor|citeyear)\*?"
                     r"\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]+)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^{}]+)\}")


@dataclass
class TexNode:
    env: str
    kind: str
    name: str                 # display name ("Theorem")
    number: str               # "2.1", "" when unnumbered
    label: str
    labels: list[str]         # every label inside (equations too)
    title: str                # optional argument
    text: str                 # statement (macros expanded, comments removed)
    start: int
    section: str              # "2" / "2.3"
    section_title: str
    proof: str = ""
    proof_refs: list[str] = field(default_factory=list)
    stmt_refs: list[str] = field(default_factory=list)
    cites: list[str] = field(default_factory=list)
    starred: bool = False


@dataclass
class TexDoc:
    title: str = ""
    abstract: str = ""
    sections: list[dict] = field(default_factory=list)          # {number, title, start, level}
    nodes: list[TexNode] = field(default_factory=list)
    paragraphs: list[dict] = field(default_factory=list)        # {section, section_title, text, start}
    bibitems: dict = field(default_factory=dict)                # key -> text
    bib_files: list[str] = field(default_factory=list)
    label_map: dict = field(default_factory=dict)               # label -> "Theorem 2.1" / "Section 3" / "(2.4)"
    warnings: list[str] = field(default_factory=list)


def _split_refs(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


SECTION_RE = re.compile(r"\\(chapter|section|subsection|subsubsection)(\*?)\s*(?:\[[^\]]*\])?\s*\{")
ENV_RE = re.compile(r"\\(begin|end)\s*\{([A-Za-z@*]+)\}")


def parse_tex(tex: str, root: Path | None = None) -> TexDoc:
    """Parse a paper's TeX (never compiled). `root`: directory of the extracted archive for \\input."""
    doc = TexDoc()
    full = strip_comments(tex[:MAX_TEX])
    full = inline_inputs(full, root)
    macros = collect_macros(full)
    decls = theorem_decls(full, macros)
    m = re.search(r"\\begin\{document\}", full)
    body = full[m.end():] if m else full
    e = re.search(r"\\end\{document\}", body)
    body = body[:e.start()] if e else body
    body = remove_definitions(body)
    doc.title = clean_inline(expand_macros(braced_after(full, "\\title"), macros))
    am = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
    if am:
        doc.abstract = clean_inline(expand_macros(am.group(1), macros))
    doc.bib_files = [b.strip() for m2 in re.finditer(r"\\(?:bibliography|addbibresource)\s*\{([^{}]+)\}", full)
                     for b in m2.group(1).split(",")]
    for bm in re.finditer(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\}|$)",
                          body, re.S):
        doc.bibitems[bm.group(1).strip()] = clean_inline(bm.group(2))[:600]
    # ---- walk sections and environments in order
    events = []
    for sm in SECTION_RE.finditer(body):
        r = braced_at(body, sm.end() - 1)
        if r:
            events.append((sm.start(), "section", sm.group(1), sm.group(2), r[0], r[1]))
    for am2 in re.finditer(r"\\appendix\b", body):
        events.append((am2.start(), "appendix", "", "", "", am2.end()))
    stack = []
    for em in ENV_RE.finditer(body):
        name = em.group(2)
        base = name.rstrip("*")
        is_thm = name in decls or base in decls or base in DEFAULT_ENVS or name == "proof"
        if not is_thm:
            continue
        if em.group(1) == "begin":
            stack.append((name, em.start(), em.end()))
        else:
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][0] == name:
                    nm, s0, s1 = stack.pop(k)
                    if not any(st[0] != "proof" and st[1] < s0 for st in stack):     # outermost theorem-like only
                        events.append((s0, "env", nm, "", body[s1:em.start()], em.end()))
                    elif nm == "proof":
                        events.append((s0, "env", nm, "", body[s1:em.start()], em.end()))
                    break
    events.sort(key=lambda x: x[0])
    sec = [0, 0, 0, 0]
    appendix = False
    cur_sec, cur_title = "", ""
    counters: dict[str, int] = {}
    last_node: TexNode | None = None
    pending = ""
    pending_paras = 0
    last_end = 0
    for ev in events:
        pos = ev[0]
        if ev[1] == "appendix":
            appendix = True
            sec = [0, 0, 0, 0]
            continue
        if ev[1] == "section":
            _paragraphs(doc, body[last_end:pos], (cur_sec, cur_title), macros, last_end)
            level = {"chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3}[ev[2]]
            title = clean_inline(expand_macros(ev[4], macros))
            if ev[3] != "*":
                sec[level] += 1
                for k in range(level + 1, 4):
                    sec[k] = 0
                top = sec[1]
                head = (chr(64 + top) if appendix and top <= 26 else str(top)) if level >= 1 else str(sec[0])
                parts = [head] + [str(sec[k]) for k in range(2, level + 1)]
                number = ".".join(parts) if level >= 1 else str(sec[0])
                for c in list(counters):
                    d = next((x for x in decls.values() if x.counter == c), None)
                    if d and d.within in ("section", "chapter") and level <= 1 or \
                            d and d.within == "subsection" and level <= 2:
                        counters[c] = 0
            else:
                number = ""
            _section_proof(doc, pending, pending_paras)
            cur_sec, cur_title = number, title
            pending_paras = len(doc.paragraphs)
            pm = re.search(r"(?i)(proof|preuve|beweis).*?\\(?:ref|cref|Cref|autoref)\*?\s*\{([^{}]+)\}", ev[4])
            pending = pm.group(2).strip() if pm else ""
            doc.sections.append({"number": number, "title": title, "start": pos, "level": level})
            seg_label = LABEL_RE.search(body[ev[5]:ev[5] + 200])
            if seg_label and number:
                doc.label_map[seg_label.group(1)] = f"Section {number}"
            last_end = ev[5]
            continue
        name, inner, end = ev[2], ev[4], ev[5]
        _paragraphs(doc, body[last_end:pos], (cur_sec, cur_title), macros, last_end)
        last_end = end
        if name == "proof":
            opt = bracket_at(inner, 0)
            ptext = inner[opt[1]:] if opt and inner.lstrip().startswith("[") else inner
            target = last_node
            if pending:
                target = next((n for n in doc.nodes if pending in n.labels), target)
                pending = ""
            if opt:
                lm = REF_RE.search(opt[0])
                if lm:
                    target = next((n for n in doc.nodes if lm.group(1) in n.labels), target)
            if target is not None and not target.proof:
                target.proof = clean_block(expand_macros(ptext, macros))
                target.proof_refs = list(dict.fromkeys(r for x in REF_RE.findall(ptext) for r in _split_refs(x)
                                                       if r not in target.labels))
                target.cites += [c for x in CITE_RE.findall(ptext) for c in _split_refs(x) if c not in target.cites]
            continue
        base = name.rstrip("*")
        d = decls.get(name) or decls.get(base)
        disp = d.title if d else DEFAULT_ENVS.get(base, base.capitalize())
        kind = (d.kind if d and d.kind else kind_of(disp) or kind_of(base)) or "other"
        starred = name.endswith("*") or (d.starred if d else False)
        number = ""
        if not starred:
            cname = d.counter if d else base
            counters[cname] = counters.get(cname, 0) + 1
            within = d.within if d else (decls[cname].within if cname in decls else "")
            if not d and cname in decls:
                within = decls[cname].within
            if within in ("section", "chapter") and cur_sec:
                number = f"{cur_sec.split('.')[0]}.{counters[cname]}"
            elif within == "subsection" and cur_sec:
                number = f"{cur_sec}.{counters[cname]}"
            else:
                number = str(counters[cname])
        opt = bracket_at(inner, 0) if inner.lstrip().startswith("[") else None
        title = clean_inline(expand_macros(opt[0], macros)) if opt else ""
        stmt = inner[opt[1]:] if opt else inner
        labels = LABEL_RE.findall(stmt)
        node = TexNode(env=name, kind=kind, name=disp, number=number, label=labels[0] if labels else "", labels=labels,
                       title=title, text=clean_block(expand_macros(stmt, macros)), start=pos, section=cur_sec,
                       section_title=cur_title, starred=starred,
                       stmt_refs=[r for x in REF_RE.findall(stmt) for r in _split_refs(x)],
                       cites=list(dict.fromkeys(c for x in CITE_RE.findall(stmt + " " + (opt[0] if opt else ""))
                                                for c in _split_refs(x))))
        for lb in labels:
            doc.label_map[lb] = f"{disp} {number}".strip() if lb == node.label else f"({number})"
        doc.nodes.append(node)
        last_node = node
    _paragraphs(doc, body[last_end:], (cur_sec, cur_title), macros, last_end)
    _section_proof(doc, pending, pending_paras)
    for sct in doc.sections:
        sct["title"] = resolve_refs(sct["title"], doc.label_map)
    # equation labels outside theorem-like environments
    for lm in LABEL_RE.finditer(body):
        doc.label_map.setdefault(lm.group(1), "(eq)")
    if not decls and not doc.nodes:
        doc.warnings.append("no theorem-like environment found")
    return doc


def _section_proof(doc: TexDoc, label: str, first_para: int) -> None:
    """« Proof of Theorem \\ref{x} » written as a section without a proof environment: its paragraphs are the proof."""
    if not label:
        return
    node = next((n for n in doc.nodes if label in n.labels), None)
    paras = doc.paragraphs[first_para:]
    if node is None or node.proof or not paras:
        return
    text = "\n\n".join(p["text"] for p in paras)
    node.proof = text
    node.proof_refs = list(dict.fromkeys(r for x in REF_RE.findall(text) for r in _split_refs(x) if r not in node.labels))
    node.cites += [c for x in CITE_RE.findall(text) for c in _split_refs(x) if c not in node.cites]


DEF_RE = re.compile(r"\\(?:global\s*)?(?:\\long\s*)?\\(?:def|gdef|edef)\s*\\[A-Za-z@]+\s*(?:#\d)*\s*\{|"
                    r"\\(?:(?:re)?newcommand|providecommand|DeclareMathOperator)\*?\s*\{?\\[A-Za-z@]+\}?\s*"
                    r"(?:\[\d\])?\s*(?:\[[^\]]*\])?\s*\{")


def remove_definitions(text: str) -> str:
    out, i = [], 0
    for m in DEF_RE.finditer(text):
        if m.start() < i:
            continue
        r = braced_at(text, m.end() - 1)
        if r is None:
            continue
        out.append(text[i:m.start()])
        i = r[1]
    out.append(text[i:])
    return "".join(out)


def drop_commands(text: str, names: tuple[str, ...]) -> str:
    pat = re.compile(r"\\(" + "|".join(names) + r")\*?(?![A-Za-z])\s*(\[[^\]]*\])?\s*")
    out, i = [], 0
    for m in pat.finditer(text):
        if m.start() < i:
            continue
        out.append(text[i:m.start()])
        j = m.end()
        r = braced_at(text, j)
        i = r[1] if r else j
    out.append(text[i:])
    return "".join(out)


def _paragraphs(doc: TexDoc, seg: str, sec: tuple[str, str], macros: dict, offset: int) -> None:
    seg = re.sub(r"\\begin\{(abstract|thebibliography)\}.*?\\end\{\1\}", "", seg, flags=re.S)
    seg = drop_commands(seg, ("title", "author", "address", "email", "curraddr", "thanks", "date", "keywords",
                              "subjclass", "dedicatory", "urladdr", "maketitle", "bibliographystyle", "bibliography",
                              "addbibresource", "affiliation", "institute"))
    seg = re.sub(r"\\(maketitle|tableofcontents|newpage|clearpage|bigskip|medskip|smallskip|noindent)\b", "", seg)
    for para in re.split(r"\n\s*\n", seg):
        t = clean_block(expand_macros(para, macros))
        if len(t) >= 40:
            doc.paragraphs.append({"section": sec[0], "section_title": sec[1], "text": t, "start": offset})


def clean_inline(s: str) -> str:
    s = re.sub(r"\\(thanks|footnote|label|index)\s*\{(?:[^{}]|\{[^{}]*\})*\}", "", s or "")
    s = re.sub(r"\\(emph|textbf|textit|textrm|textsf|text|mbox|textsc|underline)\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"\2", s)
    s = s.replace("\\\\", " ").replace("~", " ")
    return re.sub(r"\s+", " ", s).strip()


def clean_block(s: str) -> str:
    """TeX of a statement / proof / paragraph → readable text with $math$ kept (for display, index, prompts)."""
    s = re.sub(r"\\(label|index)\s*\{[^{}]*\}", "", s or "")
    s = re.sub(r"\\(qedhere|qed|hfill|newline|par|vspace\*?\{[^}]*\}|hspace\*?\{[^}]*\})", " ", s)
    env_map = {"equation": "", "displaymath": "", "multline": "gathered", "gather": "gathered", "align": "aligned",
               "eqnarray": "aligned", "flalign": "aligned", "alignat": "aligned"}

    def disp(m):
        inner = m.group(3)
        inner = re.sub(r"\\(nonumber|notag)\b", "", inner)
        target = env_map.get(m.group(1), "")
        if m.group(1) == "alignat":
            inner = re.sub(r"^\s*\{\d+\}", "", inner)
        return "$$" + (f"\\begin{{{target}}}{inner}\\end{{{target}}}" if target else inner.strip()) + "$$"
    s = re.sub(r"\\begin\{(equation|align|gather|multline|displaymath|eqnarray|flalign|alignat)(\*?)\}(.*?)"
               r"\\end\{\1\2\}", disp, s, flags=re.S)
    s = re.sub(r"\\\[(.*?)\\\]", lambda m: "$$" + m.group(1).strip() + "$$", s, flags=re.S)
    s = re.sub(r"(?<!\\)~", " ", s)
    s = re.sub(r"\\(emph|textit)\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"*\2*", s)
    s = re.sub(r"\\textbf\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"**\1**", s)
    s = re.sub(r"\\begin\{(enumerate|itemize|description)\}(\[[^\]]*\])?|\\end\{(enumerate|itemize|description)\}", "\n",
               s)
    s = re.sub(r"\\item\s*(\[[^\]]*\])?", lambda m: "\n- " + (m.group(1)[1:-1] + " " if m.group(1) else ""), s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*", "\n\n", s)
    return s.strip()


def resolve_refs(text: str, label_map: dict) -> str:
    """`\\ref{l}` → number, `\\cite{k}` → `[@k]` (for display and prompts; unknown labels become '??')."""
    def ref(m):
        out = []
        for lb in _split_refs(m.group(1)):
            v = label_map.get(lb, "??")
            out.append(re.sub(r"^[A-Za-z]+ ", "", v) if m.group(0).startswith(("\\ref", "\\eqref")) else v)
        return ", ".join(out)
    text = REF_RE.sub(ref, text)
    return CITE_RE.sub(lambda m: "[" + "; ".join("@" + k for k in _split_refs(m.group(1))) + "]", text)


# ================================================================ chunks
@dataclass
class Chunk:
    id: str
    source_id: str
    ord: int
    kind: str                 # paragraph | theorem | lemma | … | proof | heading | ocr
    text: str
    page: int | None = None
    bbox: list | None = None  # [x0, y0, x1, y1] PDF points, top-left origin (pdftotext)
    section: str = ""
    label: str = ""
    locator: str = ""         # human anchor: « Theorem 2.1 », « §3, p. 5 »
    meta: dict = field(default_factory=dict)


def chunk_id(source_id: str, anchor: str, text: str) -> str:
    h = hashlib.sha1(f"{source_id}|{anchor}|{re.sub(r'\s+', ' ', text).strip()}".encode()).hexdigest()
    return "c-" + h[:16]


def tex_chunks(source_id: str, doc: TexDoc) -> list[Chunk]:
    items = []
    for p in doc.paragraphs:
        items.append((p["start"], "paragraph", p["text"], p["section"], p["section_title"], "", ""))
    for n in doc.nodes:
        loc = f"{n.name} {n.number}".strip() + (f" ({n.title})" if n.title else "")
        items.append((n.start, n.kind if n.kind != "other" else "statement", resolve_refs(n.text, doc.label_map),
                      n.section, n.section_title, n.label, loc))
        if n.proof:
            items.append((n.start + 1, "proof", resolve_refs(n.proof, doc.label_map), n.section, n.section_title,
                          n.label, f"Proof of {loc}"))
    items.sort(key=lambda x: x[0])
    out: list[Chunk] = []
    if doc.abstract:
        out.append(Chunk(chunk_id(source_id, "abstract", doc.abstract), source_id, 0, "abstract", doc.abstract,
                         locator="Abstract"))
    for start, kind, text, sec, stitle, label, loc in items:
        text = resolve_refs(text, doc.label_map) if kind == "paragraph" else text
        pieces = _split_long(text)
        for k, piece in enumerate(pieces):
            locator = loc or (f"§{sec} {stitle}".strip() if sec or stitle else "")
            anchor = f"{kind}|{sec}|{label}|{start}|{k}"
            out.append(Chunk(chunk_id(source_id, anchor, piece), source_id, len(out), kind, piece, None, None,
                             f"{sec} {stitle}".strip(), label, locator))
    return out


def _split_long(text: str, limit: int = CHUNK_CHARS * 2) -> list[str]:
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for sent in re.split(r"(?<=[.;:])\s+(?=[A-Z$\\])", text):
        if cur and len(cur) + len(sent) > CHUNK_CHARS:
            out.append(cur.strip())
            cur = ""
        cur += sent + " "
    if cur.strip():
        out.append(cur.strip())
    return out


# ================================================================ PDF
@dataclass
class PdfLine:
    text: str
    bbox: tuple
    block: int


@dataclass
class PdfResult:
    state: str                 # ok | no_text_layer | ocr | error
    pages: int
    chunks: list[Chunk]
    warnings: list[str]
    two_columns: int = 0       # pages detected as two-column
    removed_lines: int = 0     # header / footer lines removed


def _bbox_xml(path: Path, first: int | None = None, last: int | None = None) -> str:
    cmd = ["pdftotext", "-bbox-layout", "-enc", "UTF-8"]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    r = run_tool(cmd + [str(path), "-"], timeout=180, cpu=180)
    if r.rc != 0:
        raise RuntimeError(f"pdftotext failed: {r.stderr[:300] if r.rc is not None else 'timeout'}")
    return r.stdout.decode("utf-8", "replace")


def pdf_pages(path: Path, max_pages: int = 600) -> tuple[list[dict], int]:
    """[{width, height, blocks: [{bbox, lines: [PdfLine]}]}] from pdftotext -bbox-layout."""
    from .safety import parse_xml
    xml = _bbox_xml(path, 1, max_pages)
    xml = re.sub(r"^\s*<!DOCTYPE[^>]*>", "", xml, count=1)          # poppler's own doctype (texts are escaped)
    xml = re.sub(r'xmlns="[^"]*"', "", xml, count=1)
    xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]", "", xml)     # characters XML 1.0 forbids
    root = parse_xml(xml.encode("utf-8"))
    pages = []
    for pg in root.iter("page"):
        w, h = float(pg.get("width", 612)), float(pg.get("height", 792))
        blocks = []
        bi = 0
        for blk in pg.iter("block"):
            lines = []
            for ln in blk.iter("line"):
                words = [wd.text or "" for wd in ln.iter("word")]
                t = " ".join(x for x in words if x)
                if t.strip():
                    lines.append(PdfLine(t, tuple(float(ln.get(k, 0)) for k in ("xMin", "yMin", "xMax", "yMax")), bi))
            if lines:
                blocks.append({"bbox": tuple(float(blk.get(k, 0)) for k in ("xMin", "yMin", "xMax", "yMax")),
                               "lines": lines})
                bi += 1
        pages.append({"width": w, "height": h, "blocks": blocks})
    return pages, len(pages)


def _norm_hf(t: str) -> str:
    return re.sub(r"\d+", "#", t.lower()).strip()


def remove_headers_footers(pages: list[dict], band: float = 0.08) -> int:
    """Drop lines in the top / bottom bands repeated on many pages (and lone page numbers). Returns count."""
    counts: dict[str, int] = {}
    for pg in pages:
        seen = set()
        for b in pg["blocks"]:
            for ln in b["lines"]:
                y0, y1 = ln.bbox[1], ln.bbox[3]
                if y1 < band * pg["height"] or y0 > (1 - band) * pg["height"]:
                    k = _norm_hf(ln.text)
                    if k not in seen:
                        seen.add(k)
                        counts[k] = counts.get(k, 0) + 1
    n = len(pages)
    rep = {k for k, c in counts.items() if n >= 3 and c >= max(2, int(0.3 * n))}
    removed = 0
    for pg in pages:
        for b in pg["blocks"]:
            keep = []
            for ln in b["lines"]:
                y0, y1 = ln.bbox[1], ln.bbox[3]
                in_band = y1 < band * pg["height"] or y0 > (1 - band) * pg["height"]
                if in_band and (_norm_hf(ln.text) in rep or re.fullmatch(r"[-–—\s]*(\d{1,4}|[ivxlc]{1,6})[-–—\s]*",
                                                                          ln.text.strip(), re.I)):
                    removed += 1
                    continue
                keep.append(ln)
            b["lines"] = keep
        pg["blocks"] = [b for b in pg["blocks"] if b["lines"]]
    return removed


def join_lines(lines: list[str]) -> str:
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not out:
            out = ln
        elif re.search(r"[A-Za-zÀ-ÿ]-$", out) and re.match(r"[a-zà-ÿ]", ln):
            out = out[:-1] + ln                         # end-of-line hyphenation
        else:
            out += " " + ln
    return out


HEADING_RE = re.compile(r"^(?:(\d+(?:\.\d+){0,2})\.?|([A-Z])\.|§\s*\d+\.?)\s+([A-Z][^.]{2,80})$")


def is_two_column(pg: dict) -> bool:
    w = pg["width"]
    left = sum(1 for b in pg["blocks"] if b["bbox"][2] < 0.56 * w and len(b["lines"]) > 1)
    right = sum(1 for b in pg["blocks"] if b["bbox"][0] > 0.44 * w and len(b["lines"]) > 1)
    return left >= 2 and right >= 2


def pdf_chunks(source_id: str, pages: list[dict]) -> tuple[list[Chunk], int]:
    out: list[Chunk] = []
    section = ""
    two = 0
    for pi, pg in enumerate(pages, 1):
        if is_two_column(pg):
            two += 1
        cur_text, cur_box, k = "", None, 0

        def flush():
            nonlocal cur_text, cur_box, k
            if cur_text.strip():
                anchor = f"p{pi}|{k}"
                loc = (f"§{section.split(' ')[0].rstrip('.')}, " if section else "") + f"p. {pi}"
                out.append(Chunk(chunk_id(source_id, anchor, cur_text), source_id, len(out), "paragraph",
                                 cur_text.strip(), pi, [round(v, 1) for v in cur_box] if cur_box else None, section,
                                 "", loc))
                k += 1
            cur_text, cur_box = "", None
        for b in pg["blocks"]:
            text = join_lines([ln.text for ln in b["lines"]])
            if len(b["lines"]) == 1 and HEADING_RE.match(text.strip()) and len(text) < 90:
                flush()
                section = text.strip()
                continue
            if re.match(r"^(Theorem|Lemma|Proposition|Corollary|Definition|Conjecture|Claim|Proof)\b", text):
                flush()
            if cur_text and len(cur_text) + len(text) > CHUNK_CHARS:
                flush()
            cur_text = (cur_text + "\n" + text) if cur_text else text
            bb = b["bbox"]
            cur_box = bb if cur_box is None else (min(cur_box[0], bb[0]), min(cur_box[1], bb[1]),
                                                   max(cur_box[2], bb[2]), max(cur_box[3], bb[3]))
        flush()
    return out, two


def tesseract_langs() -> set[str]:
    if not shutil.which("tesseract"):
        return set()
    r = run_tool(["tesseract", "--list-langs"], timeout=20)
    out = (r.stdout.decode("utf-8", "replace") + r.stderr).splitlines()
    return {x.strip() for x in out if re.fullmatch(r"[a-z_]{3,8}", x.strip())}


def ocr_pdf(source_id: str, path: Path, pages: int, max_pages: int = 30) -> tuple[list[Chunk], list[str]]:
    langs = tesseract_langs()
    if not langs or not shutil.which("pdftoppm"):
        return [], []
    lang = "+".join(x for x in ("eng", "fra") if x in langs) or sorted(langs)[0]
    out: list[Chunk] = []
    warnings = ["ocr", "ocr_math_unreliable"]
    with tempfile.TemporaryDirectory(prefix="madalean-ocr-") as tmp:
        for pi in range(1, min(pages, max_pages) + 1):
            r = run_tool(["pdftoppm", "-r", "200", "-gray", "-f", str(pi), "-l", str(pi), "-png", str(path),
                          str(Path(tmp) / "p")], timeout=120, cwd=tmp)
            imgs = sorted(Path(tmp).glob("p*.png"))
            if r.rc != 0 or not imgs:
                continue
            t = run_tool(["tesseract", str(imgs[-1]), "-", "-l", lang], timeout=180, cwd=tmp)
            for im in imgs:
                im.unlink()
            text = t.stdout.decode("utf-8", "replace") if t.rc == 0 else ""
            for k, para in enumerate(p for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 20):
                para = join_lines(para.split("\n"))
                out.append(Chunk(chunk_id(source_id, f"ocr{pi}|{k}", para), source_id, len(out), "ocr", para, pi, None,
                                 "", "", f"p. {pi} (OCR)", {"ocr": True}))
        if pages > max_pages:
            warnings.append(f"ocr_truncated:{max_pages}")
    return out, warnings


def extract_pdf(source_id: str, path: Path, max_pages: int = 600) -> PdfResult:
    try:
        pages, n = pdf_pages(path, max_pages)
    except Exception as e:  # noqa: BLE001 (broken / hostile PDF: reported, never fatal)
        return PdfResult("error", 0, [], [f"pdftotext: {str(e)[:200]}"])
    chars = sum(len(ln.text) for pg in pages for b in pg["blocks"] for ln in b["lines"])
    if n and chars < 40 * n:
        chunks, warns = ocr_pdf(source_id, path, n)
        if chunks:
            return PdfResult("ocr", n, chunks, ["no_text_layer"] + warns)
        return PdfResult("no_text_layer", n, [], ["no_text_layer"] + (["no_ocr"] if not shutil.which("tesseract")
                                                                      else ["ocr_failed"]))
    removed = remove_headers_footers(pages)
    chunks, two = pdf_chunks(source_id, pages)
    warns = [f"truncated:{max_pages}"] if n >= max_pages else []
    return PdfResult("ok", n, chunks, warns, two, removed)


def extract_epub(source_id: str, root: Path) -> list[Chunk]:
    out: list[Chunk] = []
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".xhtml", ".html", ".htm") and p.is_file()
                   and not p.is_symlink())
    for fi, p in enumerate(files[:400]):
        raw = p.read_text(encoding="utf-8", errors="replace")
        raw = re.sub(r"(?is)<(script|style|head)\b.*?</\1\s*>", "", raw)
        import html as _h
        for k, para in enumerate(re.split(r"(?i)</p\s*>|<br\s*/?>|</h\d>|</div>", raw)):
            t = re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", para))).strip()
            if len(t) > 40:
                out.append(Chunk(chunk_id(source_id, f"epub{fi}|{k}", t), source_id, len(out), "paragraph", t,
                                 None, None, p.stem, "", p.stem))
    return out


# ================================================================ index
SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, source_id TEXT NOT NULL, ord INTEGER, kind TEXT, page INTEGER,
  bbox TEXT, section TEXT, label TEXT, locator TEXT, text TEXT, meta TEXT);
CREATE INDEX IF NOT EXISTS chunks_src ON chunks(source_id, ord);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(text, section, chunk_id UNINDEXED, source_id UNINDEXED,
  tokenize="unicode61 remove_diacritics 2");
"""


class Index:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _conn(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(self.path), timeout=30)
        c.row_factory = sqlite3.Row
        c.executescript(SCHEMA)
        return c

    def replace(self, source_id: str, chunks: list[Chunk]) -> None:
        c = self._conn()
        try:
            with c:
                c.execute("DELETE FROM chunks WHERE source_id=?", (source_id,))
                c.execute("DELETE FROM fts WHERE source_id=?", (source_id,))
                seen = set()
                for ch in chunks:
                    if ch.id in seen:
                        continue
                    seen.add(ch.id)
                    c.execute("INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                              (ch.id, source_id, ch.ord, ch.kind, ch.page, json.dumps(ch.bbox), ch.section, ch.label,
                               ch.locator, ch.text, json.dumps(ch.meta)))
                    c.execute("INSERT INTO fts(text, section, chunk_id, source_id) VALUES (?,?,?,?)",
                              (ch.text, ch.section, ch.id, source_id))
        finally:
            c.close()

    def remove(self, source_id: str) -> None:
        self.replace(source_id, [])

    def chunks(self, source_id: str, page: int | None = None, limit: int = 5000) -> list[dict]:
        if not self.path.exists():
            return []
        c = self._conn()
        try:
            q = "SELECT * FROM chunks WHERE source_id=?" + (" AND page=?" if page is not None else "") + \
                " ORDER BY ord LIMIT ?"
            args = (source_id, page, limit) if page is not None else (source_id, limit)
            return [row(r) for r in c.execute(q, args)]
        finally:
            c.close()

    def get(self, chunk_ids: list[str]) -> dict[str, dict]:
        if not self.path.exists() or not chunk_ids:
            return {}
        c = self._conn()
        try:
            marks = ",".join("?" * len(chunk_ids))
            return {r["id"]: row(r) for r in c.execute(f"SELECT * FROM chunks WHERE id IN ({marks})", chunk_ids)}
        finally:
            c.close()

    def search(self, query: str, k: int = 12, source_ids: list[str] | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        q = fts_query(query)
        if not q:
            return []
        c = self._conn()
        try:
            sql = ("SELECT chunks.*, bm25(fts, 1.0, 0.4) AS score FROM fts JOIN chunks ON chunks.id = fts.chunk_id "
                   "WHERE fts MATCH ?")
            args: list = [q]
            if source_ids:
                sql += f" AND fts.source_id IN ({','.join('?' * len(source_ids))})"
                args += list(source_ids)
            sql += " ORDER BY score LIMIT ?"
            args.append(k)
            try:
                rows = list(c.execute(sql, args))
            except sqlite3.OperationalError:
                return []
            out = []
            for r in rows:
                d = row(r)
                d["score"] = round(-float(r["score"]), 4)
                out.append(d)
            return out
        finally:
            c.close()


def row(r: sqlite3.Row) -> dict:
    d = dict(r)
    for k in ("bbox", "meta"):
        try:
            d[k] = json.loads(d[k]) if d.get(k) else None
        except ValueError:
            d[k] = None
    d.pop("score", None)
    return d


QSTOP = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "is", "are", "what", "which", "does", "do", "how",
         "why", "that", "this", "with", "for", "by", "be", "it", "as", "le", "la", "les", "de", "des", "du", "un",
         "une", "et", "ou", "est", "que", "qui", "quoi", "dans", "pour", "par", "sur", "en", "ce", "cette", "il",
         "elle", "se", "au", "aux", "comment", "pourquoi", "quel", "quelle", "quels", "quelles", "paper", "article"}


def fts_query(text: str) -> str:
    words = [w for w in re.findall(r"[^\W_]{2,}", (text or "").lower()) if w not in QSTOP][:24]
    if not words:
        return ""
    terms = []
    for w in dict.fromkeys(words):
        terms.append(f'"{w}"' + ("*" if len(w) >= 5 else ""))
    return " OR ".join(terms)


async def semantic_rerank(query: str, hits: list[dict], enabled: bool = True) -> list[dict]:
    """Optional re-ranking with a local Ollama embedding model — `madalean.brain.rag.Embedder`, not duplicated."""
    if not enabled or len(hits) < 3:
        return hits
    try:
        from ..brain.rag import shared_embedder
    except Exception:  # noqa: BLE001
        return hits
    emb = shared_embedder("http://127.0.0.1:11434")     # one instance: no re-detection, a warm vector cache
    try:
        docs = [{"name": h.get("locator") or h.get("section") or "", "signature": h["text"][:1500], "doc": "",
                 "score": h["score"], "_i": i} for i, h in enumerate(hits)]
        ranked = await emb.rerank(query, docs)
        return [{**hits[d["_i"]], "score": d["score"], "semantic": d.get("semantic")} for d in ranked]
    except Exception:  # noqa: BLE001 (Ollama absent: lexical order kept)
        return hits


def chunk_dict(ch: Chunk) -> dict:
    return asdict(ch)
