<script lang="ts">
  // Interactive figure of a Calcul « Figure » cell: curves (explicit, implicit, parametric, polar, sequences) and
  // dynamic geometry with Fikajiana's named tools. Pan (drag), wheel and pinch zoom, double-click to reset; arrows
  // move the chosen point. Exports PNG / SVG / TikZ and exact Sage code. Spec contract: lib/figure/spec.ts.
  import { untrack } from 'svelte';
  import { Figure, intersections, paramOf, conicAt, lineEq, type Obj, type Val } from '../../lib/figure/geometry';
  import { render, fitView, toWorld, toScreen, sampled, type Prim } from '../../lib/figure/render';
  import { parseCurve, valueTable, nearestOnCurve, niceStep, type View } from '../../lib/figure/curves';
  import { TOOLS, GROUPS, toolById, type Tool, type Want, type Group } from '../../lib/figure/tools';
  import { toSVG, toPNG, toTikZ, toSage } from '../../lib/figure/export';
  import { fmtNum, decimal } from '../../lib/figure/exact';
  import { ft } from '../../lib/figure/strings';
  import type { FigureSpec } from '../../lib/figure/spec';

  let { spec, editable = true, onchange, onsage, label }: {
    spec: FigureSpec; editable?: boolean; onchange?: (s: FigureSpec) => void; onsage?: (code: string) => void; label: string;
  } = $props();

  const uid = `fig-${Math.random().toString(36).slice(2, 8)}`;
  let fig = $state.raw(untrack(() => Figure.load(spec)));
  let last = untrack(() => JSON.stringify(spec));
  let rev = $state(0);
  let view = $state<View>(untrack(() => ({ ...fig.view })));
  let w = $state(640);
  const h = $derived(Math.round(Math.min(560, Math.max(240, w * 0.62))));
  const frame = $derived({ w: Math.max(200, w), h, view: fitView(view, Math.max(200, w), h) });
  const prims = $derived.by(() => { void rev; return render(fig, frame); });
  let group = $state<Group>('base');
  let tool = $state<Tool>(TOOLS[0]!);
  let picks = $state<string[]>([]);
  let pending = $state<{ kind: string; parents: string[]; number: NonNullable<Tool['number']>; value: string } | null>(null);
  let selected = $state<string | null>(null);
  let status = $state('');
  let reading = $state<{ x: number; y: number; sx: number; sy: number } | null>(null);
  let curveInput = $state('');
  let curveErr = $state('');
  let tableFor = $state<string | null>(null);
  let svgEl: SVGSVGElement | undefined = $state();

  $effect(() => {                       // a new spec from outside (server, another device): reload
    const j = JSON.stringify(spec);
    if (j !== last) { last = j; untrack(() => { fig = Figure.load(spec); view = { ...fig.view }; picks = []; rev++; }); }
  });
  function emit() {
    fig.view = { ...view };
    const s = fig.toSpec();
    last = JSON.stringify(s);
    onchange?.(s);
  }
  const bump = () => { rev++; };

  // ------------------------------------------------------------ status
  const wantOf = (): Want | null => {
    if (tool.id === 'polygon') return 'point';
    if (tool.freeOrder) { const done = picks.map((id) => fig.byId(id)?.val?.t); const rest = [...tool.wants]; for (const d of done) { const i = rest.findIndex((x) => fits(x, d)); if (i >= 0) rest.splice(i, 1); } return rest[0] ?? null; }
    return tool.wants[picks.length] ?? null;
  };
  const statusText = $derived.by(() => {
    void rev;
    const name = ft(`t.${tool.id}`);
    if (pending) return ft('statusFree', { tool: name, want: ft(`n.${pending.number}`) });
    if (tool.id === 'move') return ft('statusFree', { tool: name, want: ft('w.move') });
    if (tool.id === 'slider') return ft('statusFree', { tool: name, want: ft('w.slider') });
    if (tool.id === 'polygon') return ft('statusFree', { tool: name, want: ft(picks.length >= 3 ? 'w.polygonMore' : 'w.point') });
    const want = wantOf();
    return want ? ft('status', { tool: name, step: picks.length + 1, n: tool.wants.length, want: ft(`w.${want}`) }) : name;
  });

  // ------------------------------------------------------------ hit testing (screen pixels)
  const scale = () => frame.w / (frame.view.xmax - frame.view.xmin);
  const tol = () => (matchMedia?.('(pointer: coarse)').matches ? 22 : 12);
  function distTo(v: Val, x: number, y: number): number {
    switch (v.t) {
      case 'point': return Math.hypot(v.x - x, v.y - y);
      case 'line': { const t = paramOf(v, { x, y })!; const s = v.sub === 'line' ? t : v.sub === 'ray' ? Math.max(0, t) : Math.max(0, Math.min(1, t)); return Math.hypot(v.p.x + s * v.d.x - x, v.p.y + s * v.d.y - y); }
      case 'circle': return Math.abs(Math.hypot(x - v.c.x, y - v.c.y) - v.r);
      case 'conic': { const f = conicAt(v.k, x, y), gx = 2 * v.k[0]! * x + v.k[1]! * y + v.k[3]!, gy = v.k[1]! * x + 2 * v.k[2]! * y + v.k[4]!; return Math.abs(f) / (Math.hypot(gx, gy) || 1); }
      case 'polygon': { let best = Infinity; v.pts.forEach((p, i) => { const q = v.pts[(i + 1) % v.pts.length]!; best = Math.min(best, distTo({ t: 'line', p, d: { x: q.x - p.x, y: q.y - p.y }, sub: 'segment' }, x, y)); }); return best; }
      case 'locus': return Math.min(Infinity, ...v.lines.flat().map((p) => Math.hypot(p.x - x, p.y - y)));
      default: return Infinity;
    }
  }
  function fits(want: Want, t: Val['t'] | undefined, o?: Obj): boolean {
    if (!t) return false;
    switch (want) {
      case 'point': case 'point_existing': return t === 'point';
      case 'glider': return o?.kind === 'point_on';
      case 'line': case 'vector': return t === 'line';
      case 'circle_or_conic': return t === 'circle' || t === 'conic';
      case 'curve': return t === 'line' || t === 'circle' || t === 'conic' || t === 'polygon';
      case 'polygon': return t === 'polygon';
      case 'object': return t !== 'number';
      case 'length': return t === 'line' || t === 'circle' || t === 'polygon' || t === 'point';
      case 'point_or_line': return t === 'point' || t === 'line';
      case 'surface': return t === 'polygon' || t === 'circle' || t === 'conic';
    }
  }
  function hit(x: number, y: number, ok: (o: Obj) => boolean): Obj | null {
    const lim = tol() / scale();
    let best: Obj | null = null, bd = Infinity;
    for (const o of fig.objects) {
      if (!o.val || o.hidden || !ok(o)) continue;
      const d = distTo(o.val, x, y) - (o.val.t === 'point' ? lim * 0.4 : 0);   // points win over the lines under them
      if (d < lim && d < bd) { bd = d; best = o; }
    }
    return best;
  }
  /** Short coordinates (exact rationals for Sage): 2 decimals, or the grid's half step when close to it. */
  function snap(x: number, y: number): [number, number] {
    const d = Math.max(0, 2 - Math.floor(Math.log10(Math.max(1e-9, frame.view.xmax - frame.view.xmin))));
    let px = +x.toFixed(d), py = +y.toFixed(d);
    if (fig.grid) { const g = niceStep((frame.view.xmax - frame.view.xmin) / 16) / 2; const gx = Math.round(x / g) * g, gy = Math.round(y / g) * g; if (Math.hypot(gx - x, gy - y) * scale() < 8) { px = +gx.toPrecision(10); py = +gy.toPrecision(10); } }
    return [px, py];
  }
  /** A point where the person touched: an existing point, a crossing, a point on an object, else a free point. */
  function pointAt(x: number, y: number): Obj {
    const p = hit(x, y, (o) => o.val?.t === 'point');
    if (p) return p;
    const lim = tol() / scale();
    const near = fig.objects.filter((o) => o.val && !o.hidden && fits('curve', o.val.t) && distTo(o.val, x, y) < lim);
    for (let i = 0; i < near.length; i++) for (let j = i + 1; j < near.length; j++) {
      const pts = intersections(near[i]!.val!, near[j]!.val!);
      const k = pts.findIndex((q) => Math.hypot(q.x - x, q.y - y) < lim);
      if (k >= 0) return fig.add('intersection', [near[i]!.id, near[j]!.id], { params: [k] });
    }
    const on = near[0];
    if (on?.val) {
      const s = on.val;
      if (s.t === 'conic') return fig.add('point_on', [on.id], { x, y });
      const t = paramOf(s, { x, y });
      if (t !== null) return fig.add('point_on', [on.id], { params: [t] });
    }
    const [px, py] = snap(x, y);
    return fig.add('point', [], { x: px, y: py });
  }

  // ------------------------------------------------------------ constructions
  function choose(t: Tool) { tool = t; picks = []; pending = null; status = ''; }
  function tap(x: number, y: number) {
    if (!editable) return;
    if (tool.id === 'slider') { const o = fig.add('slider', [], { params: [1, -5, 5, 0.1] }); done(o.name); return; }
    const want = wantOf();
    if (!want) return;
    let o: Obj | null;
    if (want === 'point') o = pointAt(x, y);
    else o = hit(x, y, (c) => fits(want, c.val?.t, c) && !picks.includes(c.id));
    if (!o) return;
    if (tool.id === 'polygon' && picks.length >= 3 && o.id === picks[0]) { finishPolygon(); return; }
    if (picks.includes(o.id) && tool.id !== 'polygon') return;
    picks = [...picks, o.id];
    // a measured segment, circle or polygon needs no second object
    if (tool.id === 'distance' && picks.length === 1 && o.val?.t !== 'point') { complete(); return; }
    if (tool.id !== 'polygon' && !wantOf()) complete(); else bump();
  }
  function finishPolygon() { if (picks.length >= 3) { const o = fig.add('polygon', picks); done(o.name); } }
  function complete() {
    const ps = picks;
    switch (tool.id) {
      case 'delete': { const gone = fig.remove(ps[0]!); done(ft('removed', { n: gone.length })); return; }
      case 'relation': {
        const r = fig.relation(ps);
        const [a, b] = ps.map((id) => fig.byId(id)?.name ?? '?');
        const head = ft('relHeader', { a: a!, b: b! });
        status = r.now.length ? head + ' ' + r.checked.map((c) => `${ft(`r.${c.rel}`)} — ${c.held === c.trials ? ft('relHeld', { n: c.trials }) : ft('relBroken', { k: c.trials - c.held, n: c.trials })}`).join(' ; ') : head + ' ' + ft('relNone');
        picks = []; bump(); return;
      }
      case 'intersection': {
        const a = fig.byId(ps[0]!)!.val!, b = fig.byId(ps[1]!)!.val!;
        const n = Math.max(1, intersections(a, b).length);
        fig.snapshot();
        const made = Array.from({ length: n }, (_, k) => fig.add('intersection', ps, { params: [k] }, false));
        done(made.map((o) => o.name).join(', ')); return;
      }
      case 'tangent': {
        fig.snapshot();
        const t0 = fig.add('tangent', ps, { params: [0] }, false), t1 = fig.add('tangent', ps, { params: [1] }, false);
        if (!t1.val || (t0.val && t1.val && JSON.stringify(t0.val) === JSON.stringify(t1.val))) fig.remove(t1.id, false);
        done(t0.name); return;
      }
    }
    if (tool.number) {
      const d = { radius: '1', angle: '90', ratio: '2', sides: '5' }[tool.number];
      pending = { kind: tool.kind!, parents: ps, number: tool.number, value: d };
      bump();
      queueMicrotask(() => document.getElementById(`${uid}-num`)?.focus());
      return;
    }
    const o = fig.add(tool.kind!, ps);
    done(o.name);
  }
  function submitNumber(e: Event) {
    e.preventDefault();
    if (!pending) return;
    const v = Number(pending.value.replace(',', '.'));
    if (!Number.isFinite(v)) return;
    const o = fig.add(pending.kind, pending.parents, { params: [v] });
    pending = null;
    done(o.name);
  }
  function done(what: string) { picks = []; status = what ? `✓ ${ft(`t.${tool.id}`)} : ${what}` : ''; bump(); emit(); }

  // ------------------------------------------------------------ pointer: drag, pan, pinch, tap
  const ptrs = new Map<number, { x: number; y: number }>();
  let drag: { id?: string; sx: number; sy: number; view: View; moved: boolean; pinch?: { d: number; cx: number; cy: number } } | null = null;
  function local(e: PointerEvent | WheelEvent | MouseEvent): [number, number] {
    const r = svgEl!.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * frame.w, ((e.clientY - r.top) / r.height) * frame.h];
  }
  function down(e: PointerEvent) {
    try { svgEl?.setPointerCapture(e.pointerId); } catch { /* synthetic or already released pointer */ }
    const [sx, sy] = local(e);
    ptrs.set(e.pointerId, { x: sx, y: sy });
    if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()] as [{ x: number; y: number }, { x: number; y: number }];
      drag = { sx, sy, view: { ...view }, moved: true, pinch: { d: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 } };
      return;
    }
    const [x, y] = toWorld(frame, sx, sy);
    const m = editable && tool.id === 'move' ? hit(x, y, (o) => fig.movable(o)) : null;
    if (m) { fig.snapshot(); selected = m.id; }
    drag = { id: m?.id, sx, sy, view: { ...frame.view }, moved: false };
  }
  function move(e: PointerEvent) {
    const [sx, sy] = local(e);
    if (ptrs.has(e.pointerId)) ptrs.set(e.pointerId, { x: sx, y: sy });
    if (!drag) { hover(sx, sy, e.pointerType === 'mouse'); return; }
    if (drag.pinch && ptrs.size === 2) {
      const [a, b] = [...ptrs.values()] as [{ x: number; y: number }, { x: number; y: number }];
      const k = drag.pinch.d / Math.max(10, Math.hypot(a.x - b.x, a.y - b.y));
      const f0 = { w: frame.w, h: frame.h, view: drag.view };
      const [cx, cy] = toWorld(f0, drag.pinch.cx, drag.pinch.cy);
      view = zoomed(drag.view, cx, cy, k);
      return;
    }
    if (Math.hypot(sx - drag.sx, sy - drag.sy) > 5) drag.moved = true;
    if (!drag.moved) return;
    if (drag.id) { const [x, y] = toWorld(frame, sx, sy); const o = fig.byId(drag.id); const [px, py] = o?.kind === 'point' ? snap(x, y) : [x, y]; fig.move(drag.id, px, py); bump(); return; }
    const k = (drag.view.xmax - drag.view.xmin) / frame.w;
    const dx = (sx - drag.sx) * k, dy = (sy - drag.sy) * k;
    view = { xmin: drag.view.xmin - dx, xmax: drag.view.xmax - dx, ymin: drag.view.ymin + dy, ymax: drag.view.ymax + dy };
  }
  function up(e: PointerEvent) {
    ptrs.delete(e.pointerId);
    const d = drag;
    if (ptrs.size > 0) return;
    drag = null;
    if (!d) return;
    if (d.id && d.moved) { emit(); return; }
    if (d.moved) { emit(); return; }
    const [x, y] = toWorld(frame, d.sx, d.sy);
    if (tool.id !== 'move') tap(x, y); else if (!d.id) read(d.sx, d.sy, true);
  }
  function zoomed(v: View, cx: number, cy: number, k: number): View {
    return { xmin: cx + (v.xmin - cx) * k, xmax: cx + (v.xmax - cx) * k, ymin: cy + (v.ymin - cy) * k, ymax: cy + (v.ymax - cy) * k };
  }
  function zoom(k: number, sx = frame.w / 2, sy = frame.h / 2) { const [cx, cy] = toWorld(frame, sx, sy); view = zoomed(frame.view, cx, cy, k); emit(); }
  function reset() { view = { ...untrack(() => JSON.parse(last).view as View) }; if (!view || !(view.xmin < view.xmax)) view = { xmin: -8, xmax: 8, ymin: -5, ymax: 5 }; }
  $effect(() => {
    const el = svgEl;
    if (!el) return;
    const wheel = (e: WheelEvent) => { e.preventDefault(); const [sx, sy] = local(e); zoom(Math.exp(e.deltaY * 0.0015), sx, sy); };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => el.removeEventListener('wheel', wheel);
  });
  function read(sx: number, sy: number, announce: boolean) {
    const [x, y] = toWorld(frame, sx, sy);
    const env = fig.env();
    let best: { x: number; y: number; d: number } | null = null;
    for (const c of fig.curves) {
      if (c.hidden) continue;
      const s = sampled(c.expr, env, frame.view);
      const n = s && nearestOnCurve(s, x, y);
      if (n && (!best || n.d < best.d)) best = n;
    }
    if (best && best.d * scale() < (announce ? 30 : 16)) { const [px, py] = toScreen(frame, best.x, best.y); reading = { x: best.x, y: best.y, sx: px, sy: py }; if (announce) status = ft('reading', { x: decimal(best.x, 5), y: decimal(best.y, 5) }); }
    else reading = null;
  }
  function hover(sx: number, sy: number, mouse: boolean) { if (mouse && fig.curves.length) read(sx, sy, false); }

  // ------------------------------------------------------------ keyboard
  function key(e: KeyboardEvent) {
    if (e.target !== e.currentTarget) return;
    const span = frame.view.xmax - frame.view.xmin;
    const step = span / (e.shiftKey ? 500 : 50);
    const arrows: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };
    const a = arrows[e.key];
    if (a) {
      e.preventDefault();
      const o = selected ? fig.byId(selected) : null;
      if (editable && o && fig.movable(o) && o.val?.t === 'point') { fig.snapshot(); fig.move(o.id, +(o.val.x + a[0] * step).toPrecision(6), +(o.val.y + a[1] * step).toPrecision(6)); bump(); emit(); }
      else { view = { xmin: frame.view.xmin + a[0] * step * 5, xmax: frame.view.xmax + a[0] * step * 5, ymin: frame.view.ymin + a[1] * step * 5, ymax: frame.view.ymax + a[1] * step * 5 }; }
    } else if (e.key === '+' || e.key === '=') { e.preventDefault(); zoom(1 / 1.25); }
    else if (e.key === '-') { e.preventDefault(); zoom(1.25); }
    else if (e.key === '0') { e.preventDefault(); reset(); }
    else if (e.key === 'Escape') { picks = []; pending = null; bump(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey ? fig.redo() : fig.undo()) { bump(); emit(); } }
  }

  // ------------------------------------------------------------ curves, sliders, description
  function addCurve(e: Event) {
    e.preventDefault();
    const expr = curveInput.trim();
    if (!expr) return;
    try { parseCurve(expr, Object.keys(fig.env()), fig.env()); } catch (x) { curveErr = ft('badCurve', { e: (x as Error).message }); return; }
    fig.snapshot();
    let n = fig.curves.length + 1;
    while (fig.curves.some((c) => c.id === `f${n}`)) n++;
    fig.curves = [...fig.curves, { id: `f${n}`, expr }];
    curveInput = ''; curveErr = ''; bump(); emit();
  }
  function curveKind(expr: string): string { try { return parseCurve(expr, Object.keys(fig.env()), fig.env()).kind; } catch { return 'bad'; } }
  const table = $derived.by(() => {
    void rev;
    const c = fig.curves.find((x) => x.id === tableFor);
    if (!c) return [];
    try {
      const def = parseCurve(c.expr, Object.keys(fig.env()), fig.env());
      const st = niceStep((frame.view.xmax - frame.view.xmin) / 20);
      return valueTable(def, Math.ceil(frame.view.xmin / st) * st, frame.view.xmax, st, fig.env());
    } catch { return []; }
  });
  function describe(o: Obj, _rev = 0): string {
    const v = o.val;
    const ex = fig.exact;
    const n = (x: number) => fmtNum(x, ex).replace(/^≈ /, '');
    if (!v) return ft('undefinedObj');
    switch (v.t) {
      case 'point': return `${o.kind === 'point' ? ft('k.point') : o.kind === 'point_on' ? ft('k.point_on', { p: fig.byId(o.parents[0] ?? '')?.name ?? '' }) : ft(`t.${o.kind}`)} (${n(v.x)} ; ${n(v.y)})`;
      case 'line': { const [a, b, c] = lineEq(v); const kind = ft(`t.${o.kind}`); return Math.abs(b) > 1e-12 ? `${kind} : y = ${n(-a / b)}x + ${n(c / b)}` : `${kind} : x = ${n(c / a)}`; }
      case 'circle': return `${ft(`t.${o.kind}`)} : (${n(v.c.x)} ; ${n(v.c.y)}), r = ${n(v.r)}`;
      case 'conic': return `${ft(`t.${o.kind}`)} : ${v.k.map((k) => decimal(k, 4)).join(', ')}`;
      case 'polygon': return `${ft(`t.${o.kind}`)} (${v.pts.length})`;
      case 'number': return `${ft(o.kind === 'slider' ? 't.slider' : `t.${o.kind}`)} = ${fmtNum(v.v, ex, v.unit)}`;
      case 'locus': return ft('t.locus');
    }
  }
  const sliders = $derived.by(() => { void rev; return fig.objects.filter((o) => o.kind === 'slider').map((o) => ({ ...o })); });
  const objects = $derived.by(() => { void rev; return fig.objects.map((o) => ({ ...o })); });
  const curves = $derived.by(() => { void rev; return fig.curves.map((c) => ({ ...c })); });

  // ------------------------------------------------------------ exports
  function save(blob: Blob, name: string) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  const base = () => (fig.title || 'figure').replace(/[^\w-]+/g, '_').slice(0, 40);
  async function exportAs(kind: 'png' | 'svg' | 'tikz' | 'sage') {
    fig.view = { ...view };
    if (kind === 'png') save(await toPNG(fig), `${base()}.png`);
    else if (kind === 'svg') save(new Blob([toSVG(fig)], { type: 'image/svg+xml' }), `${base()}.svg`);
    else if (kind === 'tikz') save(new Blob([toTikZ(fig)], { type: 'text/x-tex' }), `${base()}.tex`);
    else { const code = toSage(fig); try { await navigator.clipboard.writeText(code); status = ft('copied'); } catch { save(new Blob([code], { type: 'text/plain' }), `${base()}.sage`); } }
  }
  const color = (p: Prim) => (p.color && /^c\d$/.test(p.color) ? `var(--fig-${p.color})` : p.color ?? '');
