"""Static SVG of a Calcul figure (FigureSpec, web/src/lib/figure/spec.ts) for the published site: curves (explicit
y = f(x), implicit F(x, y) = 0, polar r = f(θ), parametric (x(t), y(t))), points and graphs, with axes and grid.
Same expression grammar as web/src/lib/figure/expr.ts (a small parser, never `eval`). Geometric constructions are
drawn by the app itself (a Figure cell carries its own SVG); here free points are drawn and the rest is listed in the
text description. Pure Python, no dependency: used by the publication template at build time (no client script)."""
from __future__ import annotations

import html
import math
import re

E = html.escape
W, H = 640, 400
COLORS = ("#1f4e79", "#b35c00", "#1b7f3b", "#8e2c8a", "#a61b29", "#00727a")

FUNCS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos, "atan": math.atan,
         "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan, "sinh": math.sinh, "cosh": math.cosh,
         "tanh": math.tanh, "exp": math.exp, "ln": math.log, "log": math.log, "log10": math.log10,
         "sqrt": math.sqrt, "abs": abs, "floor": math.floor, "ceil": math.ceil,
         "sign": lambda v: (v > 0) - (v < 0)}
CONSTS = {"pi": math.pi, "π": math.pi, "e": math.e}
VARS = ("x", "y", "t", "θ", "theta", "n")


class ExprError(ValueError):
    pass


_TOK = re.compile(r"\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-zα-ωΑ-Ω_][A-Za-z0-9α-ωΑ-Ω_']*)|"
                  r"([-+*/^(),]))")


def _tokens(src: str) -> list[tuple[str, str]]:
    s = re.sub(r"[−–]", "-", src).replace("·", "*").replace("×", "*").replace("**", "^").replace("²", "^2") \
        .replace("³", "^3")
    out, i = [], 0
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        m = _TOK.match(s, i)
        if not m or m.end() == i:
            raise ExprError(f"unexpected {s[i]!r}")
        out.append(("num", m.group(1)) if m.group(1) else ("id", m.group(2)) if m.group(2) else ("op", m.group(3)))
        i = m.end()
    return out


def compile_expr(src: str):
    """(fn(env) -> float, set of variables). Grammar of expr.ts: + - * / ^, unary minus, implicit multiplication."""
    toks = _tokens(src)
    pos = [0]
    used: set[str] = set()

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def is_op(v):
        p = peek()
        return p is not None and p[0] == "op" and p[1] == v

    def expect(v):
        if not is_op(v):
            raise ExprError(f"{v!r} expected")
        pos[0] += 1

    def ident(n):
        if n == "theta":
            n = "θ"
        if n in VARS or n == "θ":
            used.add(n)
            return lambda env, n=n: env.get(n, math.nan)
        if n in CONSTS:
            return lambda env, v=CONSTS[n]: v
        parts, rest = [], n                      # « xy » = x·y, « tpi » = t·π
        keys = ["pi", "π", "theta"] + sorted(VARS, key=len, reverse=True) + ["e"]
        while rest:
            k = next((k for k in keys if rest.startswith(k)), None)
            if k is None:
                raise ExprError(f"unknown name {n!r}")
            parts.append(ident(k))
            rest = rest[len(k):]
        f = parts[0]
        for g in parts[1:]:
            f = (lambda a, b: lambda env: a(env) * b(env))(f, g)
        return f

    def primary():
        p = peek()
        if p is None:
            raise ExprError("incomplete expression")
        if p[0] == "num":
            pos[0] += 1
            v = float(p[1])
            return lambda env: v
        if p[0] == "id":
            pos[0] += 1
            if p[1] in FUNCS:
                fn = FUNCS[p[1]]
                if is_op("("):
                    pos[0] += 1
                    a = expr()
                    expect(")")
                    return lambda env: fn(a(env))
                if is_op("^"):                    # sin^2(x)
                    pos[0] += 1
                    e = power()
                    a = primary()
                    return lambda env: _pow(fn(a(env)), e(env))
                a = power()
                return lambda env: fn(a(env))
            return ident(p[1])
        if p[1] == "(":
            pos[0] += 1
            a = expr()
            expect(")")
            return a
        raise ExprError(f"unexpected {p[1]!r}")

    def power():
        a = primary()
        if is_op("^"):
            pos[0] += 1
            b = unary()
            return lambda env: _pow(a(env), b(env))
        return a

    def unary():
        if is_op("-"):
            pos[0] += 1
            a = unary()
            return lambda env: -a(env)
        if is_op("+"):
            pos[0] += 1
            return unary()
        return power()

    def starts_primary():
        p = peek()
        return p is not None and (p[0] != "op" or p[1] == "(")

    def term():
        a = unary()
        while True:
            if is_op("*") or is_op("/"):
                op = peek()[1]
                pos[0] += 1
                b = unary()
                a = (lambda a, b: lambda env: a(env) * b(env))(a, b) if op == "*" else \
                    (lambda a, b: lambda env: _div(a(env), b(env)))(a, b)
            elif starts_primary():
                b = power()
                a = (lambda a, b: lambda env: a(env) * b(env))(a, b)
            else:
                return a

    def expr():
        a = term()
        while is_op("+") or is_op("-"):
            op = peek()[1]
            pos[0] += 1
            b = term()
            a = (lambda a, b: lambda env: a(env) + b(env))(a, b) if op == "+" else \
                (lambda a, b: lambda env: a(env) - b(env))(a, b)
        return a

    if not toks:
        raise ExprError("empty expression")
    fn = expr()
    if pos[0] < len(toks):
        raise ExprError(f"unexpected {toks[pos[0]][1]!r}")

    def safe(env):
        try:
            v = fn(env)
            return float(v) if isinstance(v, (int, float)) else math.nan
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return math.nan
    return safe, used


