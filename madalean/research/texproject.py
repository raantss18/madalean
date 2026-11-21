"""LaTeX project of an article (session S-R, docs/ARTICLE.md): ONE representation, the LaTeX files.

    <config>/projects/<pid>/article/
        main.tex                 managed regions (preamble, front, sections, backmatter) + abstract block + your lines
        sections/NN-slug.tex     one file per top-level section, made of block regions (`%% mdl:block <id> <kind>`)
        figures/<sha16>.<ext>    content-addressed images
        madalean.toml            settings (class, packages, macros, theorems, language, layout, front matter)
        madalean.lock            package analysis (derived, written by texbuild)
        .madalean/               history (content-addressed), blocks.json (per-block source/versions, trash),
                                 suggestions.json

`to_view` / `apply_view` give `article.py` (and S-Q's suggestion engine) the v1 « blocks » dictionary on top of the
files: block ids are the markers, nothing is stored twice. Suggestions (track changes) are anchored on block ids and
exact text, applied only when the user accepts them."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import tomllib
import uuid
import zlib
from pathlib import Path

from .. import config, texio

# ================================================================ constants
DIR = "article"
MARK = re.compile(r"^%% mdl:block (abstract|b-[0-9a-f]{8}) (intro|section|conclusion|prose|dossier|abstract)"
                  r"(?: dossier=([A-Za-z0-9][A-Za-z0-9._-]{0,79}))?[ \t]*$")
END = "%% mdl:end"
MANAGED = ("preamble", "front", "sections", "backmatter")
SECTION_PATH = re.compile(r"^sections/[A-Za-z0-9][A-Za-z0-9_.-]{0,80}\.tex$")
FIGURE_PATH = re.compile(r"^figures/[0-9a-f]{16}\.(png|jpg|pdf)$")
HEAD_KINDS = ("intro", "section", "conclusion")
MAX_FILE = 2_000_000
MAX_HISTORY = 200
PLAIN = texio.Fonts(frozenset(), frozenset(), frozenset(), [], False, False)   # no font wrapping: portable LaTeX
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class TexProjectError(Exception):
    def __init__(self, kind: str, status: int = 400, **info):
        super().__init__(kind)
        self.kind, self.status, self.info = kind, status, info


def lock(pid: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(pid, threading.RLock())


def root(ctx, pid: str) -> Path:
    return ctx.projects.store.dir(pid) / DIR


def exists(ctx, pid: str) -> bool:
    r = root(ctx, pid)
    return (r / "main.tex").is_file() and (r / "madalean.toml").is_file()


def valid_path(path: str) -> bool:
    return path == "main.tex" or bool(SECTION_PATH.match(path or "")) or bool(FIGURE_PATH.match(path or ""))


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def slugify(title: str, n: int = 40) -> str:
    t = texio_plain(title).lower()
    t = re.sub(r"[àáâä]", "a", t)
    t = re.sub(r"[éèêë]", "e", t)
    t = re.sub(r"[îï]", "i", t)
    t = re.sub(r"[ôö]", "o", t)
    t = re.sub(r"[ùûü]", "u", t)
    t = t.replace("ç", "c")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:n].strip("-") or "section"


def texio_plain(s: str) -> str:
    """LaTeX title → plain text (for file names and outlines)."""
    s = re.sub(r"\$[^$]*\$", "", s or "")
    s = re.sub(r"\\[A-Za-z]+\*?", "", s)
    return re.sub(r"[{}]", "", s).strip()


def new_id() -> str:
    return "b-" + uuid.uuid4().hex[:8]


# ================================================================ settings (madalean.toml)
THEOREMS_DEFAULT = [
    {"env": "theorem", "fr": "Théorème", "en": "Theorem", "style": "plain", "counter": ""},
    {"env": "lemma", "fr": "Lemme", "en": "Lemma", "style": "plain", "counter": "theorem"},
    {"env": "proposition", "fr": "Proposition", "en": "Proposition", "style": "plain", "counter": "theorem"},
    {"env": "corollary", "fr": "Corollaire", "en": "Corollary", "style": "plain", "counter": "theorem"},
    {"env": "conjecture", "fr": "Conjecture", "en": "Conjecture", "style": "plain", "counter": "theorem"},
    {"env": "claim", "fr": "Affirmation", "en": "Claim", "style": "plain", "counter": "theorem"},
    {"env": "definition", "fr": "Définition", "en": "Definition", "style": "definition", "counter": "theorem"},
    {"env": "example", "fr": "Exemple", "en": "Example", "style": "definition", "counter": "theorem"},
    {"env": "remark", "fr": "Remarque", "en": "Remark", "style": "remark", "counter": "theorem"},
]
# Templates: every class here is in tectonic's pinned bundle (LPPL); nothing is vendored. `implied` = packages the
# class loads itself (never loaded twice); `builtin_envs` = theorem-like environments the class already defines.
TEMPLATES: dict[str, dict] = {
    "amsart": {"class": "amsart", "options": ["11pt"], "front": "amsart", "bibstyle": "amsalpha",
               "packages": ["mathtools", "amssymb", "graphicx", "xcolor", "hyperref", "cleveref"],
               "implied": ["amsmath", "amsthm", "amsfonts"], "builtin_envs": [], "geometry": True,
               "fr": "Article de mathématiques (AMS)", "en": "Mathematics paper (AMS)"},
    "article": {"class": "article", "options": ["11pt"], "front": "article", "bibstyle": "plain",
                "packages": ["amsmath", "amsthm", "mathtools", "amssymb", "graphicx", "xcolor", "hyperref",
                             "cleveref"],
                "implied": [], "builtin_envs": [], "geometry": True,
                "fr": "Article standard", "en": "Standard article"},
    "report": {"class": "report", "options": ["11pt"], "front": "article", "bibstyle": "plain",
               "packages": ["amsmath", "amsthm", "mathtools", "amssymb", "graphicx", "xcolor", "hyperref",
                            "cleveref"],
               "implied": [], "builtin_envs": [], "geometry": True,
               "fr": "Rapport, mémoire", "en": "Report, thesis"},
    "beamer": {"class": "beamer", "options": [], "front": "beamer", "bibstyle": "plain",
               "packages": ["amsmath", "mathtools", "amssymb"],
               "implied": ["hyperref", "xcolor", "graphicx", "amsthm"],
               "builtin_envs": ["theorem", "lemma", "corollary", "definition", "example", "proof"],
               "geometry": False, "fr": "Exposé (diapositives)", "en": "Talk (slides)"},
    "elsarticle": {"class": "elsarticle", "options": ["preprint", "11pt"], "front": "elsarticle",
                   "bibstyle": "elsarticle-num",
                   "packages": ["amsmath", "amsthm", "mathtools", "amssymb", "graphicx", "xcolor", "hyperref",
                                "cleveref"],
                   "implied": ["natbib"], "builtin_envs": [], "geometry": False,
                   "fr": "Revue Elsevier (elsarticle)", "en": "Elsevier journal (elsarticle)"},
}
FONTS = {
    "latin-modern": {"text": "", "math": "latinmodern-math.otf", "pdftex": "lmodern"},
    "libertinus": {"text": "Libertinus Serif", "math": "LibertinusMath-Regular.otf", "pdftex": "libertinus"},
    "stix2": {"text": "STIX Two Text", "math": "STIXTwoMath-Regular.otf", "pdftex": "stix2"},
}
LANGS = {"fr": "french", "en": "english"}
# mathematical characters typed in running text (Latin Modern's text fonts lack them): typeset with the math font
TEXT_MATH_CHARS = [("∀", r"\forall"), ("∃", r"\exists"), ("ℕ", r"\mathbb{N}"), ("ℤ", r"\mathbb{Z}"),
                   ("ℚ", r"\mathbb{Q}"), ("ℝ", r"\mathbb{R}"), ("ℂ", r"\mathbb{C}"), ("∈", r"\in"),
                   ("∉", r"\notin"), ("≤", r"\leq"), ("≥", r"\geq"), ("≠", r"\neq"), ("→", r"\to"),
                   ("↔", r"\leftrightarrow"), ("⇒", r"\Rightarrow"), ("⇔", r"\Leftrightarrow"),
                   ("∧", r"\wedge"), ("∨", r"\vee"), ("¬", r"\neg"), ("⊆", r"\subseteq"), ("∩", r"\cap"),
                   ("∪", r"\cup"), ("∘", r"\circ"), ("∞", r"\infty"), ("≈", r"\approx"), ("≡", r"\equiv")]


def default_settings(template: str = "amsart", lang: str = "fr", title: str = "") -> dict:
    t = TEMPLATES.get(template, TEMPLATES["amsart"])
    return {
        "document": {"template": template if template in TEMPLATES else "amsart", "class": t["class"],
                     "options": list(t["options"]), "language": lang if lang in LANGS else "fr"},
        "front": {"title": title, "authors": [], "date": ""},
        "packages": {"base": list(t["packages"]), "extra": [], "removed": []},
        "macros": {"R": r"\mathbb{R}", "N": r"\mathbb{N}", "Z": r"\mathbb{Z}", "Q": r"\mathbb{Q}",
                   "C": r"\mathbb{C}"},
        "theorems": {"numbering": "section", "envs": [dict(x) for x in THEOREMS_DEFAULT]},
        "bibliography": {"style": t["bibstyle"]},
        "layout": {"paper": "a4", "margin": "2.5cm", "font": "latin-modern", "linespread": 1.0},
        "madalean": {"lean_appendix": True, "verification_table": True, "preamble": "managed"},
    }


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_value(x)}" for k, x in v.items()) + " }"
    raise TypeError(type(v))


def _toml_key(k: str) -> str:
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k, ensure_ascii=False)


def dump_toml(s: dict) -> str:
    out = ["# Madalean article settings (edited from « Options avancées »; hand edits are kept).", ""]
    for table, vals in s.items():
        out.append(f"[{table}]")
        for k, v in vals.items():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                out.append(f"{_toml_key(k)} = [")
                out += [f"  {_toml_value(x)}," for x in v]
                out.append("]")
            else:
                out.append(f"{_toml_key(k)} = {_toml_value(v)}")
        out.append("")
    return "\n".join(out)


def read_settings(ctx, pid: str) -> dict:
    try:
        data = tomllib.loads((root(ctx, pid) / "madalean.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        data = {}
    return normalize_settings(data)


def normalize_settings(data: dict) -> dict:
    tpl = str((data.get("document") or {}).get("template", "amsart"))
    base = default_settings(tpl if tpl in TEMPLATES else "amsart")
    for table, vals in data.items():
        if table in base and isinstance(vals, dict):
            if table == "macros":
                base["macros"] = {str(k): str(v) for k, v in vals.items() if re.fullmatch(r"[A-Za-z]{1,30}", str(k))}
            else:
                base[table].update(vals)
    return base


MACRO_NAME = re.compile(r"^[A-Za-z]{1,30}$")
PKG_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,60}$")


def validate_settings(s: dict) -> list[str]:
    """Problems that make a settings dict unusable (unsafe or malformed)."""
    from .texbuild import guard_ai
    bad = []
    d = s["document"]
    if not PKG_NAME.match(str(d.get("class", ""))):
        bad.append("document.class")
    if not all(isinstance(o, str) and re.fullmatch(r"[A-Za-z0-9=.,-]{1,30}", o) for o in d.get("options", [])):
        bad.append("document.options")
    if d.get("language") not in LANGS:
        bad.append("document.language")
    for k in ("base", "extra", "removed"):
        if not all(isinstance(p, str) and PKG_NAME.match(p) for p in s["packages"].get(k, [])):
            bad.append(f"packages.{k}")
    for name, body in s["macros"].items():
        if not MACRO_NAME.match(name) or not isinstance(body, str) or len(body) > 400 or guard_ai(body):
            bad.append(f"macros.{name}")
    th = s["theorems"]
    if th.get("numbering") not in ("section", "global", "none"):
        bad.append("theorems.numbering")
    for e in th.get("envs", []):
        if not (isinstance(e, dict) and re.fullmatch(r"[a-z]{1,20}", str(e.get("env", "")))
                and e.get("style") in ("plain", "definition", "remark")
                and all(isinstance(e.get(x, ""), str) and len(e.get(x, "")) <= 40 and not guard_ai(e.get(x, ""))
                        for x in ("fr", "en", "counter"))):
            bad.append("theorems.envs")
            break
    if not PKG_NAME.match(str(s["bibliography"].get("style", ""))):
        bad.append("bibliography.style")
    lay = s["layout"]
    if lay.get("paper") not in ("a4", "letter") or lay.get("font") not in FONTS:
        bad.append("layout")
    if not re.fullmatch(r"\d(\.\d+)?(cm|mm|in)", str(lay.get("margin", ""))):
        bad.append("layout.margin")
    if not isinstance(lay.get("linespread"), (int, float)) or not 0.8 <= float(lay["linespread"]) <= 2.5:
        bad.append("layout.linespread")
    fr = s["front"]
    if not isinstance(fr.get("title", ""), str) or guard_ai(fr.get("title", "")) or \
            not isinstance(fr.get("authors", []), list):
        bad.append("front")
    for a in fr.get("authors", []):
        if not isinstance(a, dict) or any(guard_ai(str(a.get(k, ""))) for k in ("name", "affiliation", "email")):
            bad.append("front.authors")
            break
    if s["madalean"].get("preamble") not in ("managed", "manual"):
        bad.append("madalean.preamble")
    return bad


def packages_of(s: dict) -> list[str]:
    t = TEMPLATES.get(s["document"].get("template"), TEMPLATES["amsart"])
    implied = set(t["implied"])
    removed = set(s["packages"].get("removed", []))
    out: list[str] = []
    for p in list(s["packages"].get("base", [])) + list(s["packages"].get("extra", [])):
        if p not in out and p not in implied and p not in removed:
            out.append(p)
    # hyperref then cleveref, always last (cleveref must come after hyperref)
    for late in ("hyperref", "cleveref"):
        if late in out:
            out.remove(late)
            out.append(late)
    return out


# ================================================================ managed regions of main.tex
def _region(name: str, body: str) -> str:
    return f"%% mdl:{name} begin\n{body.rstrip()}\n%% mdl:{name} end"


def gen_preamble(s: dict) -> str:
    d, lay = s["document"], s["layout"]
    t = TEMPLATES.get(d.get("template"), TEMPLATES["amsart"])
    lang = d.get("language", "fr")
    opts = list(d.get("options", []))
    if lay.get("paper") == "a4" and d.get("class") != "beamer" and "a4paper" not in opts:
        opts.append("a4paper")
    out = [r"\documentclass" + (f"[{','.join(opts)}]" if opts else "") + "{" + d["class"] + "}"]
    pk = packages_of(s)
    font = FONTS.get(lay.get("font"), FONTS["latin-modern"])
    early = [p for p in pk if p not in ("hyperref", "cleveref", "amssymb")]
    if "amsmath" not in t["implied"] and "amsmath" not in early and \
            any(p in early for p in ("mathtools", "amsthm")):
        early.insert(0, "amsmath")
    out += [r"\usepackage{" + p + "}" for p in early]
    out += [r"\usepackage{iftex}",
            r"\ifTUTeX",
            r"  \usepackage{unicode-math}",
            r"  \setmathfont{" + font["math"] + "}",
            r"  \usepackage{newunicodechar}"] + [
            "  \\newunicodechar{" + ch + "}{\\ensuremath{" + cmd + "}}" for ch, cmd in TEXT_MATH_CHARS]
    if font["text"]:
        out.append(r"  \setmainfont{" + font["text"] + "}")
    out += [r"\else",
            r"  \usepackage[T1]{fontenc}",
            r"  \usepackage{" + font["pdftex"] + "}",
            r"  \usepackage{amssymb}",
            r"\fi"]
    out.append(r"\usepackage[" + LANGS.get(lang, "french") + "]{babel}")
    if t["geometry"]:
        out.append(r"\usepackage[margin=" + lay.get("margin", "2.5cm") + "]{geometry}")
    if float(lay.get("linespread", 1.0)) != 1.0:
        out.append(r"\linespread{" + f"{float(lay['linespread']):g}" + "}")
    out += [r"\usepackage" + ("[" + LANGS.get(lang, "french") + "]" if p == "cleveref" else "") + "{" + p + "}"
            for p in pk if p in ("hyperref", "cleveref")]
    # theorem environments
    th = s["theorems"]
    within = {"section": "[section]", "global": "", "none": ""}.get(th.get("numbering"), "[section]")
    builtin = set(t["builtin_envs"])
    style = None
    defined: set[str] = set()
    first = None
    for e in sorted(th.get("envs", []), key=lambda e: ("plain", "definition", "remark").index(e["style"])):
        if e["env"] in builtin:
            defined.add(e["env"])
            continue
        if e["style"] != style:
            style = e["style"]
            out.append(r"\theoremstyle{" + style + "}")
        title = e.get(lang) or e.get("en") or e["env"]
        star = "*" if th.get("numbering") == "none" else ""
        counter = e.get("counter") or ""
        if star:
            out.append(r"\newtheorem*{" + e["env"] + "}{" + title + "}")
        elif counter and counter in defined:
            out.append(r"\newtheorem{" + e["env"] + "}[" + counter + "]{" + title + "}")
        else:
            out.append(r"\newtheorem{" + e["env"] + "}{" + title + "}" + (within if first is None else ""))
            first = first or e["env"]
        defined.add(e["env"])
    for env, fr, en in (("claim", "Affirmation", "Claim"), ("conjecture", "Conjecture", "Conjecture")):
        if env not in defined:                       # the truth rule needs them (build-time downgrade)
            out.append(r"\theoremstyle{plain}\newtheorem*{" + env + "}{" + (fr if lang == "fr" else en) + "}")
    unv = "non vérifié par Lean" if lang == "fr" else "not verified by Lean"
    out.append(r"\providecommand\MLunverified{\textcolor{red!60!black}{\textup{[" + unv + "]}}}")
    if "xcolor" not in pk and "xcolor" not in t["implied"]:
        out.insert(1, r"\usepackage{xcolor}")
    for name, body in s["macros"].items():
        out.append("\\providecommand{\\" + name + "}{" + body + "}")
    return "\n".join(out)


def _tex_text(s: str) -> str:
    """Plain front-matter text → LaTeX (maths `$…$` kept through the allow-list)."""
    return texio._inline(s or "", PLAIN, None)


def gen_front(s: dict) -> str:
    fr = s["front"]
    tpl = s["document"].get("template")
    out = [r"\title{" + _tex_text(fr.get("title") or "") + "}"]
    for a in fr.get("authors", []):
        name = _tex_text(a.get("name", ""))
        if not name:
            continue
        if tpl == "elsarticle":
            out.append(r"\author{" + name + "}")
            if a.get("affiliation"):
                out.append(r"\affiliation{organization={" + _tex_text(a["affiliation"]) + "}}")
            if a.get("email"):
                out.append(r"\ead{" + _tex_text(a["email"]) + "}")
        elif tpl == "amsart":
            out.append(r"\author{" + name + "}")
            if a.get("affiliation"):
                out.append(r"\address{" + _tex_text(a["affiliation"]) + "}")
            if a.get("email"):
                out.append(r"\email{" + _tex_text(a["email"]) + "}")
        else:
            extra = "".join(r" \\ \small " + _tex_text(a[k]) for k in ("affiliation", "email") if a.get(k))
            out.append(r"\author{" + name + extra + "}")
    if tpl not in ("amsart",) and len([a for a in fr.get("authors", []) if a.get("name")]) > 1 and \
            tpl in ("article", "report", "beamer"):
        names = [ln for ln in out if ln.startswith(r"\author{")]
        out = [ln for ln in out if not ln.startswith(r"\author{")] + \
              [r"\author{" + r" \and ".join(n[len(r"\author{"):-1] for n in names) + "}"]
    if fr.get("date"):
        out.append(r"\date{" + _tex_text(fr["date"]) + "}")
    return "\n".join(out)


def gen_backmatter(s: dict) -> str:
    return "\n".join([r"\InputIfFileExists{madalean-generated}{}{}",
                      r"\bibliographystyle{" + s["bibliography"].get("style", "amsalpha") + "}",
                      r"\bibliography{refs}"])


def gen_sections(paths: list[str]) -> str:
    return "\n".join(r"\input{" + p[:-4] + "}" for p in paths)


def _abstract_region(text: str) -> str:
    return f"%% mdl:block abstract abstract\n{text.rstrip()}\n{END}" if text.strip() else \
        f"%% mdl:block abstract abstract\n{END}"


def main_skeleton(s: dict, user_preamble: str, abstract: str, sections: list[str], extra_body: str = "") -> str:
    tpl = s["document"].get("template")
    lang = s["document"].get("language", "fr")
    front = _region("front", gen_front(s))
    ab = _abstract_region(abstract)
    if tpl == "amsart":
        head = [front, r"\begin{abstract}", ab, r"\end{abstract}", r"\maketitle"]
    elif tpl == "elsarticle":
        head = [r"\begin{frontmatter}", front, r"\begin{abstract}", ab, r"\end{abstract}", r"\end{frontmatter}"]
    elif tpl == "beamer":
        head = [front, r"\begin{frame}", r"\titlepage", r"\end{frame}",
                r"\begin{frame}{" + ("Résumé" if lang == "fr" else "Abstract") + "}", ab, r"\end{frame}"]
    else:
        head = [front, r"\maketitle", r"\begin{abstract}", ab, r"\end{abstract}"]
    parts = [_region("preamble", gen_preamble(s)),
             (user_preamble.strip("\n") + "\n") if user_preamble.strip() else
             "% Vos propres lignes de préambule (conservées telles quelles) / your own preamble lines.\n",
             r"\begin{document}", *head, ""]
    if extra_body.strip():
        parts += [extra_body.strip("\n"), ""]
    parts += [_region("sections", gen_sections(sections)), "", _region("backmatter", gen_backmatter(s)),
              r"\end{document}", ""]
    return "\n".join(parts)


def replace_region(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(?ms)^%% mdl:{name} begin\n.*?^%% mdl:{name} end$")
    new = _region(name, body)
    if pat.search(text):
        return pat.sub(lambda _m: new, text, count=1)
    return text


def get_region(text: str, name: str) -> str | None:
    m = re.search(rf"(?ms)^%% mdl:{name} begin\n(.*?)^%% mdl:{name} end$", text)
    return m.group(1).rstrip("\n") if m else None


def section_paths(main: str) -> list[str]:
    reg = get_region(main, "sections")
    if reg is None:
        reg = main
    out = []
    for m in re.finditer(r"\\(?:input|include)\{([^}]+)\}", reg):
        p = m.group(1).strip()
        p = p if p.endswith(".tex") else p + ".tex"
        if SECTION_PATH.match(p) and p not in out:
            out.append(p)
    return out


# ================================================================ files
def read_files(ctx, pid: str) -> dict[str, str]:
    """main.tex + section files (text). Figures are not included."""
    r = root(ctx, pid)
    out = {}
    try:
        out["main.tex"] = (r / "main.tex").read_text(encoding="utf-8")
    except OSError:
        return {}
    for p in sorted((r / "sections").glob("*.tex")) if (r / "sections").is_dir() else []:
        rel = f"sections/{p.name}"
        if SECTION_PATH.match(rel):
            try:
                out[rel] = p.read_text(encoding="utf-8")
            except OSError:
                pass
    return out


def write_file(ctx, pid: str, path: str, text: str) -> str:
    if not valid_path(path) or path.startswith("figures/"):
        raise TexProjectError("bad_path")
    if len(text.encode("utf-8")) > MAX_FILE:
        raise TexProjectError("too_large", 413)
    config.atomic_write_text(root(ctx, pid) / path, text)
    return text_hash(text)


def delete_file(ctx, pid: str, path: str) -> None:
    if not SECTION_PATH.match(path or ""):
        raise TexProjectError("bad_path")
    try:
        (root(ctx, pid) / path).unlink()
    except FileNotFoundError:
        pass


def write_settings(ctx, pid: str, s: dict) -> None:
    config.atomic_write_text(root(ctx, pid) / "madalean.toml", dump_toml(s))


def apply_settings(ctx, pid: str, s: dict) -> dict[str, str]:
    """Write madalean.toml and regenerate the managed regions of main.tex. Returns the changed files."""
    write_settings(ctx, pid, s)
    main = (root(ctx, pid) / "main.tex").read_text(encoding="utf-8")
    new = main
    if s["madalean"].get("preamble", "managed") == "managed":
        new = replace_region(new, "preamble", gen_preamble(s))
    new = replace_region(new, "front", gen_front(s))
    new = replace_region(new, "backmatter", gen_backmatter(s))
    if new != main:
        snapshot(ctx, pid, "settings", auto=True)
        write_file(ctx, pid, "main.tex", new)
        return {"main.tex": new}
    return {}


def change_template(ctx, pid: str, template: str) -> dict:
    """Switch class/template: settings keep language, front matter, macros, theorems, extra packages; main.tex is
    rebuilt around the same abstract, sections and user preamble lines."""
    if template not in TEMPLATES:
        raise TexProjectError("bad_template")
    with lock(pid):
        s = read_settings(ctx, pid)
        t = TEMPLATES[template]
        s["document"].update({"template": template, "class": t["class"], "options": list(t["options"])})
        s["packages"]["base"] = list(t["packages"])
        s["bibliography"]["style"] = t["bibstyle"]
        s["madalean"]["preamble"] = "managed"
        files = read_files(ctx, pid)
        main = files.get("main.tex", "")
        snapshot(ctx, pid, f"template:{template}", auto=False)
        regions = parse_file("main.tex", main)
        abstract = next((r["body"] for r in regions if r["id"] == "abstract"), "")
        new = main_skeleton(s, user_preamble(main), abstract, section_paths(main), extra_body(main))
        write_settings(ctx, pid, s)
        write_file(ctx, pid, "main.tex", new)
        return s


def user_preamble(main: str) -> str:
    m = re.search(r"(?ms)^%% mdl:preamble end\n(.*?)^\\begin\{document\}", main)
    return m.group(1) if m else ""


def extra_body(main: str) -> str:
    """Text of main.tex's body that is outside every managed/known part (kept when the skeleton is rebuilt)."""
    m = re.search(r"(?ms)^\\begin\{document\}\n(.*?)^\\end\{document\}", main)
    if not m:
        return ""
    body = m.group(1)
    for name in MANAGED:
        body = re.sub(rf"(?ms)^%% mdl:{name} begin\n.*?^%% mdl:{name} end\n?", "", body)
    body = re.sub(r"(?ms)^%% mdl:block abstract abstract\n.*?^%% mdl:end\n?", "", body)
    for ln in (r"\begin{abstract}", r"\end{abstract}", r"\maketitle", r"\begin{frontmatter}", r"\end{frontmatter}",
               r"\titlepage", r"\begin{frame}", r"\end{frame}"):
        body = body.replace(ln + "\n", "")
    body = re.sub(r"(?m)^\\begin\{frame\}\{[^}]*\}\n", "", body)
    return body.strip()


