"""LaTeX input/output: pull problem statements out of a .tex file, and export a verified proof as a .tex document
that compiles with XeLaTeX/LuaLaTeX (Overleaf-ready: upload the file, or paste it in a project)."""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass

from .i18n import _

ENVS = ("theorem", "thm", "lemma", "lem", "proposition", "prop", "corollary", "cor", "exercise", "exercice", "exo",
        "problem", "probleme", "question", "claim", "conjecture", "enonce", "énoncé")
_ENV_RE = re.compile(r"\\begin\{(" + "|".join(ENVS) + r")(\*?)\}(\[[^\]]*\])?(.*?)\\end\{\1\2\}", re.DOTALL | re.IGNORECASE)
_LABELS = {"theorem": "Théorème", "thm": "Théorème", "lemma": "Lemme", "lem": "Lemme", "proposition": "Proposition",
           "prop": "Proposition", "corollary": "Corollaire", "cor": "Corollaire", "exercise": "Exercice",
           "exercice": "Exercice", "exo": "Exercice", "problem": "Problème", "probleme": "Problème",
           "question": "Question", "claim": "Affirmation", "conjecture": "Conjecture", "enonce": "Énoncé", "énoncé": "Énoncé"}


@dataclass
class TexStatement:
    title: str          # e.g. « Lemme 2 — Cauchy-Schwarz »
    body: str           # LaTeX source of the statement (comments and \label removed)


def strip_comments(tex: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in tex.split("\n"))


def clean_body(body: str) -> str:
    body = re.sub(r"\\label\{[^}]*\}", "", body)
    body = re.sub(r"\\(?:vspace|hspace)\*?\{[^}]*\}", "", body)
    return re.sub(r"[ \t]+\n", "\n", body).strip()


def extract_statements(tex: str) -> list[TexStatement]:
    """Theorem-like environments of a .tex file; if there are none, the whole document body as one candidate."""
    tex = strip_comments(tex)
    out: list[TexStatement] = []
    counts: dict[str, int] = {}
    for m in _ENV_RE.finditer(tex):
        env = m.group(1).lower()
        counts[env] = counts.get(env, 0) + 1
        label = _(_LABELS.get(env, env.capitalize()))
        opt = (m.group(3) or "").strip("[]").strip()
        title = f"{label} {counts[env]}" + (f" — {opt}" if opt else "")
        body = clean_body(m.group(4))
        if body:
            out.append(TexStatement(title, body))
    if not out:
        doc = re.search(r"\\begin\{document\}(.*?)(\\end\{document\}|$)", tex, re.DOTALL)
        body = clean_body(doc.group(1) if doc else tex)
        body = re.sub(r"\\(maketitle|tableofcontents|newpage|clearpage)\b", "", body).strip()
        if body:
            out.append(TexStatement(_("Tout le document"), body[:6000]))
    return out


def looks_like_latex(text: str) -> bool:
    return bool(re.search(r"\$|\\[a-zA-Z]+|\\\(|\\\[", text))


_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def escape_plain(text: str) -> str:
    return "".join(_ESC.get(c, c) for c in text)


def _lean_body(code: str) -> str:
    return code.replace("\\end{Verbatim}", "\\end {Verbatim}")


