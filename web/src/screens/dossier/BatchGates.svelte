<script lang="ts">
  // D64: one card approves the Lean statements of several sub-dossiers (known results around an open problem).
  import type { Dossier } from '../../lib/api/types';
  import { flow } from '../../lib/api/flow';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { app } from '../../lib/store/app.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Icon from '../../components/Icon.svelte';
  import Md from '../../components/Md.svelte';
  import { flowError } from './flowtext';

  let { dossier: d, waiting }: { dossier: Dossier; waiting: Dossier[] } = $props();
  let off = $state<Record<string, boolean>>({});
  let busy = $state(false);
  const on = $derived(waiting.filter((c) => !off[c.gate!.id]));
  async function approve() {
    if (!on.length || busy) return;
    busy = true;
    const ids = on.map((c) => c.id);
    try {
      await flow.approveMany(on.map((c) => ({ dossier_id: c.id, gate_id: c.gate!.id })));
      toast('ok', t('gate.approved'));
    } catch (e) { await flowError(e, d.id); } finally {
      for (const id of ids) await app.ensureDossier(id, true).catch(() => null);
      busy = false;
    }
  }
</script>

<section class="batch" id="batch-{d.id}" tabindex="-1" aria-labelledby="batch-h-{d.id}">
  <h3 id="batch-h-{d.id}"><Icon name="info" size={18} /> {t('gate.many')}</h3>
  <p class="hint">{t('gate.manyHint')} {t('gate.statementNote')}</p>
  <ul>
    {#each waiting as c (c.id)}
      {@const s = c.gate!.statement ?? {}}
      {@const k = s.candidates?.find((x) => x.version === s.chosen) ?? s.candidates?.[0]}
      <li>
        <label class="pick"><input type="checkbox" checked={!off[c.gate!.id]} onchange={(e) => (off[c.gate!.id] = !e.currentTarget.checked)} /><span><strong>{c.title || c.theorem}</strong>
          {#if k?.verdict && k.verdict !== 'faithful'}<span class="chip running">{tk(`gate.verdict.${k.verdict}`, k.verdict)}</span>{/if}</span></label>
        {#if k?.back_translation}<div class="small"><Md src={k.back_translation} /></div>{/if}
        {#if k}<details><summary class="xs">{t('flow.leanCode', { n: k.version + 1 })}</summary><pre>{k.code}</pre></details>{/if}
        <a class="xs" href="/d/{encodeURIComponent(c.id)}">{t('flow.childGo')}<span class="sr-only"> : {c.title || c.theorem}</span></a>
      </li>
    {/each}
  </ul>
  <button class="btn primary" disabled={!on.length || busy} onclick={approve}><Icon name="check" size={16} />{t('gate.approveMany', { n: on.length })}</button>
</section>

<style>
  .batch { border: 2px solid var(--running); border-radius: var(--r-3); padding: var(--s-4); background: var(--surface); scroll-margin: 180px 0 160px; }
  h3 { margin: 0 0 4px; display: flex; gap: 8px; align-items: center; font-family: var(--font-serif); font-size: 1.0625rem; }
  ul { list-style: none; padding: 0; margin: var(--s-3) 0; display: grid; gap: var(--s-2); }
  li { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); }
  .pick { display: flex; gap: 10px; align-items: center; min-height: var(--touch); cursor: pointer; }
  pre { margin: 4px 0; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); font: 0.8125rem/1.5 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; }
  li :global(.md p) { margin: 0; }
</style>
