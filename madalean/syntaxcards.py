"""Version-aware syntax catalogue for the models that write code (session S-AB, DECISIONS D35).

One compact « syntax card » per tool AND installed version — SageMath (Calcul) and Lean 4 / Mathlib (provers) — whose
every entry was CHECKED against the installed version: each entry carries a snippet that is run (Sage) or compiled
(Lean) during a build step; an entry whose snippet fails (or, for Lean, raises a deprecation warning) is dropped. The
card is small (≈ 1–2 k tokens), stable for a given version (so it sits at the start of the system prompt, where
prompt caching works: Anthropic `cache_control`, Gemini / OpenAI implicit prefix caching), and rebuilt automatically
when the version changes (server start, the update checkers' pass, a Mathlib / Lake update applied).

Sage, besides the card:
- `sage_names`: every public name of `sage.all` for the installed version (the validator flags names that exist
  neither in Sage, in Python's builtins, in the cell nor in the kernel);
- `sage_signatures`: exact signature + first docstring paragraph of the functions a request needs (introspection of
  the installed Sage, cached per version), chosen from the request's words (FR/EN) and from the code to repair;
- `validate_sage(code)`: the installed Sage's own preparser + Python's compiler (the code is never executed), plus
  undefined names — the fast loop of the Calcul screen gives the error back to the model once before showing code.

Lean: the card's names are checked against the workspace's declaration index (madalean/names.py, not duplicated) and
compiled with the workspace's Lean (`ctx.lean.check`). Stored in `<cache>/syntax/` (`sage-<version>.json`,
`lean-<hash>.json`); nothing here sends anything anywhere."""
from __future__ import annotations

import asyncio
import builtins
import difflib
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from . import config
from .logs import get

log = get("syntax")
CARD_VERSION = 1                       # bump when the entries change: every cached card is rebuilt
_DIR: dict = {"path": Path.home() / ".cache" / "madalean" / "syntax"}
_MEM: dict[str, tuple[float, object]] = {}
_LOCK = threading.Lock()
_BUILDING: set[str] = set()


def configure(cache_dir: Path) -> None:
    """The server's cache directory (ctx.paths.cache); default ~/.cache/madalean/syntax."""
    _DIR["path"] = Path(cache_dir).resolve() / "syntax"


def cache_dir() -> Path:
    return _DIR["path"]