def _div(a, b):
    return a / b if b else math.nan


def _pow(x, p):
    if x < 0 and not float(p).is_integer():
        q = 1 / p if p else 0
        if q and float(q).is_integer() and abs(q) % 2 == 1:
            return -((-x) ** p)
        return math.nan
    try:
        r = x ** p
    except (OverflowError, ZeroDivisionError):
        return math.nan
    return r if isinstance(r, float | int) else math.nan


def _split_top(s: str, sep: str = ",") -> list[str]:
    out, depth, start = [], 0, 0
    for i, c in enumerate(s):
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == sep and depth == 0:
            out.append(s[start:i])
            start = i + 1
    out.append(s[start:])
    return [x.strip() for x in out]


def parse_curve(src: str) -> tuple[str, object]:
    """('explicit', f) | ('implicit', F) | ('polar', r) | ('parametric', (X, Y)). Raises ExprError."""
    s = src.strip()
    parts = _split_top(s)
    dom = None
    m = re.match(r"^([A-Za-zθ]+)\s*(?:in|∈)\s*\[(.+),(.+)\]$", parts[-1]) if len(parts) > 1 else None
    if m:
        a, _ = compile_expr(m.group(2))
        b, _ = compile_expr(m.group(3))
        dom = (a({}), b({}))
        parts = parts[:-1]
    if len(parts) == 1 and re.fullmatch(r"\(.*\)", parts[0]):
        inner = _split_top(parts[0][1:-1])
        if len(inner) == 2:
            return "parametric", (compile_expr(inner[0])[0], compile_expr(inner[1])[0], dom or (-10, 10))
    if len(parts) == 2:
        px, py = re.match(r"^x\s*=(.+)$", parts[0]), re.match(r"^y\s*=(.+)$", parts[1])
        if px and py:
            return "parametric", (compile_expr(px.group(1))[0], compile_expr(py.group(1))[0], dom or (-10, 10))
    if len(parts) != 1:
        raise ExprError("unexpected ','")
    eq = _split_top(parts[0], "=")
    if len(eq) > 2:
        raise ExprError("too many '='")
    if len(eq) == 2:
        left, right = eq
        if re.fullmatch(r"r|r\s*\(\s*(θ|theta|t)\s*\)", left):
            return "polar", (compile_expr(right)[0], dom or (0, 4 * math.pi))
        if re.fullmatch(r"y|[a-z]\s*\(\s*x\s*\)", left):
            f, used = compile_expr(right)
            if "y" not in used:
                return "explicit", (f, dom)
        lf, _ = compile_expr(left)
        rf, _ = compile_expr(right)
        return "implicit", lambda env: lf(env) - rf(env)
    f, used = compile_expr(parts[0])
    if "y" in used:
        return "implicit", f
    if "θ" in used and "x" not in used:
        return "polar", (f, dom or (0, 4 * math.pi))
    return "explicit", (f, dom)


def _sample(fx, a: float, b: float, n: int, view: dict) -> list[list[tuple[float, float]]]:
    """Polylines of t ↦ (x, y), cut at undefined points and at jumps far outside the view."""
    h = view["ymax"] - view["ymin"]
    lines, cur = [], []
    for i in range(n + 1):
        t = a + (b - a) * i / n
        x, y = fx(t)
        if not (math.isfinite(x) and math.isfinite(y)) or abs(y - (view["ymin"] + view["ymax"]) / 2) > 20 * h:
            if len(cur) > 1:
                lines.append(cur)
            cur = []
            continue
        if cur and abs(y - cur[-1][1]) > 2 * h:                     # asymptote: do not join the two branches
            if len(cur) > 1:
                lines.append(cur)
            cur = []
        cur.append((x, y))
    if len(cur) > 1:
        lines.append(cur)
    return lines


