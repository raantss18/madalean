<script lang="ts">
  // S-AM (D45): « Expliquer » for Lean, right below the code it acts on (statement, proof, a note's Lean block).
  // « Expliquer l'erreur »: plain words from Lean's own messages, and a correction shown ONLY when the workspace's
  // Lean accepted it (« acceptée par Lean », never « vérifiée »: applying it makes a new version, checked again).
  // « Expliquer ligne par ligne »: tactic by tactic, with the goal Lean printed after each line when it gave one.
  // Streamed (`lean.explain` events), cached by the server. The menu follows the S-AK rules (outside click /
  // Escape close it, focus back on its button; a bottom sheet on phones).
  import { onDestroy } from 'svelte';
  import type { CheckResult, LeanExplainAnswer, LeanExplainWhere } from '../lib/api/types';
  import { api } from '../lib/api/client';
  import { app } from '../lib/store/app.svelte';
  import { t } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import { toast } from '../lib/ui/toasts.svelte';
  import Menu, { type MenuItem } from './Menu.svelte';
  import Md from './Md.svelte';
  import Icon from './Icon.svelte';

  let { where, code = undefined, errors = null, canError = false, onApply = undefined, disabled = false }: {
    where: LeanExplainWhere; code?: string; errors?: CheckResult['errors'] | null; canError?: boolean;
    onApply?: (fix: string) => Promise<boolean>; disabled?: boolean;
  } = $props();

  const uid = Math.random().toString(36).slice(2, 8);
  let mode = $state<'error' | 'lines' | null>(null);
  let answer = $state<LeanExplainAnswer | null>(null);
  let live = $state('');
  let phase = $state<'' | 'writing' | 'checking' | 'repairing'>('');
  let busy = $state(false);
  let applying = $state(false);
  let stream = '';
  let ctl: AbortController | null = null;

  const hasError = $derived(canError || Boolean(errors?.some((e) => e.severity === 'error')));
  const items = $derived<MenuItem[]>([
    ...(hasError ? [{ label: t('lx.error'), icon: 'warn', run: () => void ask('error') }] : []),
    { label: t('lx.lines'), icon: 'list', run: () => void ask('lines') },
  ]);

  $effect(() => app.on('lean.explain', (ev) => {
    const e = ev as unknown as { stream: string; text: string; state: string };
    if (!stream || e.stream !== stream) return;
    if (e.state === 'writing') { live = e.text; phase = 'writing'; }
    else if (e.state === 'checking' || e.state === 'repairing') phase = e.state;
  }));

  async function ask(m: 'error' | 'lines') {
    ctl?.abort();
    ctl = new AbortController();
    mode = m; answer = null; live = ''; phase = ''; busy = true;
    stream = `lx-${uid}-${Date.now().toString(36)}`;
    const errs = (errors ?? []).filter((e) => e.text).map((e) => ({ line: e.line, col: e.col, text: e.text, severity: e.severity }));
    try {
      answer = await api.leanExplain({ ...where, mode: m, stream, ...(code !== undefined ? { code } : {}),
        ...(m === 'error' && errs.length ? { errors: errs } : {}) }, { signal: ctl.signal });
    } catch (e) {
      if ((e as Error).name !== 'AbortError') { toast('error', errorText(e)); mode = null; }
    } finally { busy = false; phase = ''; ctl = null; }
  }
  /** `name` spans of a one-line explanation as code (no Markdown renderer for each line). */
  function inline(s: string): { t: string; code: boolean }[] {
    return s.split(/(`[^`\n]+`)/).filter(Boolean).map((p) => (p.length > 2 && p.startsWith('`') && p.endsWith('`') ? { t: p.slice(1, -1), code: true } : { t: p, code: false }));
  }
  function close() { ctl?.abort(); mode = null; answer = null; live = ''; }
  async function apply() {
    if (!answer?.fix || !onApply) return;
    applying = true;
    try { if (await onApply(answer.fix)) close(); } finally { applying = false; }
  }
  onDestroy(() => ctl?.abort());
</script>

<div class="lx">
  <Menu label={t('lx.menu')} text={t('lx.menu')} icon="sparkle" align="left" {items} />
</div>
{#if mode}
  <section class="lx-out" aria-labelledby="lx-h-{uid}" aria-busy={busy}>
    <div class="row head">
      <h3 id="lx-h-{uid}" class="xs">{mode === 'error' ? t('lx.errorTitle') : t('lx.linesTitle')}</h3>
      <span class="spacer"></span>
      <button class="btn xsmall quiet" onclick={close}>{t('common.close')}</button>
    </div>
    {#if busy}
      <p class="xs muted" role="status">{phase === 'checking' ? t('lx.checking') : phase === 'repairing' ? t('lx.repairing') : t('lx.explaining')}</p>
      {#if live && mode === 'error'}<div class="live"><Md src={live} /></div>{/if}
    {:else if answer && mode === 'error'}
      {#if answer.no_error}
        <p class="small" role="status"><Icon name="check" size={14} /> {t('lx.noError')}</p>
      {:else}
        <Md src={answer.explanation ?? ''} />
        {#if answer.fix && answer.fix_status === 'accepted'}
          <p class="xs ok-note"><Icon name="check" size={14} /> {t('lx.fixAccepted', { lean: answer.lean || '?' })}</p>
          <pre class="fix" aria-label={t('lx.fixLabel')}>{answer.fix}</pre>
          {#if onApply}
            <button class="btn small primary" onclick={apply} disabled={applying || disabled}><Icon name="check" size={14} />{applying ? t('lean.checking') : t('lx.apply')}</button>
            <p class="xs muted">{t('lx.applyHint')}</p>
          {/if}
        {:else if answer.fix_status === 'rejected'}
          <p class="xs muted">{t('lx.fixRejected')}</p>
        {:else if answer.fix_status === 'unchecked'}
          <p class="xs muted">{t('lx.fixUnchecked')}</p>
        {:else}
          <p class="xs muted">{t('lx.noFix')}</p>
        {/if}
      {/if}
    {:else if answer && mode === 'lines'}
      <p class="xs muted">{answer.goals === 'lean' ? t('lx.goalsFromLean') : t('lx.noGoals')}</p>
      <ol class="line-list">
        {#each answer.lines ?? [] as l (l.line)}
          {#if l.code.trim()}
            <li>
              <code class="lc"><span class="ln" aria-hidden="true">{l.line}</span>{l.code}</code>
              <div class="lt">
                <span>{#each inline(l.text) as p}{#if p.code}<code>{p.t}</code>{:else}{p.t}{/if}{/each}</span>
                {#if l.goal}
                  <details class="goal"><summary class="xs">{t('lx.goalAfter')}</summary>
                    <pre>{l.goal === 'no goals' ? t('lx.goalNone') : l.goal}</pre></details>
                {/if}
              </div>
            </li>
          {/if}
        {/each}
      </ol>
    {/if}
  </section>
{/if}

<style>
  .lx { display: inline-block; }
  /* inside a wrapping button row (.row) the answer takes its own full-width line, right under the buttons */
  .lx-out { flex: 1 0 100%; width: 100%; box-sizing: border-box; margin-top: var(--s-2); padding: var(--s-2) var(--s-3); background: var(--surface-2); border-radius: var(--r-2); border: 1px solid var(--line); min-width: 0; }
  .head { align-items: center; }
  h3 { margin: 0; font-weight: 700; }
  .live { opacity: 0.85; }
  .ok-note { color: var(--proved); display: flex; gap: 4px; align-items: center; margin: var(--s-2) 0 4px; }
  .fix { font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-1); padding: var(--s-2); max-height: 320px; overflow: auto; margin: 0 0 var(--s-2); }
  .line-list { list-style: none; padding: 0; margin: var(--s-1) 0 0; display: grid; gap: 6px; }
  .line-list li { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); gap: var(--s-2); align-items: baseline; }
  @media (max-width: 599px) { .line-list li { grid-template-columns: minmax(0, 1fr); gap: 2px; } }
  .lc { font: 0.8125rem/1.4 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-2); }
  .ln { display: inline-block; min-width: 2.2em; color: var(--text-2); user-select: none; }
  .lt { font-size: var(--fs-sm, 0.875rem); min-width: 0; }
  .goal { margin-top: 2px; }
  .goal summary { cursor: pointer; color: var(--text-2); min-height: 24px; display: inline-flex; align-items: center; }
  @media (pointer: coarse) { .goal summary { min-height: var(--touch); } }
  .goal pre { font: 0.75rem/1.4 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface); border-radius: var(--r-1); padding: 4px var(--s-2); margin: 2px 0 0; }
</style>
