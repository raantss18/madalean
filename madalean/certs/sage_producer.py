# Madalean's certificate producer (session S-AT, DECISIONS D52): the FIXED program that runs in the Sage sandbox.
#
# The server never imports this file: it reads it as text (after evalcore.py, whose functions `evaluate`, `holds`,
# `is_prime` it uses) and executes it in a sandboxed Sage kernel as plain Python — never through Sage's preparser.
# The request arrives as JSON data in `_madalean_cert_req`; no text of a statement is ever evaluated: polynomials
# are lists of integers, propositions are trees interpreted by `holds`. The answer is one line
# `MADALEAN_CERT {json}`. Nothing computed here is trusted: the server turns the witness into a Lean proof and Lean
# decides.
import itertools
import json
import time

_DEADLINE = [0.0]


class NoWitness(Exception):
    pass


def _tick():
    if time.time() > _DEADLINE[0]:
        raise NoWitness("timeout")


def _frac(v):
    from sage.all import QQ
    q = QQ(v)
    return [str(int(q.numerator())), str(int(q.denominator()))]


def _ring(base, n):
    from sage.all import PolynomialRing, QQ, ZZ
    return PolynomialRing(ZZ if base == "ZZ" else QQ, n, "x", order="degrevlex")


def _poly(R, wire):
    from sage.all import QQ
    X = R.gens()
    out = R(0)
    for num, den, exps in wire:
        m = R(1)
        for x, e in zip(X, exps):
            m *= x ** int(e)
        out += R(QQ(int(num)) / QQ(int(den))) * m
    return out


def _wire(p):
    out = []
    for exps, c in p.dict().items():
        num, den = _frac(c)
        out.append([num, den, [int(e) for e in (exps if hasattr(exps, "__iter__") else [exps])]])
    return out