# ================================================================ regions / parsing
def parse_file(path: str, text: str) -> list[dict]:
    """Regions of a file: [{id, kind, dossier_id, start, end, body_start, body, marked}] (offsets in `text`).
    Text before the first marker of a section file becomes a region with a deterministic id (written at the
    next save). main.tex only has the abstract region."""
    lines = text.split("\n")
    offs = []
    pos = 0
    for ln in lines:
        offs.append(pos)
        pos += len(ln) + 1
    regions: list[dict] = []
    cur = None

    def close(i_end_line: int):
        nonlocal cur
        if cur is None:
            return
        end = offs[i_end_line] if i_end_line < len(offs) else len(text)
        cur["end"] = end
        body = text[cur["body_start"]:end]
        cur["body"] = body[:-1] if body.endswith("\n") else body
        regions.append(cur)
        cur = None
    for i, ln in enumerate(lines):
        m = MARK.match(ln)
        if m:
            close(i)
            cur = {"id": m.group(1), "kind": m.group(2), "dossier_id": m.group(3) or "", "start": offs[i],
                   "body_start": offs[i] + len(ln) + 1, "marked": True}
            continue
        if ln.strip() == END and cur is not None:
            close(i)
            continue
        if cur is None and path != "main.tex" and not regions and ln.strip() and not ln.startswith("%"):
            # unmarked leading text of a section file
            cur = {"id": "b-" + hashlib.sha1(path.encode()).hexdigest()[:8], "start": offs[i], "body_start": offs[i],
                   "kind": "section" if re.match(r"\s*\\section\*?\{", ln) else "prose", "dossier_id": "",
                   "marked": False}
    close(len(lines))
    for r in regions:
        if r["body_start"] > len(text):
            r["body_start"] = len(text)
    return regions


