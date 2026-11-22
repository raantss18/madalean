"""« Expliquer les étapes du calcul » (session S-AJ, DECISIONS D42): deterministic **step probes** that compute the
intermediate quantities of a Sage cell's computation with Sage itself, so that the model's explanation is built on
facts, not on invented numbers.

A probe is Madalean's own FIXED program (`PROBE`, below). It receives, as data, the cell's code — code that has
already run and was allowed to run (user code, or model code approved on this host: the caller checks
`NotebookStore.may_run`) — and the operation. In the cell's kernel it re-evaluates the cell in a COPY of the kernel's
namespace (the user's names are never rebound), takes the value of the last expression, then computes a few checks
keyed by the operation:

- `factor`   degree and base field, each factor's degree and irreducibility, product of the factors == the input
             (integers: each factor is prime, product == n);
- `integrate` an antiderivative and the check F' == f; for a definite integral F(b) − F(a) == the result;
- `roots`    f(r) == 0 for each root, its multiplicity and minimal polynomial;
- `det`      triangular form (LU with permutation P): det = det(P) · product of U's diagonal == the result; rank;
- `solve`    substitution of each solution into every equation (== 0); A·x == b and the kernel's dimension for
             `solve_right` / `solve_left`.

Model-written code never reaches the kernel through this module: the only executed text is `PROBE` + the cell's own
code (already approved), passed as a JSON string literal. The probe's recomputed result is compared with the cell's
displayed output; when they differ (the kernel's state changed since the run), its facts are dropped."""
from __future__ import annotations

import json
import re

PROBE_OPS = ("factor", "integrate", "roots", "det", "solve")
# operation names in the code (the last expression's function / method) → probe
CODE_OPS = {"factor": "factor", "factorization": "factor", "integrate": "integrate", "integral": "integrate",
            "roots": "roots", "real_roots": "roots", "complex_roots": "roots", "det": "det", "determinant": "det",
            "solve": "solve", "solve_right": "solve", "solve_left": "solve"}
INTENT_OPS = {"factor": "factor", "integrate": "integrate", "roots": "roots", "det": "det", "solve": "solve"}
MARK = "MADALEAN_STEPS "
MAX_FACTS = 14