# ================================================================ SageMath entries
# (id, rule shown to the model, snippet run by the installed Sage; `assert` lines check the documented behaviour)
SAGE_ENTRIES: list[tuple[str, str, str]] = [
    ("var", "`x` is the only predefined symbolic variable; declare others with `n, k = var('n k')` (a Python loop "
            "variable is an int, not a symbol).",
     "n, k = var('n k')\nassert ((n + k)^2).expand() == n^2 + 2*n*k + k^2"),
    ("pow", "`^` is the power in Sage code (preparsed to `**`); `a^b` in plain Python would be XOR.",
     "assert 2^10 == 1024"),
    ("exact", "Arithmetic is exact: `1/3` is a rational, `sqrt(2)` symbolic; numbers: `N(e, digits=20)` or "
              "`e.n()`; `RR`, `RDF` are real fields.",
     "assert 1/3 == QQ((1, 3))\nassert abs(N(pi, digits=20) - 3.14159265358979323846) < 1e-15"),
    ("func", "Callable symbolic function: `f(x) = x^2*sin(x)` then `f(2)`, `f.diff(x)`; an expression "
             "`g = x^2` is evaluated with `g(x=2)` or `g.subs(x=2)`.",
     "f(x) = x^2*sin(x)\nassert f(0) == 0\ng = x^2\nassert g(x=3) == 9 and g.subs(x=2) == 4"),
    ("integral", "`integral` and `integrate` are the same: `integral(f, x)`, `integral(f, x, a, b)` or "
                 "`integrate(f, (x, a, b))`; numeric: `numerical_integral(f, a, b)` → (value, error).",
     "assert integral(x^2, x, 0, 1) == 1/3\nassert integrate(x^2, (x, 0, 1)) == 1/3\n"
     "assert abs(numerical_integral(sin(x), 0, pi)[0] - 2) < 1e-9"),
    ("assume", "Parameters: `assume(n, 'integer')`, `assume(n > 0)` before integrating/simplifying with them; "
               "`forget()` clears every assumption (assumptions persist in the kernel).",
     "n = var('n')\nassume(n, 'integer')\nassume(n > 0)\n"
     "r = integral(x^2*cos(n*x), x, 0, 2*pi)\nassert bool(r == 4*pi/n^2)\nforget()"),
    ("sum", "Symbolic sum: `sum(k^2, k, 1, n)` (k = var('k')); keep it unevaluated with `sum(..., hold=True)`; "
            "numbers: Python `sum([...])` or `sum(f(k) for k in range(1, 11))`.",
     "k, n = var('k n')\nassert bool(sum(k^2, k, 1, n) == n*(n + 1)*(2*n + 1)/6)\n"
     "s = sum(k, k, 1, n, hold=True)\nassert 'sum' in str(s)\nassert sum(j^2 for j in range(1, 4)) == 14"),
    ("fourier", "Fourier series: the general coefficients come from integrals with a symbolic integer "
                "(`n = var('n'); assume(n, 'integer'); assume(n > 0)`); with `f = piecewise([((0, 2*pi), x^2)])`: "
                "`f.fourier_series_cosine_coefficient(k, L)` / `f.fourier_series_sine_coefficient(k, L)` for a "
                "given k, and `f.fourier_series_partial_sum(N, L)` with a FINITE N (half-period L, here pi).",
     "f = piecewise([((0, 2*pi), x^2)])\nS = f.fourier_series_partial_sum(3, pi)\n"
     "assert bool(f.fourier_series_cosine_coefficient(0, pi) == 8*pi^2/3)\n"
     "assert bool(f.fourier_series_cosine_coefficient(1, pi) == 4)"),
    ("limit", "`limit(sin(x)/x, x=0)`; one side: `limit(1/x, x=0, dir='+')`.",
     "assert limit(sin(x)/x, x=0) == 1\nassert limit(1/x, x=0, dir='+') == Infinity"),
    ("taylor", "Expansions: `taylor(exp(x), x, 0, 5)` (polynomial), `exp(x).series(x, 6)` (with O-term).",
     "t = taylor(exp(x), x, 0, 3)\nassert bool(t == 1 + x + x^2/2 + x^3/6)\ns = exp(x).series(x, 4)\n"
     "assert bool(s.truncate() == t)"),
    ("diff", "Derivatives: `diff(f, x)`, `diff(f, x, 2)`, `f.derivative(x)`; partials `diff(f, y)` after "
             "`y = var('y')`.",
     "y = var('y')\nassert diff(x^3, x, 2) == 6*x\nassert diff(x*y^2, y) == 2*x*y"),
    ("solve", "Equations use `==`: `solve(x^2 - 2 == 0, x)`; systems `solve([eq1, eq2], x, y)`; numeric root "
              "`find_root(cos(x) - x, 0, 1)`.",
     "S = solve(x^2 - 2 == 0, x)\nassert len(S) == 2\nr = find_root(cos(x) - x, 0, 1)\n"
     "assert abs(r - 0.739085133) < 1e-6"),
    ("simplify", "Simplify: `expand()`, `factor()`, `simplify_full()`, `trig_reduce()`, `canonicalize_radical()`; "
                 "test identities with `bool(a == b)`.",
     "assert bool((sin(x)^2 + cos(x)^2).simplify_full() == 1)\nassert factor(x^2 - 1) == (x - 1)*(x + 1)"),
    ("poly", "Polynomial rings: `R.<t> = PolynomialRing(QQ)` (or `QQ['t']`); over Z[i]: "
             "`R.<t> = PolynomialRing(ZZ[I])`; `p.factor()`, `p.roots()`.",
     "R.<t> = PolynomialRing(QQ)\nassert len((t^4 + 4).factor()) == 2\nS.<u> = PolynomialRing(ZZ[I])\n"
     "assert len((u^4 + 4).factor()) == 4"),
    ("ode", "ODE: `y = function('y')(x)`; `desolve(diff(y, x) + y == 1, y)`; with an initial condition "
            "`ics=[0, 2]`.",
     "y = function('y')(x)\ns = desolve(diff(y, x) + y == 1, y, ics=[0, 2])\nassert bool(s == 1 + e^(-x))"),
    ("matrix", "Linear algebra: `matrix(QQ, [[1, 2], [3, 4]])`, `.det()`, `.inverse()`, `.eigenvalues()`, "
               "`.charpoly()`, `vector([1, 2])`, `A.solve_right(b)` solves A·x = b.",
     "A = matrix(QQ, [[1, 2], [3, 4]])\nassert A.det() == -2\nb = vector(QQ, [1, 1])\n"
     "assert A * A.solve_right(b) == b\nassert len(A.eigenvalues()) == 2"),
    ("nt", "Number theory: `factor(2024)`, `is_prime(n)`, `next_prime`, `euler_phi`, `gcd`, `xgcd`, "
           "`Mod(3, 7)^-1`, `primes(a, b)` (iterator), `prime_range(a, b)` (list), `divisors(n)`.",
     "assert str(factor(2024)) == '2^3 * 11 * 23'\nassert Mod(3, 7)^-1 == 5\nassert prime_range(10) == [2, 3, 5, 7]\n"
     "assert euler_phi(10) == 4"),
    ("ranges", "`range` gives Python ints; `srange(a, b, step)` and `[a..b]` give Sage numbers (exact steps: "
               "`srange(0, 5.5, 0.5)`).",
     "assert [1..4] == [1, 2, 3, 4]\nassert len(srange(0, 5.5, 0.5)) == 11"),
    ("plot", "Plots: make the Graphics object the LAST expression (it is displayed; no `show()` needed); "
             "`plot(f, (x, a, b), color=..., legend_label='$...$')`; several: `p1 + p2` or "
             "`sum(plot(...) for r in ...)`; `plot([f, g], (x, 0, 1))`.",
     "p = plot(sin(x), (x, 0, pi), legend_label='$\\\\sin$') + plot(cos(x), (x, 0, pi), color='red')\n"
     "assert isinstance(p, sage.plot.graphics.Graphics)\nq = sum(plot(r*x*(1 - x), (x, 0, 1)) for r in range(3))\n"
     "assert isinstance(q, sage.plot.graphics.Graphics)"),
    ("plot2", "Other plots: `implicit_plot(x^2 + y^2 == 4, (x, -3, 3), (y, -3, 3))` (declare y), "
              "`parametric_plot((cos(t), sin(t)), (t, 0, 2*pi))`, `polar_plot(1 + cos(t), (t, 0, 2*pi))`, "
              "`list_plot(data)`, `plot3d(f, (x, -1, 1), (y, -1, 1))`.",
     "y, t = var('y t')\nimplicit_plot(x^2 + y^2 == 4, (x, -3, 3), (y, -3, 3))\n"
     "parametric_plot((cos(t), sin(t)), (t, 0, 2*pi))\npolar_plot(1 + cos(t), (t, 0, 2*pi))\n"
     "list_plot([1, 4, 9])"),
    ("latex", "LaTeX: `latex(expr)` gives the source; Madalean's `tex(expr)` displays a formula; `show(expr)` "
              "displays it too.",
     "assert latex(x^2) == 'x^{2}'\nassert latex(sqrt(2)) == '\\\\sqrt{2}'"),
    ("graphs", "Graphs: `graphs.PetersenGraph()`, `Graph({0: [1, 2]})`, `G.chromatic_number()`, "
               "`G.is_planar()`, `G.plot()`.",
     "G = graphs.PetersenGraph()\nassert G.chromatic_number() == 3 and not G.is_planar()"),
    ("print", "Several results: `print(...)` each, or return a tuple; `show(...)` for formulas and plots in a loop.",
     "a, b = 1, 2\n(a, b)"),
]