def export_document(nl_statement: str, lean_statement: str, lean_proof: str, theorem_name: str,
                    verified_with: str = "", date: _dt.date | None = None, explanation: str = "") -> str:
    """Full .tex source: informal statement, formal statement and verified proof (compile with XeLaTeX/LuaLaTeX)."""
    date = date or _dt.date.today()
    nl = nl_statement.strip()
    if nl and not looks_like_latex(nl):
        nl = escape_plain(nl)
    explain_section = (f"\\section*{{Explication de la preuve}}\n"
                       f"\\emph{{Rédigée par une IA à partir de la preuve Lean ; la preuve Lean ci-dessous fait foi.}}\n\n"
                       f"{markdown_to_latex(explanation)}\n\n" if explanation.strip() else "")
    informal = (f"\\begin{{theorem}}\n{nl}\n\\end{{theorem}}\n\n" if nl else "")
    note = (f"Preuve vérifiée par Lean ({verified_with}) le {date.strftime('%d/%m/%Y')}." if verified_with
            else f"Preuve vérifiée par Lean le {date.strftime('%d/%m/%Y')}.")
    return rf"""% !TEX program = xelatex
% Document généré par Madalean. Compiler avec XeLaTeX (sur Overleaf : Menu → Compilateur → XeLaTeX).
\documentclass[11pt]{{article}}
\usepackage[a4paper,margin=2.5cm]{{geometry}}
\usepackage{{fontspec}}
\setmonofont{{DejaVu Sans Mono}}[Scale=MatchLowercase]
\usepackage[french]{{babel}}
\usepackage{{amsmath,amssymb,amsthm}}
\usepackage{{fvextra}}
\usepackage[dvipsnames]{{xcolor}}
\theoremstyle{{plain}}
\newtheorem{{theorem}}{{Théorème}}

\title{{Énoncé et preuve vérifiée par Lean}}
\author{{}}
\date{{}}

\begin{{document}}
\maketitle

\section*{{Énoncé}}
{informal}\section*{{Énoncé formalisé en Lean 4}}
\begin{{Verbatim}}[breaklines=true,frame=single,fontsize=\small,rulecolor=\color{{black!25}}]
{_lean_body(lean_statement.strip())}
\end{{Verbatim}}

{explain_section}\section*{{Preuve formelle}}
{note}
\begin{{Verbatim}}[breaklines=true,frame=single,fontsize=\small,rulecolor=\color{{black!25}}]
{_lean_body(lean_proof.strip())}
\end{{Verbatim}}

\end{{document}}
"""


# ---------------------------------------------------------------- model text (light Markdown + $LaTeX$) -> display / LaTeX
_MATH_RE = re.compile(r"(\$\$.+?\$\$|\$.+?\$|\\\(.+?\\\)|\\\[.+?\\\])", re.DOTALL)
_UNI = {r"\geq": "≥", r"\ge": "≥", r"\leq": "≤", r"\le": "≤", r"\neq": "≠", r"\ne": "≠", r"\cdot": "·", r"\times": "×",
        r"\in": "∈", r"\notin": "∉", r"\mid": "∣", r"\forall": "∀", r"\exists": "∃", r"\to": "→", r"\rightarrow": "→",
        r"\Rightarrow": "⇒", r"\Leftrightarrow": "⇔", r"\iff": "⇔", r"\land": "∧", r"\lor": "∨", r"\neg": "¬",
        r"\subseteq": "⊆", r"\cup": "∪", r"\cap": "∩", r"\infty": "∞", r"\pm": "±", r"\sqrt": "√", r"\sum": "∑",
        r"\mathbb{N}": "ℕ", r"\mathbb{Z}": "ℤ", r"\mathbb{Q}": "ℚ", r"\mathbb{R}": "ℝ", r"\mathbb{C}": "ℂ",
        r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\varepsilon": "ε", r"\epsilon": "ε",
        r"\lambda": "λ", r"\pi": "π", r"\equiv": "≡", r"\ldots": "…", r"\dots": "…", r"\,": " ", r"\;": " ", r"\!": ""}
_SUP = str.maketrans("0123456789+-n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ")
_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def latex_math_to_unicode(m: str) -> str:
    m = m.strip().strip("$").strip()
    m = re.sub(r"^\\[(\[]|\\[)\]]$", "", m)
    m = re.sub(r"\\(?:text|mathrm|operatorname)\{([^}]*)\}", r"\1", m)
    m = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", m)
    for k in sorted(_UNI, key=len, reverse=True):
        m = m.replace(k, _UNI[k])
    m = re.sub(r"\^\{?([0-9+\-n]+)\}?", lambda x: x.group(1).translate(_SUP), m)
    m = re.sub(r"_\{?([0-9]+)\}?", lambda x: x.group(1).translate(_SUB), m)
    return m.replace("\\left", "").replace("\\right", "").replace("{", "").replace("}", "")


def display_markdown(text: str) -> str:
    """Markdown for the GUI (QTextBrowser.setMarkdown): $math$ turned into readable Unicode."""
    return _MATH_RE.sub(lambda mo: latex_math_to_unicode(mo.group(0)), text)