</script>

<div class="figure" bind:clientWidth={w}>
  {#if editable}
    <div class="bar">
      <label class="grp"><span class="sr-only">{ft('tools')}</span>
        <select class="input" bind:value={group} aria-label={ft('tools')}>
          {#each GROUPS as g (g)}<option value={g}>{ft(`g.${g}`)}</option>{/each}
        </select>
      </label>
      <div class="tools" role="group" aria-label={ft(`g.${group}`)}>
        {#each TOOLS.filter((x) => x.group === group) as x (x.id)}
          <button type="button" class="btn small" class:on={tool.id === x.id} aria-pressed={tool.id === x.id} onclick={() => choose(x)}>{ft(`t.${x.id}`)}</button>
        {/each}
      </div>
      <span class="spacer"></span>
      <button type="button" class="btn small quiet" onclick={() => { if (fig.undo()) { bump(); emit(); } }} disabled={rev < 0 || !fig.canUndo}>{ft('undo')}</button>
      <button type="button" class="btn small quiet" onclick={() => { if (fig.redo()) { bump(); emit(); } }} disabled={rev < 0 || !fig.canRedo}>{ft('redo')}</button>
    </div>
  {/if}
  <p class="status" role="status" aria-live="polite">
    {#if editable}<span>{statusText}</span>{/if}
    {#if status}<span class="note">{status}</span>{/if}
  </p>
  {#if pending}
    <form class="num row" onsubmit={submitNumber}>
      <label for="{uid}-num">{ft(`n.${pending.number}`)}</label>
      <input id="{uid}-num" class="input" inputmode="decimal" bind:value={pending.value} required />
      <button class="btn small primary" type="submit">{ft('ok')}</button>
      <button class="btn small quiet" type="button" onclick={() => { pending = null; picks = []; }}>{ft('cancel')}</button>
    </form>
  {/if}
  {#if editable && tool.id === 'polygon' && picks.length >= 3}<button type="button" class="btn small" onclick={finishPolygon}>{ft('finish')}</button>{/if}

  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
  <div class="stage" tabindex="0" role="group" aria-label={label} aria-describedby="{uid}-hint" onkeydown={key}>
    <svg bind:this={svgEl} width={frame.w} height={frame.h} viewBox="0 0 {frame.w} {frame.h}" role="img"
      aria-label={ft('figureLabel', { n: objects.length, c: curves.length })}
      onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up} ondblclick={reset}
      onpointerleave={() => { if (!drag) reading = null; }}>
      {#each prims as p, i (i)}
        {#if p.kind === 'path'}
          <path d={p.d} class="r-{p.role}" class:sel={!!p.id && (p.id === selected || picks.includes(p.id))} style:stroke={color(p) || null} stroke-dasharray={p.dash ? '5 4' : null} />
        {:else if p.kind === 'dot'}
          <circle cx={p.x} cy={p.y} r={p.r} class="r-{p.role}" class:sel={!!p.id && (p.id === selected || picks.includes(p.id))} style:fill={p.role === 'curve' ? color(p) : null} />
        {:else}
          <text x={p.x} y={p.y} class="r-{p.role}" text-anchor={p.anchor ?? null}>{p.text}</text>
        {/if}
      {/each}
      {#if reading}
        <circle cx={reading.sx} cy={reading.sy} r="4" class="reading" />
        <text x={Math.min(reading.sx + 8, frame.w - 120)} y={Math.max(14, reading.sy - 8)} class="reading-t">({decimal(reading.x, 4)} ; {decimal(reading.y, 4)})</text>
      {/if}
    </svg>
  </div>
  <p class="hint" id="{uid}-hint">{ft('moveHint')}</p>

  <div class="row view-ctl">
    <button type="button" class="btn small quiet" onclick={() => zoom(1 / 1.25)} aria-label={ft('zoomIn')}>+</button>
    <button type="button" class="btn small quiet" onclick={() => zoom(1.25)} aria-label={ft('zoomOut')}>−</button>
    <button type="button" class="btn small quiet" onclick={reset}>{ft('reset')}</button>
    <label class="chk"><input type="checkbox" checked={fig.exact} onchange={(e) => { fig.exact = (e.target as HTMLInputElement).checked; bump(); emit(); }} /> {ft('exact')}</label>
    <label class="chk"><input type="checkbox" checked={fig.grid} onchange={(e) => { fig.grid = (e.target as HTMLInputElement).checked; bump(); emit(); }} /> {ft('grid')}</label>
    <label class="chk"><input type="checkbox" checked={fig.axes} onchange={(e) => { fig.axes = (e.target as HTMLInputElement).checked; bump(); emit(); }} /> {ft('axes')}</label>
    <span class="spacer"></span>
    <details class="menu">
      <summary class="btn small">{ft('export')}</summary>
      <div class="menu-list">
        <button type="button" class="btn small quiet" onclick={() => exportAs('png')}>{ft('png')}</button>
        <button type="button" class="btn small quiet" onclick={() => exportAs('svg')}>{ft('svg')}</button>
        <button type="button" class="btn small quiet" onclick={() => exportAs('tikz')}>{ft('tikz')}</button>
        <button type="button" class="btn small quiet" onclick={() => exportAs('sage')}>{ft('sage')}</button>
        {#if onsage}<button type="button" class="btn small quiet" onclick={() => { fig.view = { ...view }; onsage?.(toSage(fig)); }}>{ft('toSage')}</button>{/if}
      </div>
    </details>
  </div>
  {#if fig.warnings.length}<p class="warn">{ft('warnings', { w: fig.warnings.slice(0, 4).join(' · ') })}</p>{/if}

  {#if sliders.length}
    <fieldset class="sliders"><legend>{ft('sliders')}</legend>
      {#each sliders as s (s.id)}
        {@const p = s.params ?? [1, -5, 5, 0.1]}
        <label class="slider"><span>{s.name} = {decimal(p[0] ?? 0, 4)}</span>
          <input type="range" min={p[1] ?? -5} max={p[2] ?? 5} step={p[3] ?? 0.1} value={p[0] ?? 0} disabled={!editable}
            oninput={(e) => { fig.setParam(s.id, Number((e.target as HTMLInputElement).value)); bump(); }} onchange={emit} />
        </label>
      {/each}
    </fieldset>
  {/if}

  <section class="curves" aria-labelledby="{uid}-ch">
    <h4 id="{uid}-ch">{ft('curves')}</h4>
    {#if editable}
      <form class="row add" onsubmit={addCurve}>
        <label for="{uid}-c" class="sr-only">{ft('curveLabel')}</label>
        <input id="{uid}-c" class="input mono" bind:value={curveInput} placeholder={ft('curvePh')} aria-invalid={!!curveErr} aria-describedby="{uid}-cl {uid}-ce" autocapitalize="off" spellcheck="false" />
        <button class="btn small" type="submit" disabled={!curveInput.trim()}>{ft('addCurve')}</button>
      </form>
      <p class="xs" id="{uid}-cl">{ft('curveLabel')}</p>
      {#if curveErr}<p class="err" id="{uid}-ce" role="alert">{curveErr}</p>{/if}
    {/if}
    <ul class="clist">
      {#each curves as c, i (c.id)}
        {@const k = curveKind(c.expr)}
        <li>
          <span class="sw" style:background={c.color ?? `var(--fig-c${i % 6})`} aria-hidden="true"></span>
          <code>{c.expr}</code>
          {#if editable}
            <label class="chk"><input type="checkbox" checked={!c.hidden} onchange={(e) => { const cc = fig.curves.find((x) => x.id === c.id); if (cc) cc.hidden = !(e.target as HTMLInputElement).checked; bump(); emit(); }} /><span class="sr-only">{ft(c.hidden ? 'showCurve' : 'hideCurve', { c: c.expr })}</span></label>
          {/if}
          {#if k === 'explicit' || k === 'sequence'}<button type="button" class="btn small quiet" aria-expanded={tableFor === c.id} onclick={() => (tableFor = tableFor === c.id ? null : c.id)}>{ft('table')}</button>{/if}
          {#if editable}<button type="button" class="btn small quiet" aria-label={ft('removeCurve', { c: c.expr })} onclick={() => { fig.snapshot(); fig.curves = fig.curves.filter((x) => x.id !== c.id); bump(); emit(); }}>✕</button>{/if}
        </li>
        {#if tableFor === c.id && table.length}
          <li class="tbl"><table><caption class="sr-only">{ft('table')} — {c.expr}</caption>
            <thead><tr><th scope="col">{ft('valueX')}</th><th scope="col">{ft('valueY')}</th></tr></thead>
            <tbody>{#each table as r (r.x)}<tr><td>{decimal(r.x, 6)}</td><td>{fmtNum(r.y, fig.exact)}</td></tr>{/each}</tbody></table></li>
        {/if}
      {/each}
    </ul>
  </section>

  <details class="desc">
    <summary>{ft('describe')} ({objects.length})</summary>
    {#if !objects.length && !curves.length}<p class="xs">{ft('emptyFig')}</p>{/if}
    <ul class="olist" aria-label={ft('objects')}>
      {#each objects as o (o.id)}
        <li><button type="button" class="obj" aria-pressed={selected === o.id} onclick={() => { selected = selected === o.id ? null : o.id; }}>
          <strong>{o.name}</strong> — {describe(o, rev)}</button></li>
      {/each}
    </ul>
  </details>
</div>

<style>
  .figure { --fig-c0: var(--accent); --fig-c1: var(--failed); --fig-c2: var(--proved); --fig-c3: var(--running); --fig-c4: var(--online); --fig-c5: var(--local);
    display: grid; gap: var(--s-2); min-width: 0; max-width: 100%; }
  .bar { display: flex; flex-wrap: wrap; gap: var(--s-1); align-items: center; }
  .grp select { width: auto; min-height: 32px; padding: 2px 6px; font-size: var(--fs-sm); }
  .tools { display: flex; flex-wrap: wrap; gap: var(--s-1); }
  .btn.on { background: var(--accent-soft); border-color: var(--accent); color: var(--text); font-weight: 600; }
  .spacer { flex: 1; }
  .status { margin: 0; font-size: var(--fs-sm); color: var(--text-2); min-height: 1.4em; display: flex; flex-wrap: wrap; gap: var(--s-2); }
  .status .note { color: var(--text); }
  .num { display: flex; gap: var(--s-2); align-items: center; flex-wrap: wrap; }
  .num input { width: 8rem; }
  .stage { border: 1px solid var(--line-strong); border-radius: var(--r-2); overflow: hidden; background: var(--surface); line-height: 0; }
  .stage:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
  svg { display: block; width: 100%; height: auto; touch-action: none; user-select: none; cursor: crosshair; font: 12px var(--font-ui); }
  path { fill: none; stroke-linejoin: round; stroke-linecap: round; }
  .r-grid { stroke: var(--line); stroke-width: 1; }
  .r-axis { stroke: var(--text-3); stroke-width: 1.2; }
  .r-tick { fill: var(--text-2); font-size: 11px; }
  .r-curve { stroke: var(--fig-c0); stroke-width: 2.2; }
  circle.r-curve { stroke: none; }
  .r-line, .r-circle, .r-poly { stroke: var(--text); stroke-width: 1.7; }
  .r-poly { fill: color-mix(in srgb, var(--accent) 10%, transparent); }
  .r-conic { stroke: var(--online); stroke-width: 1.9; }
  .r-locus { stroke: var(--failed); stroke-width: 1.9; }
  .r-graph { stroke: var(--text-2); stroke-width: 1.4; }
  .r-vertex { fill: var(--surface); stroke: var(--text); stroke-width: 1.4; }
  .r-point { fill: var(--text); }
  .r-free { fill: var(--accent); stroke: var(--surface); stroke-width: 1.5; }
  .r-label { fill: var(--text); font-weight: 600; }
  .sel { stroke: var(--running-fill) !important; stroke-width: 3.2 !important; }
  circle.sel { fill: var(--running-fill) !important; }
  .reading { fill: var(--running-fill); stroke: var(--text); }
  .reading-t { fill: var(--text); font-weight: 600; paint-order: stroke; stroke: var(--surface); stroke-width: 3px; }
  .hint, .xs { margin: 0; font-size: var(--fs-xs); color: var(--text-3); }
  .view-ctl { display: flex; flex-wrap: wrap; gap: var(--s-1); align-items: center; }
  .chk { display: inline-flex; align-items: center; gap: 4px; font-size: var(--fs-sm); min-height: 32px; }
  .menu { position: relative; }
  .menu summary { list-style: none; cursor: pointer; }
  .menu summary::-webkit-details-marker { display: none; }
  .menu-list { position: absolute; right: 0; z-index: 5; display: grid; gap: 2px; padding: var(--s-1); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); box-shadow: var(--shadow-2); min-width: 12rem; }
  .menu-list .btn { justify-content: flex-start; }
  .warn { margin: 0; font-size: var(--fs-xs); color: var(--running); }
  .err { margin: 0; font-size: var(--fs-sm); color: var(--failed); }
  .sliders { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2); margin: 0; display: grid; gap: var(--s-1); }
  .slider { display: grid; grid-template-columns: minmax(6rem, auto) 1fr; gap: var(--s-2); align-items: center; font: var(--fs-sm) var(--font-mono); }
  .slider input { width: 100%; min-height: 32px; }
  .curves h4 { margin: 0 0 var(--s-1); font-size: var(--fs-sm); }
  .add { display: flex; gap: var(--s-1); }
  .add input { flex: 1; min-width: 0; }
  .mono, code { font-family: var(--font-mono); }
  .clist, .olist { list-style: none; margin: var(--s-1) 0 0; padding: 0; display: grid; gap: 2px; }
  .clist li { display: flex; align-items: center; gap: var(--s-2); flex-wrap: wrap; min-width: 0; }
  .clist code { overflow-wrap: anywhere; font-size: var(--fs-sm); }
  .sw { width: 14px; height: 4px; border-radius: 2px; flex: none; }
  .tbl { display: block !important; overflow-x: auto; }
  table { border-collapse: collapse; font: var(--fs-xs) var(--font-mono); }
  th, td { border: 1px solid var(--line); padding: 2px 8px; text-align: right; }
  .desc summary { cursor: pointer; font-size: var(--fs-sm); color: var(--text-2); min-height: 32px; display: flex; align-items: center; }
  .obj { background: none; border: 0; padding: 4px 6px; text-align: left; color: var(--text); font: var(--fs-sm) var(--font-ui); border-radius: var(--r-1); width: 100%; cursor: pointer; overflow-wrap: anywhere; }
  .obj[aria-pressed='true'] { background: var(--accent-soft); }
  .obj:focus-visible { outline: 2px solid var(--focus); }
  @media (pointer: coarse) {
    .grp select, .chk, .slider input, .desc summary { min-height: var(--touch); }
    .obj { min-height: var(--touch); }
  }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