# request words (FR / EN) → Sage functions whose exact signatures are worth sending to the model
SAGE_TOPICS: list[tuple[str, tuple[str, ...]]] = [
    (r"fourier", ("piecewise", "PiecewiseFunction.fourier_series_partial_sum",
                  "PiecewiseFunction.fourier_series_cosine_coefficient",
                  "PiecewiseFunction.fourier_series_sine_coefficient")),
    (r"int[ée]gr|integra|primitive|antideriv", ("integral", "numerical_integral")),
    (r"\bsomme|\bsum|s[ée]rie|series", ("sum", "Expression.series")),
    (r"limite|\blimit", ("limit",)),
    (r"taylor|d[ée]veloppement|expansion", ("taylor", "Expression.series")),
    (r"d[ée]riv|deriv|diff[ée]renti", ("diff",)),
    (r"[ée]quation diff|ode\b|desolve|differential equation", ("desolve", "function")),
    (r"r[ée]sou|solve|racine|root|z[ée]ro", ("solve", "find_root")),
    (r"factori|factor", ("factor",)),
    (r"matri|d[ée]terminant|eigen|valeurs? propres?|vecteur|vector", ("matrix", "vector")),
    (r"trace|courbe|graphique|plot|dessin|draw", ("plot", "Graphics.show")),
    (r"implicite|implicit", ("implicit_plot",)),
    (r"param[ée]tr", ("parametric_plot",)),
    (r"polaire|polar", ("polar_plot",)),
    (r"3d|surface", ("plot3d",)),
    (r"premier|prime", ("is_prime", "prime_range", "primes")),
    (r"graphe|graph\b|petersen|chromati", ("Graph", "Graph.chromatic_number")),
    (r"simplifi|simplify", ("Expression.simplify_full",)),
    (r"polyn[ôo]m|polynomial", ("PolynomialRing",)),
    (r"suppos|assum|entier|integer", ("assume",)),
]
SIG_PATHS = {   # dotted names that are not global: where to find them in `sage.all`'s namespace
    "PiecewiseFunction": "sage.functions.piecewise.PiecewiseFunction.EvaluationMethods",
    "Expression": "sage.symbolic.expression.Expression",
    "Graphics": "sage.plot.graphics.Graphics",
    "Graph": "sage.graphs.graph.Graph",
}
MAX_SIGS = 6