def markdown_to_latex(text: str) -> str:
    """Light Markdown (bold, italic, `code`, numbered/bulleted lists) + $math$ → safe LaTeX body."""
    out: list[str] = []
    state = None                                    # open list environment

    def inline(s: str) -> str:
        parts = _MATH_RE.split(s)
        res = []
        for i, part in enumerate(parts):
            if i % 2:                               # math segment: keep verbatim
                res.append(part)
                continue
            part = re.sub(r"`([^`]+)`", lambda m: "\x00T" + m.group(1) + "\x00E", part)
            part = re.sub(r"\*\*(.+?)\*\*", lambda m: "\x00B" + m.group(1) + "\x00E", part)
            part = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", lambda m: "\x00I" + m.group(1) + "\x00E", part)
            part = escape_plain(part)
            part = (part.replace("\x00T", r"\texttt{").replace("\x00B", r"\textbf{").replace("\x00I", r"\emph{")
                    .replace("\x00E", "}"))
            res.append(part)
        return "".join(res)

    def close():
        nonlocal state
        if state:
            out.append(f"\\end{{{state}}}")
            state = None

    for raw in text.strip().split("\n"):
        line = raw.rstrip()
        h = re.match(r"\s{0,3}#{1,6}\s+(.*)", line)
        num = re.match(r"\s*\d+[.)]\s+(.*)", line)
        bul = re.match(r"\s*[-*•]\s+(.*)", line)
        if h:
            close()
            out.append(f"\\paragraph{{{inline(h.group(1))}}}")
        elif num or bul:
            env = "enumerate" if num else "itemize"
            if state != env:
                close()
                out.append(f"\\begin{{{env}}}")
                state = env
            out.append(f"\\item {inline((num or bul).group(1))}")
        elif not line.strip():
            close()
            out.append("")
        else:
            if state:
                out[-1] += " " + inline(line.strip())     # continuation of the previous item
            else:
                out.append(inline(line.strip()))
    close()
    return "\n".join(out).strip()


# ================================================================ 2.0 export helpers (Unicode-safe, sanitised)
# Lean listings use DejaVu Sans Mono; every character a font lacks is typeset with the first fallback font that has
# it (coverage read from the font files with fontTools, else `fc-query`). Model text (Markdown + $LaTeX$) is
# sanitised: only known math commands/environments pass, anything doubtful is printed literally.
import functools as _functools
import html as _html
import subprocess as _subprocess

from . import deps as _deps

MONO_FAMILY = "DejaVu Sans Mono"
MAIN_FONT_FILE = "lmroman10-regular.otf"
MATH_FONT_FILE = "latinmodern-math.otf"
FALLBACK_FAMILIES = ("DejaVu Sans", "Noto Sans Math", "Noto Sans Symbols", "Noto Sans Symbols 2", "Noto Sans",
                     "FreeSerif")
_FB_NAMES = "ABCDEFGH"


def _run_out(cmd: list[str]) -> str:
    try:
        r = _subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, _subprocess.SubprocessError):
        return ""


@_functools.lru_cache(maxsize=None)
def font_file(family: str) -> str | None:
    """Path of an installed font family (exact family match), or None."""
    fc = _deps.tool("fc-match")
    if not fc:
        return None
    out = _run_out([fc, "-f", "%{file}|%{family}", family]).strip()
    if "|" not in out:
        return None
    path, fams = out.split("|", 1)
    return path if family.lower() in [f.strip().lower() for f in fams.split(",")] and path else None


@_functools.lru_cache(maxsize=None)
def tex_font_file(name: str) -> str | None:
    """A file of the TeX distribution: the prefix's pinned bundle (files extracted at install, §18) first, else the
    system TeX's kpsewhich (export fallback)."""
    own = _deps.tex_files_dir() / name
    if _deps.tool("tectonic") and own.is_file():
        return str(own)
    kp = _deps.tool("kpsewhich")
    if not kp:
        return None
    out = _run_out([kp, name]).strip()
    return out or None