# ---------------------------------------------------------------- primality (Pratt) and factors
def pratt(n, small, depth=0):
    from sage.all import ZZ, power_mod
    _tick()
    n = ZZ(n)
    if not n.is_prime(proof=True):
        raise NoWitness("not prime")
    if n < small:
        return {"p": int(n)}
    if depth > 12:
        raise NoWitness("too deep")
    F = list((n - 1).factor())
    a = ZZ(2)
    while not all(power_mod(a, (n - 1) // q, n) != 1 for q, _e in F) or power_mod(a, n - 1, n) != 1:
        a += 1
        if a > 100000:
            raise NoWitness("no primitive root found")
    return {"p": str(n), "a": str(a), "factors": [dict(pratt(q, small, depth + 1), e=int(e)) for q, e in F]}


def factor(n):
    from sage.all import ZZ
    n = ZZ(n)
    d = n.trial_division(10 ** 6)
    if d == n:
        if n.is_prime():
            raise NoWitness("prime")
        d = min(p for p, _e in n.factor())
    return {"d": str(d), "q": str(n // d)}


# ---------------------------------------------------------------- ideal membership
def ideal(req):
    R = _ring(req["ring"], int(req["n"]))
    gens = [_poly(R, w) for w in req["gens"]]
    f = _poly(R, req["target"])
    I = R.ideal(gens)
    for k in (1, 2, 3):
        _tick()
        g = f ** k
        try:
            if g not in I:
                continue
            co = g.lift(I)
        except (ValueError, TypeError, ArithmeticError, NotImplementedError):
            continue
        if sum((c * h for c, h in zip(co, gens)), R(0)) == g:
            return {"exp": k, "cof": [_wire(R(c)) for c in co]}
    raise NoWitness("not in the ideal")


# ---------------------------------------------------------------- linear arithmetic (Farkas)
def _farkas(n, items):
    """items: [(coefficients of x_1..x_n, constant, kind)] meaning `a·x + c  kind  0`, kind in >=, >, =.
    Multipliers proving that they cannot all hold: Σ λ_i (a_i·x + c_i) is a constant ≤ 0, and < 0 unless a strict
    item is used; λ_i ≥ 0 except for equalities."""
    from sage.all import MixedIntegerLinearProgram, QQ
    from sage.numerical.mip import MIPSolverException
    lp = MixedIntegerLinearProgram(solver="PPL", maximization=False)
    pos = lp.new_variable(nonnegative=True)
    neg = lp.new_variable(nonnegative=True)

    def lam(i):
        return pos[i] - neg[i] if items[i][2] == "=" else pos[i]
    for j in range(n):
        lp.add_constraint(sum(items[i][0][j] * lam(i) for i in range(len(items))) == 0)
    c = sum(items[i][1] * lam(i) for i in range(len(items)))
    strict = sum(pos[i] for i in range(len(items)) if items[i][2] == ">")
    lp.add_constraint(c <= 0)
    lp.add_constraint(-c + strict == 1)
    lp.set_objective(sum(pos[i] + (neg[i] if items[i][2] == "=" else 0) for i in range(len(items))))
    try:
        lp.solve()
    except MIPSolverException:
        return None
    vp, vn = lp.get_values(pos), lp.get_values(neg)
    return [QQ(vp.get(i, 0)) - (QQ(vn.get(i, 0)) if items[i][2] == "=" else 0) for i in range(len(items))]


def linear(req):
    from sage.all import QQ
    n = int(req["n"])
    R = _ring("QQ", n)

    def item(wire, kind, sign=1):
        p = sign * _poly(R, wire)
        if p.degree() > 1:
            raise NoWitness("not linear")
        return ([QQ(p.monomial_coefficient(x)) for x in R.gens()], QQ(p.constant_coefficient()), kind)
    hyps = [item(h["poly"], h["op"]) for h in req["hyps"]]
    goal = req.get("goal")
    runs = []
    if goal is None:
        runs.append(hyps)
    elif goal["op"] == "=":          # t = 0: refute t > 0 and refute -t > 0
        runs.append(hyps + [item(goal["poly"], ">")])
        runs.append(hyps + [item(goal["poly"], ">", -1)])
    else:                            # t >= 0: refute -t > 0;  t > 0: refute -t >= 0
        runs.append(hyps + [item(goal["poly"], ">" if goal["op"] == ">=" else ">=", -1)])
    out = []
    for items in runs:
        _tick()
        lam = _farkas(n, items)
        if lam is None:
            raise NoWitness("no linear certificate")
        out.append([_frac(v) for v in lam[:len(hyps)]])
    return {"multipliers": out}


# ---------------------------------------------------------------- sums of squares
def _ldl(Q):
    """Q = Σ d_j v_j v_jᵀ with d_j ≥ 0 over ℚ (exact), or None when Q is not positive semidefinite."""
    from sage.all import QQ
    N = Q.nrows()
    A = [[QQ(Q[i, j]) for j in range(N)] for i in range(N)]
    out = []
    for j in range(N):
        d = A[j][j]
        if d < 0:
            return None
        if d == 0:
            if any(A[i][j] != 0 for i in range(j + 1, N)):
                return None
            continue
        col = [QQ(0)] * j + [A[i][j] / d for i in range(j, N)]
        for i in range(j + 1, N):
            for k in range(j + 1, N):
                A[i][k] -= col[i] * col[k] * d
        out.append((d, col))
    return out


def sos(req):
    """t = c + Σ_b g_b · (sum of squares)_b + Σ λ_ij g_i g_j with g_0 = 1, the g_i the hypotheses (≥ 0), c ≥ 0 and
    λ ≥ 0: one Gram matrix per block, found numerically, made rational, then checked exactly here (and by Lean)."""
    from sage.all import QQ, matrix, vector
    n = int(req["n"])
    R = _ring("QQ", n)
    X = R.gens()
    t = _poly(R, req["target"])
    G = [_poly(R, w) for w in req["hyps"]]
    strict = bool(req.get("strict"))
    deg = max([t.degree()] + [g.degree() for g in G])
    deg += deg % 2

    def monos(d):
        return [m for k in range(d + 1) for m in sorted(R.monomials_of_degree(k), reverse=True)]
    blocks = []                                  # (hypothesis index or -1, multiplier polynomial, basis)
    basis = monos(deg // 2)
    if not G:                                    # no hypotheses: only the monomials the Newton polytope allows
        hi = [t.degree(x) // 2 for x in X]
        lo_tot = min(m.degree() for m in t.monomials()) if t != 0 else 0
        basis = [m for m in basis if all(m.degree(x) <= h for x, h in zip(X, hi)) and 2 * m.degree() >= lo_tot]
    blocks.append((-1, R(1), basis))
    for i, g in enumerate(G):
        if g != 0 and g.degree() <= deg:
            blocks.append((i, g, monos((deg - g.degree()) // 2)))
    prods = []                                   # products of two hypotheses, with a non-negative number in front
    for i in range(len(G)):
        for j in range(i, len(G)):
            if G[i].degree() + G[j].degree() <= deg and len(prods) < 24:
                prods.append(([i, j], G[i] * G[j]))
    sizes = [len(bs) for _i, _g, bs in blocks]
    if not sizes[0] or sum(k * (k + 1) // 2 for k in sizes) > 700:
        raise NoWitness("problem too large")
    cols, off = [], 0                            # per block: {(a, b): column}
    for k in sizes:
        d = {}
        for a in range(k):
            for bb in range(a, k):
                d[(a, bb)] = off
                off += 1
        cols.append(d)
    nu = off + len(prods) + 1                    # unknowns: Gram entries, product multipliers, the constant c
    rows = {}

    def put(poly, col, factor=1):
        for m, c in zip(poly.monomials(), poly.coefficients()):
            rows.setdefault(m, {})
            rows[m][col] = rows[m].get(col, 0) + factor * c
    for (_i, g, bs), d in zip(blocks, cols):
        for (a, bb), col in d.items():
            put(g * bs[a] * bs[bb], col, 1 if a == bb else 2)
    for k, (_idx, p) in enumerate(prods):
        put(p, off + k)
    put(R(1), nu - 1)
    for m in t.monomials():
        if m not in rows:
            raise NoWitness("no certificate of this shape")
    monos_all = list(rows)
    A = matrix(QQ, len(monos_all), nu, sparse=True)
    for r, m in enumerate(monos_all):
        for col, val in rows[m].items():
            A[r, col] = val
    rhs = vector(QQ, [t.monomial_coefficient(m) for m in monos_all])
    try:
        u0 = A.solve_right(rhs)
    except ValueError:
        raise NoWitness("no certificate of this shape")
    K = A.right_kernel_matrix()

    def check(u):
        lam = [u[off + k] for k in range(len(prods))]
        c = u[nu - 1]
        if any(v < 0 for v in lam) or c < 0 or (strict and c == 0):
            return None
        total = R(c) + sum(l * p for l, (_i, p) in zip(lam, prods))
        out_blocks = []
        for (i, g, bs), d in zip(blocks, cols):
            N = len(bs)
            Q = matrix(QQ, N, N)
            for (a, bb), col in d.items():
                Q[a, bb] = Q[bb, a] = u[col]
            dec = _ldl(Q)
            if dec is None:
                return None
            forms = [(dd, sum(col[k] * bs[k] for k in range(N))) for dd, col in dec]
            forms = [(dd, f) for dd, f in forms if f != 0]
            total += g * sum(dd * f * f for dd, f in forms)
            if forms:
                out_blocks.append([i, [[_frac(dd), _wire(f)] for dd, f in forms]])
        if total != t:
            return None
        return {"c": _frac(c), "mults": [[idx, _frac(l)] for l, (idx, _p) in zip(lam, prods) if l != 0],
                "blocks": out_blocks}
    got = check(u0)
    if got is not None:
        return got
    if K.nrows() == 0:
        raise NoWitness("not a sum of squares of this shape")
    for mode in ("interior", "trace"):
        _tick()
        x = _sdp(u0, K, cols, sizes, off, len(prods), strict, mode)
        if x is None:
            continue
        for den in (1, 2, 4, 12, 60, 10 ** 3, 10 ** 5, 10 ** 7, 10 ** 9, 10 ** 12):
            _tick()
            xr = vector(QQ, [QQ(int(round(float(v) * den))) / den for v in x])
            got = check(u0 + xr * K)
            if got is not None:
                return got
    raise NoWitness("no exact certificate found")


def _sdp(u0, K, cols, sizes, off, nprod, strict, mode):
    """A numerical point x for u = u0 + x·K with every Gram block positive semidefinite, multipliers and c ≥ 0.
    mode « interior »: the main block ⪰ τ·I with τ maximal (≤ 1), which leaves room for rounding;
    mode « trace »: the smallest total trace (the simplest certificate, often with small rational entries)."""
    try:
        from cvxopt import matrix as cm
        from cvxopt import solvers
    except ImportError:
        return None
    k = K.nrows()
    nu = len(u0)
    ny = k + 1
    Kf = [[float(K[i, j]) for j in range(nu)] for i in range(k)]
    u0f = [float(v) for v in u0]
    Gs, hs = [], []
    obj = [0.0] * ny
    for bi, (d, N) in enumerate(zip(cols, sizes)):
        if N == 0:
            continue
        G = [[0.0] * (N * N) for _ in range(ny)]
        h = [0.0] * (N * N)
        for (a, b), col in d.items():
            for (r, c) in {(a, b), (b, a)}:
                h[c * N + r] = u0f[col]
                for i in range(k):
                    G[i][c * N + r] = -Kf[i][col]
            if a == b and mode == "trace":
                for i in range(k):
                    obj[i] += Kf[i][col]
        if mode == "interior" and bi == 0:
            for dd in range(N):
                G[k][dd * N + dd] = 1.0
        Gs.append(cm(G))
        hs.append(cm(h, (N, N)))
    lin_rows, lin_h = [], []
    for j in range(nprod + 1):
        col = off + j
        last = col == nu - 1
        row = [-Kf[i][col] for i in range(k)] + [1.0 if (strict and last and mode == "interior") else 0.0]
        lin_rows.append(row)
        lin_h.append(u0f[col] - (1e-4 if (strict and last and mode == "trace") else 0.0))
    lin_rows.append([0.0] * k + [1.0])
    lin_h.append(1.0)
    lin_rows.append([0.0] * k + [-1.0])
    lin_h.append(1.0)
    if mode == "interior":
        obj = [0.0] * k + [-1.0]
    solvers.options["show_progress"] = False
    solvers.options["abstol"] = 1e-11
    solvers.options["reltol"] = 1e-11
    solvers.options["feastol"] = 1e-11
    try:
        sol = solvers.sdp(cm(obj), Gl=cm(lin_rows).T, hl=cm(lin_h), Gs=Gs, hs=hs)
    except (ArithmeticError, ValueError, ZeroDivisionError):
        return None
    if sol.get("x") is None or sol.get("status") not in ("optimal", "unknown"):
        return None
    y = list(sol["x"])
    if mode == "interior" and y[k] < -1e-6:
        return None
    return y[:k]


# ---------------------------------------------------------------- certified numerics
def _iv(e, box):
    """Interval of a term over ℚ: (lo, hi)."""
    from sage.all import QQ
    h = e[0]
    if h == "num":
        v = QQ(str(number(e[1])))
        return v, v
    if h == "var":
        return box[e[1]]
    if h == "neg":
        a = _iv(e[1], box)
        return -a[1], -a[0]
    if h in ("add", "sub", "mul", "div"):
        a, b = _iv(e[1], box), _iv(e[2], box)
        if h == "add":
            return a[0] + b[0], a[1] + b[1]
        if h == "sub":
            return a[0] - b[1], a[1] - b[0]
        if h == "div":
            if b[0] <= 0 <= b[1]:
                raise NoWitness("division by an interval containing 0")
            b = (1 / b[1], 1 / b[0])
        c = [a[0] * b[0], a[0] * b[1], a[1] * b[0], a[1] * b[1]]
        return min(c), max(c)
    if h == "pow":
        k = int(evaluate(e[2], "N"))
        a = _iv(e[1], box)
        if k == 0:
            return QQ(1), QQ(1)
        c = [a[0] ** k, a[1] ** k]
        lo, hi = min(c), max(c)
        if k % 2 == 0 and a[0] < 0 < a[1]:
            lo = QQ(0)
        return lo, hi
    raise NoWitness("unsupported term")


def numeric(req):
    from sage.all import QQ, RealIntervalField, ceil, floor
    F = RealIntervalField(300)
    vals = []
    for a in req["atoms"]:
        if a["f"] == "pi":
            vals.append(F.pi())
        elif a["f"] == "exp1":
            vals.append(F(1).exp())
        elif a["f"] == "log2":
            vals.append(F(2).log())
        else:
            vals.append((F(QQ(int(a["arg"][0])) / QQ(int(a["arg"][1])))).sqrt())
    limit = req.get("digits") or {}
    op, lhs, rhs = req["prop"][1], req["prop"][2], req["prop"][3]
    for k in (2, 3, 4, 6, 9, 12, 16, 20):
        _tick()
        box, bounds = {}, []
        for i, (a, v) in enumerate(zip(req["atoms"], vals)):
            kk = min(k, int(limit.get(a["f"], 9)))
            lo = QQ(ceil(v.lower() * 10 ** kk) - 1) / 10 ** kk
            hi = QQ(floor(v.upper() * 10 ** kk) + 1) / 10 ** kk
            box["t%d" % i] = (lo, hi)
            bounds.append([_frac(lo), _frac(hi)])
        a, b = _iv(lhs, box), _iv(rhs, box)
        sure = {"<": a[1] < b[0], "<=": a[1] <= b[0], ">": a[0] > b[1], ">=": a[0] >= b[1]}[op]
        if sure:
            return {"bounds": bounds, "digits": k}
        wrong = {"<": a[0] >= b[1], "<=": a[0] > b[1], ">": a[1] <= b[0], ">=": a[1] < b[0]}[op]
        if wrong:
            raise NoWitness("false")
    raise NoWitness("the bounds available in Mathlib are not precise enough")


# ---------------------------------------------------------------- witnesses of existence
def _conjuncts(p):
    if p[0] == "and":
        return _conjuncts(p[1]) + _conjuncts(p[2])
    return [p]


def _term_poly(e, R, names):
    from sage.all import QQ
    h = e[0]
    if h == "num":
        return R(QQ(str(number(e[1]))))
    if h == "var":
        return R.gens()[names.index(e[1])]
    if h == "neg":
        return -_term_poly(e[1], R, names)
    if h in ("add", "sub", "mul"):
        a, b = _term_poly(e[1], R, names), _term_poly(e[2], R, names)
        return a + b if h == "add" else (a - b if h == "sub" else a * b)
    if h == "pow":
        return _term_poly(e[1], R, names) ** int(evaluate(e[2], "N"))
    raise ValueError("not a polynomial")


def _values(dom, size):
    """Candidate values by increasing size: 0, 1, -1, 2, … (and small fractions for ℚ / ℝ)."""
    from fractions import Fraction
    if dom == "N":
        return list(range(size))
    if dom == "Z":
        out = [0]
        for k in range(1, size):
            out += [k, -k]
        return out
    seen, out = set(), []
    for h in range(0, size):
        for q in range(1, h + 2):
            for p in (h, -h):
                v = Fraction(p, q)
                if v not in seen and max(abs(v.numerator), v.denominator) <= max(h, 1):
                    seen.add(v)
                    out.append(v)
    return out


def exists(req):
    from fractions import Fraction
    from sage.all import QQ, ZZ, gcd, inverse_mod, xgcd
    names = [v[0] for v in req["vars"]]
    dom, body, n = req["dom"], req["body"], len(req["vars"])
    exact = dom in ("N", "Z")

    def fits(vals):
        try:
            vals = [Fraction(int(QQ(v).numerator()), int(QQ(v).denominator())) for v in vals]
        except (TypeError, ValueError):
            return None
        if exact and any(v.denominator != 1 for v in vals):
            return None
        if dom == "N" and any(v < 0 for v in vals):
            return None
        env = {nm: (int(v) if exact else v) for nm, v in zip(names, vals)}
        try:
            if holds(body, dom, env):
                return {"values": [[str(v.numerator), str(v.denominator)] for v in vals]}
        except (Unsupported, ZeroDivisionError, OverflowError):
            return None
        return None
    conj = _conjuncts(body)
    R = _ring("QQ", n)
    # 1. one linear congruence in one unknown: c1·x + c0 ≡ 0 (mod m)
    if n == 1 and len(conj) == 1 and exact:
        a = conj[0]
        try:
            if a[0] == "modeq":
                m, p = evaluate(a[2], dom), _term_poly(a[3], R, names) - _term_poly(a[4], R, names)
            elif a[0] == "rel" and a[1] == "=" and a[2][0] == "mod":
                m, p = evaluate(a[2][2], dom), _term_poly(a[2][1], R, names) - _term_poly(a[3], R, names)
            else:
                m, p = 0, None
            if p is not None and m > 1 and p.degree() == 1:
                x = R.gens()[0]
                c1, c0 = ZZ(p.monomial_coefficient(x)), ZZ(p.constant_coefficient())
                g = gcd(c1, m)
                if c0 % g == 0:
                    mm = m // g
                    sol = (-(c0 // g) * inverse_mod(c1 // g, mm)) % mm if mm > 1 else 0
                    for cand in (sol, sol + mm, sol + m):
                        got = fits([cand])
                        if got:
                            return got
        except (ValueError, TypeError, ZeroDivisionError, Unsupported):
            pass
    # 2. one linear equation over ℤ: Bézout
    if dom == "Z" and len(conj) == 1 and conj[0][0] == "rel" and conj[0][1] == "=":
        try:
            p = _term_poly(conj[0][2], R, names) - _term_poly(conj[0][3], R, names)
            if p.degree() == 1:
                cs = [ZZ(p.monomial_coefficient(x)) for x in R.gens()]
                c = -ZZ(p.constant_coefficient())
                g, co = ZZ(0), []
                for a in cs:
                    g, s, t = xgcd(g, a)
                    co = [s * v for v in co] + [t]
                if g != 0 and c % g == 0:
                    got = fits([v * (c // g) for v in co])
                    if got:
                        return got
        except (ValueError, TypeError, Unsupported):
            pass
    # 3. polynomial equations with finitely many rational solutions
    eqs = []
    for a in conj:
        if a[0] == "rel" and a[1] == "=":
            try:
                eqs.append(_term_poly(a[2], R, names) - _term_poly(a[3], R, names))
            except (ValueError, TypeError, Unsupported):
                pass
    eqs = [p for p in eqs if p != 0]
    if eqs:
        try:
            I = R.ideal(eqs)
            if I.dimension() == 0:
                for pt in I.variety(QQ):
                    got = fits([pt[x] for x in R.gens()])
                    if got:
                        return got
            elif n == 1:
                for r, _m in eqs[0].univariate_polynomial().roots(QQ):
                    got = fits([r])
                    if got:
                        return got
        except (ValueError, TypeError, ArithmeticError, NotImplementedError, AttributeError):
            pass
    # 4. bounded search, small values first
    budget = int(req.get("box") or 200000)
    tried, size, prev = 0, 2, 0
    while tried < budget:
        vals = _values(dom, size)
        if len(vals) ** n > 4 * budget:
            break
        old = set(_values(dom, prev)) if prev else set()
        for tup in itertools.product(vals, repeat=n):
            if prev and all(v in old for v in tup):
                continue
            tried += 1
            if tried % 512 == 0:
                _tick()
            got = fits(list(tup))
            if got:
                return got
        prev, size = size, size * 2
    raise NoWitness("no witness found in the search range")


# ---------------------------------------------------------------- entry
def _run(req):
    _DEADLINE[0] = time.time() + float(req.get("seconds") or 30)
    kind = req.get("kind")
    if kind == "pratt":
        return {"cert": pratt(int(req["n"]), int(req.get("small") or 100000))}
    if kind == "factor":
        return factor(int(req["n"]))
    if kind == "ideal":
        return ideal(req)
    if kind == "linear":
        return linear(req)
    if kind == "sos":
        return sos(req)
    if kind == "numeric":
        return numeric(req)
    if kind == "exists":
        return exists(req)
    raise NoWitness("unknown kind")


def _main(text):
    t0 = time.time()
    try:
        out = dict(_run(json.loads(text)), ok=True)
    except NoWitness as e:
        out = {"ok": False, "reason": str(e)}
    except Exception as e:  # noqa: BLE001 (anything else is a failed computation, reported as such)
        out = {"ok": False, "reason": "error", "detail": (type(e).__name__ + ": " + str(e))[:300]}
    out["seconds"] = round(time.time() - t0, 3)
    print("MADALEAN_CERT " + json.dumps(out))


_main(_madalean_cert_req)  # noqa: F821 (set by the caller)