# Python helper run by the installed Sage's interpreter: builds the card (runs each snippet), the name index and the
# signatures. Reads {entries, sigs} on stdin, writes one JSON line. Madalean's own static snippets only.
_SAGE_BUILD = r'''
import json, sys, signal, io, contextlib, importlib
req = json.loads(sys.stdin.read())
from sage.all import *
import sage.all, sage.version
from sage.repl.preparse import preparse_file
from sage.misc.sageinspect import sage_getargspec, sage_getdoc
out = {"version": sage.version.version, "entries": {}, "names": [], "sigs": {}}
def _alarm(*a):
    raise TimeoutError("snippet timeout")
signal.signal(signal.SIGALRM, _alarm)
base = dict(sage.all.__dict__)
base["x"] = SR.var("x")
for eid, code in req["entries"]:
    ns = dict(base)
    signal.alarm(int(req.get("timeout", 60)))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(preparse_file(code), "<" + eid + ">", "exec"), ns)
        out["entries"][eid] = ""
    except BaseException as e:
        out["entries"][eid] = (type(e).__name__ + ": " + str(e))[:300]
    finally:
        signal.alarm(0)
    try:
        forget()
    except Exception:
        pass
out["names"] = sorted(n for n in dir(sage.all) if not n.startswith("_"))
def _resolve(name):
    head, _, rest = name.partition(".")
    if rest and head in req["paths"]:
        parts = req["paths"][head].split(".")
        for i in range(len(parts), 0, -1):
            try:
                obj = importlib.import_module(".".join(parts[:i]))
            except ImportError:
                continue
            for a in parts[i:]:
                obj = getattr(obj, a)
            return getattr(obj, rest)
        raise ImportError(name)
    return getattr(sage.all, name)
for name in req["sigs"]:
    try:
        obj = _resolve(name)
        try:
            spec = sage_getargspec(obj)
            args = list(spec.args or [])
            dflt = list(spec.defaults or [])
            parts = []
            for i, a in enumerate(args):
                j = i - (len(args) - len(dflt))
                parts.append(a + ("=" + repr(dflt[j]) if j >= 0 else ""))
            if spec.varargs: parts.append("*" + spec.varargs)
            if spec.varkw: parts.append("**" + spec.varkw)
            skip = ("self", "parameters", "variable") if name.startswith("PiecewiseFunction.") else ("self",)
            sig = "(" + ", ".join(p for p in parts if p not in skip) + ")"
            if len(sig) > 200:
                sig = sig[:196] + ", …)"
        except Exception:
            sig = "(...)"
        doc = (sage_getdoc(obj) or "").strip()
        para = doc.split("\n\n")[0].replace("\n", " ").strip()
        ex = ""
        i = doc.find("sage: ")
        if i >= 0:
            ex = " ".join(l.strip()[6:] for l in doc[i:].splitlines()[:6] if l.strip().startswith("sage: "))[:240]
        out["sigs"][name] = {"sig": name.split(".")[-1] + sig, "doc": para[:300], "example": ex}
    except Exception as e:
        out["sigs"][name] = {"error": type(e).__name__}
print("MADALEAN_SYNTAX " + json.dumps(out))
'''

# validator: the installed Sage's preparser + compile (never executes the code); names loaded / stored
_SAGE_CHECK = r'''
import ast, json, sys
from sage.repl.preparse import preparse_file
code = sys.stdin.read()
res = {"ok": True, "error": "", "line": 0, "loads": [], "stores": []}
try:
    py = preparse_file(code)
    tree = ast.parse(py)
    compile(tree, "<cell>", "exec")
    loads, stores = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            (loads if isinstance(n.ctx, ast.Load) else stores).add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            stores.add(n.name)
            stores.update(a.arg for a in n.args.args + n.args.kwonlyargs) if hasattr(n, "args") else None
        elif isinstance(n, ast.Lambda):
            stores.update(a.arg for a in n.args.args)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            stores.update((a.asname or a.name).split(".")[0] for a in n.names)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            stores.add(n.name)
        elif isinstance(n, ast.arg):
            stores.add(n.arg)
    res["loads"], res["stores"] = sorted(loads), sorted(stores)
except SyntaxError as e:
    res.update(ok=False, error="SyntaxError: %s (line %s)" % (e.msg, e.lineno), line=e.lineno or 0)
except Exception as e:
    res.update(ok=False, error="%s: %s" % (type(e).__name__, e))
print("MADALEAN_CHECK " + json.dumps(res))
'''


# ================================================================ Sage: interpreter and version
def sage_python() -> str | None:
    """The interpreter of the Sage that Calcul's kernels use (Madalean's own Sage env first, else the system one)."""
    from .research.sagebridge import find_kernelspec
    spec = find_kernelspec("sagemath")
    if not spec:
        return None
    exe = spec["argv"][0]
    return exe if os.path.exists(exe) else None


def _run(argv: list[str], stdin: str, timeout: float, env: dict | None = None) -> str:
    try:
        p = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        log.info("syntax helper failed: %s", e)
        return ""
    return p.stdout