@_functools.lru_cache(maxsize=None)
def font_cmap(path: str | None) -> frozenset:
    """Code points covered by a font file (empty when unknown)."""
    if not path:
        return frozenset()
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(path, lazy=True, fontNumber=0)
        cm = f.getBestCmap() or {}
        f.close()
        return frozenset(cm)
    except Exception:  # noqa: BLE001 (fontTools missing or font unreadable: ask fontconfig)
        pass
    fq = _deps.tool("fc-query")
    out = _run_out([fq, "--format", "%{charset}", path]) if fq else ""
    cps: set[int] = set()
    for part in out.split():
        a, _, b = part.partition("-")
        try:
            lo = int(a, 16)
            hi = int(b, 16) if b else lo
        except ValueError:
            continue
        cps.update(range(lo, hi + 1))
    return frozenset(cps)


@dataclass
class Fonts:
    mono: frozenset
    main: frozenset
    math: frozenset
    fallbacks: list        # [(macro, family, cmap)]
    has_mono: bool
    has_math: bool

    def fallback(self, ch: str) -> str | None:
        cp = ord(ch)
        for macro, _fam, cm in self.fallbacks:
            if cp in cm:
                return macro
        return None

    def preamble(self) -> str:
        out = []
        for macro, fam, _cm in self.fallbacks:
            out.append(f"\\newfontfamily{{\\{macro}}}{{{fam}}}[Scale=MatchLowercase]")
        return "\n".join(out)


@_functools.lru_cache(maxsize=1)
def fonts() -> Fonts:
    mono_path = font_file(MONO_FAMILY)
    fbs = []
    for fam in FALLBACK_FAMILIES:
        p = font_file(fam)
        if p:
            fbs.append((f"MLfb{_FB_NAMES[len(fbs)]}", fam, font_cmap(p)))
        if len(fbs) == len(_FB_NAMES):
            break
    math_path = tex_font_file(MATH_FONT_FILE)
    return Fonts(font_cmap(mono_path), font_cmap(tex_font_file(MAIN_FONT_FILE)), font_cmap(math_path), fbs,
                 bool(mono_path), bool(math_path))


def wrap_uncovered(text: str, cmap: frozenset, f: Fonts | None = None) -> str:
    """Put every non-ASCII character the font lacks inside `{\\MLfbX c}` (first fallback font that has it)."""
    f = f or fonts()
    if not cmap:
        return text
    out = []
    for ch in text:
        if ord(ch) < 128 or ord(ch) in cmap:
            out.append(ch)
            continue
        macro = f.fallback(ch)
        out.append(f"{{\\{macro} {ch}}}" if macro else ch)
    return "".join(out)


def lean_listing(code: str, numbers: bool = True, f: Fonts | None = None) -> str:
    """Framed, wrapped (and line-numbered) listing of Lean code; nothing in `code` can escape the block."""
    f = f or fonts()
    code = code.replace("\t", "  ").replace("\r\n", "\n").strip("\n")
    esc = code.replace("\\", "\x00B").replace("{", "\x00L").replace("}", "\x00R")
    esc = wrap_uncovered(esc, f.mono, f)
    esc = esc.replace("\x00B", r"\MLbs{}").replace("\x00L", r"\MLlb{}").replace("\x00R", r"\MLrb{}")
    opts = "commandchars=\\\\\\{\\}" + (",numbers=left" if numbers else ",numbers=none")
    if code.count("\n") < 30:
        opts += ",samepage=true"          # short listings are never split across two pages
    return f"\\begin{{Verbatim}}[{opts}]\n{esc}\n\\end{{Verbatim}}"


def verbatim_text(text: str, f: Fonts | None = None) -> str:
    """Model text printed literally (used when its LaTeX did not compile): wrapped, not numbered, no frame."""
    f = f or fonts()
    body = lean_listing(text, numbers=False, f=f)
    return body.replace("[commandchars", "[frame=none,fontsize=\\small,commandchars", 1)


# ---------------------------------------------------------------- math sanitiser
MATH_ENVS = {"aligned", "cases", "pmatrix", "bmatrix", "vmatrix", "Vmatrix", "matrix", "array", "gathered", "split",
             "smallmatrix", "alignedat"}
_ENV_MAP = {"align": "aligned", "align*": "aligned", "eqnarray": "aligned", "eqnarray*": "aligned",
            "gather": "gathered", "gather*": "gathered", "multline": "gathered", "multline*": "gathered"}
