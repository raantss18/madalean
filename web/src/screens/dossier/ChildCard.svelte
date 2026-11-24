<script lang="ts">
  // A sub-dossier where it was created in the thread: live status, openable in place, in the pane, or on its own.
  import type { DossierSummary } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { deriveNow, pendingGate } from '../../lib/flow';
  import { t, fmtTime } from '../../lib/i18n/index.svelte';
  import { phaseOf } from '../../lib/status';
  import { separate } from '../../lib/ui/solo.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import StatusMark from '../../components/StatusMark.svelte';
  import Icon from '../../components/Icon.svelte';
  import Md from '../../components/Md.svelte';
  import GateCard from './GateCard.svelte';
  import { activityText } from './flowtext';
  import { stop } from './actions';

  let { child: c0, onpeek }: { child: DossierSummary; onpeek?: (id: string) => void } = $props();
  const c = $derived(app.m.dossiers[c0.id] ?? c0);
  const full = $derived(app.m.full[c0.id]);
  const job = $derived(app.activeJob(c0.id));
  const now = $derived(deriveNow(full ?? ({ now: c.now, gate: c.gate } as never), job));
  const gate = $derived(pendingGate(full ?? ({ gate: c.gate } as never)));
  const title = $derived(c.title || c.theorem);
  let open = $state(false);
  $effect(() => { if (open) void app.ensureDossier(c0.id).catch(() => null); });
</script>

<article class="child" aria-label="{t('flow.child')} : {title}">
  <div class="row">
    <StatusMark phase={phaseOf(c.status, job)} showLabel />
    <span class="xs muted">{t('flow.child')} · {fmtTime(c0.created)}</span>
    {#if gate}<span class="chip running">{t('flow.childWaits')}</span>{/if}
    <span class="spacer"></span>
    {#if job}<button class="btn small danger" onclick={() => stop(c0.id)} aria-label="{t('common.stop')} : {title}"><Icon name="stop" size={14} />{t('common.stop')}</button>{/if}
  </div>
  <p class="ttl"><a href="/d/{encodeURIComponent(c0.id)}">{title}</a></p>
  {#if now && now.waiting !== 'user'}<p class="small muted">{activityText(now)}…</p>{/if}
  <div class="row">
    <button class="btn small" aria-expanded={open} onclick={() => (open = !open)}><Icon name={open ? 'chevronUp' : 'chevronDown'} size={14} />{open ? t('common.hide') : t('flow.childOpen')}<span class="sr-only"> : {title}</span></button>
    {#if onpeek}<button class="btn small quiet" onclick={() => onpeek?.(c0.id)}>{t('flow.childPane')}<span class="sr-only"> : {title}</span></button>{/if}
    <button class="btn small quiet" onclick={() => { if (!separate(c0.id, 'preuve')) toast('warn', t('pane.blocked')); }}><Icon name="external" size={14} />{t('flow.childWindow')}<span class="sr-only"> : {title}</span></button>
  </div>
  {#if open}
    <div class="in">
      {#if !full}<p class="small muted" aria-busy="true">{t('common.loading')}</p>
      {:else}
        {#if gate}<GateCard dossier={full} {gate} />
        {:else}
          {#if full.problem}<Md src={full.problem} />{/if}
          {#if full.current.statement}<pre>{full.current.statement}</pre>{:else}<p class="small muted">{t('flow.childNoStatement')}</p>{/if}
        {/if}
        <ul>{#each full.events.slice(-4) as ev}<li class="small"><span class="xs muted">{fmtTime(ev.t)}</span> {ev.text.split('\n')[0]}</li>{/each}</ul>
        <a class="small" href="/d/{encodeURIComponent(c0.id)}">{t('flow.childGo')}</a>
      {/if}
    </div>
  {/if}
</article>

<style>
  .child { border: 1px solid var(--line); border-left: 4px double var(--accent); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); background: var(--surface); }
  .child p { margin: 2px 0; }
  .ttl a { color: var(--text); font-weight: 600; text-decoration: none; overflow-wrap: anywhere; }
  .ttl a:hover { text-decoration: underline; }
  .in { margin-top: var(--s-2); padding-top: var(--s-2); border-top: 1px dashed var(--line); }
  pre { margin: 4px 0; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); font: 0.8125rem/1.5 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; }
  ul { margin: var(--s-2) 0; padding-left: 1.1em; }
</style>
