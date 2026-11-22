"""Smoke suite of the sandboxed Sage / Python kernels (session S-AC, docs/CALCUL.md §10).

One real kernel, started exactly like a Calcul or conjecture kernel (Madalean's kernelspec → sagebridge launcher →
allow-listed environment, private home, rlimits, bubblewrap without network), runs one cell per item: what a
mathematician uses every day. Each item states what its output must contain; items marked `hint` must FAIL with
the kernel's clear French sentence (« Madalean : … ») instead of a raw traceback, because they cannot work in the
sandbox by design (network, writing outside the working directory, memory limit).

Used by `tests/test_sage_smoke.py` (every item, real kernel, when Sage is installed) and by the health self-test
(`update_checkers/selftest.py`, the `fast` items, after each Sage / Madalean update and on « Réparer »)."""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

HINT_RE = r"Madalean : "


@dataclass(frozen=True)
class Item:
    id: str
    label: str                 # French, shown in the health page
    code: str
    expect: str                # regex searched in stdout + results (or in the error text for `hint` items)
    fast: bool = False         # part of the health self-test subset
    hint: bool = False         # must fail with the kernel's French message
    rich: str = ""             # a display_data mime that must be produced (image/png…)
    timeout: float = 120.0
    sandbox_only: bool = False  # only meaningful inside bubblewrap (network)
    or_hint: bool = False      # passes either with `expect` or with the kernel's French message


SETUP = ("import os as _os\n_os.makedirs('.selftest', exist_ok=True)\n_os.chdir('.selftest')\n")

