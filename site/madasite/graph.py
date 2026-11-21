"""Blueprint dependency graph -> static SVG (layered layout computed at build time, no client script).

Nodes: [{id, label, sub, status, href}], edges: (dep, user) meaning `user` uses `dep`. Dependencies are drawn above
the results that use them; arrows point from a dependency to its user. Colours come from CSS classes (`st-<status>`),
so light/dark themes apply; each status also has a distinct border pattern and a text mark (not colour alone)."""
from __future__ import annotations

import html

NODE_W, NODE_H, GAP_X, GAP_Y, PAD = 210, 58, 34, 64, 16
MARKS = {"verified": "✓", "proved": "(✓)", "defined": "≔", "statement": "◇", "stated": "…", "blocked": "✕"}


def _layers(ids: list[str], deps: dict[str, list[str]]) -> dict[str, int]:
    layer: dict[str, int] = {}
    visiting: set[str] = set()

    def f(n: str) -> int:
        if n in layer:
            return layer[n]
        if n in visiting:           # cycle: break it
            return 0
        visiting.add(n)
        v = 1 + max((f(d) for d in deps.get(n, []) if d in deps), default=-1)
        visiting.discard(n)
        layer[n] = v
        return v
    for n in ids:
        f(n)
    return layer


def _trim(s: str, k: int) -> str:
    return s if len(s) <= k else s[:k - 1] + "…"


def render_svg(nodes: list[dict], edges: list[tuple[str, str]], title: str, desc: str) -> str:
    ids = [n["id"] for n in nodes]
    byid = {n["id"]: n for n in nodes}
    deps: dict[str, list[str]] = {i: [] for i in ids}
    for d, u in edges:
        if d in byid and u in byid:
            deps[u].append(d)
    layer = _layers(ids, deps)
    rows: dict[int, list[str]] = {}
    for i in ids:
        rows.setdefault(layer[i], []).append(i)
    # barycentre ordering, a few sweeps
    pos: dict[str, float] = {}
    for L in sorted(rows):
        for k, i in enumerate(rows[L]):
            pos[i] = k
    users: dict[str, list[str]] = {i: [] for i in ids}
    for u, ds in deps.items():
        for d in ds:
            users[d].append(u)
    for _ in range(4):
        for L in sorted(rows)[1:]:
            rows[L].sort(key=lambda i: (sum(pos[d] for d in deps[i]) / len(deps[i])) if deps[i] else pos[i])
            for k, i in enumerate(rows[L]):
                pos[i] = k
        for L in sorted(rows, reverse=True)[1:]:
            rows[L].sort(key=lambda i: (sum(pos[u] for u in users[i]) / len(users[i])) if users[i] else pos[i])
            for k, i in enumerate(rows[L]):
                pos[i] = k
    width_n = max(len(r) for r in rows.values()) if rows else 1
    W = PAD * 2 + width_n * NODE_W + (width_n - 1) * GAP_X
    H = PAD * 2 + len(rows) * NODE_H + (len(rows) - 1) * GAP_Y
    xy: dict[str, tuple[float, float]] = {}
    for L, r in rows.items():
        row_w = len(r) * NODE_W + (len(r) - 1) * GAP_X
        x0 = (W - row_w) / 2
        for k, i in enumerate(r):
            xy[i] = (x0 + k * (NODE_W + GAP_X), PAD + L * (NODE_H + GAP_Y))
    out = [f'<svg class="bp-graph" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
           f'width="{W:.0f}" height="{H:.0f}" role="group" aria-labelledby="bpg-title bpg-desc">',
           f'<title id="bpg-title">{html.escape(title)}</title><desc id="bpg-desc">{html.escape(desc)}</desc>',
           '<defs><marker id="bp-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="bp-arrowhead"/></marker></defs>',
           '<g class="bp-edges" aria-hidden="true">']
    for u, ds in deps.items():
        for d in ds:
            x1, y1 = xy[d][0] + NODE_W / 2, xy[d][1] + NODE_H
            x2, y2 = xy[u][0] + NODE_W / 2, xy[u][1] - 2
            my = (y1 + y2) / 2
            ok = byid[d]["status"] in ("verified", "defined")
            out.append(f'<path class="bp-edge{"" if ok else " bp-edge-open"}" d="M{x1:.1f} {y1:.1f}C{x1:.1f} {my:.1f} '
                       f'{x2:.1f} {my:.1f} {x2:.1f} {y2:.1f}" marker-end="url(#bp-arrow)"/>')
    out.append("</g><g class=\"bp-nodes\">")
    for i in ids:
        n = byid[i]
        x, y = xy[i]
        st = n["status"]
        mark = MARKS.get(st, "")
        aria = f'{n["label"]} — {n.get("sub", "")} — {n.get("status_text", st)}'
        out.append(f'<a href="{html.escape(n["href"])}" class="bp-node st-{st}" aria-label="{html.escape(aria)}">'
                   f'<rect x="{x:.1f}" y="{y:.1f}" width="{NODE_W}" height="{NODE_H}" rx="8"/>'
                   f'<text x="{x + 12:.1f}" y="{y + 23:.1f}" class="bp-label">{html.escape(_trim(n["label"], 24))}</text>'
                   f'<text x="{x + NODE_W - 12:.1f}" y="{y + 23:.1f}" class="bp-mark" text-anchor="end">{mark}</text>'
                   f'<text x="{x + 12:.1f}" y="{y + 44:.1f}" class="bp-sub">{html.escape(_trim(n.get("sub", ""), 30))}</text>'
                   "</a>")
    out.append("</g></svg>")
    return "".join(out)