def _implicit(F, view: dict, nx: int = 120, ny: int = 80) -> list[list[tuple[float, float]]]:
    """Segments of F(x, y) = 0 by marching squares (sign changes on a grid, linear interpolation)."""
    xs = [view["xmin"] + (view["xmax"] - view["xmin"]) * i / nx for i in range(nx + 1)]
    ys = [view["ymin"] + (view["ymax"] - view["ymin"]) * j / ny for j in range(ny + 1)]
    val = [[F({"x": x, "y": y}) for x in xs] for y in ys]
    segs = []

    def cross(p, q, vp, vq):
        t = vp / (vp - vq) if vp != vq else 0.5
        return p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
    for j in range(ny):
        for i in range(nx):
            c = [((xs[i], ys[j]), val[j][i]), ((xs[i + 1], ys[j]), val[j][i + 1]),
                 ((xs[i + 1], ys[j + 1]), val[j + 1][i + 1]), ((xs[i], ys[j + 1]), val[j + 1][i])]
            if not all(math.isfinite(v) for _p, v in c):
                continue
            pts = []
            for k in range(4):
                (p, vp), (q, vq) = c[k], c[(k + 1) % 4]
                if (vp < 0) != (vq < 0):
                    pts.append(cross(p, q, vp, vq))
            if len(pts) >= 2:
                segs.append(pts[:2])
                if len(pts) == 4:
                    segs.append(pts[2:])
    return segs


def _nice_step(span: float) -> float:
    raw = span / 8
    p = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    return next(s * p for s in (1, 2, 5, 10) if s * p >= raw)


def _num(v: float) -> str:
    return f"{v:.4g}".replace("-", "−")