SAGE: tuple[Item, ...] = (
    Item("home", "Dossier personnel privé et inscriptible",
         "import os, pathlib\nh = os.environ['HOME']\np = pathlib.Path(h, '.cache', 'madalean-smoke')\n"
         "p.write_text('ok')\n"
         "print('HOME', len(h) <= 64, os.access(h, os.W_OK), p.read_text(), os.path.expanduser('~') == h,\n"
         "      not os.path.exists(os.path.join(h, '.ssh')), os.environ.get('DOT_SAGE', '').startswith(h),\n"
         "      os.environ.get('MAXIMA_USERDIR', '').startswith(h), os.environ.get('TMPDIR', '').startswith(h))\n",
         r"HOME True True ok True True True True True", fast=True),
    Item("gap_probe", "Sonde GAP (chemins racine sur une ligne)",
         "from sage.libs.gap.util import kernel_info\nr = kernel_info()[2]\n"
         "print('GAPROOT', r.split(';')[0] == os.environ['HOME'] + '/.gap/', '\\\\' not in r)\n",
         r"GAPROOT True True", fast=True),
    Item("var", "var(), expressions symboliques", "n = var('n'); x = var('x'); print(n + x, (x + 1)^2)",
         r"n \+ x \(x \+ 1\)\^2", fast=True),
    Item("fourier", "Série de Fourier : integral() + assume() (Maxima)",
         "assume(n, 'integer'); assume(n > 0)\n"
         "f = x\nan = integral(f*cos(n*x), x, -pi, pi)/pi\nbn = integral(f*sin(n*x), x, -pi, pi)/pi\n"
         "print('AN', an, 'BN', bn.simplify_full())\nforget()",
         r"AN 0 BN -2\*\(-1\)\^n/n", fast=True),
    Item("integrate", "integrate() indéfinie et définie", "print(integrate(1/(1+x^2), x), integrate(exp(-x^2), x, -oo, oo))",
         r"arctan\(x\) sqrt\(pi\)"),
    Item("limit", "limit()", "print(limit(sin(x)/x, x=0), limit((1+1/x)^x, x=oo))", r"^1 e$", fast=True),
    Item("sum", "sum() et hold", "k = var('k')\nprint(sum(1/k^2, k, 1, oo), '|', sum(k, k, 1, n, hold=True), '|',"
         " sum(k, k, 1, n).factor())", r"1/6\*pi\^2 \| sum\(k, k, 1, n\) \| 1/2\*\(n \+ 1\)\*n", fast=True),
    Item("taylor", "series() / taylor()", "print(taylor(exp(x), x, 0, 3)); print(sin(x).series(x, 4))",
         r"1/6\*x\^3 \+ 1/2\*x\^2 \+ x \+ 1\s+1\*x \+ \(-1/6\)\*x\^3 \+ Order\(x\^4\)"),
    Item("solve", "solve()", "print(sorted(str(s) for s in solve(x^2 - 5*x + 6 == 0, x)))", r"\['x == 2', 'x == 3'\]"),
    Item("simplify_full", "simplify_full()", "print((sin(x)^2 + cos(x)^2).simplify_full(), ((x^2-1)/(x-1)).simplify_full())",
         r"^1 x \+ 1$"),
    Item("diff", "diff()", "print(diff(x^3*sin(x), x))", r"x\^3\*cos\(x\) \+ 3\*x\^2\*sin\(x\)"),
    Item("laplace", "laplace()", "t, s = var('t s'); print(laplace(sin(t), t, s), inverse_laplace(1/(s^2+1), s, t))",
         r"1/\(s\^2 \+ 1\) sin\(t\)"),
    Item("maxima", "Interface Maxima", "print(maxima('integrate(x^2, x)').sage(), maxima.eval('factor(x^2-1)'))",
         r"1/3\*x\^3 \(x-1\)\*\(x\+1\)"),
    Item("gap", "GAP (groupes)", "G = SymmetricGroup(5)\nprint(G.order(), libgap.eval('Size(AlternatingGroup(5))'),"
         " G.is_abelian(), len(G.conjugacy_classes_representatives()))", r"120 60 False 7", fast=True),
    Item("gap_pexpect", "GAP en processus séparé (gap.eval)", "print(gap.eval('Size(SymmetricGroup(4))'))", r"^24$"),
    Item("pari", "PARI (théorie des nombres, factor)",
         "print(factor(2^64 + 1), next_prime(10^20), euler_phi(100), pari('quadclassunit(-23)[1]'))",
         r"274177 \* 67280421310721 100000000000000000039 40 3", fast=True),
    Item("gp", "PARI/GP en processus séparé (gp)", "print(gp('2^10 + 1'), gp.eval('isprime(2^61-1)'))", r"1025 1"),
    Item("numberfield", "Corps de nombres", "K.<i> = NumberField(x^2 + 1)\nprint(K.class_number(), factor(K(5)))",
         r"1 \(-i\) \* \(-?i \+ 2\) \* \(-?i - 2\)|1 \(.*\) \* \(.*\)"),
    Item("singular", "Singular (idéaux, base de Gröbner)",
         "R.<a,b,c> = PolynomialRing(QQ, order='degrevlex')\nI = R.ideal([a^2 - b, b^2 - c, c^2 - a])\n"
         "print(len(I.groebner_basis()), I.dimension(), singular.eval('ring r=0,(u,v),dp; 1+1;'))",
         r"\d+ 0 2", fast=True),
    Item("flint_ntl", "FLINT / NTL (polynômes)",
         "R.<y> = ZZ[]\nprint(factor(y^6 - 1))\nS.<z> = PolynomialRing(GF(2), implementation='NTL')\n"
         "print((z^4 + z + 1).is_irreducible(), ntl.ZZX([1, 2, 1]))",
         r"\(y - 1\) \* \(y \+ 1\) \* \(y\^2 - y \+ 1\) \* \(y\^2 \+ y \+ 1\)\s+True \[1 2 1\]"),
    Item("linalg", "Algèbre linéaire sur QQ, GF(p), RR",
         "A = matrix(QQ, [[1, 2], [3, 4]])\nprint(A.inverse().list(), matrix(GF(7), [[1, 2], [2, 4]]).rank(),"
         " round(matrix(RR, [[2, 1], [1, 2]]).det(), 6), sorted(round(v, 6) for v in matrix(RDF, [[2, 1], [1, 2]]).eigenvalues()))",
         r"\[-2, 1, 3/2, -1/2\] 1 3\.0 \[1\.0, 3\.0\]", fast=True),
    Item("numerical", "Numérique : find_root, numerical_integral, scipy, numpy",
         "import numpy, scipy.integrate\nr = find_root(cos(x) - x, 0, 1)\nq = numerical_integral(exp(-x^2), 0, 1)[0]\n"
         "s = scipy.integrate.quad(lambda u: numpy.exp(-u*u), 0, 1)[0]\n"
         "print('%.6f %.6f %.6f %s' % (r, q, s, numpy.linalg.solve([[2, 0], [0, 4]], [2, 8]).tolist()))",
         r"0\.739085 0\.746824 0\.746824 \[1\.0, 2\.0\]", fast=True),
    Item("plot2d", "Tracé 2D enregistré en PNG et SVG",
         "p = plot(sin(x), (x, -pi, pi))\np.save('smoke_2d.png'); p.save('smoke_2d.svg')\n"
         "print(open('smoke_2d.png', 'rb').read(4) == b'\\x89PNG', '<svg' in open('smoke_2d.svg').read())",
         r"True True", fast=True),
    Item("plot3d", "Tracé 3D (Tachyon) en PNG",
         "y = var('y')\nplot3d(x^2 - y^2, (x, -1, 1), (y, -1, 1)).save('smoke_3d.png')\n"
         "print(open('smoke_3d.png', 'rb').read(4) == b'\\x89PNG')", r"True", timeout=180),
    Item("implicit_parametric", "Tracés implicite et paramétrique",
         "y, t = var('y t')\nimplicit_plot(x^2 + y^2 == 4, (x, -3, 3), (y, -3, 3)).save('smoke_impl.png')\n"
         "parametric_plot((cos(t), sin(2*t)), (t, 0, 2*pi)).save('smoke_param.png')\n"
         "print(all(open(f, 'rb').read(4) == b'\\x89PNG' for f in ('smoke_impl.png', 'smoke_param.png')))", r"True"),
    Item("show", "show() d'un tracé (image affichée)", "show(plot(x^2, (x, -1, 1)))", r"", rich="image/png", fast=True),
    Item("latex", "latex()", "print(latex(integrate(1/(1+x^2), x)), latex(sqrt(2)/2))",
         r"\\arctan\\left\(x\\right\) \\frac\{1\}\{2\} \\, \\sqrt\{2\}", fast=True),
    Item("widgets", "Widgets sans interact (ipywidgets)",
         "try:\n    import ipywidgets\n    w = ipywidgets.IntSlider(value=3, min=0, max=5)\n    print('WIDGET', w.value)\n"
         "except ImportError:\n    print('WIDGET absent')", r"WIDGET (3|absent)"),
    Item("random", "Aléatoire (set_random_seed, random_matrix, os.urandom)",
         "set_random_seed(1); a = randint(1, 10**6); set_random_seed(1); b = randint(1, 10**6)\n"
         "import os\nprint(a == b, random_matrix(GF(5), 3).nrows(), len(os.urandom(8)))", r"True 3 8"),
    Item("matplotlib", "matplotlib (PNG, cache de polices)",
         "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\nfig, ax = plt.subplots()\n"
         "ax.plot([0, 1, 2], [0, 1, 4]); ax.set_title('$x^2$')\nfig.savefig('smoke_mpl.png'); plt.close(fig)\n"
         "print(open('smoke_mpl.png', 'rb').read(4) == b'\\x89PNG', os.environ['MPLCONFIGDIR'].startswith(os.environ['HOME']))",
         r"True True", fast=True),
    Item("sympy", "Conversion sympy ↔ Sage",
         "import sympy\ne = (x^2 + 1)._sympy_()\nprint(e, sympy.integrate(e, sympy.Symbol('x'))._sage_())",
         r"x\*\*2 \+ 1 1/3\*x\^3 \+ x"),
    # cython() needs the Python module `pkgconfig`, an optional dependency of some Sage packages (Arch: absent):
    # then the kernel must say so in French, which passes too (`or_hint`)
    Item("cython", "Compilation cython() (ou message clair si impossible)",
         "cython('def smoke_sq(int n):\\n    return n*n')\nprint(smoke_sq(12))", r"^144$", timeout=240, or_hint=True),
    Item("files", "Lecture / écriture de fichiers dans le dossier de travail",
         "with open('smoke_data.txt', 'w') as f:\n    f.write('1 2 3')\n"
         "print(sum(int(v) for v in open('smoke_data.txt').read().split()), os.path.exists('../.selftest/smoke_data.txt'))",
         r"6 True", fast=True),
    Item("multiprocessing", "multiprocessing et @parallel",
         "import multiprocessing\nwith multiprocessing.Pool(2) as pool:\n    r = pool.map(abs, [-1, -2, -3])\n"
         "@parallel(2)\ndef smoke_sq(k):\n    return k*k\nprint(r, sorted(v for _a, v in smoke_sq([1, 2, 3])))",
         r"\[1, 2, 3\] \[1, 4, 9\]"),
    Item("no_network", "Réseau coupé : message clair",
         "import urllib.request\nurllib.request.urlopen('https://example.org', timeout=5)", HINT_RE + "pas d'accès au réseau",
         hint=True, fast=True, sandbox_only=True),
    Item("read_only", "Écriture hors du dossier de travail : message clair",
         "open('/usr/madalean-smoke.txt', 'w')", HINT_RE + "écriture impossible", hint=True, fast=True,
         sandbox_only=True),
    Item("memory", "Limite mémoire : message clair", "smoke_big = bytearray(1 << 46)", HINT_RE + "mémoire insuffisante",
         hint=True),
)

