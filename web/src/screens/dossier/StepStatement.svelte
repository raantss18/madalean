<script lang="ts">
  // Step 1 « Énoncé »: the problem as the user wrote it (editable), what the AI understood, re-translate.
  import type { Dossier, Job } from '../../lib/api/types';
  import { t } from '../../lib/i18n/index.svelte';
  import { modelLabel } from '../../lib/status';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import Md from '../../components/Md.svelte';
  import StreamView from '../../components/StreamView.svelte';
  import { patch, run } from './actions';
  import { navigate } from '../../lib/router.svelte';

  let { dossier: d, job }: { dossier: Dossier; job: Job | undefined } = $props();
  let editing = $state(false);
  let text = $state('');
  let saving = $state(false);
  const understoodEvent = $derived([...d.events].reverse().find((e) => e.kind === 'understood'));
  const translating = $derived(job && ['understand', 'route'].includes(job.stage));

  function startEdit() { text = d.problem; editing = true; }
  async function save(rerun: boolean) {
    saving = true;
    const ok = await patch(d.id, { problem: text });
    saving = false;
    if (!ok) return;
    editing = false;
    if (rerun && (await run(d.id, ['understand', 'statement']))) navigate(`/d/${encodeURIComponent(d.id)}/lean`);
  }
</script>

<div class="stack">
  <section class="panel" aria-labelledby="pb-h">
    <div class="row"><h2 id="pb-h">{t('enonce.problem')}</h2><span class="spacer"></span>
      {#if !editing}<button class="btn small" onclick={startEdit} disabled={Boolean(job)}>{t('common.edit')}</button>{/if}
    </div>
    {#if editing}
      <CodeEditor bind:value={text} language="natural" label={t('enonce.problem')} minLines={5} onSubmit={() => save(true)} />
      <div class="row" style="margin-top: var(--s-3)">
        <button class="btn primary" onclick={() => save(true)} disabled={saving || !text.trim()}>{t('enonce.saveRetranslate')}</button>
        <button class="btn" onclick={() => save(false)} disabled={saving}>{t('enonce.saveOnly')}</button>
        <button class="btn quiet" onclick={() => (editing = false)}>{t('common.cancel')}</button>
      </div>
      <p class="hint">{t('enonce.editHint')}</p>
    {:else if d.problem}
      <div class="theorem"><span class="th-head">{t('home.statementWord')}. </span><Md src={d.problem} cls="th-body" /></div>
    {:else}
      <p class="muted">{t('enonce.noProblem')}</p>
    {/if}
    {#if d.source?.original_text}
      <details><summary class="small">{t('enonce.source', { where: d.source.locator })}</summary><Md src={d.source.original_text} /></details>
    {/if}
  </section>

  <section class="panel" aria-labelledby="und-h">
    <h2 id="und-h">{t('enonce.understood')}</h2>
    {#if translating && job}
      <p class="small">{t('enonce.understanding')}</p>
      <StreamView jobId={job.id} stage={job.stage} maxHeight="240px" />
    {:else if d.understood_display}
      <p class="hint">{t('enonce.understoodHint')}</p>
      <div class="theorem understood"><Md src={d.understood_display} cls="th-body" /></div>
      {#if understoodEvent?.model}<p class="xs muted">{t('common.by', { model: modelLabel(understoodEvent.model).name })}</p>{/if}
    {:else}
      <p class="muted small">{d.statements.length ? t('enonce.leanOnly') : t('enonce.notYet')}</p>
      {#if d.problem && !job}<button class="btn primary" onclick={async () => { if (await run(d.id, ['understand', 'statement'])) navigate(`/d/${encodeURIComponent(d.id)}/lean`); }}>{t('enonce.translate')}</button>{/if}
    {/if}
  </section>
</div>

<style>
  h2 { margin: 0; }
  .panel .theorem { margin-top: var(--s-3); max-width: var(--measure); }
  .understood { border-left: 3px solid var(--line-strong); padding-left: var(--s-3); }
  .theorem :global(.md), .theorem :global(.md p) { display: inline; }
  details { margin-top: var(--s-3); }
  summary { cursor: pointer; min-height: var(--touch); display: flex; align-items: center; }
</style>