def _sage_env(work: Path) -> dict:
    """Snippets run with their own Sage / Maxima directories (never the user's ~/.sage, never /nonexistent)."""
    keep = {k: v for k, v in os.environ.items()
            if k in ("PATH", "LANG", "LC_ALL", "TZ", "TERM", "USER", "LOGNAME", "HOME")}
    work.mkdir(parents=True, exist_ok=True)
    # HOME stays (GAP's startup reads it: with an empty HOME its banner breaks libgap's kernel_info on Sage 10.10)
    return {**keep, "DOT_SAGE": str(work / ".sage"),
            "MAXIMA_USERDIR": str(work / ".sage" / "maxima"), "MPLCONFIGDIR": str(work / ".mpl"),
            "PYTHONUNBUFFERED": "1"}


def sage_version(py: str | None = None) -> str:
    """Version of the installed Sage, read at runtime (cached 10 min per interpreter)."""
    py = py or sage_python()
    if not py:
        return ""
    k = f"ver:{py}"
    hit = _MEM.get(k)
    if hit and time.monotonic() - hit[0] < 600:
        return str(hit[1])
    out = _run([py, "-I", "-c", "import sage.version as v; print(v.version)"], "", 30)
    v = out.strip().splitlines()[-1] if out.strip() else ""
    if not re.fullmatch(r"[\w.+-]{1,40}", v):
        v = ""
    _MEM[k] = (time.monotonic(), v)
    return v


def _sage_file(version: str) -> Path:
    return cache_dir() / f"sage-{re.sub(r'[^\w.+-]', '_', version)}.json"


def _all_sig_names() -> list[str]:
    seen: list[str] = []
    for _rx, names in SAGE_TOPICS:
        for n in names:
            if n not in seen:
                seen.append(n)
    return seen


def build_sage(py: str | None = None, timeout: float = 600) -> dict | None:
    """Run every entry's snippet with the installed Sage, keep those that pass; index names and signatures.
    Blocking (minutes at most): call from a thread."""
    py = py or sage_python()
    if not py:
        return None
    version = sage_version(py)
    if not version:
        return None
    work = cache_dir() / "work"
    req = {"entries": [[e[0], e[2]] for e in SAGE_ENTRIES], "sigs": _all_sig_names(), "paths": SIG_PATHS,
           "timeout": 60}
    t0 = time.monotonic()
    out = _run([py, "-I", "-c", _SAGE_BUILD], json.dumps(req), timeout, env=_sage_env(work))
    m = re.search(r"^MADALEAN_SYNTAX (\{.*\})\s*$", out, re.M)
    if not m:
        log.warning("Sage syntax card: build produced no result")
        return None
    raw = json.loads(m.group(1))
    failed = {k: v for k, v in raw["entries"].items() if v}
    card = {"tool": "sage", "version": raw["version"], "card_version": CARD_VERSION, "built": time.time(),
            "seconds": round(time.monotonic() - t0, 1),
            "entries": [{"id": e[0], "text": e[1]} for e in SAGE_ENTRIES if raw["entries"].get(e[0]) == ""],
            "dropped": failed, "names": raw["names"], "sigs": raw["sigs"]}
    f = _sage_file(raw["version"])
    f.parent.mkdir(parents=True, exist_ok=True)
    config.atomic_write_text(f, json.dumps(card, ensure_ascii=False))
    _MEM.pop(f"sage:{raw['version']}", None)
    if failed:
        log.info("Sage %s syntax card: %d entries dropped (%s)", raw["version"], len(failed), ", ".join(failed))
    return card