_SAGE = {i.id: i for i in SAGE}
PYTHON: tuple[Item, ...] = (
    _SAGE["home"],
    Item("numpy", "numpy / scipy", "import numpy, scipy.integrate\n"
         "print('%.6f' % scipy.integrate.quad(lambda u: numpy.exp(-u*u), 0, 1)[0])", r"0\.746824", fast=True),
    _SAGE["matplotlib"], _SAGE["files"],
    Item("multiprocessing", "multiprocessing", "import multiprocessing\nwith multiprocessing.Pool(2) as pool:\n"
         "    print(pool.map(abs, [-1, -2]))", r"\[1, 2\]"),
    _SAGE["no_network"], _SAGE["read_only"],
)


def items_for(language: str, fast: bool = False, sandbox: str = "bwrap") -> list[Item]:
    out = SAGE if language == "sage" else PYTHON
    return [i for i in out if (i.fast or not fast) and (sandbox == "bwrap" or not i.sandbox_only)]


def check(item: Item, res) -> tuple[bool, str]:
    """(passed, detail) for one ExecResult."""
    text = (res.stdout + "\n" + res.result).strip()
    if item.hint:
        blob = res.error + "\n" + res.stderr
        if res.status == "error" and re.search(item.expect, blob):
            return True, re.search(r"Madalean : [^\n]*", blob).group(0)[:300]
        return False, f"{res.status}: {(res.error or text)[-600:]}"
    if res.status == "error" and item.or_hint and re.search(HINT_RE, res.error):
        return True, re.search(r"Madalean : [^\n]*", res.error).group(0)[:300]
    if res.status != "ok":
        return False, f"{res.status}: {(res.error or res.stderr or text)[-600:]}"
    if item.rich and not any(r.get("mime") == item.rich for r in res.rich):
        return False, f"pas de sortie {item.rich} : {text[-300:]}"
    if item.expect and not re.search(item.expect, text, re.M):
        return False, f"sortie inattendue : {text[-600:]}"
    return True, text[-200:]