_DROP_ENVS = {"equation", "equation*", "displaymath", "math"}
MATH_COMMANDS = set("""
alpha beta gamma Gamma delta Delta epsilon varepsilon zeta eta theta Theta vartheta iota kappa lambda Lambda mu nu xi Xi
pi Pi varpi rho varrho sigma Sigma varsigma tau upsilon Upsilon phi Phi varphi chi psi Psi omega Omega
sum prod coprod int iint iiint oint lim limsup liminf sup inf max min log ln lg exp sin cos tan cot sec csc arcsin
arccos arctan sinh cosh tanh det gcd lcm deg dim ker hom arg Pr
le leq ge geq ne neq equiv approx sim simeq cong subset subseteq subsetneq supset supseteq supsetneq in notin ni mid
nmid parallel perp propto prec preceq succ succeq ll gg lesssim gtrsim leqslant geqslant vdash models
to rightarrow leftarrow Rightarrow Leftarrow iff implies impliedby Leftrightarrow leftrightarrow mapsto
longrightarrow longleftarrow Longrightarrow Longleftrightarrow longmapsto uparrow downarrow hookrightarrow
twoheadrightarrow rightharpoonup nearrow searrow
forall exists nexists neg lnot land lor wedge vee bigwedge bigvee top bot emptyset varnothing
cup cap setminus bigcup bigcap sqcup bigsqcup times otimes oplus bigotimes bigoplus circ cdot cdots ldots dots dotsc
dotsb vdots ddots infty partial nabla pm mp div ast star prime backslash
mathbb mathbf mathrm mathit mathcal mathfrak mathsf mathtt mathscr symbf symbb symcal symrm symit text textbf textit
textrm textsf texttt mbox operatorname
frac dfrac tfrac binom dbinom tbinom sqrt overline underline hat bar tilde vec dot ddot widehat widetilde overbrace
underbrace overrightarrow overleftarrow
left right big Big bigg Bigg bigl bigr Bigl Bigr biggl biggr middle
quad qquad langle rangle lfloor rfloor lceil rceil lvert rvert lVert rVert vert Vert
begin end displaystyle textstyle scriptstyle limits nolimits not ell hbar aleph Re Im wp
pmod bmod mod colon dagger triangle angle square Box blacksquare checkmark therefore because
stackrel overset underset substack phantom hphantom vphantom mathop mathrel mathbin
lbrace rbrace iota imath jmath hookleftarrow circledast bullet diamond
""".split())
_MACRO_MAP = {r"\R": r"\mathbb{R}", r"\N": r"\mathbb{N}", r"\Z": r"\mathbb{Z}", r"\Q": r"\mathbb{Q}",
              r"\C": r"\mathbb{C}", r"\eps": r"\varepsilon", r"\boldsymbol": r"\symbf", r"\bm": r"\symbf",
              r"\dfrac": r"\dfrac", r"\tg": r"\tan", r"\cotg": r"\cot", r"\ensuremath": ""}


def _balanced(s: str) -> bool:
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


