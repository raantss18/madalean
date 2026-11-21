<script lang="ts">
  // « Suggestions »: what a consigne proposes for the article, one change at a time. Before/after (word diff), why,
  // the evidence (Lean status of the dossiers, Calcul results and figures, citations). Accept (optionally after
  // editing the proposed text) or reject; nothing is applied otherwise. A generalisation stays « Conjecture » until
  // Lean proves it.
  import { consigne, SUGGESTION_TYPES, type Suggestion } from '../lib/api/consigne';
  import { app } from '../lib/store/app.svelte';
  import { t, tk } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import { toast } from '../lib/ui/toasts.svelte';
  import Md from './Md.svelte';

  let { pid }: { pid: string } = $props();
  let items = $state<Suggestion[]>([]);
  let counts = $state<Record<string, number>>({});
  let type = $state('');
  let status = $state('proposed');
  let editing = $state<Record<string, string>>({});
  let busy = $state('');

  async function load() {
    if (!pid) return;
    try { const r = await consigne.suggestions(pid, type, status); items = r.suggestions; counts = r.counts; } catch { /* plugin absent */ }
  }
  $effect(() => { void pid; void type; void status; void load(); });
  $effect(() => app.on('research.suggestion', (ev) => {
    const e = ev as unknown as { project_id: string; suggestion: Suggestion };
    if (e.project_id !== pid) return;
    void load();
  }));

  type Part = { t: string; k: 'same' | 'del' | 'add' };
  function diff(a: string, b: string): Part[] {
    // word-level LCS (bounded): enough for paragraph-sized suggestions
    const A = a.split(/(\s+)/), B = b.split(/(\s+)/);
    if (A.length * B.length > 400000) return [{ t: a, k: 'del' }, { t: b, k: 'add' }];
    const n = A.length, m = B.length;
    const L: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i]![j] = A[i] === B[j] ? L[i + 1]![j + 1]! + 1 : Math.max(L[i + 1]![j]!, L[i]![j + 1]!);
    const out: Part[] = [];
    const push = (s: string, k: Part['k']) => { const last = out.at(-1); if (last && last.k === k) last.t += s; else out.push({ t: s, k }); };
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (A[i] === B[j]) { push(A[i]!, 'same'); i++; j++; }
      else if (L[i + 1]![j]! >= L[i]![j + 1]!) push(A[i++]!, 'del');
      else push(B[j++]!, 'add');
    }
    while (i < n) push(A[i++]!, 'del');
    while (j < m) push(B[j++]!, 'add');
    return out;
  }

  async function accept(s: Suggestion) {
    busy = s.id;
    try {
      const after = s.id in editing ? editing[s.id] : undefined;
      await consigne.accept(pid, s.id, after);
      delete editing[s.id];
      toast('ok', t('sugg.accepted'));
      await load();
    } catch (e) { toast('error', errorText(e)); await load(); } finally { busy = ''; }
  }
  async function reject(s: Suggestion) {
    busy = s.id;
    try { await consigne.reject(pid, s.id); await load(); } catch (e) { toast('error', errorText(e)); } finally { busy = ''; }
  }
  const total = $derived(Object.values(counts).reduce((a, b) => a + b, 0));
</script>