PROBE = r'''
def _madalean_steps(_req, _g):
    import ast, io, json, contextlib
    out = {"facts": [], "op": "", "result": ""}
    L = _g.get("latex") or str
    def T(x):
        try:
            return str(L(x)).replace("\n", " ")
        except Exception:
            return str(x)
    def fact(k, ok=None, **v):
        if len(out["facts"]) < _req["max"]:
            out["facts"].append({"k": k, "ok": ok, "v": {a: str(b)[:1500] for a, b in v.items()}})
    def safe(f):
        try:
            f()
        except Exception as e:
            out.setdefault("skipped", []).append(type(e).__name__)
    src = _req["code"]
    if _req["language"] == "sage":
        from sage.repl.preparse import preparse
        src = preparse(src)
    tree = ast.parse(src)
    if not tree.body or not isinstance(tree.body[-1], ast.Expr):
        out["error"] = "no_final_expression"
        return out
    last = tree.body.pop().value
    if (isinstance(last, ast.Call) and isinstance(last.func, ast.Name) and len(last.args) == 1
            and last.func.id in ("print", "show", "pretty_print", "tex")):
        last = last.args[0]
    ns = dict(_g)
    def ev(node):
        return eval(compile(ast.fix_missing_locations(ast.Expression(body=node)), "<cell>", "eval"), ns)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(tree, "<cell>", "exec"), ns)
        res = ev(last)
    out["result"] = str(res)
    name, obj, args = "", None, []
    if isinstance(last, ast.Call):
        args = list(last.args)
        if isinstance(last.func, ast.Attribute):
            name, obj = last.func.attr, last.func.value
        elif isinstance(last.func, ast.Name):
            name = last.func.id
    op = _req["code_ops"].get(name) or _req["op"]
    out["op"] = op
    def subject():
        return ev(obj) if obj is not None else (ev(args[0]) if args else None)
    with contextlib.redirect_stdout(io.StringIO()):
        if op == "factor":
            from sage.structure.factorization import Factorization
            F = res
            if not isinstance(F, Factorization):
                out["error"] = "not_a_factorization"
                return out
            n = subject()
            if n is None:
                n = F.value()
            from sage.all import ZZ
            if n not in ZZ and hasattr(n, "is_irreducible") and hasattr(n, "degree"):
                P = n.parent()
                def poly():
                    fact("poly", f=T(n), ring=T(P), deg=n.degree())
                    K = P.base_ring()
                    if K.is_finite():
                        fact("field", K=T(K), q=K.order(), p=K.characteristic())
                safe(poly)
                for g, e in F:
                    safe(lambda g=g, e=e: fact("irreducible", bool(g.is_irreducible()), g=T(g), e=e, deg=g.degree()))
                safe(lambda: fact("product", bool(F.value() == n), prod=T(F), f=T(n),
                                  degs=" + ".join((f"{e}\\cdot{g.degree()}" if e > 1 else str(g.degree()))
                                                  for g, e in F), deg=n.degree()))
            else:
                safe(lambda: fact("integer", n=T(n)))
                for p, e in F:
                    safe(lambda p=p, e=e: fact("prime", bool(p.is_prime()), p=T(p), e=e))
                safe(lambda: fact("product_int", bool(F.value() == n), prod=T(F), n=T(n)))
        elif op == "integrate":
            from sage.all import diff, integrate
            if obj is not None:
                f, rest = ev(obj), args
            else:
                f, rest = ev(args[0]), args[1:]
            x = ev(rest[0]) if rest else f.variables()[0]
            if len(rest) >= 3:
                a, b = ev(rest[1]), ev(rest[2])
                G = integrate(f, x)
                d = diff(G, x)
                fact("antiderivative", bool((d - f).simplify_full() == 0), F=T(G), dF=T(d), f=T(f), x=T(x))
                def ftc():
                    Gb, Ga = G.limit(**{str(x): b}), G.limit(**{str(x): a})
                    fact("ftc", bool((Gb - Ga - res).simplify_full() == 0), F=T(G), a=T(a), b=T(b), Fa=T(Ga),
                         Fb=T(Gb), val=T(res), x=T(x))
                safe(ftc)
            else:
                d = diff(res, x)
                fact("antiderivative", bool((d - f).simplify_full() == 0), F=T(res), dF=T(d), f=T(f), x=T(x))
        elif op == "roots":
            f = subject()
            items = list(res)
            total = 0
            for it in items[:10]:
                r, m = (it if isinstance(it, tuple) and len(it) == 2 else (it, None))
                def one(r=r, m=m):
                    val = f(r)
                    try:
                        ok = bool(val == 0)
                        if not ok and not getattr(val.parent(), "is_exact", lambda: True)():
                            ok = bool(abs(val) < 1e-9)
                    except Exception:
                        ok = None
                    v = {"r": T(r), "f": T(f), "m": m if m is not None else ""}
                    try:
                        if getattr(r.parent(), "is_exact", lambda: False)():
                            v["minpoly"] = T(r.minpoly())
                    except Exception:
                        pass
                    fact("root", ok, **v)
                safe(one)
                total += m if isinstance(m, int) or hasattr(m, "is_integer") else 1
            safe(lambda: fact("root_count", n=len(items), mult=total, deg=f.degree()))
        elif op == "det":
            M = subject()
            fact("matrix", M=T(M) if M.nrows() <= 6 else "", n=M.nrows(), ring=T(M.base_ring()))
            def tri():
                A = M if M.base_ring().is_field() else M.change_ring(M.base_ring().fraction_field())
                Pm, Lm, U = A.LU(pivot="nonzero")
                from sage.all import prod
                d = U.diagonal()
                fact("triangular", bool(Pm.det() * prod(d) == res), U=T(U) if M.nrows() <= 6 else "",
                     diag=" \\cdot ".join("(" + T(x) + ")" for x in d[:8]) + (" \\cdots" if len(d) > 8 else ""),
                     sign=T(Pm.det()), det=T(res))
            safe(tri)
            safe(lambda: fact("rank", r=M.rank(), n=M.nrows()))
        elif op == "solve":
            if name in ("solve_right", "solve_left"):
                A, b = ev(obj), ev(args[0])
                right = name == "solve_right"
                ok = bool((A * res if right else res * A) == b)
                fact("linear_check" if right else "linear_check_left", ok, A=T(A), x=T(res), b=T(b))
                safe(lambda: fact("kernel_dim", d=(A.right_kernel() if right else A.left_kernel()).dimension()))
            else:
                eqs = ev(args[0])
                eqs = list(eqs) if isinstance(eqs, (list, tuple)) else [eqs]
                sols = list(res)
                if not sols:
                    fact("no_solution")
                for s in sols[:8]:
                    def one(s=s):
                        rels = list(s) if isinstance(s, (list, tuple)) else [s]
                        sub = {e.lhs(): e.rhs() for e in rels}
                        def zero(e):
                            ex = (e.lhs() - e.rhs()) if e.is_relational() else e
                            return bool(ex.subs(sub).simplify_full() == 0)
                        fact("substitution", all(zero(e) for e in eqs),
                             sol=", ".join(T(k) + " = " + T(v) for k, v in sub.items()),
                             eqs=", ".join(T(e) for e in eqs))
                    safe(one)
        else:
            out["error"] = "no_probe"
    return out
try:
    print("MADALEAN_STEPS " + __import__("json").dumps(_madalean_steps(__import__("json").loads(_madalean_req), globals())))
except Exception as _madalean_e:
    print("MADALEAN_STEPS " + __import__("json").dumps({"error": type(_madalean_e).__name__ + ": " + str(_madalean_e)[:300], "facts": []}))
finally:
    for _madalean_n in ("_madalean_steps", "_madalean_req", "_madalean_e", "_madalean_n"):
        globals().pop(_madalean_n, None)
'''


