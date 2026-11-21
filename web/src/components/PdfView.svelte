<script lang="ts">
  // PDF reader (pdf.js, lazy chunk): pages rendered on demand when they scroll into view, a text layer for selection,
  // highlights drawn from annotation quads (PDF points, top-left origin), a flash on the passage a citation points to.
  // Selecting text offers « Surligner » → onhighlight(page, quads, text).
  import { onDestroy } from 'svelte';
  import { t } from '../lib/i18n/index.svelte';
  import type { Annotation } from '../lib/api/research';

  let { url, annotations = [], target = null, onhighlight, label, onpoint }: {
    url: string; annotations?: Annotation[]; target?: { page: number; bbox?: number[] | null; nonce: number } | null;
    onhighlight?: (page: number, quads: number[][], text: string) => void; label: string;
    /** Double-click on a page → PDF point (top-left origin), e.g. SyncTeX inverse search in the article editor (S-R). */
    onpoint?: (page: number, x: number, y: number) => void;
  } = $props();
  function onDbl(e: MouseEvent) {
    if (!onpoint) return;
    const pageEl = (e.target as HTMLElement).closest<HTMLElement>('.page');
    if (!pageEl) return;
    const r = pageEl.getBoundingClientRect();
    onpoint(Number(pageEl.dataset['page']), (e.clientX - r.left) / scale, (e.clientY - r.top) / scale);
  }

  type PdfDoc = { numPages: number; getPage: (n: number) => Promise<PdfPage>; destroy: () => Promise<void> };
  type PdfPage = { getViewport: (o: { scale: number }) => { width: number; height: number; scale: number }; render: (o: object) => { promise: Promise<void> };
    getTextContent: () => Promise<unknown>; view: number[] };
  let host: HTMLDivElement | undefined = $state();
  let doc: PdfDoc | null = null;
  let pages = $state<{ n: number; w: number; h: number; ptH: number; rendered: boolean }[]>([]);
  let err = $state('');
  let scale = $state(1.2);
  let selection = $state<{ page: number; quads: number[][]; text: string; x: number; y: number } | null>(null);
  let pdfjs: typeof import('pdfjs-dist') | null = null;
  let observer: IntersectionObserver | null = null;
  let fitted = false;

  async function load() {
    err = '';
    try {
      pdfjs = await import('pdfjs-dist');
      const worker = (await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default;
      pdfjs.GlobalWorkerOptions.workerSrc = worker;
      doc = (await pdfjs.getDocument({ url, isEvalSupported: false, withCredentials: true }).promise) as unknown as PdfDoc;
      if (!fitted && host) {
        // First display: fit the page width to the reading column.
        const p1 = await doc.getPage(1);
        const w1 = p1.getViewport({ scale: 1 }).width;
        scale = Math.max(0.5, Math.min(1.6, Math.floor(((host.clientWidth - 32) / w1) * 10) / 10));
        fitted = true;
      }
      const list = [];
      for (let n = 1; n <= doc.numPages; n++) {
        const p = await doc.getPage(n);
        const vp = p.getViewport({ scale });
        list.push({ n, w: vp.width, h: vp.height, ptH: p.view[3] ?? vp.height / scale, rendered: false });
      }
      pages = list;
      queueMicrotask(observe);
    } catch (e) { err = String((e as Error).message ?? e); }
  }
  $effect(() => { void url; void load(); return () => { void doc?.destroy(); doc = null; }; });

  function observe() {
    observer?.disconnect();
    observer = new IntersectionObserver((entries) => {
      for (const en of entries) if (en.isIntersecting) void render(Number((en.target as HTMLElement).dataset['page']));
    }, { root: host, rootMargin: '600px 0px' });
    host?.querySelectorAll('.page').forEach((el) => observer!.observe(el));
  }
  async function render(n: number) {
    const st = pages[n - 1];
    if (!doc || !pdfjs || !st || st.rendered) return;
    st.rendered = true;
    const page = await doc.getPage(n);
    const vp = page.getViewport({ scale });
    const el = host?.querySelector<HTMLElement>(`.page[data-page="${n}"]`);
    if (!el) return;
    const canvas = el.querySelector('canvas')!;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(vp.width * ratio);
    canvas.height = Math.floor(vp.height * ratio);
    await page.render({ canvasContext: canvas.getContext('2d')!, viewport: vp, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined }).promise;
    const tl = el.querySelector<HTMLElement>('.textLayer')!;
    tl.replaceChildren();
    tl.style.setProperty('--scale-factor', String(scale));
    tl.style.setProperty('--total-scale-factor', String(scale));
    const layer = new pdfjs.TextLayer({ textContentSource: await page.getTextContent() as never, container: tl, viewport: vp as never });
    await layer.render();
  }
  $effect(() => {
    // Jump to a cited passage.
    if (!target || !host || !pages.length) return;
    const el = host.querySelector<HTMLElement>(`.page[data-page="${target.page}"]`);
    if (!el) return;
    const y = target.bbox ? target.bbox[1]! * scale : 0;
    host.scrollTo({ top: el.offsetTop + y - 80, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });
  function onMouseUp() {
    const sel = document.getSelection();
    if (!sel || sel.isCollapsed || !host) { selection = null; return; }
    const range = sel.getRangeAt(0);
    const pageEl = (range.startContainer.parentElement as HTMLElement | null)?.closest<HTMLElement>('.page');
    if (!pageEl || !host.contains(pageEl)) { selection = null; return; }
    const n = Number(pageEl.dataset['page']);
    const base = pageEl.getBoundingClientRect();
    const quads = [...range.getClientRects()].filter((r) => r.width > 1).map((r) => {
      const x0 = (r.left - base.left) / scale, y0 = (r.top - base.top) / scale, x1 = (r.right - base.left) / scale, y1 = (r.bottom - base.top) / scale;
      return [x0, y0, x1, y0, x0, y1, x1, y1].map((v) => Math.round(v * 10) / 10);
    });
    const last = [...range.getClientRects()].pop();
    selection = quads.length ? { page: n, quads, text: sel.toString().trim().slice(0, 2000), x: (last?.right ?? base.left) - host.getBoundingClientRect().left, y: (last?.bottom ?? base.top) - host.getBoundingClientRect().top + host.scrollTop } : null;
  }
  function highlight() {
    if (!selection) return;
    onhighlight?.(selection.page, selection.quads, selection.text);
    selection = null;
    document.getSelection()?.removeAllRanges();
  }
  function zoom(d: number) {
    scale = Math.min(3, Math.max(0.6, Math.round((scale + d) * 10) / 10));
    void load();
  }
  onDestroy(() => observer?.disconnect());
  const byPage = $derived((n: number) => annotations.filter((a) => a.page === n && a.quads?.length));
</script>

<div class="pdf">
  <div class="tools row">
    <button class="btn small" onclick={() => zoom(-0.2)} aria-label={t('reader.zoomOut')}>−</button>
    <span class="xs">{Math.round(scale * 100)} %</span>
    <button class="btn small" onclick={() => zoom(0.2)} aria-label={t('reader.zoomIn')}>+</button>
    <span class="xs muted">{t('reader.pages', { n: pages.length })}</span>
  </div>
  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions (scrollable document reachable by keyboard; mouseup only reads the text selection) -->
  <div class="scroll" bind:this={host} onmouseup={onMouseUp} ondblclick={onDbl} role="document" aria-label={label} tabindex="0">
    {#if err}<p class="error-text">{t('reader.pdfError', { e: err })}</p>{/if}
    {#each pages as p (p.n)}
      <div class="page" data-page={p.n} style:width="{p.w}px" style:height="{p.h}px" aria-label={t('reader.page', { n: p.n })} role="region">
        <canvas style:width="{p.w}px" style:height="{p.h}px"></canvas>
        <div class="textLayer"></div>
        {#each byPage(p.n) as a (a.id)}
          {#each a.quads ?? [] as q}
            <div class="hl {a.color}" style:left="{Math.min(q[0]!, q[4] ?? q[0]!) * scale}px" style:top="{Math.min(q[1]!, q[3]!) * scale}px"
              style:width="{(Math.max(q[2]!, q[6] ?? q[2]!) - Math.min(q[0]!, q[4] ?? q[0]!)) * scale}px" style:height="{(Math.max(q[5] ?? q[3]!, q[7] ?? q[3]!) - Math.min(q[1]!, q[3]!)) * scale}px"
              title={a.note || a.text}></div>
          {/each}
        {/each}
        {#if target && target.page === p.n && target.bbox}
          {#key target.nonce}<div class="flash" style:left="{target.bbox[0]! * scale}px" style:top="{target.bbox[1]! * scale}px" style:width="{(target.bbox[2]! - target.bbox[0]!) * scale}px" style:height="{(target.bbox[3]! - target.bbox[1]!) * scale}px"></div>{/key}
        {/if}
      </div>
    {/each}
    {#if selection && onhighlight}
      <button class="btn small primary hl-btn" style:left="{selection.x}px" style:top="{selection.y + 6}px" onclick={highlight}>{t('reader.highlight')}</button>
    {/if}
  </div>
</div>

<style>
  .pdf { display: flex; flex-direction: column; min-height: 0; height: 100%; }
  .tools { padding: 4px 0; }
  .scroll { position: relative; overflow: auto; flex: 1; background: var(--surface-3); border-radius: var(--r-2); padding: var(--s-3); min-height: 60vh; max-height: calc(100dvh - var(--topbar-h) - 170px); }
  .page { position: relative; margin: 0 auto var(--s-3); background: #fff; box-shadow: var(--shadow-1); }
  canvas { display: block; }
  .textLayer { position: absolute; inset: 0; overflow: hidden; line-height: 1; opacity: 1; }
  .textLayer :global(span), .textLayer :global(br) { color: transparent; position: absolute; white-space: pre; cursor: text; transform-origin: 0 0; }
  .textLayer :global(::selection) { background: rgba(44, 70, 173, 0.3); }
  .hl { position: absolute; pointer-events: auto; mix-blend-mode: multiply; border-radius: 2px; }
  .hl.yellow { background: rgba(255, 214, 0, 0.4); } .hl.green { background: rgba(60, 200, 90, 0.35); } .hl.blue { background: rgba(70, 140, 255, 0.3); }
  .hl.pink { background: rgba(255, 90, 160, 0.3); } .hl.purple { background: rgba(150, 90, 255, 0.3); } .hl.red { background: rgba(255, 70, 50, 0.3); }
  .hl.orange { background: rgba(255, 150, 40, 0.35); } .hl.grey { background: rgba(120, 120, 120, 0.3); }
  .flash { position: absolute; outline: 3px solid var(--laterite-mark); border-radius: 3px; animation: flash 1.6s ease-out 2; pointer-events: none; }
  @keyframes flash { 50% { background: rgba(217, 100, 63, 0.25); } }
  .hl-btn { position: absolute; z-index: 5; }
</style>