def sage_card_data(version: str | None = None) -> dict | None:
    """The verified card of the installed Sage version (None while it is not built)."""
    version = version if version is not None else sage_version()
    if not version:
        return None
    k = f"sage:{version}"
    hit = _MEM.get(k)
    if hit and time.monotonic() - hit[0] < 300:
        return hit[1]  # type: ignore[return-value]
    try:
        d = json.loads(_sage_file(version).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = None
    if d is not None and (d.get("card_version") != CARD_VERSION or d.get("version") != version):
        d = None
    if d is not None:
        _MEM[k] = (time.monotonic(), d)
        if len(_MEM) > 32:
            _MEM.clear()
    return d


def sage_card(version: str | None = None) -> tuple[str, bool]:
    """(card text, verified). Without a built card for this version: the built-in entries, marked unverified (and a
    build should be scheduled by the caller: `schedule_sage`)."""
    version = version if version is not None else sage_version()
    d = sage_card_data(version)
    if d is not None:
        lines = [f"SageMath {d['version']} — idioms checked on this installation:"]
        lines += [f"- {e['text']}" for e in d["entries"]]
        return "\n".join(lines), True
    lines = [f"SageMath {version or '10'} — usual idioms:"] + [f"- {e[1]}" for e in SAGE_ENTRIES]
    return "\n".join(lines), False


def sage_signatures(text: str, code: str = "", version: str | None = None, limit: int = MAX_SIGS) -> str:
    """Exact signatures (installed Sage) of the functions the request / the code to repair needs."""
    d = sage_card_data(version)
    if not d:
        return ""
    sigs = d.get("sigs") or {}
    want: list[str] = []
    low = (text or "").lower()
    for rx, names in SAGE_TOPICS:
        if re.search(rx, low):
            want += [n for n in names if n not in want]
    if code:
        used = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", code)) | set(re.findall(r"\.(\w+)\s*\(", code))
        for n in sigs:
            if n.split(".")[-1] in used and n not in want:
                want.append(n)
    out = []
    for n in want:
        s = sigs.get(n) or {}
        if not s.get("sig"):
            continue
        out.append(f"- {s['sig']}: {s.get('doc', '')}" + (f" e.g. {s['example']}" if s.get("example") else ""))
        if len(out) >= limit:
            break
    return "\n".join(out)


HELPERS = {"x", "tex", "fig", "report", "show", "_", "__", "___", "In", "Out", "_madalean_vars", "_madalean_approx",
           "_madalean_latex", "display", "get_ipython", "exit", "quit"}


def validate_sage(code: str, known: set[str] | None = None, version: str | None = None,
                  py: str | None = None) -> dict:
    """{ok, error, unknown: [names]} — the installed Sage's preparser + compile, then names defined nowhere
    (Sage, builtins, the cell, the kernel/earlier cells `known`). Never executes the code. ≈ 0.1 s."""
    py = py or sage_python()
    if not py:
        return {"ok": True, "error": "", "unknown": [], "checked": False}
    out = _run([py, "-I", "-c", _SAGE_CHECK], code, 20, env=_sage_env(cache_dir() / "work"))
    m = re.search(r"^MADALEAN_CHECK (\{.*\})\s*$", out, re.M)
    if not m:
        return {"ok": True, "error": "", "unknown": [], "checked": False}
    r = json.loads(m.group(1))
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "unknown": [], "checked": True}
    d = sage_card_data(version)
    unknown: list[str] = []
    if d and d.get("names"):
        names = set(d["names"])
        defined = set(r["stores"]) | set(known or ()) | HELPERS | set(dir(builtins))
        unknown = [n for n in r["loads"] if n not in names and n not in defined and not n.startswith("_")]
    if unknown:
        hints = []
        for n in unknown[:4]:
            close = difflib.get_close_matches(n, d["names"], 3, 0.75)
            hints.append(f"`{n}`" + (f" (close Sage names: {', '.join(close)})" if close else ""))
        return {"ok": False, "error": f"NameError: not defined in SageMath {d['version']} nor in the notebook: "
                                      + "; ".join(hints), "unknown": unknown, "checked": True}
    return {"ok": True, "error": "", "unknown": [], "checked": True}


def validate_python(code: str) -> dict:
    try:
        compile(code, "<cell>", "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError: {e.msg} (line {e.lineno})", "unknown": [], "checked": True}
    except (ValueError, TypeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "unknown": [], "checked": True}
    return {"ok": True, "error": "", "unknown": [], "checked": True}


# ================================================================ Lean 4 / Mathlib entries
# (id, rule, snippet compiled after leancheck.GOEDEL_HEADER, Mathlib names the rule cites — checked in the index)
LEAN_ENTRIES: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("lean4", "Lean 4 only: `theorem t (n : ℕ) : n + 0 = n := by simp` — no Lean 3 `begin … end`, no `assume`, "
              "no `λ x,` (write `fun x => …` or `fun x ↦ …`), no `at h ⊢,` commas between tactics (new lines).",
     "theorem syntax_card_t (n : ℕ) : n + 0 = n := by simp\nexample : (fun x : ℕ => x + 1) 1 = 2 := rfl", ()),
    ("names", "Mathlib 4 names: types and namespaces UpperCamelCase (`Nat`, `Finset`, `Real`), lemmas snake_case "
              "with dotted namespace (`Nat.succ_le_iff`, `Finset.sum_range_succ`); Lean 3 `nat.succ_le_iff` is gone.",
     "#check Nat.succ_le_iff\n#check Finset.sum_range_succ", ("Nat.succ_le_iff", "Finset.sum_range_succ")),
    ("bigop", "Big operators: `∑ i ∈ Finset.range n, f i` and `∏ i ∈ s, f i` (`∈`, not the old `in`).",
     "example (n : ℕ) : ∑ i ∈ Finset.range (n + 1), i = ∑ i ∈ Finset.range n, i + n :=\n"
     "  Finset.sum_range_succ _ _", ("Finset.sum_range_succ",)),
    ("bigop_in", "Big operators (this Mathlib): `∑ i in Finset.range n, f i` and `∏ i in s, f i`.",
     "example (n : ℕ) : ∑ i in Finset.range (n + 1), i = ∑ i in Finset.range n, i + n :=\n"
     "  Finset.sum_range_succ _ _", ("Finset.sum_range_succ",)),
    ("destruct", "Hypotheses: `obtain ⟨k, hk⟩ := h`, `rcases h with ⟨x, rfl⟩ | h2`, `cases h with | inl h => … "
                 "| inr h => …`; goals: `constructor`, `refine ⟨_, ?_⟩`, `use 2`, `exists`.",
     "example (a : ℕ) (h : ∃ k, a = 2 * k) : Even a := by\n  obtain ⟨k, hk⟩ := h\n  exact ⟨k, by omega⟩", ()),
    ("induction", "Induction: `induction n with\\n  | zero => simp\\n  | succ n ih => …`.",
     "example (n : ℕ) : 0 + n = n := by\n  induction n with\n  | zero => rfl\n  | succ n ih => omega", ()),
    ("auto", "Closing tactics: `simp`, `norm_num`, `ring`, `linarith`, `nlinarith [sq_nonneg (a - b)]`, "
             "`positivity`, `omega` (ℕ/ℤ linear), `decide`, `field_simp`, `gcongr`, `aesop`.",
     "example (a b : ℝ) : 0 ≤ (a - b) ^ 2 := by positivity\n"
     "example (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2 := by nlinarith [sq_nonneg (a - b)]\n"
     "example (n : ℕ) (h : n < 3) : n ≤ 2 := by omega", ("sq_nonneg",)),
    ("cast", "Coercions: `(n : ℝ)`, `push_cast`, `exact_mod_cast`, `Nat.cast_le`; ℕ subtraction truncates "
             "(`5 - 7 = 0`): prefer `omega` or work in ℤ.",
     "example (n : ℕ) (h : 2 ≤ n) : (2 : ℝ) ≤ n := by exact_mod_cast h\nexample : (5 : ℕ) - 7 = 0 := by norm_num",
     ("Nat.cast_le",)),
    ("calc", "`calc a = b := by ring\\n  _ ≤ c := by linarith` (each step on its own line, `_` for the previous "
             "right-hand side).",
     "example (a b : ℝ) (h : b ≤ 1) : a + b ≤ a + 1 := by\n  calc a + b ≤ a + 1 := by linarith", ()),
    ("contra", "`by_contra h`, `push_neg at h`, `by_cases h : p`, `exfalso`, `absurd`.",
     "example (p : Prop) [Decidable p] : p ∨ ¬p := by\n  by_cases h : p\n  · exact Or.inl h\n  · exact Or.inr h", ()),
    ("preds", "Predicates: `Nat.Prime p` (`p.Prime`), `Even n`, `Odd n`, `n ∣ m`, `Function.Injective f`, "
              "`Set` builder `{x | p x}`, `Finset.card s` (`#s`).",
     "example : Nat.Prime 7 := by norm_num\nexample : Even 4 := ⟨2, rfl⟩\nexample : (3 : ℕ) ∣ 12 := ⟨4, rfl⟩",
     ("Nat.Prime",)),
    ("real", "Reals: `Real.sqrt x` (`√x`), `Real.pi` (`π` after `open Real`; ambiguous with `Nat` open: write `Real.pi`), `Real.exp`, `Real.log`, "
             "`|x|` for `abs`; `deriv f x`, `∫ x in a..b, f x`.",
     "example : Real.sqrt 4 = 2 := by\n  rw [show (4 : ℝ) = 2 ^ 2 by norm_num, Real.sqrt_sq (by norm_num)]\n"
     "example : (0 : ℝ) < Real.pi := Real.pi_pos\n#check (∫ x in (0 : ℝ)..1, x)",
     ("Real.sqrt_sq", "Real.pi_pos")),
]


