<script lang="ts">
  // The problem graph of a dossier (S-AY, D57, docs/PROOF_GRAPH.md): target, known results, lemmas to prove, what was
  // tried and why. One list that reads well on a phone (indented tree; a lemma shared by two others is listed once,
  // under the first, and the others say « utilise aussi »). Status = icon + words + border style, never colour alone;
  // « conditionnel » is always spelled out. Node detail: « Pourquoi cette piste ? », attempts, sources, « Arrêter cette
  // piste » / « Reprendre », « Ouvrir comme sous-dossier », « Adapter la méthode ». « Expliquer la démonstration »:
  // the recorded account (no model writes it), with the bibliography and exports.
  import type { Dossier } from '../../lib/api/types';
  import { graphApi, treeOf, STATE_ICON, type Explanation, type Graph, type Why } from '../../lib/api/graph';
  import { app } from '../../lib/store/app.svelte';
  import { i18n, t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Md from '../../components/Md.svelte';
  import LeanExplain from '../../components/LeanExplain.svelte';

  let { dossier: d }: { dossier: Dossier } = $props();
  let graph = $state<Graph | null>(null);
  let sel = $state('');
  let why = $state<Why | null>(null);
  let busy = $state('');
  let explainOpen = $state(false);
  let explanation = $state<Explanation | null>(null);
  // D59: the drawn view is optional (the list stays), lazy-loaded, and not offered on phones (the list reads better)
  const narrow = typeof matchMedia !== 'undefined' && matchMedia('(max-width: 767px)').matches;
  let drawn = $state(false);
  let mapChunk: Promise<typeof import('./GraphMap.svelte').default> | null = null;
  function loadMap() {
    mapChunk ??= import('./GraphMap.svelte').then((m) => m.default);
    mapChunk.catch(() => { mapChunk = null; });
    return mapChunk;
  }

  async function load() {
    try { graph = (await graphApi.get(d.id, i18n.base)).graph; } catch (e) { toast('error', errorText(e)); }
  }
  $effect(() => { void d.id; void i18n.base; void load(); });
  $effect(() => app.on('pg.updated', (ev) => { if ((ev as { dossier_id?: string }).dossier_id === d.id) void load(); }));

  const tree = $derived(graph ? treeOf(graph) : { order: [], alsoUsedBy: {} });
  const node = $derived(graph && sel ? graph.nodes[sel] : undefined);
  const running = $derived(Boolean(graph?.run?.running));
  const lastRun = $derived(graph?.runs?.length ? graph.runs[graph.runs.length - 1] : null);
  const root = $derived(graph ? graph.nodes[graph.root] : undefined);

  async function act(name: string, fn: () => Promise<unknown>, ok?: string) {
    busy = name;
    try {
      const r = await fn();
      if (r && typeof r === 'object' && 'graph' in r && (r as { graph?: Graph }).graph) graph = (r as { graph: Graph }).graph;
      if (ok) toast('ok', ok);
    } catch (e) { toast('error', errorText(e)); } finally { busy = ''; }
  }
  async function pick(id: string) {
    sel = id;
    why = null;
    try { why = await graphApi.why(d.id, id, i18n.base); } catch { /* the panel shows what the graph has */ }
  }
  async function explain(nodeId?: string) {
    explainOpen = true;
    explanation = null;
    try { explanation = (await graphApi.explain(d.id, i18n.base, nodeId)).explanation; } catch (e) { explainOpen = false; toast('error', errorText(e)); }
  }
  async function exportAs(format: 'note' | 'latex' | 'bibtex') {
    await act('export', async () => {
      const r = await graphApi.exportAs(d.id, format, i18n.base, explanation?.node);
      if (format === 'note') toast('ok', t('pg.exportedNote'));
      else {
        const text = format === 'latex' ? (r.latex ?? '') + (r.bibtex ? `\n% BibTeX\n${r.bibtex}` : '') : r.bibtex ?? '';
        try { await navigator.clipboard.writeText(text); toast('ok', t('pg.copied')); } catch { toast('info', text.slice(0, 400)); }
      }
    });
  }
  async function openSub(id: string) {
    await act('open', async () => {
      const r = await graphApi.open(d.id, id);
      navigate(`/d/${encodeURIComponent(r.dossier_id)}`);
    });
  }
  const stateLabel = (s: string, composed = false) => (s === 'verified' && composed ? t('pg.state.composed') : tk(`pg.state.${s}`, s));
  const srcLabel = (k: string) => tk(`pg.src.${k}`, k);
</script>

<section class="pg" aria-labelledby="pg-h">
  <div class="row head"><h3 id="pg-h">{t('pg.title')}</h3>
    <span class="spacer"></span>
    <button class="btn small" onclick={() => explain()} disabled={!graph}><Icon name="bulb" size={14} />{t('pg.explain')}</button>
  </div>

  {#if !graph}
    <p class="muted" aria-busy="true">{t('common.loading')}</p>
  {:else}
    {#if root}
      <div class="target st-{root.state}">
        <p class="xs muted lbl">{t('pg.target')}</p>
        <p class="ttl">{root.title}</p>
        <p class="badge"><Icon name={STATE_ICON[root.state] ?? 'info'} size={14} />{stateLabel(root.state, root.composed)}</p>
        {#if root.state === 'conditional'}<p class="small cond">{t('pg.conditionalText', { names: root.rests_on.map((x) => graph!.nodes[x]?.title ?? x).join(', ') })}</p>{/if}
      </div>
    {/if}

    <div class="run" role="status">
      {#if running && graph.run}
        <p class="small"><Icon name="activity" size={14} /> {t('pg.running', { steps: graph.run.steps, attempts: graph.run.spent['attempts'] ?? 0, max: graph.run.budgets['max_attempts'] ?? 0 })}</p>
        <button class="btn danger small" disabled={busy !== '' || graph.run.stopping} onclick={() => act('stop', () => graphApi.stop(d.id), t('pg.stopping'))}><Icon name="stop" size={14} />{t('pg.stop')}</button>
      {:else}
        {#if lastRun}<p class="small">{t('pg.lastRun', { reason: tk(`pg.stop.${lastRun.reason}`, lastRun.reason), steps: lastRun.steps, when: fmtTime(lastRun.end) })}</p>{/if}
        <button class="btn small primary" disabled={busy !== '' || !d.statements.length || root?.state === 'verified'} onclick={() => act('search', () => graphApi.search(d.id), t('pg.started'))}><Icon name="play" size={14} />{t('pg.search')}</button>
      {/if}
      <p class="xs muted">{t('pg.budgets', { minutes: Math.round((graph.budgets['wall_s'] ?? 0) / 60), attempts: graph.budgets['max_attempts'] ?? 0, depth: graph.budgets['max_depth'] ?? 0, usd: (graph.budgets['usd'] ?? 0).toFixed(2) })}</p>
    </div>

    <ul class="legend" aria-label={t('pg.legend')}>
      {#each ['verified', 'conditional', 'open', 'refuted', 'abandoned'] as s (s)}
        <li class="st-{s}"><Icon name={STATE_ICON[s] ?? 'info'} size={12} />{stateLabel(s)}{#if graph.counts[s]} ({graph.counts[s]}){/if}</li>
      {/each}
    </ul>

    {#if !narrow}
      <div class="views" role="group" aria-label={t('pg.view')}>
        <button class="btn small" aria-pressed={!drawn} onclick={() => (drawn = false)}><Icon name="list" size={14} />{t('pg.view.list')}</button>
        <button class="btn small" aria-pressed={drawn} onclick={() => { drawn = true; void loadMap(); }}><Icon name="split" size={14} />{t('pg.view.drawn')}</button>
      </div>
    {/if}

    <div class="body" class:with-panel={Boolean(node)}>
      {#if drawn && !narrow}
        {#await loadMap()}
          <p class="muted" aria-busy="true">{t('common.loading')}</p>
        {:then GraphMap}
          <GraphMap {graph} order={tree.order.map((x) => x.id)} selected={sel} onselect={pick} />
        {:catch}
          <p class="muted small">{t('pg.view.failed')}</p>
        {/await}
      {:else}
      <ul class="nodes" aria-label={t('pg.nodes')}>
        {#each tree.order as it (it.id)}
          {@const n = graph.nodes[it.id]}
          {#if n && it.id !== graph.root}
            <li style:margin-left="{Math.min(it.depth, 6) * 14}px">
              <button class="nd st-{n.state}" aria-current={sel === n.id ? 'true' : undefined} onclick={() => pick(n.id)}>
                <span class="t">{n.title}</span>
                <span class="m xs"><Icon name={STATE_ICON[n.state] ?? 'info'} size={12} />{stateLabel(n.state, n.composed)}
                  · {srcLabel(n.source?.kind ?? 'user')}{#if n.proposal} · {t('pg.proposal')}{/if}{#if n.dossier_id} · {t('pg.hasDossier')}{/if}</span>
                {#if tree.alsoUsedBy[n.id]?.length}<span class="also xs">{t('pg.alsoUsedBy', { names: tree.alsoUsedBy[n.id]!.map((x) => graph!.nodes[x]?.title ?? x).join(', ') })}</span>{/if}
              </button>
            </li>
          {/if}
        {:else}
          <li class="muted small">{t('pg.empty')}</li>
        {/each}
      </ul>
      {/if}

      {#if node}
        <aside class="panel" aria-labelledby="pgn-h">
          <div class="row"><h4 id="pgn-h">{node.title}</h4><span class="spacer"></span>
            <button class="btn quiet icon small" aria-label={t('common.close')} onclick={() => (sel = '')}><Icon name="x" size={14} /></button></div>
          <p class="badge st-{node.state}"><Icon name={STATE_ICON[node.state] ?? 'info'} size={14} />{stateLabel(node.state, node.composed)}{#if node.reason} — {node.reason}{/if}</p>
          {#if node.state === 'conditional'}<p class="small cond">{t('pg.conditionalNode')}</p>{/if}
          {#if node.claimed}<p class="xs muted">{t('pg.claimed', { claim: node.claimed })}</p>{/if}
          {#if node.lean}<pre class="lean">{node.lean}</pre>{/if}
          {#if node.aliases?.length}<p class="xs muted">{t('pg.aliases', { names: node.aliases.map((a) => a.title).join(', ') })}</p>{/if}
          {#if node.probe?.confirmed}<p class="small"><Icon name="x" size={12} /> {t('pg.cexConfirmed', { witness: node.probe.candidate })}</p>
          {:else if node.probe}<p class="small">{t('pg.cexCandidate', { witness: node.probe.candidate })}</p>{/if}
          {#if node.tested?.text}<p class="xs muted">{t('pg.tested', { what: node.tested.text })}</p>{/if}
          <h5>{t('pg.whyTitle')}</h5>
          {#if node.why}<p class="small">{node.why}</p>{/if}
          <p class="small">{why?.reason_text || node.reason_text || t('pg.noReason')}</p>
          {#if why?.alternatives?.length}
            <ul class="alts small">
              {#each why.alternatives as a, i (i)}
                <li>{a.idea || '—'} {#if a.active}<strong>({t('pg.active')})</strong>{:else if a.abandoned}({t('pg.abandonedTrack')}){/if}{#if a.why} — {a.why}{/if}</li>
              {/each}
            </ul>
          {/if}
          {#if node.attempts.length}
            <h5>{t('pg.attempts', { n: node.attempts_n })}</h5>
            <ol class="atts xs">
              {#each node.attempts as a, i (i)}<li>{fmtTime(a.t)} · {a.how}{a.model ? ` (${a.model})` : ''} · {a.ok ? t('pg.ok') : t('pg.failed')}{#if a.error} — <span class="err">{a.error.split('\n').find((l) => l.trim()) ?? ''}</span>{/if}</li>{/each}
            </ol>
          {/if}
          {#if node.citation}
            <h5>{t('pg.source')}</h5>
            <p class="small">{String(node.citation['title'] ?? '')}{#if node.citation['DOI']} · DOI {String(node.citation['DOI'])}{/if} · {node.citation['verified'] ? t('pg.refVerified') : t('pg.refUnverified')}</p>
            {#if node.citation['quote']}<blockquote class="small">{String(node.citation['quote'])}</blockquote>{/if}
          {/if}
          <div class="acts">
            <button class="btn small" onclick={() => explain(node.id)}><Icon name="bulb" size={14} />{t('pg.explainNode')}</button>
            {#if node.status === 'abandoned'}
              <button class="btn small" disabled={busy !== ''} onclick={() => act('resume', () => graphApi.resume(d.id, node.id), t('pg.resumed'))}><Icon name="play" size={14} />{t('pg.resume')}</button>
            {:else if !['proved', 'mathlib', 'certified', 'refuted'].includes(node.status)}
              <button class="btn small danger" disabled={busy !== ''} onclick={() => act('abandon', () => graphApi.abandon(d.id, node.id), t('pg.abandoned'))}><Icon name="stop" size={14} />{t('pg.abandon')}</button>
            {/if}
            {#if node.id !== graph.root && node.lean}
              <button class="btn small" disabled={busy !== ''} onclick={() => openSub(node.id)}><Icon name="folderOpen" size={14} />{node.dossier_id ? t('pg.openDossier') : t('pg.openAsDossier')}</button>
            {/if}
            {#if node.proof || node.citation?.['quote']}
              <button class="btn small quiet" disabled={busy !== ''} onclick={() => act('adapt', () => graphApi.adapt(d.id, node.id), t('pg.adapted'))}><Icon name="sparkle" size={14} />{t('pg.adapt')}</button>
            {/if}
            {#if node.proposal && !node.used_by.length}
              <button class="btn small quiet" disabled={busy !== ''} onclick={() => act('adopt', () => graphApi.adopt(d.id, node.id))}><Icon name="plus" size={14} />{t('pg.adopt')}</button>
            {/if}
          </div>
        </aside>
      {/if}
    </div>
  {/if}
</section>

<Dialog bind:open={explainOpen} title={t('pg.explainTitle')} wide>
  {#if !explanation}
    <p class="muted" aria-busy="true">{t('common.loading')}</p>
  {:else}
    {#if explanation.conditional}<p class="cond-box"><Icon name="warn" size={16} />{t('pg.conditionalText', { names: explanation.rests_on.map((r) => r.title).join(', ') })}</p>{/if}
    <Md src={explanation.text} />
    {#if explanation.proof}
      <h4>{t('pg.stepByStep')}</h4>
      <pre class="lean">{explanation.proof}</pre>
      {#if explanation.node === graph?.root}<LeanExplain where={{ dossier: d.id, part: 'proof' }} code={explanation.proof} />{/if}
    {/if}
  {/if}
  {#snippet actions()}
    <button class="btn quiet" disabled={!explanation || busy !== ''} onclick={() => exportAs('bibtex')}>{t('pg.copyBibtex')}</button>
    <button class="btn quiet" disabled={!explanation || busy !== ''} onclick={() => exportAs('latex')}>{t('pg.copyLatex')}</button>
    <button class="btn primary" disabled={!explanation || busy !== ''} onclick={() => exportAs('note')}>{t('pg.toNote')}</button>
  {/snippet}
</Dialog>

<style>
  .pg { display: grid; gap: var(--s-3); container-type: inline-size; }
  .pg h3 { margin: 0; }
  .head { align-items: center; }
  .target { border: 2px solid var(--line-strong); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); background: var(--surface); }
  .target p { margin: 0; }
  .lbl { text-transform: uppercase; letter-spacing: 0.04em; }
  .ttl { font-weight: 700; font-size: var(--fs-md); overflow-wrap: anywhere; }
  .badge { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; font-size: var(--fs-sm); margin: 4px 0 0; }
  .cond, .cond-box { color: var(--running); }
  .cond-box { display: flex; gap: 8px; border: 2px dashed var(--running-fill); background: var(--running-soft); padding: var(--s-2); border-radius: var(--r-2); }
  .run { display: grid; gap: 6px; justify-items: start; }
  .run p { margin: 0; }
  .legend { list-style: none; display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 0; padding: 0; font-size: var(--fs-xs); font-weight: 700; }
  .legend li { display: inline-flex; align-items: center; gap: 4px; }
  .body { display: grid; gap: var(--s-3); grid-template-columns: minmax(0, 1fr); align-items: start; }
  @container (min-width: 820px) { .body.with-panel { grid-template-columns: minmax(0, 1fr) 360px; } }
  .nodes { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
  .nd { display: grid; gap: 2px; width: 100%; min-height: var(--touch); text-align: left; padding: 6px 10px; border: 1.5px solid var(--line-strong); border-left-width: 5px; border-radius: var(--r-2); background: var(--surface); color: var(--text); cursor: pointer; font: inherit; }
  .nd[aria-current='true'] { outline: 3px solid var(--focus); outline-offset: 1px; }
  .nd .t { font-weight: 600; font-size: var(--fs-sm); overflow-wrap: anywhere; }
  .nd .m { display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap; color: var(--text-2); }
  .also { color: var(--text-2); font-style: italic; }
  .st-verified { border-left-color: var(--proved); }
  .st-verified .m, .legend .st-verified, .badge.st-verified { color: var(--proved); }
  .st-conditional { border-left-style: dashed; border-left-color: var(--running-fill); }
  .st-conditional .m, .legend .st-conditional, .badge.st-conditional { color: var(--running); }
  .st-refuted { border-left-color: var(--failed); }
  .st-refuted .m, .legend .st-refuted, .badge.st-refuted { color: var(--failed); }
  .st-abandoned { border-left-style: dotted; border-left-color: var(--text-3); }
  .st-abandoned .t { text-decoration: line-through; text-decoration-color: var(--text-3); }
  .panel { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-3); background: var(--surface); display: grid; gap: 6px; min-width: 0; }
  .panel h4 { margin: 0; overflow-wrap: anywhere; }
  .panel h5 { margin: var(--s-2) 0 0; font-size: var(--fs-sm); }
  .panel p { margin: 0; }
  .lean { white-space: pre-wrap; overflow-wrap: anywhere; font-family: var(--font-mono); font-size: var(--fs-xs); background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); margin: 0; max-height: 220px; overflow: auto; }
  .alts, .atts { margin: 0; padding-left: 1.2em; display: grid; gap: 2px; }
  .err { color: var(--failed); }
  blockquote { margin: 0; padding-left: var(--s-2); border-left: 3px solid var(--line-strong); color: var(--text-2); }
  .views { display: flex; gap: 6px; }
  .views [aria-pressed='true'] { border-color: var(--accent); font-weight: 700; }
  .acts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: var(--s-2); }
</style>