SECTION_LINE = re.compile(r"^\s*\\(section|chapter)\*?\{((?:[^{}]|\{[^{}]*\})*)\}(\s*\\label\{[^}]*\})?[ \t]*\n?")


def split_heading(body: str) -> tuple[str, str, str]:
    """(title, heading line, rest) of a section-like region."""
    m = SECTION_LINE.match(body)
    if not m:
        return "", "", body
    return m.group(2), body[:m.end()], body[m.end():]


def heading_line(title: str, label: str = "", template: str = "") -> str:
    cmd = "chapter" if template == "report" and False else "section"
    lab = r"\label{sec:" + slugify(title, 30) + "}" if not label else label
    return "\\" + cmd + "{" + title + "}" + lab


# ================================================================ sidecar (blocks.json)
def _side_path(ctx, pid: str) -> Path:
    return root(ctx, pid) / ".madalean" / "blocks.json"


def read_side(ctx, pid: str) -> dict:
    data, _bad = config.read_json(_side_path(ctx, pid)) if _side_path(ctx, pid).exists() else ({}, False)
    if not isinstance(data, dict):
        data = {}
    data.setdefault("blocks", {})
    data.setdefault("trash", [])
    data.setdefault("created", time.time())
    return data


def write_side(ctx, pid: str, side: dict) -> None:
    config.atomic_write_text(_side_path(ctx, pid), json.dumps(side, ensure_ascii=False, indent=1))