def lean_key(ws) -> str:
    """Toolchain + Mathlib revision of a workspace (the card is rebuilt when either changes)."""
    from .runtime.lean import workspace_info
    info = workspace_info(ws) or {}
    raw = f"{ws.key}|{getattr(ws, 'toolchain', '')}|{info.get('mathlib', '')}|{CARD_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _lean_file(ws) -> Path:
    return cache_dir() / f"lean-{lean_key(ws)}.json"


def _indexed(idx, name: str) -> bool:
    """In the workspace's declaration index (names.py). Its light parser does not expand `@[to_additive]`: an
    additive name counts when its multiplicative source is there (`Finset.sum_range_succ` ← `prod_range_succ`)."""
    if name in idx:
        return True
    return any(name.replace(a, m) in idx for a, m in (("sum", "prod"), ("add", "mul"), ("zero", "one"),
                                                         ("neg", "inv"), ("sub", "div")) if a in name)


async def build_lean(ctx, ws) -> dict | None:
    """Compile every entry with the workspace's Lean (one file, one check), keep those without error or
    deprecation warning and whose cited names exist in the workspace's declaration index (madalean/names.py)."""
    from . import leancheck, names as names_mod
    from .runtime.lean import workspace_info
    if ws is None or not ws.has_mathlib():
        return None
    idx = await asyncio.to_thread(names_mod.get, ws, True)
    header = leancheck.GOEDEL_HEADER
    body, spans = header, []
    for eid, _text, code, cited in LEAN_ENTRIES:
        if idx is not None and not all(_indexed(idx, n) for n in cited):
            spans.append((eid, -1, -1))
            continue
        start = body.count("\n") + 1
        body += f"\n-- {eid}\n{code}\n"
        spans.append((eid, start, body.count("\n")))
    t0 = time.monotonic()
    res = await ctx.lean.check(body, ws, timeout_s=600, owner="syntax-card")
    if res.infra_error or res.timed_out:
        log.info("Lean syntax card not built: %s", res.infra_error or "timeout")
        return None
    bad: dict[str, str] = {}
    for eid, a, b in spans:
        if a < 0:
            bad[eid] = "name not in this Mathlib"
    msgs = list(res.verdict.errors) + [m for m in leancheck.parse_lean_json(res.stdout)
                                       if "deprecated" in (m.text or "")]
    for m in msgs:
        if m.severity != "error" and "deprecated" not in (m.text or ""):
            continue
        for eid, a, b in spans:
            if a <= (m.line or 0) <= b:
                bad.setdefault(eid, (m.text or "")[:200])
    info = workspace_info(ws) or {}
    card = {"tool": "lean", "workspace": ws.key, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
            "card_version": CARD_VERSION, "built": time.time(), "seconds": round(time.monotonic() - t0, 1),
            "entries": [{"id": e[0], "text": e[1]} for e in LEAN_ENTRIES if e[0] not in bad], "dropped": bad}
    f = _lean_file(ws)
    f.parent.mkdir(parents=True, exist_ok=True)
    config.atomic_write_text(f, json.dumps(card, ensure_ascii=False))
    if bad:
        log.info("Lean syntax card (%s): %d entries dropped (%s)", ws.key, len(bad), ", ".join(bad))
    return card