async def run(bridge, language: str, items: list[Item], on_item=None) -> dict:
    """Run `items` in ONE fresh kernel of `language` (Madalean's sandboxed kernelspec), then shut it down. Never
    raises for kernel problems: they become a failed report."""
    t0 = time.monotonic()
    report = {"language": language, "sandbox": bridge.sandbox_kind, "ok": False, "passed": 0, "failed": 0,
              "items": [], "error": "", "started": time.time(), "seconds": 0.0}
    kid = ""
    try:
        try:
            kid = await bridge.start_kernel(language)
        except Exception as e:  # noqa: BLE001
            report["error"] = f"unavailable: {e}"[:500]
            return report
        if not await bridge.wait_ready(kid, timeout=240):
            report["error"] = "kernel died while starting\n" + "\n".join(bridge.ctx.jupyter._tail[-15:])
            return report
        pre = await bridge.execute(kid, SETUP, timeout=60, language=language, kill_on_limit=False)
        if pre.status != "ok":
            report["error"] = f"setup {pre.status}: {pre.error[-500:]}"
            return report
        for it in items:
            r = await bridge.execute(kid, it.code, timeout=it.timeout, language=language, kill_on_limit=False)
            ok, detail = check(it, r)
            row = {"id": it.id, "label": it.label, "ok": ok, "seconds": round(r.seconds, 2), "detail": detail}
            report["items"].append(row)
            report["passed" if ok else "failed"] += 1
            if on_item is not None:
                on_item(row)
            if r.status in ("died", "timeout") and r.killed:
                report["error"] = f"kernel {r.status} at {it.id}"
                break
            if r.status == "timeout":           # interrupted: the next item runs in the same, still live kernel
                await asyncio.sleep(0.5)
        report["ok"] = report["failed"] == 0 and len(report["items"]) == len(items)
        return report
    finally:
        if kid:
            await bridge.shutdown(kid)
        report["seconds"] = round(time.monotonic() - t0, 1)