# ================================================================ creation / migration
def ensure(ctx, pid: str) -> bool:
    """Create the LaTeX project when missing: from the v1 article.json when there is one (migration, the JSON is
    renamed article.v1.json), else from the v1 default article (intro + one block per dossier). True if created."""
    with lock(pid):
        if exists(ctx, pid):
            return False
        from . import article as art_mod
        old = ctx.projects.store.dir(pid) / "article.json"
        art = None
        if old.is_file():
            try:
                art = json.loads(old.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                art = None
        if art is None:
            art = art_mod.default_article(ctx, pid)
        create_from_article(ctx, pid, art)
        if old.is_file():
            old.rename(old.with_name("article.v1.json"))
        return True


def _keys(ctx, pid: str) -> dict:
    try:
        from .sources import library
        return library(ctx).all_entries(pid)
    except Exception:  # noqa: BLE001
        return {}


def looks_markdown(text: str) -> bool:
    return bool(re.search(r"\[@|\*\*|```|^#{1,6}\s|^\s*[-*•]\s+\S|^\s*\d+[.)]\s+\S|(?<![\\])\*[^*\s][^*]*\*",
                          text or "", re.M))


def prose_to_latex(text: str, keys) -> str:
    """Markdown/prose (model drafts, older clients) → LaTeX through texio's sanitiser (maths allow-list,
    citations of existing keys only, everything else escaped)."""
    if not (text or "").strip():
        return ""
    return texio.sanitize_markdown(text, PLAIN, keys if keys is not None else {}).strip()


def latex_to_markdown(tex: str) -> str:
    """Derived Markdown of a LaTeX region (for readers of the v1 view such as the publish site)."""
    t = re.sub(r"(?m)^%.*\n?", "", tex or "")
    t = re.sub(r"(?<!\\)%.*", "", t)

    def cite(m):
        loc = m.group(1)
        return "[" + "; ".join("@" + k.strip() + (f", {loc}" if loc and i == 0 else "")
                               for i, k in enumerate(m.group(2).split(","))) + "]"
    t = re.sub(r"\\(?:cite|citep|citet)(?:\[([^\]]*)\])?\{([^}]+)\}", cite, t)
    t = re.sub(r"\\(?:emph|textit)\{([^{}]*)\}", r"*\1*", t)
    t = re.sub(r"\\textbf\{([^{}]*)\}", r"**\1**", t)
    t = re.sub(r"\\(?:label)\{[^}]*\}", "", t)
    t = re.sub(r"\\(?:c?ref|eqref)\{([^}]*)\}", r"(\1)", t)
    t = re.sub(r"\\(?:section|subsection|chapter)\*?\{([^{}]*)\}", r"\n## \1\n", t)
    t = re.sub(r"\\begin\{proof\}", "*Démonstration.* ", t)
    t = re.sub(r"\\begin\{(theorem|lemma|proposition|corollary|definition|claim|conjecture|remark|example)\}"
               r"(?:\[([^\]]*)\])?", lambda m: f"**{m.group(1).capitalize()}" + (f" ({m.group(2)})" if m.group(2)
                                                                                  else "") + ".** ", t)
    t = re.sub(r"\\end\{(proof|theorem|lemma|proposition|corollary|definition|claim|conjecture|remark|example|"
               r"itemize|enumerate)\}", "", t)
    t = re.sub(r"\\begin\{(itemize|enumerate)\}", "", t)
    t = re.sub(r"\\item\s*", "- ", t)
    t = t.replace(r"\MLunverified", "")
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def dossier_region_body(ctx, d, lang: str) -> str:
    """LaTeX of a dossier block, written once at creation (the article's own text from then on)."""
    from . import article as art_mod
    if d is None:
        return ""
    keys = _keys(ctx, d.project_id) if d.project_id else {}
    env = art_mod.env_for(d)
    if env == "claim" and art_mod._status(d) is False:
        env = "theorem"           # the source says what the author means; the build downgrades it (truth rule)
    title = re.sub(r"\s*\[[^\]]*\]$", "", d.title)[:120]
    label = "ml:" + re.sub(r"[^A-Za-z0-9]", "", d.id)
    out = [r"\begin{" + env + "}[" + texio.escape_plain(title) + r"]\label{" + label + "}",
           prose_to_latex(art_mod.statement_text(d), keys), r"\end{" + env + "}"]
    from ..export import strip_restated_theorem
    proof = re.sub(r"\s*[□∎■]\s*$", "", strip_restated_theorem(d.informal_proof or d.explanation or "").strip())
    if proof and env != "definition":
        out += [r"\begin{proof}", prose_to_latex(proof, keys), r"\end{proof}"]
    return "\n".join(out)


def region_text(rid: str, kind: str, body: str, dossier_id: str = "") -> str:
    head = f"%% mdl:block {rid} {kind}" + (f" dossier={dossier_id}" if dossier_id else "")
    return head + "\n" + body.strip("\n") + "\n"


def create_from_article(ctx, pid: str, art: dict, template: str = "amsart") -> None:
    """v1 article dict → LaTeX project (block ids kept: S-Q's suggestions stay valid)."""
    lang = (art.get("options") or {}).get("lang", "fr")
    s = default_settings(template, lang, art.get("title", ""))
    s["front"]["authors"] = [{k: str(a.get(k, "")) for k in ("name", "affiliation", "email")}
                             for a in art.get("authors", [])]
    opts = art.get("options") or {}
    s["madalean"]["lean_appendix"] = bool(opts.get("lean_appendix", True))
    s["madalean"]["verification_table"] = bool(opts.get("verification_table", True))
    s["theorems"]["numbering"] = opts.get("numbering", "section") if opts.get("numbering") in ("section", "global") \
        else "section"
    keys = _keys(ctx, pid)
    files: dict[str, list[str]] = {}
    order: list[str] = []
    side = {"blocks": {}, "trash": [], "created": time.time(), "migrated_from": "article.json"}
    cur = None
    n = 0

    def conv(b):
        t = b.get("text", "") or ""
        return prose_to_latex(t, keys) if t.strip() else ""
    for b in art.get("blocks", []):
        kind = b.get("kind", "prose")
        if kind in HEAD_KINDS or cur is None:
            n += 1
            title = b.get("title") or ({"intro": "Introduction", "conclusion": "Conclusion"}.get(kind)
                                       if kind in HEAD_KINDS else "")
            name = f"sections/{n:02d}-{slugify(title or 'preliminaires', 30)}.tex"
            while name in files:
                name = name[:-4] + "-x.tex"
            files[name] = []
            order.append(name)
            cur = name
            if kind not in HEAD_KINDS:
                pass
        if kind in HEAD_KINDS:
            body = heading_line(texio.escape_plain(b.get("title") or title)) + "\n" + conv(b)
        elif kind == "dossier":
            d = ctx.repo.get(b.get("dossier_id") or "")
            lead = conv(b)
            body = (lead + "\n\n" if lead else "") + dossier_region_body(ctx, d, lang)
        else:
            body = conv(b)
        files[cur].append(region_text(b["id"], kind, body, b.get("dossier_id", "") if kind == "dossier" else ""))
        side["blocks"][b["id"]] = {"source": b.get("source", "user"), "versions": b.get("versions", [])[-50:],
                                   "updated": b.get("updated", time.time())}
    ab = art.get("abstract") or {}
    side["blocks"]["abstract"] = {"source": ab.get("source", "user"), "versions": ab.get("versions", [])[-50:],
                                  "updated": ab.get("updated", time.time())}
    for t in art.get("trash", []):
        if isinstance(t, dict) and isinstance(t.get("block"), dict):
            side["trash"].append({"block": t["block"], "index": t.get("index", 0), "path": ""})
    r = root(ctx, pid)
    (r / "sections").mkdir(parents=True, exist_ok=True)
    (r / "figures").mkdir(parents=True, exist_ok=True)
    for name, regs in files.items():
        config.atomic_write_text(r / name, "\n".join(regs))
    write_settings(ctx, pid, s)
    config.atomic_write_text(r / "main.tex", main_skeleton(s, "", conv(ab), order))
    write_side(ctx, pid, side)
    snapshot(ctx, pid, "creation", auto=False)


def create_new(ctx, pid: str, template: str, title: str, lang: str) -> None:
    """An empty project from a template (gallery)."""
    with lock(pid):
        if exists(ctx, pid):
            raise TexProjectError("exists", 409)
        art = {"title": title, "authors": [], "options": {"lang": lang},
               "abstract": {"text": "", "source": "user", "versions": []},
               "blocks": [{"id": new_id(), "kind": "intro", "title": "Introduction" if lang == "fr" or True else "",
                           "text": "", "source": "user", "versions": []}]}
        create_from_article(ctx, pid, art, template)


# ================================================================ view (article.py compatibility)
def to_view(ctx, pid: str) -> dict:
    s = read_settings(ctx, pid)
    files = read_files(ctx, pid)
    side = read_side(ctx, pid)
    main = files.get("main.tex", "")
    blocks = []
    abstract = None

    def mk(reg: dict, path: str) -> dict:
        sd = side["blocks"].get(reg["id"], {})
        title, text = "", reg["body"]
        if reg["kind"] in HEAD_KINDS:
            title_tex, _h, rest = split_heading(reg["body"])
            title, text = title_tex, rest
        text = text.strip("\n")
        return {"id": reg["id"], "kind": reg["kind"], "title": title, "source": sd.get("source", "user"),
                "text": text, "md": latex_to_markdown(text), "format": "latex", "dossier_id": reg["dossier_id"],
                "path": path, "versions": sd.get("versions", []), "updated": sd.get("updated", 0)}
    for reg in parse_file("main.tex", main):
        if reg["id"] == "abstract":
            abstract = mk(reg, "main.tex")
            abstract["kind"] = "prose"
    if abstract is None:
        abstract = {"id": "abstract", "kind": "prose", "title": "", "source": "user", "text": "", "md": "",
                    "format": "latex", "dossier_id": "", "path": "main.tex", "versions": [], "updated": 0}
    for path in section_paths(main):
        if path in files:
            for reg in parse_file(path, files[path]):
                blocks.append(mk(reg, path))
    lang = "fr" if s["document"].get("language") == "fr" else "en"
    return {"title": s["front"].get("title", ""), "authors": s["front"].get("authors", []), "abstract": abstract,
            "blocks": blocks, "format": "latex",
            "options": {"lean_appendix": bool(s["madalean"].get("lean_appendix", True)),
                        "verification_table": bool(s["madalean"].get("verification_table", True)), "lang": lang,
                        "numbering": "global" if s["theorems"].get("numbering") == "global" else "section"},
            "trash": side["trash"],
            "created": side.get("created", 0), "updated": max([b["updated"] for b in blocks] + [0])}


def _block_body(ctx, pid: str, b: dict, keys, template: str) -> str:
    text = b.get("text", "") or ""
    if looks_markdown(text):
        text = prose_to_latex(text, keys)
    if b["kind"] in HEAD_KINDS:
        title = b.get("title") or ""
        if title and not re.search(r"\\[A-Za-z]", title):
            title = texio.escape_plain(title)
        return heading_line(title, "", template) + "\n" + text
    if b["kind"] == "dossier" and not text.strip():
        d = ctx.repo.get(b.get("dossier_id") or "")
        lang = "fr" if read_settings(ctx, pid)["document"].get("language") == "fr" else "en"
        return dossier_region_body(ctx, d, lang)
    return text


def apply_view(ctx, pid: str, art: dict) -> dict[str, str]:
    """Write a (modified) view back to the files. Unchanged regions are copied byte for byte; returns the files
    that changed {path: text}."""
    with lock(pid):
        s = read_settings(ctx, pid)
        files = read_files(ctx, pid)
        side = read_side(ctx, pid)
        main = files.get("main.tex", "")
        tpl = s["document"].get("template", "amsart")
        keys = _keys(ctx, pid)
        # settings
        s2 = json.loads(json.dumps(s))
        s2["front"]["title"] = str(art.get("title", s["front"].get("title", "")))[:300]
        s2["front"]["authors"] = [{k: str(a.get(k, ""))[:200] for k in ("name", "affiliation", "email")}
                                  for a in art.get("authors", []) if isinstance(a, dict)]
        o = art.get("options") or {}
        s2["madalean"]["lean_appendix"] = bool(o.get("lean_appendix", s["madalean"].get("lean_appendix", True)))
        s2["madalean"]["verification_table"] = bool(o.get("verification_table",
                                                          s["madalean"].get("verification_table", True)))
        if o.get("lang") in LANGS:
            s2["document"]["language"] = o["lang"]
        if o.get("numbering") in ("section", "global"):
            s2["theorems"]["numbering"] = o["numbering"]
        # current regions
        cur: dict[str, tuple[str, dict]] = {}
        for path in section_paths(main):
            for reg in parse_file(path, files.get(path, "")):
                cur[reg["id"]] = (path, reg)
        old_view = {b["id"]: b for b in to_view(ctx, pid)["blocks"]}
        first_of = {}
        for path in section_paths(main):
            regs = parse_file(path, files.get(path, ""))
            if regs:
                first_of[path] = regs[0]["id"]
        out_files: dict[str, list[str]] = {}
        order: list[str] = []
        used_names = set()
        current = None
        for i, b in enumerate(art.get("blocks", [])):
            bid, kind = b.get("id"), b.get("kind", "prose")
            if not isinstance(bid, str) or not re.fullmatch(r"b-[0-9a-f]{8}", bid):
                bid = new_id()
                b["id"] = bid
            if kind not in ("intro", "section", "conclusion", "prose", "dossier"):
                kind = "prose"
            prev = old_view.get(bid)
            unchanged = prev is not None and prev["text"] == (b.get("text") or "").strip("\n") and \
                prev["title"] == (b.get("title") or "") and prev["kind"] == kind and bid in cur and \
                cur[bid][1]["marked"]
            if unchanged:
                path0, reg = cur[bid]
                body_text = files[path0][reg["start"]:reg["end"]]
                if not body_text.endswith("\n"):
                    body_text += "\n"
            else:
                body = _block_body(ctx, pid, {**b, "kind": kind}, keys, tpl)
                body_text = region_text(bid, kind, body, b.get("dossier_id", "") if kind == "dossier" else "") + "\n"
            starts = kind in HEAD_KINDS or current is None
            if starts:
                if bid in cur and first_of.get(cur[bid][0]) == bid and cur[bid][0] not in used_names:
                    name = cur[bid][0]
                else:
                    title = texio_plain(b.get("title") or "") or "preliminaires"
                    name = f"sections/{len(order) + 1:02d}-{slugify(title, 30)}.tex"
                    while name in used_names or name in files:
                        name = name[:-4] + "-" + uuid.uuid4().hex[:4] + ".tex"
                used_names.add(name)
                order.append(name)
                out_files[name] = []
                current = name
            out_files[current].append(body_text)
            sd = side["blocks"].setdefault(bid, {})
            sd["source"] = b.get("source", sd.get("source", "user"))
            sd["versions"] = list(b.get("versions", sd.get("versions", [])))[-50:]
            sd["updated"] = b.get("updated", sd.get("updated", time.time()))
        # abstract
        ab = art.get("abstract") or {}
        ab_text = ab.get("text", "") or ""
        old_ab = next((r for r in parse_file("main.tex", main) if r["id"] == "abstract"), None)
        if old_ab is None or ab_text.strip("\n") != old_ab["body"].strip("\n"):
            new_ab = prose_to_latex(ab_text, keys) if looks_markdown(ab_text) else ab_text
            if old_ab is not None:
                main = main[:old_ab["start"]] + _abstract_region(new_ab) + "\n" + main[old_ab["end"]:]
        sd = side["blocks"].setdefault("abstract", {})
        sd["source"] = ab.get("source", sd.get("source", "user"))
        sd["versions"] = list(ab.get("versions", sd.get("versions", [])))[-50:]
        sd["updated"] = ab.get("updated", sd.get("updated", time.time()))
        # trash (v1 shape [{block, index}])
        tr = art.get("trash")
        if isinstance(tr, list):
            side["trash"] = [t for t in tr if isinstance(t, dict) and isinstance(t.get("block"), dict)][-50:]
        changed: dict[str, str] = {}
        new_files = {name: "".join(regs) for name, regs in out_files.items()}
        for name, text in new_files.items():
            if files.get(name) != text:
                changed[name] = text
        removed = [p for p in section_paths(main) if p not in new_files]
        main = replace_region(main, "sections", gen_sections(order))
        if changed or removed or main != files.get("main.tex"):
            snapshot(ctx, pid, "view", auto=True)
        for name, text in changed.items():
            write_file(ctx, pid, name, text)
        for p in removed:
            delete_file(ctx, pid, p)
        if main != files.get("main.tex"):
            write_file(ctx, pid, "main.tex", main)
            changed["main.tex"] = main
        if s2 != s:
            changed.update(apply_settings(ctx, pid, s2))
        write_side(ctx, pid, side)
        return changed


# ================================================================ history (content-addressed)
def _hist(ctx, pid: str) -> Path:
    return root(ctx, pid) / ".madalean" / "history"


def _hist_index(ctx, pid: str) -> list[dict]:
    p = _hist(ctx, pid) / "index.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def snapshot(ctx, pid: str, label: str = "", auto: bool = True, by: str = "") -> dict | None:
    """Store the current files (deduplicated by content). Automatic snapshots are spaced ≥ 120 s apart."""
    with lock(pid):
        idx = _hist_index(ctx, pid)
        if auto and idx and time.time() - idx[-1]["t"] < 120:
            return None
        files = read_files(ctx, pid)
        if not files:
            return None
        try:
            files["madalean.toml"] = (root(ctx, pid) / "madalean.toml").read_text(encoding="utf-8")
        except OSError:
            pass
        objs = _hist(ctx, pid) / "objects"
        objs.mkdir(parents=True, exist_ok=True)
        manifest = {}
        for path, text in files.items():
            data = text.encode("utf-8")
            h = hashlib.sha256(data).hexdigest()
            if not (objs / h).exists():
                (objs / h).write_bytes(zlib.compress(data, 6))
            manifest[path] = h
        if auto and idx and idx[-1]["files"] == manifest:
            return idx[-1]
        v = {"id": "v-" + uuid.uuid4().hex[:8], "t": time.time(), "label": label[:120], "auto": auto, "by": by,
             "files": manifest}
        idx.append(v)
        if len(idx) > MAX_HISTORY:                     # drop the oldest automatic ones first
            autos = [x for x in idx if x["auto"]]
            for x in autos[:len(idx) - MAX_HISTORY]:
                idx.remove(x)
            idx = idx[-MAX_HISTORY:]
        config.atomic_write_text(_hist(ctx, pid) / "index.json", json.dumps(idx, ensure_ascii=False))
        _gc_objects(ctx, pid, idx)
        return v


def _gc_objects(ctx, pid: str, idx: list[dict]) -> None:
    live = {h for v in idx for h in v["files"].values()}
    objs = _hist(ctx, pid) / "objects"
    for p in objs.iterdir():
        if p.name not in live and time.time() - p.stat().st_mtime > 60:
            p.unlink(missing_ok=True)


def versions(ctx, pid: str) -> list[dict]:
    return [{k: v[k] for k in ("id", "t", "label", "auto", "by")} | {"files": sorted(v["files"])}
            for v in reversed(_hist_index(ctx, pid))]


def version_file(ctx, pid: str, vid: str, path: str) -> str:
    v = next((x for x in _hist_index(ctx, pid) if x["id"] == vid), None)
    if v is None or path not in v["files"]:
        raise TexProjectError("not_found", 404)
    return zlib.decompress((_hist(ctx, pid) / "objects" / v["files"][path]).read_bytes()).decode("utf-8")


def restore_version(ctx, pid: str, vid: str, by: str = "") -> dict[str, str]:
    with lock(pid):
        v = next((x for x in _hist_index(ctx, pid) if x["id"] == vid), None)
        if v is None:
            raise TexProjectError("not_found", 404)
        snapshot(ctx, pid, "before-restore", auto=False, by=by)
        cur = read_files(ctx, pid)
        changed = {}
        for path in v["files"]:
            text = version_file(ctx, pid, vid, path)
            if path == "madalean.toml":
                config.atomic_write_text(root(ctx, pid) / path, text)
                continue
            if cur.get(path) != text:
                write_file(ctx, pid, path, text)
                changed[path] = text
        for path in cur:
            if path not in v["files"] and SECTION_PATH.match(path):
                delete_file(ctx, pid, path)
                changed[path] = ""
        return changed


# ================================================================ suggestions (track changes)
def _sug_path(ctx, pid: str) -> Path:
    return root(ctx, pid) / ".madalean" / "suggestions.json"


def _sug_read(ctx, pid: str) -> list[dict]:
    try:
        data = json.loads(_sug_path(ctx, pid).read_text(encoding="utf-8"))
        return data.get("items", []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return []


def _sug_write(ctx, pid: str, items: list[dict]) -> None:
    pending = [x for x in items if x["state"] == "pending"]
    done = [x for x in items if x["state"] != "pending"][-300:]
    config.atomic_write_text(_sug_path(ctx, pid), json.dumps({"items": done + pending}, ensure_ascii=False))


def find_block(ctx, pid: str, block_id: str, files: dict | None = None) -> tuple[str, dict] | None:
    files = files if files is not None else read_files(ctx, pid)
    main = files.get("main.tex", "")
    for path in ["main.tex"] + section_paths(main):
        for reg in parse_file(path, files.get(path, "")):
            if reg["id"] == block_id:
                return path, reg
    return None


def anchor(ctx, pid: str, sug: dict, files: dict | None = None) -> dict | None:
    """Current position {path, from, to} of a suggestion's `find` text (inside its block when it has one)."""
    files = files if files is not None else read_files(ctx, pid)
    if sug.get("block_id"):
        hit = find_block(ctx, pid, sug["block_id"], files)
        if hit is None:
            return None
        path, reg = hit
        lo, hi = reg["body_start"], reg["end"]
    else:
        path = sug.get("path", "")
        if path not in files:
            return None
        lo, hi = 0, len(files[path])
    text = files[path]
    find = sug.get("find", "")
    if not find:
        pos = hi if sug.get("at") != "before" else lo
        return {"path": path, "from": pos, "to": pos}
    start = lo
    for _ in range(int(sug.get("occurrence", 0)) + 1):
        i = text.find(find, start, hi)
        if i < 0:
            return None
        start = i + 1
    return {"path": path, "from": i, "to": i + len(find)}


def add_suggestion(ctx, pid: str, *, find: str, replace: str, block_id: str = "", path: str = "",
                   at: str = "replace", occurrence: int = 0, kind: str = "rewrite", origin: str = "assistant",
                   rationale: str = "", model: str = "", meta: dict | None = None) -> dict:
    from .texbuild import guard_ai
    from . import biblio
    if at not in ("replace", "after", "before") or origin not in ("assistant", "research", "user"):
        raise TexProjectError("bad_fields")
    if not block_id and not valid_path(path):
        raise TexProjectError("bad_path")
    replace = replace or ""
    if "[@" in replace:
        keys = _keys(ctx, pid)
        res = biblio.check_citations(replace, set(keys))
        replace = res.text
        replace = re.sub(r"\[([^\[\]\n]*@[^\[\]\n]*)\]",
                         lambda m: biblio.cite_to_latex(m.group(1), keys) or m.group(0), replace)
    bad = guard_ai(replace)
    if bad:
        raise TexProjectError("unsafe_tex", 422, found=", ".join(bad))
    with lock(pid):
        sug = {"id": "s-" + uuid.uuid4().hex[:8], "block_id": block_id, "path": path, "find": find[:20000],
               "occurrence": max(0, int(occurrence)), "at": at, "replace": replace[:40000], "kind": kind[:40],
               "origin": origin, "rationale": rationale[:2000], "model": model[:120], "created": time.time(),
               "state": "pending", "decided": 0, "by": "", "meta": meta or {}}
        files = read_files(ctx, pid)
        a = anchor(ctx, pid, sug, files)
        if a is None:
            raise TexProjectError("anchor_not_found", 409)
        sug["path"] = a["path"]
        items = _sug_read(ctx, pid)
        items.append(sug)
        _sug_write(ctx, pid, items)
        return dict(sug, anchor=a)


def list_suggestions(ctx, pid: str, state: str = "") -> list[dict]:
    with lock(pid):
        items = _sug_read(ctx, pid)
        files = read_files(ctx, pid)
        out, dirty = [], False
        for s in items:
            if s["state"] == "pending":
                a = anchor(ctx, pid, s, files)
                if a is None:
                    s["state"], s["decided"], dirty = "stale", time.time(), True
                else:
                    s = dict(s, anchor=a)
            if not state or s["state"] == state:
                out.append(s)
        if dirty:
            _sug_write(ctx, pid, [{k: v for k, v in x.items() if k != "anchor"} for x in items])
        return out


def _decide(ctx, pid: str, sid: str, state: str, by: str, apply: bool) -> tuple[dict, dict[str, str]]:
    with lock(pid):
        items = _sug_read(ctx, pid)
        s = next((x for x in items if x["id"] == sid), None)
        if s is None:
            raise TexProjectError("not_found", 404)
        if s["state"] != "pending":
            raise TexProjectError("decided", 409, state=s["state"])
        changed: dict[str, str] = {}
        if apply:
            files = read_files(ctx, pid)
            a = anchor(ctx, pid, s, files)
            if a is None:
                s["state"], s["decided"] = "stale", time.time()
                _sug_write(ctx, pid, items)
                raise TexProjectError("stale", 409)
            text = files[a["path"]]
            if s["at"] == "replace":
                new = text[:a["from"]] + s["replace"] + text[a["to"]:]
            elif s["at"] == "after":
                new = text[:a["to"]] + s["replace"] + text[a["to"]:]
            else:
                new = text[:a["from"]] + s["replace"] + text[a["from"]:]
            snapshot(ctx, pid, f"suggestion {sid}", auto=True, by=by)
            write_file(ctx, pid, a["path"], new)
            changed[a["path"]] = new
        s["state"], s["decided"], s["by"] = state, time.time(), by[:80]
        _sug_write(ctx, pid, items)
        return s, changed


def accept_suggestion(ctx, pid: str, sid: str, by: str = "", applied: bool = False) -> tuple[dict, dict[str, str]]:
    """`applied=True`: the editor already applied the change to its buffer (it saves the file itself)."""
    return _decide(ctx, pid, sid, "accepted", by, apply=not applied)


def reject_suggestion(ctx, pid: str, sid: str, by: str = "") -> dict:
    return _decide(ctx, pid, sid, "rejected", by, apply=False)[0]


# ================================================================ figures
IMAGE_MAGIC = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg", b"%PDF-": "pdf"}


def add_figure(ctx, pid: str, data: bytes) -> str:
    ext = next((e for m, e in IMAGE_MAGIC.items() if data.startswith(m)), None)
    if ext is None:
        raise TexProjectError("bad_type", 415)
    if len(data) > 15 * 1024 * 1024:
        raise TexProjectError("too_large", 413)
    h = hashlib.sha256(data).hexdigest()[:16]
    rel = f"figures/{h}.{ext}"
    p = root(ctx, pid) / rel
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.rename(p)
    return rel


def figures(ctx, pid: str) -> list[str]:
    d = root(ctx, pid) / "figures"
    return sorted(f"figures/{p.name}" for p in d.iterdir() if FIGURE_PATH.match(f"figures/{p.name}")) \
        if d.is_dir() else []


# ================================================================ outline / labels / cites (for completion)
LABEL_RE = re.compile(r"\\label\{([^}]{1,120})\}")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|parencite|textcite)\*?(?:\[[^\]]*\]){0,2}\{([^}]{1,400})\}")
ENV_RE = re.compile(r"\\begin\{([A-Za-z*]+)\}(?:\[([^\]]*)\])?")