def sanitize_math(src: str, f: Fonts | None = None) -> str:
    """`$…$` / `$$…$$` / `\\(…\\)` / `\\[…\\]` from a model → safe LaTeX math, or the literal text in \\texttt."""
    f = f or fonts()
    s = src.strip()
    display = s.startswith("$$") or s.startswith("\\[")
    if s.startswith("$$") and s.endswith("$$") and len(s) >= 4:
        inner = s[2:-2]
    elif s.startswith("\\[") and s.endswith("\\]") or s.startswith("\\(") and s.endswith("\\)"):
        inner = s[2:-2]
    else:
        inner = s[1:-1]
    m = inner
    for k, v in _MACRO_MAP.items():
        m = re.sub(re.escape(k) + r"(?![A-Za-z])", lambda _x, v=v: v, m)

    def env(mo):
        name = mo.group(2)
        if name in _DROP_ENVS:
            return ""
        return f"\\{mo.group(1)}{{{_ENV_MAP.get(name, name)}}}"
    m = re.sub(r"\\(begin|end)\{([A-Za-z*]+)\}", env, m)
    ok = _balanced(m) and len(re.findall(r"\\left\b", m)) == len(re.findall(r"\\right\b", m))
    envs = re.findall(r"\\begin\{([A-Za-z*]+)\}", m)
    ok = ok and all(e in MATH_ENVS for e in envs) and len(envs) == len(re.findall(r"\\end\{", m))
    cmds = re.findall(r"\\([A-Za-z]+)", m)
    ok = ok and all(c in MATH_COMMANDS for c in cmds)
    ok = ok and ("&" not in m.replace("\\&", "") or bool(envs)) and "$" not in m.replace("\\$", "")
    ok = ok and bool(m.strip())
    if ok and "\\\\" in m and not envs:
        ok = False
    if not ok:
        lit = wrap_uncovered(escape_plain(src.strip()), f.mono, f)
        return f"\\texttt{{{lit}}}"
    m = re.sub(r"(?<!\\)%", r"\\%", m).replace("#", r"\#")
    out = []
    for ch in m:
        if ord(ch) >= 128 and f.math and ord(ch) not in f.math:
            macro = f.fallback(ch)
            out.append(f"\\text{{\\{macro} {ch}}}" if macro else ch)
        else:
            out.append(ch)
    m = "".join(out).strip()
    return f"\\[{m}\\]" if display else f"${m}$"


# ---------------------------------------------------------------- Markdown sanitiser
_MATH_ANY = re.compile(r"(\$\$.+?\$\$|(?<![\\$])\$(?!\$)[^$\n]+?(?<!\\)\$|\\\(.+?\\\)|\\\[.+?\\\])", re.DOTALL)
_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?/?>")


CITE_GROUP = re.compile(r"\[([^\[\]\n]{0,400}?@[^\[\]\n]{0,400})\]")


def _inline(s: str, f: Fonts, cites=None) -> str:
    parts = _MATH_ANY.split(s)
    res = []
    for i, part in enumerate(parts):
        if i % 2:
            res.append(sanitize_math(part, f))
            continue
        tokens: list[str] = []

        def keep(tex: str) -> str:
            tokens.append(tex)
            return f"\x01{len(tokens) - 1}\x02"
        if cites is not None:            # citations [@key, Thm 2] → \cite[Thm 2]{key} (known keys only: research.biblio)
            from .research.biblio import cite_to_latex
            part = CITE_GROUP.sub(lambda mo: keep(t) if (t := cite_to_latex(mo.group(1), cites)) is not None
                                  else mo.group(0), part)
        part = re.sub(r"`([^`]+)`", lambda mo: keep(r"\texttt{" + wrap_uncovered(escape_plain(mo.group(1)), f.mono, f)
                                                     + "}"), part)
        part = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda mo: "\x03B" + (mo.group(1) or mo.group(2)) + "\x03E", part)
        part = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", lambda mo: "\x03I" + mo.group(1) + "\x03E", part)
        part = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda mo: mo.group(1) + " (" + mo.group(2) + ")", part)
        part = escape_plain(part)
        part = wrap_uncovered(part, f.main, f)
        part = part.replace("\x03B", r"\textbf{").replace("\x03I", r"\emph{").replace("\x03E", "}")
        part = re.sub(r"\x01(\d+)\x02", lambda mo: tokens[int(mo.group(1))], part)
        res.append(part)
    return "".join(res)


