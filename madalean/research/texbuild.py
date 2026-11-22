"""Compilation of an article's LaTeX project (session S-R, docs/ARTICLE.md §6): security guard, package analysis
against the pinned tectonic bundle (no second TeX distribution), build with the prefix's tectonic (confined, cache
only, SyncTeX), plain-language diagnostics with one-click fixes, SyncTeX forward/inverse search.

Engines: the prefix's tectonic (`export.tectonic_cmd`). A development checkout without a prefix (tests) falls back
to the system XeLaTeX through latexmk (`-no-shell-escape`); an installed Madalean never uses the system TeX Live nor
the Overleaf container to compile."""
from __future__ import annotations

import asyncio
import difflib
import functools
import gzip
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

from .. import config, deps, export
from ..i18n import msg
from . import texproject as tp

# ================================================================ guard (S-H F5 rules on the whole project)
_DANGER = [
    (re.compile(r"\\write\s*18|\\immediate(?![A-Za-z])|\\openout(?![A-Za-z])|\\openin(?![A-Za-z])|\\read(?![A-Za-z])|\\newwrite(?![A-Za-z])|\\newread(?![A-Za-z])"
                r"|\\closeout(?![A-Za-z])|\\closein(?![A-Za-z])"), "file"),
    (re.compile(r"\^\^"), "hex"),
    (re.compile(r"\\csname(?![A-Za-z])|\\catcode(?![A-Za-z])|\\scantokens(?![A-Za-z])|\\endlinechar(?![A-Za-z])|\\lccode(?![A-Za-z])|\\uccode(?![A-Za-z])"), "rebuild"),
    (re.compile(r"\\(?:directlua|luaexec|latelua|ShellEscape|pdfshellescape|special)(?![A-Za-z])"), "engine"),
    (re.compile(r"\\(?:input|include|InputIfFileExists|IfFileExists|includegraphics|lstinputlisting|verbatiminput"
                r"|includeonly|addbibresource|bibliography)\s*(?:\[[^\]]*\])?\s*\{\s*(?:[/~]|[^}]*\.\.)"), "path"),
    (re.compile(r"\\input\s+[/~]"), "path"),
]
_DEFS = re.compile(r"\\(?:def|gdef|edef|xdef|let|futurelet|newcommand|renewcommand|providecommand|"
                   r"DeclareRobustCommand|makeatletter|makeatother|usepackage|RequirePackage|documentclass|"
                   r"newenvironment|renewenvironment|input|include|expandafter|noexpand)(?![A-Za-z])|\\(?:begin|end)\{document\}")


def strip_comments(text: str) -> str:
    """Comments removed, line structure kept (for scanning)."""
    return "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in text.split("\n"))


def xetex_branch(text: str) -> str:
    """Blank the `\\else … \\fi` part of `\\ifTUTeX` (pdfTeX-only lines, e.g. for Overleaf) keeping line numbers:
    Madalean compiles with XeTeX."""
    out, state = [], 0
    for ln in text.split("\n"):
        s = ln.strip()
        if state == 0 and s.startswith("\\ifTUTeX"):
            state = 1
        elif state == 1 and s == "\\else":
            state = 2
            out.append("")
            continue
        elif state in (1, 2) and s == "\\fi":
            state = 0
        out.append("" if state == 2 else ln)
    return "\n".join(out)


def guard(text: str) -> list[dict]:
    """Constructs refused in the project's source: [{line, what, kind}] (empty = fine)."""
    out = []
    for i, ln in enumerate(strip_comments(text).split("\n")):
        for rx, kind in _DANGER:
            m = rx.search(ln)
            if m:
                out.append({"line": i + 1, "what": m.group(0)[:40], "kind": kind})
    return out


def guard_ai(text: str) -> list[str]:
    """Constructs refused in AI-produced LaTeX (suggestions, macros, titles): the project guard + definitions and
    file inclusion. Returns what was found."""
    found = [g["what"] for g in guard(text or "")]
    found += [m.group(0) for m in _DEFS.finditer(strip_comments(text or ""))]
    return list(dict.fromkeys(found))


# ================================================================ package analysis
# command / environment → package that provides it (only when that package is not loaded)
CMD_PKG = {
    "includegraphics": "graphicx", "textcolor": "xcolor", "colorbox": "xcolor", "definecolor": "xcolor",
    "url": "url", "href": "hyperref", "cref": "cleveref", "Cref": "cleveref", "crefrange": "cleveref",
    "coloneqq": "mathtools", "eqqcolon": "mathtools", "DeclarePairedDelimiter": "mathtools", "mathclap": "mathtools",
    "SI": "siunitx", "si": "siunitx", "qty": "siunitx", "unit": "siunitx", "num": "siunitx",
    "todo": "todonotes", "listoftodos": "todonotes", "toprule": "booktabs", "midrule": "booktabs",
    "bottomrule": "booktabs", "multirow": "multirow", "lipsum": "lipsum", "xrightarrow": "amsmath",
    "DeclareMathOperator": "amsmath", "eqref": "amsmath", "numberwithin": "amsmath", "tikz": "tikz",
    "usetikzlibrary": "tikz", "theoremstyle": "amsthm", "qedhere": "amsthm", "subcaption": "subcaption",
    "captionof": "caption", "ding": "pifont", "cancel": "cancel", "bcancel": "cancel", "xspace": "xspace",
    "mathbbm": "bbm", "nicefrac": "nicefrac", "sfrac": "xfrac", "ensuremath": "", "citep": "natbib",
    "citet": "natbib", "autoref": "hyperref", "nameref": "hyperref", "texorpdfstring": "hyperref",
    "pgfmathsetmacro": "tikz", "tcbset": "tcolorbox", "newtcolorbox": "tcolorbox",
}
ENV_PKG = {
    "tikzpicture": "tikz", "tikzcd": "tikz-cd", "align": "amsmath", "align*": "amsmath", "gather": "amsmath",
    "gather*": "amsmath", "multline": "amsmath", "multline*": "amsmath", "cases": "amsmath", "pmatrix": "amsmath",
    "bmatrix": "amsmath", "vmatrix": "amsmath", "Bmatrix": "amsmath", "aligned": "amsmath", "split": "amsmath",
    "proof": "amsthm", "algorithm": "algorithm", "algorithmic": "algpseudocode", "tabularx": "tabularx",
    "longtable": "longtable", "subfigure": "subcaption", "lstlisting": "listings", "tcolorbox": "tcolorbox",
    "dcases": "mathtools", "multicols": "multicol", "minted": "minted", "Verbatim": "fvextra",
    "wrapfigure": "wrapfig", "landscape": "pdflscape",
}
# what a class / package loads by itself
CLASS_IMPLIES = {"amsart": {"amsmath", "amsthm", "amsfonts", "amstext"}, "amsbook": {"amsmath", "amsthm", "amsfonts"},
                 "amsproc": {"amsmath", "amsthm", "amsfonts"},
                 "beamer": {"hyperref", "xcolor", "graphicx", "amsthm", "amssymb", "amsmath", "geometry", "pgf"},
                 "elsarticle": {"natbib", "graphicx"}, "revtex4-2": {"natbib", "url"}, "article": set(),
                 "report": set(), "book": set()}