def outline(files: dict[str, str], order: list[str]) -> tuple[list[dict], list[dict], list[str]]:
    """(headings, labels, cited keys) across main.tex then the sections in order."""
    heads, labels, cites = [], [], []
    for path in ["main.tex"] + order:
        text = files.get(path, "")
        envs: list[tuple[str, str]] = []
        for i, line in enumerate(text.split("\n")):
            if line.lstrip().startswith("%"):
                continue
            m = re.match(r"\s*\\(section|subsection|subsubsection|chapter)\*?\{((?:[^{}]|\{[^{}]*\})*)\}", line)
            if m:
                heads.append({"path": path, "line": i + 1, "level": m.group(1), "title": m.group(2)})
            for e in ENV_RE.finditer(line):
                envs.append((e.group(1), e.group(2) or ""))
            for lm in LABEL_RE.finditer(line):
                env = envs[-1][0] if envs else (heads[-1]["level"] if heads else "")
                title = envs[-1][1] if envs else (heads[-1]["title"] if heads else "")
                if m:
                    env, title = m.group(1), m.group(2)
                labels.append({"label": lm.group(1), "path": path, "line": i + 1, "env": env, "title": title[:120]})
            for cm in CITE_RE.finditer(line):
                for k in cm.group(1).split(","):
                    k = k.strip()
                    if k and k not in cites:
                        cites.append(k)
    return heads, labels, cites