def render(spec: dict, lang: str = "fr") -> tuple[str, str]:
    """(svg, description) of a FigureSpec. Never raises on bad input: what cannot be drawn is described."""
    fr = lang == "fr"
    spec = spec if isinstance(spec, dict) else {}
    raw_view = spec.get("view") if isinstance(spec.get("view"), dict) else {}
    view = {k: float(raw_view.get(k, d)) if isinstance(raw_view.get(k, d), (int, float)) else d
            for k, d in (("xmin", -8.0), ("xmax", 8.0), ("ymin", -5.0), ("ymax", 5.0))}
    if not (view["xmin"] < view["xmax"] and view["ymin"] < view["ymax"]):
        view = {"xmin": -8.0, "xmax": 8.0, "ymin": -5.0, "ymax": 5.0}

    def X(x):
        return (x - view["xmin"]) / (view["xmax"] - view["xmin"]) * W

    def Y(y):
        return H - (y - view["ymin"]) / (view["ymax"] - view["ymin"]) * H

    def path(pts):
        return "M" + " L".join(f"{X(x):.1f} {Y(y):.1f}" for x, y in pts)
    title = str(spec.get("title") or "")[:200]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="DejaVu Sans,sans-serif" font-size="11">', f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    desc: list[str] = []
    if spec.get("grid", True):
        sx, sy = _nice_step(view["xmax"] - view["xmin"]), _nice_step(view["ymax"] - view["ymin"])
        g = []
        k = math.ceil(view["xmin"] / sx)
        while k * sx <= view["xmax"] and len(g) < 60:
            g.append(f"M{X(k * sx):.1f} 0V{H}")
            k += 1
        k = math.ceil(view["ymin"] / sy)
        while k * sy <= view["ymax"] and len(g) < 120:
            g.append(f"M0 {Y(k * sy):.1f}H{W}")
            k += 1
        out.append(f'<path d="{" ".join(g)}" stroke="#e3e6ea" stroke-width="1" fill="none"/>')
    if spec.get("axes", True):
        ax = []
        if view["ymin"] <= 0 <= view["ymax"]:
            ax.append(f"M0 {Y(0):.1f}H{W}")
        if view["xmin"] <= 0 <= view["xmax"]:
            ax.append(f"M{X(0):.1f} 0V{H}")
        if ax:
            out.append(f'<path d="{" ".join(ax)}" stroke="#555b63" stroke-width="1.2" fill="none"/>')
        out.append(f'<text x="4" y="{H - 4}" fill="#555b63">x ∈ [{_num(view["xmin"])}, {_num(view["xmax"])}], '
                   f'y ∈ [{_num(view["ymin"])}, {_num(view["ymax"])}]</text>')
    drawn = skipped = 0
    curves = spec.get("curves") if isinstance(spec.get("curves"), list) else []
    for i, c in enumerate(curves[:50]):
        if not isinstance(c, dict) or c.get("hidden") or not isinstance(c.get("expr"), str):
            continue
        expr = c["expr"][:2000]
        color = c.get("color") if isinstance(c.get("color"), str) and re.fullmatch(r"#[0-9a-fA-F]{3,8}", c["color"]) \
            else COLORS[i % len(COLORS)]
        try:
            kind, f = parse_curve(expr)
        except ExprError:
            skipped += 1
            desc.append((f"courbe non dessinée : {expr}" if fr else f"curve not drawn: {expr}"))
            continue
        if kind == "explicit":
            fn, dom = f
            a, b = dom or (view["xmin"], view["xmax"])
            lines = _sample(lambda x: (x, fn({"x": x})), max(a, view["xmin"]), min(b, view["xmax"]), 800, view)
        elif kind == "polar":
            fn, (a, b) = f
            lines = _sample(lambda t: (fn({"θ": t, "t": t}) * math.cos(t), fn({"θ": t, "t": t}) * math.sin(t)),
                            a, b, 1200, view)
        elif kind == "parametric":
            fx, fy, (a, b) = f
            lines = _sample(lambda t: (fx({"t": t, "θ": t}), fy({"t": t, "θ": t})), a, b, 1200, view)
        else:
            lines = _implicit(f, view)
        if lines:
            drawn += 1
            out.append(f'<path d="{" ".join(path(p) for p in lines)}" stroke="{color}" stroke-width="2" '
                       f'fill="none" stroke-linejoin="round"/>')
        label = c.get("label") if isinstance(c.get("label"), str) else ""
        desc.append((label + " : " if label else "") + expr)
    g = spec.get("graph") if isinstance(spec.get("graph"), dict) else None
    if g and isinstance(g.get("pos"), dict):
        pos = {str(k): v for k, v in g["pos"].items() if isinstance(v, list) and len(v) == 2
               and all(isinstance(t, (int, float)) for t in v)}
        edges = [e for e in (g.get("edges") if isinstance(g.get("edges"), list) else [])[:3000] if isinstance(e, list) and len(e) >= 2
                 and str(e[0]) in pos and str(e[1]) in pos]
        if edges:
            out.append('<path d="' + " ".join(f"M{X(pos[str(a)][0]):.1f} {Y(pos[str(a)][1]):.1f} "
                                                f"L{X(pos[str(b)][0]):.1f} {Y(pos[str(b)][1]):.1f}"
                                                for a, b, *_ in edges) + '" stroke="#555b63" stroke-width="1.4"/>')
        for v, (x, y) in list(pos.items())[:500]:
            out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="5" fill="#1f4e79"/>'
                       f'<text x="{X(x) + 7:.1f}" y="{Y(y) - 7:.1f}" fill="#222">{E(v[:40])}</text>')
        n_v = len(g.get("vertices") or pos)
        desc.append(f"graphe : {n_v} sommets, {len(edges)} arêtes" if fr else
                    f"graph: {n_v} vertices, {len(edges)} edges")
    lst = lambda k: spec.get(k) if isinstance(spec.get(k), list) else []  # noqa: E731
    pts = [p for p in lst("points")[:2000] if isinstance(p, dict)
           and isinstance(p.get("x"), (int, float)) and isinstance(p.get("y"), (int, float))]
    pts += [{"x": o["x"], "y": o["y"], "label": o.get("name", "")} for o in lst("objects")[:500]
            if isinstance(o, dict) and o.get("kind") == "point" and not o.get("hidden")
            and isinstance(o.get("x"), (int, float)) and isinstance(o.get("y"), (int, float))]
    for p in pts:
        out.append(f'<circle cx="{X(p["x"]):.1f}" cy="{Y(p["y"]):.1f}" r="3.5" fill="#a61b29"/>')
        if p.get("label"):
            out.append(f'<text x="{X(p["x"]) + 6:.1f}" y="{Y(p["y"]) - 6:.1f}" fill="#222">'
                       f'{E(str(p["label"])[:40])}</text>')
    if pts:
        desc.append(f"{len(pts)} point(s)")
    others = [o for o in lst("objects") if isinstance(o, dict) and o.get("kind") != "point"]
    if others:
        desc.append((f"{len(others)} objet(s) de géométrie : voir le carnet" if fr else
                     f"{len(others)} geometry object(s): see the notebook"))
    out.append("</svg>")
    head = title or ("Figure" if fr else "Figure")
    return "\n".join(out) + "\n", head + (" — " + " ; ".join(desc) if desc else "")