def sanitize_markdown(text: str, f: Fonts | None = None, cites=None) -> str:
    """Model Markdown (headings, lists, tables, code fences, quotes, HTML tags, $math$) → LaTeX that compiles.
    `cites`: keys that exist (set/dict) → `[@key, loc]` becomes `\\cite[loc]{key}`; None = printed literally."""
    f = f or fonts()
    text = re.sub(r"<think>.*?(</think>|$)", "", text or "", flags=re.DOTALL)
    text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = _TAG_RE.sub("", text)
    out: list[str] = []
    state: str | None = None
    lines = text.strip().split("\n")
    i = 0

    def close():
        nonlocal state
        if state:
            out.append(f"\\end{{{state}}}")
            state = None
    while i < len(lines):
        line = lines[i].rstrip()
        fence = re.match(r"\s*```+\s*([A-Za-z0-9]*)", line)
        if fence:
            close()
            body = []
            i += 1
            while i < len(lines) and not re.match(r"\s*```", lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            out.append(lean_listing("\n".join(body), numbers=fence.group(1).lower().startswith("lean"), f=f))
            continue
        if line.lstrip().startswith("|"):
            close()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            out.append("\\begin{quote}")
            for r_ in rows:
                out.append(" \\quad\\textbar\\quad ".join(_inline(c, f, cites) for c in r_) + "\\\\")
            out.append("\\end{quote}")
            continue
        h = re.match(r"\s{0,3}#{1,6}\s+(.*)", line)
        num = re.match(r"\s*\d+[.)]\s+(.*)", line)
        bul = re.match(r"\s*[-*•+]\s+(.*)", line)
        quote = re.match(r"\s*>\s?(.*)", line)
        if re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", line):
            close()
            out.append("\\par\\noindent\\textcolor{black!30}{\\rule{\\linewidth}{0.4pt}}\\par")
        elif h:
            close()
            out.append(f"\\par\\medskip\\noindent\\textbf{{{_inline(h.group(1).strip('# '), f, cites)}}}\\par\\nopagebreak")
        elif num or bul:
            env = "enumerate" if num else "itemize"
            if state != env:
                close()
                out.append(f"\\begin{{{env}}}")
                state = env
            out.append(f"\\item {_inline((num or bul).group(1), f, cites)}")
        elif quote:
            close()
            out.append(f"\\begin{{quote}}{_inline(quote.group(1), f, cites)}\\end{{quote}}")
        elif not line.strip():
            close()
            out.append("")
        elif state:
            out[-1] += " " + _inline(line.strip(), f, cites)
        else:
            out.append(_inline(line.strip(), f, cites))
        i += 1
    close()
    return "\n".join(out).strip()


# ---------------------------------------------------------------- Markdown → HTML (no-TeX fallback)
def markdown_to_html(text: str, keep_tex: bool = False) -> str:
    """Light Markdown → safe HTML. Math → Unicode (or kept as TeX in <span class="math"> for KaTeX)."""
    text = re.sub(r"<think>.*?(</think>|$)", "", text or "", flags=re.DOTALL)
    text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", "", text)
    text = _TAG_RE.sub("", re.sub(r"(?i)<br\s*/?>", "\n", text))
    out: list[str] = []
    state = None

    def inline(s: str) -> str:
        parts = _MATH_ANY.split(s)
        res = []
        for i, part in enumerate(parts):
            if i % 2:
                if keep_tex:
                    disp = part.startswith("$$") or part.startswith("\\[")
                    res.append(f'<span class="math{" display" if disp else ""}">{_html.escape(part)}</span>')
                else:
                    res.append(f'<span class="math">{_html.escape(latex_math_to_unicode(part))}</span>')
                continue
            p = _html.escape(part, quote=False)
            p = re.sub(r"`([^`]+)`", r"<code>\1</code>", p)
            p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
            p = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", p)
            res.append(p)
        return "".join(res)

    def close():
        nonlocal state
        if state:
            out.append(f"</{state}>")
            state = None
    lines = text.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if re.match(r"\s*```", line):
            close()
            body = []
            i += 1
            while i < len(lines) and not re.match(r"\s*```", lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre class=\"code\">{_html.escape(chr(10).join(body))}</pre>")
            continue
        h = re.match(r"\s{0,3}#{1,6}\s+(.*)", line)
        num = re.match(r"\s*\d+[.)]\s+(.*)", line)
        bul = re.match(r"\s*[-*•+]\s+(.*)", line)
        if h:
            close()
            out.append(f"<h4>{inline(h.group(1))}</h4>")
        elif num or bul:
            tag = "ol" if num else "ul"
            if state != tag:
                close()
                out.append(f"<{tag}>")
                state = tag
            out.append(f"<li>{inline((num or bul).group(1))}</li>")
        elif line.lstrip().startswith("|"):
            close()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                out.append("<p class=\"row\">" + " | ".join(inline(c) for c in cells) + "</p>")
        elif not line.strip():
            close()
        else:
            close()
            out.append(f"<p>{inline(line.strip())}</p>")
        i += 1
    close()
    return "\n".join(out)
