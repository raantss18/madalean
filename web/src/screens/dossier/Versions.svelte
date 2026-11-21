<script lang="ts">
  // Versions of the statement / proof / explanation: who wrote each (AI model or you), when, did Lean accept it,
  // view it, restore it (nothing is ever deleted).
  import type { Dossier, VersionKind } from '../../lib/api/types';
  import { api } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t, fmtTime } from '../../lib/i18n/index.svelte';
  import { modelLabel } from '../../lib/status';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Md from '../../components/Md.svelte';
  import { reportError } from './actions';

  let { dossier: d, kind, busy = false }: { dossier: Dossier; kind: VersionKind; busy?: boolean } = $props();
  const list = $derived(kind === 'statement' ? d.statements : kind === 'proof' ? d.proofs : d.explanations);
  const cur = $derived(kind === 'statement' ? d.cur_statement : kind === 'proof' ? d.cur_proof : d.cur_explanation);
  let viewing = $state<number | null>(null);
  let open = $state(false);
  let restoring = $state(-1);

  async function restore(i: number) {
    const prev = cur;
    restoring = i;
    try {
      const r = await api.restoreVersion(d.id, kind, i);
      app.m.full[d.id] = r.dossier;
      toast('ok', t('versions.restored', { n: i + 1 }), { action: { label: t('common.undo'), run: async () => {
        try { const r2 = await api.restoreVersion(d.id, kind, prev); app.m.full[d.id] = r2.dossier; } catch (e) { reportError(e, d.id); }
      } } });
      viewing = null;
    } catch (e) { reportError(e, d.id); } finally { restoring = -1; }
  }
</script>

{#if list.length > 1}
  <button class="btn small" onclick={() => (open = true)}>{t('versions.button', { n: list.length })}</button>
{/if}

<Dialog bind:open title={t(`versions.title.${kind}`)} wide>
  <ol class="vlist" reversed>
    {#each [...list.keys()].reverse() as i (i)}
      {@const v = list[i]!}
      <li class:current={i === cur}>
        <div class="vh row">
          <strong>{t('versions.n', { n: i + 1 })}</strong>
          {#if i === cur}<span class="chip proved">{t('versions.current')}</span>{/if}
          <span class="chip {v.source === 'user' ? '' : modelLabel(v.model).local ? 'local' : 'online'}">{v.source === 'user' ? t('versions.byYou') : modelLabel(v.model).name || t('versions.byAi')}</span>
          {#if kind !== 'explanation'}<span class="chip {v.ok ? 'proved' : 'failed'}">{v.ok ? t('versions.leanOk') : t('versions.leanNo')}</span>{/if}
          <span class="xs muted">{fmtTime(v.t)}</span>
          <span class="spacer"></span>
          <button class="btn small" aria-expanded={viewing === i} onclick={() => (viewing = viewing === i ? null : i)}>{viewing === i ? t('versions.hide') : t('versions.view')}</button>
          {#if i !== cur}<button class="btn small primary" disabled={busy || restoring >= 0} onclick={() => restore(i)}>{t('versions.restore')}</button>{/if}
        </div>
        {#if v.note}<p class="xs muted">{t('versions.request', { note: v.note })}</p>{/if}
        {#if viewing === i}
          {#if kind === 'explanation'}<Md src={v.code} />{:else}<pre class="code">{v.code}</pre>{/if}
        {/if}
      </li>
    {/each}
  </ol>
  {#if busy}<p class="hint">{t('versions.busy')}</p>{/if}
</Dialog>

<style>
  .vlist { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-2); }
  .vlist li { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); }
  .vlist li.current { border-color: var(--proved); }
  .vh { gap: 6px; }
  .code { font: 0.8125rem/1.5 var(--font-mono); background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 300px; overflow: auto; }
</style>