def probe_op(intent_op: str, code: str) -> str:
    """The probe for this cell: the operation recognized in the request (S-AG), else the one written in the code's
    last expression (`f.factor()`, `integrate(…)`, `M.det()`, `solve(…)`), else ''."""
    if intent_op in INTENT_OPS:
        return INTENT_OPS[intent_op]
    lines = [l for l in (code or "").strip().split("\n") if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return ""
    for name in re.findall(r"([A-Za-z_]\w*)\s*\(", lines[-1])[::-1]:
        if name in CODE_OPS:
            return CODE_OPS[name]
    return ""


def program(code: str, language: str, op: str) -> str:
    """The text run in the kernel: Madalean's fixed probe, the cell's code only as a JSON string (data)."""
    req = json.dumps({"code": code, "language": language, "op": op, "code_ops": CODE_OPS, "max": MAX_FACTS})
    return "_madalean_req = " + repr(req) + "\n" + PROBE


def parse(stdout: str) -> dict:
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(MARK):
            try:
                d = json.loads(line[len(MARK):])
            except ValueError:
                break
            return d if isinstance(d, dict) else {"error": "bad_probe_output", "facts": []}
    return {"error": "no_probe_output", "facts": []}


_INLINE_MATH = re.compile(r"(?<![$\\])\$(?!\$)([^$\n]+?)(?<![\\$])\$(?!\$)")


def inline_delims(text: str) -> str:
    """The Markdown renderer reads « $641$ » as money (a $ followed by a digit or a space is not maths, lib/md.ts),
    and facts / steps often start a formula with a number: « ${}641$ » (an empty group, same rendering, still valid
    LaTeX when copied). Display maths ($$…$$) is left as is."""
    def fix(m: re.Match) -> str:
        body = m.group(1).strip()
        return "$" + ("{}" if body[:1].isdigit() else "") + body + "$" if body else m.group(0)
    return _INLINE_MATH.sub(fix, text or "")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def matches_output(result: str, shown: str) -> bool:
    """The probe recomputed the cell's value: it must be what the cell shows (else the kernel's state changed)."""
    r, s = _norm(result), _norm(shown)
    return bool(r) and (r in s or s in r and len(s) > 0.8 * len(r))


# ---------------------------------------------------------------- facts in words (FR / EN), LaTeX in $…$
FACT_TEXT = {
    "fr": {
        "poly": "Le polynôme $f = {f}$ est de degré ${deg}$ dans ${ring}$.",
        "field": "Le corps de base ${K}$ a ${q}$ éléments (caractéristique ${p}$).",
        "irreducible": "Le facteur ${g}$ (degré ${deg}$, exposant {e}) est irréductible.",
        "product": "Le produit des facteurs redonne $f$ : ${prod} = {f}$ (degrés : ${degs} = {deg}$).",
        "integer": "L'entier à factoriser est $n = {n}$.",
        "prime": "${p}$ est premier (exposant {e}).",
        "product_int": "Le produit des facteurs redonne $n$ : ${prod} = {n}$.",
        "antiderivative": "Une primitive de $f = {f}$ est $F = {F}$ ; contrôle : $F'({x}) = {dF} = f$.",
        "ftc": "$\\int_{{{a}}}^{{{b}}} f\\,d{x} = F({b}) - F({a}) = {Fb} - ({Fa}) = {val}$.",
        "root": "$r = {r}$ annule $f = {f}$ : $f(r) = 0${mult}{minpoly}.",
        "root_count": "{n} racine(s) distincte(s), {mult} avec multiplicité, pour un polynôme de degré {deg}.",
        "matrix": "La matrice est de taille ${n} \\times {n}$ sur ${ring}${M}.",
        "triangular": "Forme triangulaire (élimination de Gauss) : $U = {U}$ ; $\\det = {sign} \\cdot {diag} = {det}$.",
        "rank": "Le rang de la matrice est {r} (sur {n} lignes).",
        "linear_check": "Contrôle : $A x = b$ avec $x = {x}$.",
        "linear_check_left": "Contrôle : $x A = b$ avec $x = {x}$.",
        "kernel_dim": "Le noyau est de dimension {d} ({uniq}).",
        "substitution": "En remplaçant ${sol}$ dans ${eqs}$, chaque équation est satisfaite.",
        "no_solution": "Sage ne trouve aucune solution.",
    },
    "en": {
        "poly": "The polynomial $f = {f}$ has degree ${deg}$ in ${ring}$.",
        "field": "The base field ${K}$ has ${q}$ elements (characteristic ${p}$).",
        "irreducible": "The factor ${g}$ (degree ${deg}$, exponent {e}) is irreducible.",
        "product": "The product of the factors gives back $f$: ${prod} = {f}$ (degrees: ${degs} = {deg}$).",
        "integer": "The integer to factor is $n = {n}$.",
        "prime": "${p}$ is prime (exponent {e}).",
        "product_int": "The product of the factors gives back $n$: ${prod} = {n}$.",
        "antiderivative": "An antiderivative of $f = {f}$ is $F = {F}$; check: $F'({x}) = {dF} = f$.",
        "ftc": "$\\int_{{{a}}}^{{{b}}} f\\,d{x} = F({b}) - F({a}) = {Fb} - ({Fa}) = {val}$.",
        "root": "$r = {r}$ is a root of $f = {f}$: $f(r) = 0${mult}{minpoly}.",
        "root_count": "{n} distinct root(s), {mult} with multiplicity, for a polynomial of degree {deg}.",
        "matrix": "The matrix is ${n} \\times {n}$ over ${ring}${M}.",
        "triangular": "Triangular form (Gaussian elimination): $U = {U}$; $\\det = {sign} \\cdot {diag} = {det}$.",
        "rank": "The rank of the matrix is {r} (out of {n} rows).",
        "linear_check": "Check: $A x = b$ with $x = {x}$.",
        "linear_check_left": "Check: $x A = b$ with $x = {x}$.",
        "kernel_dim": "The kernel has dimension {d} ({uniq}).",
        "substitution": "Substituting ${sol}$ into ${eqs}$ satisfies every equation.",
        "no_solution": "Sage finds no solution.",
    },
}


def fact_text(f: dict, lang: str) -> str:
    lang = lang if lang in FACT_TEXT else "en"
    tpl = FACT_TEXT[lang].get(f.get("k", ""))
    if not tpl:
        return ""
    v = {k: str(x) for k, x in (f.get("v") or {}).items()}
    fr = lang == "fr"
    if f["k"] == "root":
        v["mult"] = ((", multiplicité " if fr else ", multiplicity ") + v["m"]) if v.get("m") else ""
        v["minpoly"] = ((" ; polynôme minimal $" if fr else "; minimal polynomial $") + v["minpoly"] + "$") \
            if v.get("minpoly") else ""
    if f["k"] == "matrix":
        v["M"] = f" : $M = {v['M']}$" if fr and v.get("M") else (f": $M = {v['M']}$" if v.get("M") else "")
    if f["k"] == "triangular" and not v.get("U"):
        tpl = tpl.split(" : $U")[0] + " : $\\det = {sign} \\cdot {diag} = {det}$." if fr else \
            tpl.split(": $U")[0] + ": $\\det = {sign} \\cdot {diag} = {det}$."
    if f["k"] == "kernel_dim":
        unique = v.get("d") == "0"
        v["uniq"] = ("solution unique" if unique else "infinité de solutions") if fr else \
            ("unique solution" if unique else "infinitely many solutions")
    try:
        return inline_delims(tpl.format(**v))
    except (KeyError, IndexError, ValueError):
        return ""


def facts_view(raw: list[dict], lang: str) -> list[dict]:
    """[{text, status: verified | computed | failed, key}] for the UI and the prompt."""
    out = []
    for f in raw or []:
        t = fact_text(f, lang)
        if t:
            ok = f.get("ok")
            out.append({"key": f.get("k", ""), "text": t,
                        "status": "verified" if ok is True else ("failed" if ok is False else "computed")})
    return out