PKG_IMPLIES = {"mathtools": {"amsmath", "keyval", "calc"}, "amssymb": {"amsfonts"}, "unicode-math": {"fontspec"},
               "tikz": {"pgf", "xcolor", "graphicx", "keyval"}, "tikz-cd": {"tikz", "pgf", "xcolor"},
               "pgfplots": {"tikz", "pgf", "xcolor"}, "graphicx": {"graphics", "keyval"},
               "hyperref": {"url", "keyval", "kvoptions"}, "tcolorbox": {"pgf", "xcolor", "verbatim"},
               "cleveref": set(), "siunitx": {"xparse"}, "fvextra": {"fancyvrb"}, "subcaption": {"caption"},
               "algpseudocode": {"algorithmicx"}, "todonotes": {"tikz", "xcolor"}, "xcolor": set()}
NO_SHELL = {"minted": "listings", "svg": "graphicx (PNG/PDF)", "epstopdf": "graphicx (PNG/PDF)",
            "pythontex": "", "gnuplottex": "", "shellesc": ""}
USEPKG = re.compile(r"\\(usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
DOCCLASS = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
TIKZLIB = re.compile(r"\\usetikzlibrary\s*\{([^}]*)\}")
CMD = re.compile(r"\\([A-Za-z]+)")
BEGIN = re.compile(r"\\begin\{([A-Za-z*]+)\}")


@functools.lru_cache(maxsize=4)
def _bundle_index(index_path: str, mtime: float) -> frozenset:
    names = set()
    try:
        with open(index_path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                n = ln.split(" ", 1)[0]
                if n:
                    names.add(n)
    except OSError:
        pass
    return frozenset(names)


def bundle() -> dict:
    """{digest, index: frozenset(file names) | None, cached_dir: Path | None, engine: tectonic|system|none}."""
    cache = deps.tectonic_cache()
    try:
        from ..deps import manifest
        url = manifest.component("tex-bundle")["url"]
        from ..deps.installer import bundle_digest
        digest = bundle_digest(url)
    except Exception:  # noqa: BLE001
        digest = ""
    idx = cache / "bundles" / "data" / f"{digest}.index" if digest else None
    if export.tectonic_cmd() and idx is not None and idx.is_file():
        return {"digest": digest, "index": _bundle_index(str(idx), idx.stat().st_mtime),
                "cached_dir": cache / "bundles" / "data" / digest, "engine": "tectonic"}
    if not deps.installed() and shutil.which("kpsewhich"):
        return {"digest": "", "index": None, "cached_dir": None, "engine": "system"}
    return {"digest": digest, "index": None, "cached_dir": None, "engine": "none"}


@functools.lru_cache(maxsize=512)
def _kpse(name: str) -> bool:
    k = shutil.which("kpsewhich")
    if not k:
        return False
    try:
        return bool(subprocess.run([k, name], capture_output=True, text=True, timeout=10).stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def file_state(name: str, b: dict) -> str:
    """cached (compiles offline) | bundle (in the pinned bundle, not downloaded) | missing | system (dev only)."""
    if b["engine"] == "tectonic":
        if (b["cached_dir"] / name).is_file():
            return "cached"
        return "bundle" if name in b["index"] else "missing"
    if b["engine"] == "system":
        return "system" if _kpse(name) else "missing"
    return "missing"


def analyse(files: dict[str, str], settings: dict | None = None) -> dict:
    """Packages of the project: {class, packages:[{name, file, state, where:[{path,line}], why}], needed:[…],
    redundant:[{name, reason, path, line}], refused:[…], engine, digest}."""
    b = bundle()
    loaded: dict[str, list[dict]] = {}
    cls = ""
    tikzlibs: list[str] = []
    used_cmds: dict[str, dict] = {}
    used_envs: dict[str, dict] = {}
    order: list[str] = []
    for path in ["main.tex"] + [p for p in files if p != "main.tex"]:
        text = xetex_branch(strip_comments(files.get(path, "")))
        for i, ln in enumerate(text.split("\n")):
            m = DOCCLASS.search(ln)
            if m and not cls:
                cls = m.group(1).strip()
            for m in USEPKG.finditer(ln):
                for name in m.group(2).split(","):
                    name = name.strip()
                    if tp.PKG_NAME.match(name):
                        loaded.setdefault(name, []).append({"path": path, "line": i + 1})
                        order.append(name)
            for m in TIKZLIB.finditer(ln):
                tikzlibs += [x.strip() for x in m.group(1).split(",") if re.fullmatch(r"[A-Za-z0-9.-]+", x.strip())]
            for m in CMD.finditer(ln):
                used_cmds.setdefault(m.group(1), {"path": path, "line": i + 1})
            for m in BEGIN.finditer(ln):
                used_envs.setdefault(m.group(1), {"path": path, "line": i + 1})
    implied_by_class = CLASS_IMPLIES.get(cls, set())
    implied: dict[str, str] = {p: f"class:{cls}" for p in implied_by_class}
    for p in loaded:
        for q in PKG_IMPLIES.get(p, set()):
            implied.setdefault(q, f"package:{p}")
    have = set(loaded) | set(implied) | {"fontspec", "unicode-math"}
    pk = []
    if cls:
        pk.append({"name": cls, "file": f"{cls}.cls", "kind": "class", "state": file_state(f"{cls}.cls", b),
                   "where": [{"path": "main.tex", "line": 1}]})
    for name, where in loaded.items():
        pk.append({"name": name, "file": f"{name}.sty", "kind": "package", "state": file_state(f"{name}.sty", b),
                   "where": where})
    for lib in dict.fromkeys(tikzlibs):
        f = f"tikzlibrary{lib}.code.tex"
        st = file_state(f, b)
        if st == "missing":
            st2 = file_state(f"pgflibrary{lib}.code.tex", b)
            st, f = (st2, f"pgflibrary{lib}.code.tex") if st2 != "missing" else (st, f)
        pk.append({"name": f"tikz:{lib}", "file": f, "kind": "tikzlibrary", "state": st, "where": []})
    needed, seen = [], set()
    for cmd, where in used_cmds.items():
        p = CMD_PKG.get(cmd)
        if p and p not in have and p not in seen and not (settings and cmd in settings.get("macros", {})):
            seen.add(p)
            needed.append({"name": p, "why": "\\" + cmd, **where, "state": file_state(f"{p}.sty", b)})
    for env, where in used_envs.items():
        p = ENV_PKG.get(env)
        if p and p not in have and p not in seen and not _env_defined(env, files):
            seen.add(p)
            needed.append({"name": p, "why": f"\\begin{{{env}}}", **where, "state": file_state(f"{p}.sty", b)})
    redundant = []
    for name, where in loaded.items():
        if len(where) > 1:
            redundant.append({"name": name, "reason": "twice", **where[1]})
        elif name in implied and name != "amsmath" or (name == "amsmath" and name in implied_by_class):
            src = implied[name]
            redundant.append({"name": name, "reason": src, **where[0]})
    if "cleveref" in order and "hyperref" in order and order.index("cleveref") < order.index("hyperref"):
        w = loaded["cleveref"][0]
        redundant.append({"name": "cleveref", "reason": "order", **w})
    refused = [{"name": n, "instead": NO_SHELL[n], **loaded[n][0]} for n in loaded if n in NO_SHELL]
    return {"class": cls, "packages": pk, "needed": needed, "redundant": redundant, "refused": refused,
            "engine": b["engine"], "digest": b["digest"]}


def _env_defined(env: str, files: dict) -> bool:
    pat = re.compile(r"\\new(?:theorem|environment|tcolorbox)\*?\{" + re.escape(env) + r"\}")
    return any(pat.search(t) for t in files.values())


def write_lock(ctx, pid: str, a: dict) -> None:
    lock = {"generated_by": "madalean", "engine": a["engine"], "bundle_digest": a["digest"],
            "class": a["class"],
            "files": {p["file"]: p["state"] for p in sorted(a["packages"], key=lambda x: x["file"])}}
    path = tp.root(ctx, pid) / "madalean.lock"
    text = json.dumps(lock, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    try:
        if path.read_text(encoding="utf-8") == text:
            return
    except OSError:
        pass
    config.atomic_write_text(path, text)


# ================================================================ truth rule (build copy only)
THM = ("theorem", "lemma", "proposition", "corollary")


def dossier_states(ctx, ids: set[str]) -> dict[str, dict]:
    out = {}
    for did in ids:
        d = ctx.repo.get(did)
        if d is None:
            out[did] = {"status": "missing", "title": "", "theorem": ""}
            continue
        cond = (d.extra or {}).get("conditional_proof")
        st = "verified" if d.proof_is_current else ("conditional" if cond else "unverified")
        out[did] = {"status": st, "title": d.title, "theorem": d.theorem or "", "dossier_status": d.status,
                    "admitted": list((cond or {}).get("admitted") or [])}
    return out


LEAN_LINK = re.compile(r"^\s*%\s*mdl:lean\s+([A-Za-z0-9][A-Za-z0-9._-]{0,79})\s*$")


def linked_dossiers(files: dict[str, str]) -> list[tuple[str, str, int]]:
    """[(dossier id, path, line)] — dossier regions and `% mdl:lean <id>` links."""
    out = []
    for path, text in files.items():
        for i, ln in enumerate(text.split("\n")):
            m = tp.MARK.match(ln)
            if m and m.group(3):
                out.append((m.group(3), path, i + 1))
            m = LEAN_LINK.match(ln)
            if m:
                out.append((m.group(1), path, i + 1))
    return out


WAS = "%mdl:was="


def untruth(text: str) -> str:
    """Inverse of truth_transform (files coming back from Overleaf)."""
    text = re.sub(r"\\begin\{claim\}(.*?) \\MLunverified\\ %mdl:was=([a-z]+)$",
                  lambda m: "\\begin{" + m.group(2) + "}" + m.group(1), text, flags=re.M)
    return re.sub(r"\\end\{claim\}(.*?)%mdl:was=([a-z]+)$", lambda m: "\\end{" + m.group(2) + "}" + m.group(1),
                  text, flags=re.M)


def truth_transform(text: str, states: dict[str, dict]) -> str:
    """Theorem-like environments of a dossier region (or linked by `% mdl:lean`) whose dossier is not
    Lean-verified become `claim` + \\MLunverified (the source is untouched)."""
    lines = text.split("\n")
    pending: str | None = None            # dossier id of the current region
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = tp.MARK.match(ln)
        if m:
            pending = m.group(3) or None
            i += 1
            continue
        mb = re.match(r"(\s*)\\begin\{(" + "|".join(THM) + r")\}", ln)
        if mb:
            did = pending
            nxt = LEAN_LINK.match(lines[i + 1]) if i + 1 < len(lines) else None
            if nxt:
                did = nxt.group(1)
            if did and states.get(did, {}).get("status") != "verified":
                env = mb.group(2)
                lines[i] = ln.replace(r"\begin{" + env + "}", r"\begin{claim}", 1) + r" \MLunverified\ " + \
                    WAS + env
                for j in range(i + 1, len(lines)):
                    if r"\end{" + env + "}" in lines[j]:
                        lines[j] = lines[j].replace(r"\end{" + env + "}", r"\end{claim}", 1) + WAS + env
                        break
            pending = None if not nxt else pending
        i += 1
    return "\n".join(lines)


def generated_tex(ctx, files: dict[str, str], states: dict[str, dict], s: dict) -> str:
    """madalean-generated.tex: verification table and Lean appendix of the linked dossiers."""
    fr = s["document"].get("language") == "fr"
    links = list(dict.fromkeys(did for did, _p, _l in linked_dossiers(files)))
    if not links:
        return "% (no Lean dossier linked)\n"
    from ..export import _esc
    out = []
    if s["madalean"].get("verification_table", True):
        title = "Vérification formelle" if fr else "Formal verification"
        cols = ("Résultat", "Nom Lean", "État") if fr else ("Result", "Lean name", "State")
        out += [r"\section*{" + title + "}",
                r"{\footnotesize " + ("Un résultat n'est marqué vérifié que si Lean a accepté sa preuve "
                                      "(verdict strict)." if fr else
                                      "A result is marked verified only if Lean accepted its proof (strict verdict).")
                + r"\par}\smallskip", r"{\footnotesize\noindent\begin{tabular}{p{0.38\linewidth}p{0.32\linewidth}"
                                      r"p{0.2\linewidth}}", r"\textbf{" + cols[0] + r"} & \textbf{" + cols[1] +
                r"} & \textbf{" + cols[2] + r"}\\\hline"]
        names = {"verified": ("vérifié", "verified"), "conditional": ("conditionnel", "conditional"),
                 "unverified": ("non vérifié", "not verified"), "missing": ("dossier absent", "missing dossier")}
        for did in links:
            st = states.get(did, {"status": "missing", "title": "", "theorem": ""})
            nm = names.get(st["status"], names["missing"])[0 if fr else 1]
            out.append(_esc(st.get("title") or did, tp.PLAIN)[:200] + " & " + r"\texttt{" +
                       _esc(st.get("theorem") or "—", tp.PLAIN, True)[:80] + "} & " + nm + r"\\")
        out.append(r"\end{tabular}}")
    if s["madalean"].get("lean_appendix", True):
        codes = []
        for did in links:
            d = ctx.repo.get(did)
            if d is not None and d.proof_is_current:
                codes.append((d.theorem, d.proof))
        if codes:
            out += [r"\section*{" + ("Code Lean" if fr else "Lean code") + "}"]
            for name, code in codes:
                safe = code.replace(r"\end{verbatim}", r"\end {verbatim}")
                out += [r"\subsection*{\texttt{" + _esc(name or "", tp.PLAIN, True) + "}}", r"{\footnotesize",
                        r"\begin{verbatim}", safe.rstrip(), r"\end{verbatim}", "}"]
    return "\n".join(out) + "\n"


# ================================================================ bibliography of the build
def bib_text(ctx, pid: str, cites: list[str]) -> tuple[str, list[str]]:
    from . import biblio
    known = tp._keys(ctx, pid)
    have = [k for k in cites if k in known]
    unknown = [k for k in cites if k not in known]
    return "".join(biblio.item_to_bibtex(known[k], k) + "\n" for k in have), unknown


# ================================================================ engines and runs
def engine_cmd(online: bool = False) -> tuple[list[str], str] | None:
    tec = export.tectonic_cmd()
    if tec:
        cmd = [x for x in tec if not (online and x == "--only-cached")] + ["--synctex"]
        return cmd, "tectonic"
    if deps.installed():
        return None                       # an installed Madalean never compiles with the system TeX
    latexmk, xe = deps.tool("latexmk"), deps.tool("xelatex")
    if latexmk and xe:
        return [latexmk, "-xelatex", "-norc", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
                "-synctex=1", "-latexoption=-no-shell-escape", "-silent"], "xelatex"
    return None


async def run_tex(cmd: list[str], cwd: Path, timeout: float, net: bool = False) -> tuple[int | None, str]:
    """export._run with an optional network (only for fetching files of the pinned bundle, on demand)."""
    env = export.tex_env()
    full = export.tex_confine(cmd, cwd, env)
    if net and full and full[0] != cmd[0] and "--unshare-all" in full:
        i = full.index("--unshare-all") + 1
        extra = ["--share-net"]
        resolv = Path("/etc/resolv.conf")
        if resolv.is_symlink():                   # systemd-resolved: the stub file lives under /run
            target = resolv.resolve()
            if target.is_file():
                extra += ["--ro-bind", str(target.parent), str(target.parent)]
        full[i:i] = extra
    try:
        proc = await asyncio.create_subprocess_exec(*full, cwd=str(cwd), stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL,
                                                    start_new_session=True, env=env)
    except OSError as e:
        return 127, str(e)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        await proc.wait()
        return None, "timeout"
    except asyncio.CancelledError:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        raise
    return proc.returncode, out.decode("utf-8", "replace")[-20000:]


# ================================================================ diagnostics
def _d(severity: str, path: str, line: int, message: str, tkey: str, fix: dict | None = None, **params) -> dict:
    return {"severity": severity, "path": path, "line": line, "message": message[:400], "plain": msg(tkey, **params),
            "fix": fix}


def _norm_path(p: str, files: dict) -> str:
    p = p.strip().lstrip("./")
    for cand in (p, p + ".tex"):
        if cand in files:
            return cand
    base = os.path.basename(p)
    for f in files:
        if os.path.basename(f) in (base, base + ".tex"):
            return f
    return "main.tex"


def _find(files: dict, needle: str) -> tuple[str, int]:
    for path, text in files.items():
        i = text.find(needle)
        if i >= 0:
            return path, text.count("\n", 0, i) + 1
    return "main.tex", 0


def known_commands(files: dict, s: dict) -> list[str]:
    from .. import texio
    defined = set(re.findall(r"\\(?:newcommand|renewcommand|providecommand|DeclareMathOperator)\*?\{?\\([A-Za-z]+)",
                             "\n".join(files.values())))
    return sorted(set(texio.MATH_COMMANDS) | set(CMD_PKG) | set(s.get("macros", {})) | defined |
                  set("section subsection emph textbf textit label ref cite item begin end footnote caption".split()))


def parse_log(out: str, log: str, files: dict, s: dict, b: dict) -> list[dict]:
    diags: list[dict] = []
    text = out + "\n" + log
    # error location: tectonic "error: sections/a:3: msg", latexmk -file-line-error "./sections/a.tex:3: msg"
    loc = None
    for m in re.finditer(r"(?m)^(?:error: )?\.?/?([A-Za-z0-9_./-]+?(?:\.tex)?):(\d+): (.+)$", text):
        if m.group(1).endswith((".log", ".sty", ".cls")) or "something bad" in m.group(3):
            continue
        loc = (_norm_path(m.group(1), files), int(m.group(2)), m.group(3).strip())
        break
    # the TeX error block of the log
    m = re.search(r"(?m)^(?:! |\.?/?[A-Za-z0-9_./-]+\.tex:\d+: )(.+?)\n(.*?)(?:^l\.(\d+) (.*?)\n(.*?)$)", log, re.S)
    raw = m.group(1).strip() if m else (loc[2] if loc else "")
    ctx_line = (m.group(4) if m else "") or ""
    path, line = (loc[0], loc[1]) if loc else ("main.tex", int(m.group(3)) if m and m.group(3) else 0)
    lower = (raw + " " + (loc[2] if loc else "")).lower()
    if "not loadable" in lower or "font" in lower and "not found" in lower:
        fn = re.search(r"\[([^\]:]+)\]", raw + log)
        fname = (fn.group(1) + ".otf") if fn and "." not in fn.group(1) else (fn.group(1) if fn else "")
        diags.append(_d("error", path, line, raw, "Une police utilisée par la mise en page n'est pas encore "
                         "téléchargée : téléchargez-la une fois.", {"kind": "fetch", "files": [fname] if fname
                                                                     else []}))
    elif "not found" in lower and ("file" in lower or ".sty" in lower or ".cls" in lower):
        f = re.search(r"[`']([^`']+\.(?:sty|cls|tex|code\.tex|bst|def|fd))'", raw + " " + log)
        fname = f.group(1) if f else ""
        st = file_state(fname, b) if fname else ("bundle" if b["engine"] == "tectonic" else "missing")
        if st == "bundle":
            diags.append(_d("error", path, line, raw, "Le fichier {file} est dans le TeX de Madalean mais pas encore "
                             "téléchargé : téléchargez-le une fois (ensuite tout marche hors ligne).",
                             {"kind": "fetch", "files": [fname]}, file=fname))
        else:
            diags.append(_d("error", path, line, raw, "Le fichier {file} n'existe pas dans le TeX de Madalean. "
                             "Retirez ce paquet ou remplacez-le.", {"kind": "remove_package",
                                                                    "name": fname.rsplit(".", 1)[0]}, file=fname))
    elif "undefined control sequence" in lower:
        cmds = re.findall(r"\\([A-Za-z]+)", ctx_line)
        cmd = cmds[-1] if cmds else ""
        pkg = CMD_PKG.get(cmd, "")
        if pkg:
            diags.append(_d("error", path, line, raw, "La commande \\{cmd} vient du paquet {pkg}, qui n'est pas "
                             "chargé.", {"kind": "add_package", "name": pkg}, cmd=cmd, pkg=pkg))
        else:
            close = difflib.get_close_matches(cmd, known_commands(files, s), 1, 0.75) if cmd else []
            if close:
                diags.append(_d("error", path, line, raw, "Commande inconnue \\{cmd}. Vouliez-vous écrire \\{close} ?",
                                {"kind": "replace", "find": "\\" + cmd, "replace": "\\" + close[0]}, cmd=cmd,
                                close=close[0]))
            else:
                diags.append(_d("error", path, line, raw, "Commande inconnue \\{cmd} : définissez-la dans les "
                                 "macros (Options avancées) ou corrigez-la.", {"kind": "add_macro", "name": cmd},
                                cmd=cmd or "?"))
    elif re.search(r"environment (\S+) undefined", lower):
        env = re.search(r"nvironment (\S+) undefined", raw + " " + (loc[2] if loc else "")).group(1).strip("`'.")
        pkg = ENV_PKG.get(env)
        if pkg:
            diags.append(_d("error", path, line, raw, "L'environnement {env} vient du paquet {pkg}, qui n'est pas "
                             "chargé.", {"kind": "add_package", "name": pkg}, env=env, pkg=pkg))
        else:
            diags.append(_d("error", path, line, raw, "L'environnement {env} n'est pas défini : ajoutez-le aux "
                             "environnements de théorèmes (Options avancées) ou corrigez son nom.",
                             {"kind": "add_theorem", "env": env}, env=env))
    elif "missing $ inserted" in lower:
        diags.append(_d("error", path, line, raw, "Une formule est hors des $…$ (ou un _ ou ^ est dans le texte). "
                         "Entourez-la de $…$ ou écrivez \\_.", None))
    elif "missing } inserted" in lower or "extra }" in lower or "too many }" in lower or "runaway argument" in lower \
            or "file ended while scanning" in lower or "missing { inserted" in lower:
        diags.append(_d("error", path, line, raw, "Accolades { } mal appariées près de cette ligne.", None))
    elif re.search(r"\\begin\{.*\} on input line \d+ ended by", raw):
        diags.append(_d("error", path, line, raw, "Un \\begin{…} n'est pas fermé par le bon \\end{…}.", None))
    elif "missing \\begin{document}" in lower:
        diags.append(_d("error", path, line, raw, "Du texte se trouve avant \\begin{document} (dans le préambule).",
                        None))
    elif "unrecoverable error" in lower or raw:
        diags.append(_d("error", path, line, raw or "?", "Erreur LaTeX : {raw}", None, raw=(raw or "?")[:200]))
    # warnings (also when the build succeeded)
    seen = set()
    for m in re.finditer(r"Reference `([^']+)' on page \d+ undefined", log):
        k = m.group(1)
        if ("ref", k) in seen:
            continue
        seen.add(("ref", k))
        p, ln = _find(files, "{" + k + "}")
        diags.append(_d("warning", p, ln, m.group(0), "Référence \\ref{{{name}}} vers une étiquette qui n'existe pas.",
                        None, name=k))
    for m in re.finditer(r"Citation `([^']+)' on page \d+ undefined", log):
        k = m.group(1)
        if ("cite", k) in seen:
            continue
        seen.add(("cite", k))
        p, ln = _find(files, k)
        diags.append(_d("warning", p, ln, m.group(0), "Citation {name} absente de la bibliothèque du projet.",
                        {"kind": "open_sources"}, name=k))
    over = len(re.findall(r"Overfull \\hbox", log))
    if over:
        diags.append(_d("info", "main.tex", 0, f"{over} overfull hbox", "{n} ligne(s) dépassent légèrement la "
                         "marge.", None, n=over))
    return diags


# ================================================================ build
def build_dir(ctx, pid: str) -> Path:
    return Path(ctx.paths.cache) / "texbuild" / pid


def last_result(ctx, pid: str) -> dict | None:
    try:
        return json.loads((build_dir(ctx, pid) / "out" / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def prepare(ctx, pid: str, for_export: bool = False,
            overrides: dict[str, str] | None = None) -> tuple[dict, dict, dict, str]:
    """(files for the build {path: text|bytes}, settings, analysis, input hash). Raises nothing.
    `overrides`: source files replaced for this build only (a proposed fix checked before it is offered)."""
    files = {**tp.read_files(ctx, pid), **(overrides or {})}
    s = tp.read_settings(ctx, pid)
    main = files.get("main.tex", "")
    order = tp.section_paths(main)
    _h, _l, cites = tp.outline(files, order)
    states = dossier_states(ctx, {d for d, _p, _l in linked_dossiers(files)})
    build: dict = {}
    for path, text in files.items():
        build[path] = truth_transform(text, states)
    bib, unknown = bib_text(ctx, pid, cites)
    build["refs.bib"] = bib
    if for_export:
        pass
    elif bib:
        build["refs.bib"] = bib
    else:                                  # no citation: no BibTeX run (it would stop on « no \citation »)
        build["main.tex"] = re.sub(r"(?m)^(\\bibliography(?:style)?\{[^}]*\})", r"% \1", build["main.tex"])
    build["madalean-generated.tex"] = generated_tex(ctx, files, states, s)
    for f in tp.figures(ctx, pid):
        build[f] = tp.root(ctx, pid) / f
    a = analyse(files, s)
    h = hashlib.sha256()
    for k in sorted(build):
        v = build[k]
        h.update(k.encode() + b"\0" + (v.encode() if isinstance(v, str) else v.name.encode()) + b"\0")
    h.update(json.dumps(states, sort_keys=True).encode())
    return build, s, {**a, "unknown_cites": unknown, "states": states}, h.hexdigest()[:20]


_COMPILING: dict[str, asyncio.Lock] = {}


async def compile_project(ctx, pid: str, *, online: bool = False, force: bool = False,
                          timeout: float = 240.0) -> dict:
    lk = _COMPILING.setdefault(pid, asyncio.Lock())
    async with lk:
        return await _compile(ctx, pid, online=online, force=force, timeout=timeout)


async def _compile(ctx, pid: str, *, online: bool, force: bool, timeout: float) -> dict:
    t0 = time.time()
    build, s, a, h = await asyncio.to_thread(prepare, ctx, pid)
    files = {k: v for k, v in build.items() if isinstance(v, str)}
    src = await asyncio.to_thread(tp.read_files, ctx, pid)
    base = {"hash": h, "packages": {k: a[k] for k in ("class", "packages", "needed", "redundant", "refused",
                                                      "engine", "digest")}, "states": a["states"]}
    await asyncio.to_thread(write_lock, ctx, pid, a)
    # 1. guard
    diags = []
    for path, text in src.items():
        for g in guard(text):
            diags.append(_d("error", path, g["line"], g["what"], "Construction refusée pour la sécurité ({what}) : "
                             "Madalean ne compile pas ce qui lit ou écrit des fichiers hors du projet, lance des "
                             "commandes ou reconstruit des noms de commandes.", None, what=g["what"]))
    for r in a["refused"]:
        diags.append(_d("error", r["path"], r["line"], r["name"], "Le paquet {name} a besoin d'exécuter des "
                         "programmes : refusé. {instead}", {"kind": "remove_package", "name": r["name"]},
                         name=r["name"], instead=("Utilisez plutôt " + r["instead"] + ".") if r["instead"] else ""))
    if diags:
        return {**base, "ok": False, "pdf": None, "diagnostics": diags, "seconds": round(time.time() - t0, 2),
                "engine": a["engine"], "cached": False}
    # 2. packages that cannot be satisfied
    for p in a["packages"] + a["needed"]:
        if p["state"] == "missing":
            w = (p.get("where") or [{}])[0] if "where" in p else p
            diags.append(_d("error", w.get("path", "main.tex"), w.get("line", 0), p["name"],
                            "« {name} » n'est ni dans le TeX de Madalean ni téléchargeable : il ne peut pas être "
                            "utilisé ici. Retirez-le ou choisissez une autre classe.",
                            {"kind": "remove_package", "name": p["name"]}, name=p["name"]))
    for p in a["needed"]:
        if p["state"] != "missing":
            diags.append(_d("warning", p["path"], p["line"], p["why"], "{why} demande le paquet {name}.",
                            {"kind": "add_package", "name": p["name"]}, why=p["why"], name=p["name"]))
    for r in a["redundant"]:
        key = {"twice": "Le paquet {name} est chargé deux fois.",
               "order": "cleveref doit être chargé après hyperref."}.get(r["reason"],
                                                                         "Le paquet {name} est déjà chargé par {by}.")
        diags.append(_d("info", r["path"], r["line"], r["name"], key, {"kind": "remove_package", "name": r["name"]}
                        if r["reason"] != "order" else None, name=r["name"], by=r["reason"].split(":")[-1]))
    for k in a["unknown_cites"]:
        p, ln = _find(src, k)
        diags.append(_d("warning", p, ln, k, "Citation {name} absente de la bibliothèque du projet.",
                        {"kind": "open_sources"}, name=k))
    if any(d["severity"] == "error" for d in diags):
        return {**base, "ok": False, "pdf": None, "diagnostics": diags, "seconds": round(time.time() - t0, 2),
                "engine": a["engine"], "cached": False}
    to_fetch = [p["file"] for p in a["packages"] if p["state"] == "bundle"] + \
               [p["name"] + ".sty" for p in a["needed"] if p["state"] == "bundle"]
    if to_fetch and not online:
        diags.insert(0, _d("error", "main.tex", 0, ", ".join(to_fetch),
                           "{n} fichier(s) du TeX de Madalean ne sont pas encore téléchargés ({files}) : "
                           "téléchargez-les une fois, ensuite tout marche hors ligne.",
                           {"kind": "fetch", "files": to_fetch}, n=len(to_fetch), files=", ".join(to_fetch[:6])))
        return {**base, "ok": False, "pdf": None, "diagnostics": diags, "seconds": round(time.time() - t0, 2),
                "engine": a["engine"], "cached": False}
    # 3. cache
    out_dir = build_dir(ctx, pid) / "out"
    last = last_result(ctx, pid)
    if not force and not online and last and last.get("hash") == h and last.get("ok") and \
            (out_dir / "main.pdf").is_file():
        return {**last, "cached": True, "seconds": round(time.time() - t0, 2),
                "diagnostics": diags + [x for x in last.get("diagnostics", []) if x["severity"] != "info"]}
    eng = engine_cmd(online)
    if eng is None:
        d = _d("error", "main.tex", 0, "no engine", "Le moteur TeX de Madalean (tectonic) n'est pas installé : "
                                                   "réparez « TeX » dans Système.", {"kind": "repair"})
        return {**base, "ok": False, "pdf": None, "diagnostics": [d], "seconds": 0, "engine": "none",
                "cached": False}
    cmd, engine = eng
    # 4. build directory (fresh)
    work = build_dir(ctx, pid) / "work"
    await asyncio.to_thread(shutil.rmtree, work, True)
    await asyncio.to_thread(work.mkdir, parents=True, exist_ok=True)

    def write_all():
        for rel, v in build.items():
            p = work / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(v, Path):
                try:
                    os.link(v, p)
                except OSError:
                    shutil.copyfile(v, p)
            else:
                p.write_text(v, encoding="utf-8")
    await asyncio.to_thread(write_all)
    rc, out = await run_tex(cmd + ["main.tex"], work, timeout, net=online)
    log = ""
    try:
        log = (work / "main.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    b = bundle()
    pdf_ok = rc == 0 and (work / "main.pdf").is_file()
    if rc is None:
        diags.append(_d("error", "main.tex", 0, "timeout", "La compilation a dépassé {s} s.", None, s=int(timeout)))
    else:
        diags += [x for x in parse_log(out, log, files, s, b) if pdf_ok is False or x["severity"] != "error"]
    res = {**base, "ok": pdf_ok, "engine": engine, "cached": False, "seconds": round(time.time() - t0, 2),
           "diagnostics": diags, "pdf": None, "t": time.time(), "ran": rc is not None}
    if online:
        a2 = await asyncio.to_thread(analyse, src, s)       # files now cached
        await asyncio.to_thread(write_lock, ctx, pid, a2)
        res["packages"] = {k: a2[k] for k in ("class", "packages", "needed", "redundant", "refused", "engine",
                                              "digest")}

    def keep():
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ("main.pdf", "main.synctex.gz", "main.synctex", "main.log"):
            src_f = work / name
            if src_f.is_file():
                shutil.copyfile(src_f, out_dir / (name + ".tmp"))
                os.replace(out_dir / (name + ".tmp"), out_dir / name)
            elif name != "main.log" and pdf_ok:
                (out_dir / name).unlink(missing_ok=True)
        (out_dir / "work-root").write_text(str(work), encoding="utf-8")
        config.atomic_write_text(out_dir / "result.json", json.dumps(res, ensure_ascii=False, default=str))
    if pdf_ok:
        res["pdf"] = h
        await asyncio.to_thread(keep)
    else:
        await asyncio.to_thread(lambda: (out_dir.mkdir(parents=True, exist_ok=True),
                                         (work / "main.log").is_file() and shutil.copyfile(work / "main.log",
                                                                                           out_dir / "main.log")))
    return res


async def trial_compile(ctx, pid: str, overrides: dict[str, str], timeout: float = 150.0) -> dict:
    """Compile the project with some source files replaced, in its own build directory, by the same engine and
    sandbox as `compile_project` (guard first, offline, no shell escape); nothing is kept: the author's PDF, log and
    cache stay as they are. → {ok, diagnostics, seconds, engine}. Session S-AN (D46): a fix proposed by the
    conductor is offered only when this compiles."""
    t0 = time.time()
    build, s, a, _h = await asyncio.to_thread(prepare, ctx, pid, False, overrides)
    files = {k: v for k, v in build.items() if isinstance(v, str)}
    diags = []
    for path, text in overrides.items():
        for g in guard(text):
            diags.append(_d("error", path, g["line"], g["what"], "Construction refusée pour la sécurité ({what}) : "
                             "Madalean ne compile pas ce qui lit ou écrit des fichiers hors du projet, lance des "
                             "commandes ou reconstruit des noms de commandes.", None, what=g["what"]))
    eng = engine_cmd(False)
    if diags or eng is None:
        return {"ok": False, "diagnostics": diags, "seconds": round(time.time() - t0, 2),
                "engine": eng[1] if eng else "none"}
    cmd, engine = eng
    work = build_dir(ctx, pid) / f"trial-{uuid.uuid4().hex[:10]}"

    def write_all():
        work.mkdir(parents=True, exist_ok=True)
        for rel, v in build.items():
            p = work / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(v, Path):
                try:
                    os.link(v, p)
                except OSError:
                    shutil.copyfile(v, p)
            else:
                p.write_text(v, encoding="utf-8")
    try:
        await asyncio.to_thread(write_all)
        rc, out = await run_tex(cmd + ["main.tex"], work, timeout)
        log = ""
        try:
            log = (work / "main.log").read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        ok = rc == 0 and (work / "main.pdf").is_file()
        if rc is None:
            diags.append(_d("error", "main.tex", 0, "timeout", "La compilation a dépassé {s} s.", None, s=int(timeout)))
        elif not ok:
            diags += parse_log(out, log, files, s, bundle())
        return {"ok": ok, "diagnostics": diags, "seconds": round(time.time() - t0, 2), "engine": engine}
    finally:
        await asyncio.to_thread(shutil.rmtree, work, True)


def pdf_path(ctx, pid: str) -> Path | None:
    p = build_dir(ctx, pid) / "out" / "main.pdf"
    return p if p.is_file() else None


# ================================================================ SyncTeX
SP_PER_BP = 65536 * 72.27 / 72


@functools.lru_cache(maxsize=8)
def _synctex(path: str, mtime: float) -> dict:
    p = Path(path)
    raw = gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
    inputs: dict[int, str] = {}
    unit, xoff, yoff = 1.0, 0.0, 0.0
    recs = []                     # (page, tag, line, x_bp, y_bp, w_bp, h_bp)
    page = 0
    rx = re.compile(r"^([\[\(vhxkg$])(\d+),(\d+)(?:,-?\d+)?:(-?\d+),(-?\d+)(?::(-?\d+),(-?\d+)(?:,(-?\d+))?)?")
    for ln in raw.decode("utf-8", "replace").split("\n"):
        if ln.startswith("Input:"):
            _, n, name = ln.split(":", 2)
            inputs[int(n)] = name
        elif ln.startswith("Unit:"):
            unit = float(ln[5:] or 1)
        elif ln.startswith("X Offset:"):
            xoff = float(ln[9:] or 0)
        elif ln.startswith("Y Offset:"):
            yoff = float(ln[9:] or 0)
        elif ln.startswith("{"):
            try:
                page = int(ln[1:])
            except ValueError:
                pass
        else:
            m = rx.match(ln)
            if m and page:
                f = unit / SP_PER_BP
                x = (int(m.group(4)) + xoff) * f            # xdv (XeLaTeX): offsets = 1in; tectonic: 0
                y = (int(m.group(5)) + yoff) * f
                w = int(m.group(6)) * f if m.group(6) else 0.0
                hgt = int(m.group(7)) * f if m.group(7) else 0.0
                recs.append((page, int(m.group(2)), int(m.group(3)), x, y, w, hgt, m.group(1)))
    return {"inputs": inputs, "recs": recs}


def _synctex_data(ctx, pid: str) -> tuple[dict, str] | None:
    out = build_dir(ctx, pid) / "out"
    for name in ("main.synctex.gz", "main.synctex"):
        p = out / name
        if p.is_file():
            try:
                work = (out / "work-root").read_text(encoding="utf-8").strip()
            except OSError:
                work = ""
            return _synctex(str(p), p.stat().st_mtime), work
    return None


def _rel(name: str, work: str) -> str:
    n = name
    if work and n.startswith(work):
        n = n[len(work):]
    n = re.sub(r"^(\./|/)+", "", n.replace("/./", "/"))
    return n if n.endswith(".tex") else n + ".tex"


def forward(ctx, pid: str, path: str, line: int) -> dict | None:
    """Source line → {page, x, y, w, h} (PDF points from the top-left) of the first box of that line or after."""
    got = _synctex_data(ctx, pid)
    if not got:
        return None
    data, work = got
    tags = [t for t, n in data["inputs"].items() if _rel(n, work) == path]
    if not tags:
        return None
    cands = [r for r in data["recs"] if r[1] in tags and r[2] >= line]
    if not cands:
        return None
    best = min(cands, key=lambda r: (r[2] - line, r[0], r[4]))
    same = [r for r in cands if r[2] == best[2] and r[0] == best[0]]
    x0 = min(r[3] for r in same)
    y0 = min(r[4] - r[6] for r in same)
    y1 = max(r[4] for r in same)
    x1 = max(r[3] + r[5] for r in same)
    return {"page": best[0], "x": round(x0, 1), "y": round(y0, 1), "w": round(max(x1 - x0, 20), 1),
            "h": round(max(y1 - y0, 10), 1), "line": best[2]}


def inverse(ctx, pid: str, page: int, x: float, y: float) -> dict | None:
    """PDF click (points from the top-left) → {path, line}."""
    got = _synctex_data(ctx, pid)
    if not got:
        return None
    data, work = got
    cands = [r for r in data["recs"] if r[0] == page and r[7] in "xkg$h"] or \
        [r for r in data["recs"] if r[0] == page]
    if not cands:
        return None

    def dist(r):
        dy = 0 if r[4] - max(r[6], 8) <= y <= r[4] + 2 else min(abs(y - r[4]), abs(y - (r[4] - r[6])))
        dx = 0 if r[3] <= x <= r[3] + max(r[5], 1) else min(abs(x - r[3]), abs(x - r[3] - r[5]))
        return dy * 4 + dx
    best = min(cands, key=dist)
    return {"path": _rel(data["inputs"].get(best[1], "main.tex"), work), "line": best[2]}


# ================================================================ exports for article.export (v1 routes)
def flatten(build: dict) -> str:
    """main.tex with the section files inlined (single-file .tex export)."""
    main = build["main.tex"]

    def inline(m):
        p = m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex"
        v = build.get(p)
        return v if isinstance(v, str) else m.group(0)
    main = re.sub(r"\\input\{(sections/[^}]+)\}", inline, main)
    gen = build.get("madalean-generated.tex", "")
    return main.replace(r"\InputIfFileExists{madalean-generated}{}{}", gen)


async def export_compat(ctx, pid: str, fmt: str) -> tuple[str, str, bytes, str]:
    from ..dossiers import slugify
    from . import overleaf
    p = ctx.projects.get(pid)
    name = slugify((p.title if p else "") or "article", 40)
    if fmt == "pdf":
        res = await compile_project(ctx, pid)
        pdfp = pdf_path(ctx, pid)
        if res["ok"] and pdfp is not None:
            return f"{name}.pdf", "application/pdf", await asyncio.to_thread(pdfp.read_bytes), ""
        from .. import texio
        build, _s, _a, _h = await asyncio.to_thread(prepare, ctx, pid)
        page = texio.markdown_to_html(tp.latex_to_markdown(flatten(build)))
        html = f'<!doctype html><html><head><meta charset="utf-8"><title>{name}</title></head><body>{page}</body></html>'
        return f"{name}.html", "text/html; charset=utf-8", html.encode(), "html"
    build, _s, _a, _h = await asyncio.to_thread(prepare, ctx, pid)
    if fmt == "tex":
        return f"{name}.tex", "application/x-tex; charset=utf-8", flatten(build).encode(), ""
    if fmt == "md":
        body = re.search(r"(?s)\\begin\{document\}(.*)\\end\{document\}", flatten(build))
        return f"{name}.md", "text/markdown; charset=utf-8", \
            tp.latex_to_markdown(body.group(1) if body else "").encode(), ""
    data = await asyncio.to_thread(overleaf.export_zip, ctx, pid)
    res = await compile_project(ctx, pid)
    pdfp = pdf_path(ctx, pid)
    if res["ok"] and pdfp is not None:
        import io
        import zipfile
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{name}.pdf", await asyncio.to_thread(pdfp.read_bytes))
        data = buf.getvalue()
    return f"{name}.zip", "application/zip", data, ""