<section class="panel sugg" id="suggestions" aria-labelledby="sg-h">
  <div class="row">
    <h2 id="sg-h">{t('sugg.title')}</h2>
    {#if total}<span class="chip running">{t('sugg.pending', { n: total })}</span>{/if}
  </div>
  <p class="hint">{t('sugg.lead')}</p>
  <div class="row filters" role="group" aria-label={t('sugg.filters')}>
    <label class="sr-only" for="sg-type">{t('sugg.type')}</label>
    <select id="sg-type" class="input" bind:value={type}>
      <option value="">{t('sugg.allTypes')}</option>
      {#each SUGGESTION_TYPES as ty}<option value={ty}>{tk(`sugg.type.${ty}`, ty)}{counts[ty] ? ` (${counts[ty]})` : ''}</option>{/each}
    </select>
    <label class="sr-only" for="sg-st">{t('sugg.status')}</label>
    <select id="sg-st" class="input" bind:value={status}>
      <option value="proposed">{t('sugg.st.proposed')}</option><option value="accepted">{t('sugg.st.accepted')}</option>
      <option value="rejected">{t('sugg.st.rejected')}</option><option value="stale">{t('sugg.st.stale')}</option><option value="">{t('sugg.st.all')}</option>
    </select>
  </div>
  {#if !items.length}<p class="small muted">{t('sugg.none')}</p>{/if}
  <ol class="list">
    {#each items as s (s.id)}
      <li class="item {s.status}">
        <div class="row">
          <span class="chip">{tk(`sugg.type.${s.type}`, s.type)}</span>
          <strong class="small">{s.title}</strong>
          {#if s.conjecture}<span class="chip {s.proved ? 'proved' : 'running'}">{s.proved ? t('sugg.provedLean') : t('sugg.conjecture')}</span>{/if}
          {#if s.touches_math}<span class="chip failed" title={t('sugg.mathTitle')}>{t('sugg.math')}</span>{/if}
          {#if s.status !== 'proposed'}<span class="chip">{tk(`sugg.st.${s.status}`, s.status)}</span>{/if}
        </div>
        {#if s.before}
          <p class="diff small" aria-label={t('sugg.diff')}>{#each diff(s.before, s.after) as p}{#if p.k === 'same'}{p.t}{:else if p.k === 'del'}<del>{p.t}</del>{:else}<ins>{p.t}</ins>{/if}{/each}</p>
        {:else}
          <div class="after"><span class="xs muted">{t('sugg.newText')}</span><Md src={s.conjecture && s.proved && s.after_if_proved ? s.after_if_proved : s.after} /></div>
        {/if}
        {#if s.rationale}<p class="xs"><strong>{t('sugg.why')}</strong> {s.rationale}</p>{/if}
        {#if s.evidence.lean?.length || s.evidence.calcul?.length || s.evidence.citations?.length}
          <details class="ev"><summary class="xs">{t('sugg.evidence')}</summary>
            {#each s.evidence.lean ?? [] as l}
              <p class="xs">Lean : <a href="/d/{encodeURIComponent(l.dossier_id)}">{l.title ?? l.dossier_id}</a> —
                <span class="chip {l.proved ? 'proved' : l.running ? 'running' : l.vacuous ? 'failed' : ''}">{l.vacuous ? t('sugg.lean.vacuous') : l.proved ? t('sugg.lean.proved') : l.running ? t('sugg.lean.running') : l.statement_ok ? t('sugg.lean.statement') : t('sugg.lean.none')}</span></p>
              {#if l.lean}<details><summary class="xs">{t('sugg.lean.code')}</summary><pre class="out">{l.lean}</pre></details>{/if}
            {/each}
            {#each s.evidence.calcul ?? [] as c}
              <div class="xs">Sage : <a href="/calcul">{t('sugg.cell', { id: c.cell_id })}</a>
                {#if !c.run}<span class="chip running">{c.approved ? t('sugg.calc.notRun') : t('sugg.calc.toApprove')}</span>
                {:else if c.run.ok}<span class="chip proved">{t('sugg.calc.ok')}</span>{:else}<span class="chip failed">{t('sugg.calc.error')}</span>{/if}
                {#if c.run?.text}<pre class="out">{c.run.text}</pre>{/if}
                {#each c.run?.assets ?? [] as a}<img src="/api/calcul/assets/{a}" alt={t('sugg.figureAlt', { t: s.title })} loading="lazy" />{/each}
              </div>
            {/each}
            {#each s.evidence.citations ?? [] as c}
              <p class="xs">{#if c.key}[@{c.key}{c.locator ? `, ${c.locator}` : ''}]{:else if c.url}<a href={c.url.startsWith('http') ? c.url : `https://doi.org/${c.url}`} target="_blank" rel="noopener noreferrer">{c.title}</a>{c.year ? ` (${c.year})` : ''}{:else}{c.title}{/if}</p>
            {/each}
          </details>
        {/if}
        {#if s.status === 'proposed'}
          {#if s.id in editing}
            <label class="sr-only" for="ed-{s.id}">{t('sugg.editLabel')}</label>
            <textarea id="ed-{s.id}" class="input" rows="4" bind:value={editing[s.id]}></textarea>
          {/if}
          <div class="row">
            <button class="btn small primary" onclick={() => accept(s)} disabled={busy === s.id}>{s.id in editing ? t('sugg.acceptEdited') : t('sugg.accept')}</button>
            {#if s.target.mode !== 'add_dossier' && !(s.id in editing)}<button class="btn small" onclick={() => (editing[s.id] = s.after)}>{t('sugg.edit')}</button>{/if}
            <button class="btn small quiet" onclick={() => reject(s)} disabled={busy === s.id}>{t('sugg.reject')}</button>
          </div>
        {/if}
      </li>
    {/each}
  </ol>
</section>

<style>
  .sugg { margin-bottom: var(--s-4); }
  .filters .input { width: auto; }
  .list { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: var(--s-3); }
  .item { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); }
  .item.accepted { border-color: color-mix(in srgb, var(--proved) 50%, var(--line)); }
  .item.rejected, .item.stale { opacity: 0.75; }
  .diff { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
  del { background: var(--failed-soft); color: var(--text); text-decoration: line-through; }
  ins { background: var(--proved-soft, color-mix(in srgb, var(--proved) 18%, transparent)); color: var(--text); text-decoration: underline; }
  .after { border-left: 3px solid var(--accent); padding-left: var(--s-2); margin: 4px 0; }
  .ev img { max-width: 100%; max-height: 280px; display: block; margin: 4px 0; background: white; }
  .out { max-height: 10rem; overflow: auto; white-space: pre-wrap; font-size: var(--fs-xs); background: var(--surface-2, var(--surface)); padding: 4px; }
  textarea { width: 100%; }
</style>