def lean_card(ws) -> str:
    """The verified Lean card of this workspace's toolchain + Mathlib ('' while it is not built)."""
    if ws is None:
        return ""
    try:
        d = json.loads(_lean_file(ws).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not d.get("entries"):
        return ""
    head = f"Lean {d.get('lean') or '4'}, Mathlib {d.get('mathlib') or '?'} — syntax checked on this workspace:"
    return "\n".join([head] + [f"- {e['text']}" for e in d["entries"]])


# ================================================================ automatic (re)builds
def status() -> dict:
    """For the tests and the update screen: what is built for the installed versions."""
    v = sage_version()
    d = sage_card_data(v) if v else None
    return {"sage": {"version": v, "built": bool(d), "entries": len(d["entries"]) if d else 0,
                     "dropped": sorted((d or {}).get("dropped", {}))}}


ON_SAGE_BUILT: list = []          # callbacks(version) run in a thread after a new Sage card (recipes re-checked)


async def ensure_sage() -> bool:
    """Build the Sage card when the installed version has none (single flight). True when one was built."""
    py = await asyncio.to_thread(sage_python)
    if not py:
        return False
    v = await asyncio.to_thread(sage_version, py)
    if not v or sage_card_data(v) is not None or f"sage:{v}" in _BUILDING:
        return False
    _BUILDING.add(f"sage:{v}")
    try:
        built = await asyncio.to_thread(build_sage, py) is not None
    finally:
        _BUILDING.discard(f"sage:{v}")
    for fn in list(ON_SAGE_BUILT) if built else []:
        try:
            await asyncio.to_thread(fn, v)
        except Exception:  # noqa: BLE001
            log.exception("after the Sage card build")
    return built


async def ensure_lean(ctx, ws=None) -> bool:
    ws = ws or ctx.workspace()
    if ws is None or not ws.has_mathlib() or ws.problems:
        return False
    k = f"lean:{lean_key(ws)}"
    if _lean_file(ws).exists() or k in _BUILDING:
        return False
    _BUILDING.add(k)
    try:
        return await build_lean(ctx, ws) is not None
    finally:
        _BUILDING.discard(k)


async def ensure_all(ctx) -> None:
    """Server start (delayed), each update checkers' pass, after a Mathlib / Lake update: rebuild what changed."""
    from .research import codecat
    # S-AG (D39): the catalogue of canonical code structures is (re)verified by the same hooks
    for fn in (ensure_sage, lambda: ensure_lean(ctx), lambda: codecat.ensure(ctx)):
        try:
            await fn()
        except Exception:  # noqa: BLE001 (a catalogue build must never break anything)
            log.exception("syntax card build failed")


def schedule(ctx, loop=None) -> None:
    """Thread-safe: start `ensure_all` on the server's loop (used from the update checkers' thread)."""
    if os.environ.get("MADALEAN_NO_SYNTAX_BUILD") == "1":
        return
    async def run():
        await ensure_all(ctx)
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is not None:
        ctx.spawn(run())
    elif loop is not None:
        loop.call_soon_threadsafe(lambda: ctx.spawn(run()))
