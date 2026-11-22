<script lang="ts">
  import EnterHint from './EnterHint.svelte';
  import { enterSubmit } from '../lib/ui/enter';
  // Grounded answers (NotebookLM-like): every sentence carries the passages it rests on; a click on a citation opens
  // the source at that passage. Sentences without a verified citation are shown struck as « non étayé »; the optional
  // general-knowledge part is labelled as such. POST /research/ask|summarize|compare → qa.token… qa.done.
  import { research, type Citation, type QaResult } from '../lib/api/research';
  import { app } from '../lib/store/app.svelte';
  import { t, tk } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import Md from './Md.svelte';
  import Icon from './Icon.svelte';

  let {
    project, scope, oncite, title = '', summary = null, compare = null,
  }: {
    project: string; scope?: { shelves?: string[]; sources?: string[] }; oncite: (c: Citation) => void; title?: string;
    summary?: { shelf: string; source: string } | null; compare?: { shelf: string; id: string }[] | null;
  } = $props();

  interface Turn { q: string; kind: string; result: QaResult | null; streaming: string; error: string; rid: string }
  let turns = $state<Turn[]>([]);
  let question = $state('');
  let general = $state(false);
  let busy = $state(false);

  async function run(kind: 'ask' | 'summary' | 'compare', q: string) {
    if (busy) return;
    busy = true;
    const turn: Turn = { q, kind, result: null, streaming: '', error: '', rid: '' };
    turns = [...turns, turn];
    const i = turns.length - 1;
    try {
      const r = kind === 'ask' ? await research.ask(q, project, scope, general)
        : kind === 'summary' && summary ? await research.summarize(summary.shelf, summary.source)
        : await research.compare(compare ?? []);
      turns[i]!.rid = r.request_id;
      await new Promise<void>((resolve) => {
        app.listenRequest(r.request_id, (ev) => {
          if (ev.type === 'qa.token') turns[i]!.streaming += ev.text;
          else if (ev.type === 'qa.done') { turns[i]!.result = ev['result'] as QaResult; resolve(); }
          else if (ev.type === 'qa.error') { turns[i]!.error = (ev.text as string) || String(ev['error'] ?? ''); resolve(); }
        });
      });
    } catch (e) { turns[i]!.error = errorText(e); } finally { busy = false; }
  }
  function ask(e: Event) { e.preventDefault(); const q = question.trim(); if (!q) return; question = ''; void run('ask', q); }
  function stop() { const rid = turns[turns.length - 1]?.rid; if (rid) void research.stopRequest(rid); }
</script>

<section class="qa" aria-labelledby="qa-h">
  <h2 id="qa-h">{title || t('qa.title')}</h2>
  <p class="hint">{t('qa.lead')}</p>
  {#if summary || compare}
    <div class="row">
      {#if summary}<button class="btn small" onclick={() => run('summary', t('qa.summaryQ'))} disabled={busy}>{t('qa.summary')}</button>{/if}
      {#if compare && compare.length >= 2}<button class="btn small" onclick={() => run('compare', t('qa.compareQ'))} disabled={busy}>{t('qa.compare', { n: compare.length })}</button>{/if}
    </div>
  {/if}
  <ol class="turns" aria-live="polite">
    {#each turns as turn, ti (ti)}
      <li>
        <p class="q"><Icon name="search" size={14} /> {turn.q}</p>
        {#if turn.error}<p class="error-text">{turn.error}</p>
        {:else if !turn.result}
          <p class="muted small" aria-busy="true">{turn.streaming ? t('qa.writing') : t('qa.searching')}</p>
        {:else}
          {@const r = turn.result}
          {#if r.status !== 'ok'}<p class="notice small">{tk(`qa.status.${r.status}`, r.status)}</p>{/if}
          <div class="answer">
            {#each r.sentences as s}
              <span class="sent" class:unsupported={!s.supported && !s.notice}>
                <Md inline src={s.text} />
                {#each s.citations as c}
                  <button class="cite" onclick={() => oncite(c)} title={`${c.source_key}${c.locator ? ', ' + c.locator : ''}${c.page ? ' p. ' + c.page : ''} — « ${c.quote} »`}
                    aria-label={t('qa.openCitation', { key: c.source_key, where: c.locator || (c.page ? `p. ${c.page}` : '') })}>{c.passage}</button>
                {/each}
                {#if !s.supported && !s.notice}<span class="tag xs">{t('qa.unsupported')}</span>{/if}
              </span>{' '}
            {/each}
          </div>
          {#if r.general?.length}
            <div class="general">
              <p class="xs gl">{t('qa.general')}{#if r.general_model} · {r.general_model}{/if}</p>
              {#each r.general as g}<Md src={g.text} />{/each}
            </div>
          {/if}
          {#if r.passages.length}
            <details><summary class="xs">{t('qa.passages', { n: r.passages.length })}{#if r.dropped} · {t('qa.dropped', { n: r.dropped })}{/if}</summary>
              <ol class="passages">
                {#each r.passages as p}<li><button class="linkish" onclick={() => oncite({ ...p, quote: '', span: [0, 0], match: 1, bbox: null })}>{p.passage} — {p.source_key}{p.locator ? `, ${p.locator}` : ''}</button></li>{/each}
              </ol>
            </details>
          {/if}
          <p class="xs muted">{t('common.by', { model: r.model || '—' })}</p>
        {/if}
      </li>
    {/each}
  </ol>
  <form onsubmit={ask}>
    <label class="label" for="qa-in">{t('qa.ask')}</label>
    <textarea id="qa-in" class="input" rows="2" bind:value={question} placeholder={t('qa.placeholder')}
      use:enterSubmit={() => ask(new Event('submit'))} aria-describedby="qa-e"></textarea>
    <EnterHint id="qa-e" />
    <div class="row">
      <label class="switch small"><input type="checkbox" bind:checked={general} />{t('qa.allowGeneral')}</label>
      <span class="spacer"></span>
      {#if busy}<button class="btn quiet" type="button" onclick={stop}>{t('common.stop')}</button>{/if}
      <button class="btn primary" type="submit" disabled={busy || !question.trim()}>{t('qa.send')}</button>
    </div>
  </form>
</section>

<style>
  .qa h2 { margin-bottom: 2px; }
  .turns { list-style: none; padding: 0; margin: var(--s-3) 0; display: grid; gap: var(--s-3); }
  .q { font-weight: 650; margin: 0 0 4px; display: flex; gap: 6px; align-items: baseline; }
  .answer { line-height: 1.65; font-family: var(--font-serif); }
  .sent.unsupported { color: var(--text-3); text-decoration: line-through; text-decoration-color: var(--line-strong); }
  .cite { font: 600 0.72rem var(--font-ui); vertical-align: super; border: 1px solid var(--accent); color: var(--accent); background: var(--accent-soft); border-radius: 4px; padding: 0 3px; margin-left: 2px; cursor: pointer; min-height: 20px; }
  @media (pointer: coarse) { .cite { min-height: 28px; min-width: 28px; } }
  .tag { color: var(--running); margin-left: 4px; font-family: var(--font-ui); text-decoration: none; display: inline-block; }
  .notice { background: var(--running-soft); color: var(--running); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
  .general { margin-top: var(--s-2); padding: var(--s-2) var(--s-3); border-left: 3px dashed var(--line-strong); }
  .gl { color: var(--text-3); font-weight: 650; margin: 0; }
  .passages { margin: 4px 0; padding-left: 1.2em; font-size: var(--fs-sm); }
  .linkish { background: none; border: 0; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; text-align: left; }
</style>
