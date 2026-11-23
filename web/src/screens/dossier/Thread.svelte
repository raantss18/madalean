<script lang="ts">
  // The dossier's thread (« fil »): every request and every result, in order, with who produced it; follow-up
  // requests to the statement, the proof or the explanation (or « auto »: the router decides).
  import type { Dossier, Job, FollowStage, DossierEvent } from '../../lib/api/types';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { modelLabel } from '../../lib/status';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import { follow, stop } from './actions';
  import StatementVerdict from './StatementVerdict.svelte';
  import EnterHint from '../../components/EnterHint.svelte';
  import { enterSubmit } from '../../lib/ui/enter';

  let { dossier: d, job }: { dossier: Dossier; job: Job | undefined } = $props();
  let text = $state('');
  let loadedFor = '';
  $effect(() => { if (loadedFor !== d.id) { loadedFor = d.id; text = loadJSON<string>(`draft.thread.${d.id}`, ''); } });
  let stage = $state<FollowStage>('auto');
  let sending = $state(false);
  let all = $state(false);
  $effect(() => { if (loadedFor === d.id) saveJSON(`draft.thread.${d.id}`, text); });
  const events = $derived(all ? d.events : d.events.slice(-60));
  const STEP_OF: Record<string, string> = { understood: 'enonce', statement: 'lean', notes: 'lean', check: 'lean', proof: 'preuve', explanation: 'preuve', informal: 'preuve' };

  async function send() {
    if (!text.trim() || sending) return;
    sending = true;
    const msg = text.trim();
    text = '';
    const ok = await follow(d.id, msg, stage);
    if (!ok) text = msg;   // the request comes back to the input (L Katta)
    sending = false;
  }
  // S-AK: Enter sends, Shift+Enter is a new line (lib/ui/enter.ts)
  function firstLine(ev: DossierEvent): string { return ev.text.split('\n')[0] ?? ''; }
  // only the last statement check of the current statement offers « Corriger » / « Prouver quand même »
  const lastCheck = $derived([...d.events].reverse().find((e) => e.kind === 'check'));
  function rest(ev: DossierEvent): string { return ev.text.split('\n').slice(1).join('\n'); }
</script>

<section class="thread" aria-labelledby="th-h">
  <h2 id="th-h">{t('thread.title')}</h2>
  {#if d.events.length > 60 && !all}<button class="btn small quiet" onclick={() => (all = true)}>{t('thread.earlier', { n: d.events.length - 60 })}</button>{/if}
  <ol class="events" aria-label={t('thread.events')}>
    {#each events as ev, i (i + ':' + ev.t)}
      <li class="ev {ev.kind}">
        {#if ev.kind === 'user'}
          <div class="bubble me">
            <span class="meta xs">{t('thread.you')}{#if ev.stage && ev.stage !== 'auto'} · {tk(`follow.${ev.stage}`, ev.stage)}{/if} · {fmtTime(ev.t)}</span>
            <p>{ev.text}</p>
          </div>
        {:else}
          <div class="bubble">
            <span class="meta xs">
              {#if ev.kind === 'error'}<Icon name="warn" size={12} />{/if}
              {ev.kind === 'certificate' ? 'Sage + Lean' : ev.model ? modelLabel(ev.model).name : ev.kind === 'info' || ev.kind === 'error' ? 'Madalean' : 'Lean'} · {fmtTime(ev.t)}
            </span>
            <p class="first">{firstLine(ev)}</p>
            {#if ev.kind === 'check'}<StatementVerdict id={d.id} params={ev.params} busy={Boolean(job)}
              actions={ev === lastCheck && ev.ref === d.cur_statement && !d.proofs.some((p) => p.parent === d.cur_statement && p.ok)} />
            {:else if rest(ev).trim()}<details><summary class="xs">{t('thread.details')}</summary><Md src={rest(ev)} /></details>{/if}
            {#if STEP_OF[ev.kind]}<a class="xs" href="/d/{encodeURIComponent(d.id)}/{STEP_OF[ev.kind]}">{t('thread.see')}</a>{/if}
          </div>
        {/if}
      </li>
    {/each}
  </ol>

  <form class="composer" onsubmit={(e) => { e.preventDefault(); void send(); }}>
    <label for="follow-{d.id}" class="label">{t('thread.ask')}</label>
    <textarea id="follow-{d.id}" class="input" rows="3" bind:value={text} use:enterSubmit={() => void send()} placeholder={t('thread.placeholder')} aria-describedby="follow-h-{d.id} follow-e-{d.id}"></textarea>
    <EnterHint id="follow-e-{d.id}" />
    <p class="hint" id="follow-h-{d.id}">{job ? t('thread.busy') : t('thread.hint')}</p>
    <div class="row">
      <label class="sr-only" for="follow-stage-{d.id}">{t('thread.target')}</label>
      <select id="follow-stage-{d.id}" class="input stage" bind:value={stage}>
        {#each ['auto', 'statement', 'proof', 'explanation'] as s}<option value={s}>{tk(`follow.${s}`, s)}</option>{/each}
      </select>
      {#if job}
        <button class="btn danger" type="button" onclick={() => stop(d.id)}><Icon name="stop" size={14} />{t('common.stop')}</button>
      {:else}
        <button class="btn primary" type="submit" disabled={!text.trim() || sending} aria-keyshortcuts="Control+Enter"><Icon name="send" size={16} />{t('thread.send')}</button>
      {/if}
    </div>
  </form>
  <a class="btn small quiet planlink" href="/d/{encodeURIComponent(d.id)}/plan"><Icon name="split" size={14} />{t('plan.fromThread')}</a>
</section>

<style>
  .thread { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-4); }
  .events { list-style: none; padding: 0; margin: 0 0 var(--s-3); display: grid; gap: var(--s-2); }
  .bubble { padding: var(--s-2) var(--s-3); border-radius: var(--r-2); background: var(--surface-2); font-size: var(--fs-sm); }
  .bubble p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
  .bubble.me { background: var(--accent-soft); margin-left: 14%; }
  .ev.error .bubble { background: var(--failed-soft); }
  .ev.proof .bubble { border-left: 3px solid var(--proved); }
  .ev.check .bubble { border-left: 3px solid var(--accent); }
  .ev.certificate .bubble { border-left: 3px solid var(--proved); }
  .ev.info .bubble { background: transparent; border: 1px dashed var(--line); color: var(--text-2); }
  .meta { display: flex; align-items: center; gap: 4px; color: var(--text-3); font-weight: 600; margin-bottom: 2px; }
  details summary { cursor: pointer; color: var(--text-2); }
  .composer .stage { width: auto; flex: 1; min-width: 9rem; }
</style>