# ================================================================ TeX bundle warm-up (deps/installer.py)
def warmup_documents() -> list[tuple[str, dict]]:
    """One real document per template (theorems, proof, align, cite, cross-references, tables), so that
    `install tex-bundle` caches every file the article editor's defaults need (offline afterwards)."""
    body = ("%% mdl:block b-00000001 section\n\\section{Introduction}\\label{sec:intro}\n"
            "Soit $f\\colon \\R \\to \\R$ continue \\cite{knuth} ; voir \\cref{thm:a} et \\eqref{eq:a}.\n"
            "\\begin{theorem}[Somme]\\label{thm:a}\nSi $a$ et $b$ sont pairs, $a+b$ est pair.\n\\end{theorem}\n"
            "\\begin{proof}\n\\begin{align}\na+b &= 2k+2l \\label{eq:a}\\\\ &= 2(k+l).\n\\end{align}\n\\end{proof}\n"
            "\\begin{definition}\nUn entier est \\emph{pair} s'il est divisible par $2$.\n\\end{definition}\n"
            "\\begin{remark}\n\\textbf{Gras}, \\textit{italique}, \\textsc{Petites Capitales}.\\footnote{Note.}\n"
            "\\end{remark}\n\\begin{itemize}\n\\item un\n\\end{itemize}\n"
            "\\begin{tabular}{cc}\\hline $x$ & $y$\\\\\\hline\\end{tabular}\n")
    bib = ("@book{knuth, author={Knuth, Donald E.}, title={The {\\TeX}book}, publisher={Addison-Wesley}, "
           "year={1984}}\n")
    out = []
    for tpl in TEMPLATES:
        for lang in (("fr", "en") if tpl == "amsart" else ("fr",)):
            s = default_settings(tpl, lang, "Échantillon ∀ ℕ")
            s["front"]["authors"] = [{"name": "A. Auteur", "affiliation": "Université", "email": "a@b.c"}]
            main = main_skeleton(s, "", "Résumé avec $x^2$.", ["sections/01-intro.tex"])
            sec = body if tpl != "beamer" else body.replace("\\section{Introduction}\\label{sec:intro}\n",
                                                            "\\section{Introduction}\n\\begin{frame}{Intro}\n") \
                .replace("\\begin{tabular}", "\\end{frame}\n\\begin{frame}\n\\begin{tabular}") + "\\end{frame}\n"
            if tpl == "beamer":
                sec = sec.replace("\\cref{", "\\ref{")
            doc = main.replace("\\input{sections/01-intro}", sec) \
                .replace("\\InputIfFileExists{madalean-generated}{}{}", "")
            out.append((doc, {"refs.bib": bib}))
    return out
