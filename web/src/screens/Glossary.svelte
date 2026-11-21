<script lang="ts">
  import { GLOSSARY, type GlossKind } from '../lib/lean/glossary';
  import { ABBREVIATIONS } from '../lib/lean/abbrev';
  import { t, tk, i18n } from '../lib/i18n/index.svelte';
  let { params: _p }: { params: Record<string, string> } = $props();
  let q = $state('');
  let kind = $state<GlossKind | ''>('');
  const entries = $derived(Object.entries(GLOSSARY).filter(([k, e]) => (!kind || e.kind === kind) && (!q.trim() || (k + ' ' + e[i18n.lang]).toLowerCase().includes(q.trim().toLowerCase()))));
  const abbr = $derived(Object.entries(ABBREVIATIONS).filter(([k, v]) => !q.trim() || k.includes(q.trim()) || v === q.trim()));
</script>

<div class="glossary">
  <h1>{t('glossary.title')}</h1>
  <p class="lead">{t('glossary.lead')}</p>
  <div class="row filters">
    <label class="sr-only" for="g-q">{t('glossary.search')}</label>
    <input id="g-q" class="input" type="search" placeholder={t('glossary.search')} bind:value={q} />
    <label class="sr-only" for="g-k">{t('glossary.kind')}</label>
    <select id="g-k" class="input" bind:value={kind} style="width:auto">
      <option value="">{t('glossary.all')}</option>
      {#each ['tactic', 'keyword', 'notation', 'type', 'predicate'] as k}<option value={k}>{tk(`gloss.kind.${k}`, k)}</option>{/each}
    </select>
  </div>
  <dl class="entries">
    {#each entries as [k, e] (k)}
      <div><dt><code>{k}</code> <span class="chip">{tk(`gloss.kind.${e.kind}`, e.kind)}</span></dt><dd>{e[i18n.lang]}</dd></div>
    {:else}<p class="muted">{t('glossary.none')}</p>{/each}
  </dl>
  <h2>{t('glossary.abbrevTitle')}</h2>
  <p class="small">{t('glossary.abbrevLead')}</p>
  <ul class="abbr">{#each abbr as [k, v] (k)}<li><kbd>\{k}</kbd> <span class="sym">{v}</span></li>{/each}</ul>
</div>

<style>
  .glossary { max-width: 900px; }
  .lead { color: var(--text-2); }
  .filters { margin-bottom: var(--s-4); }
  .filters .input[type='search'] { max-width: 360px; flex: 1; }
  .entries { margin: 0; display: grid; gap: var(--s-2); }
  .entries > div { border-bottom: 1px solid var(--line); padding: var(--s-2) 0; }
  dt { font-weight: 600; }
  dd { margin: 4px 0 0; color: var(--text-2); }
  .abbr { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 6px; }
  .sym { font-family: var(--font-mono); font-size: 1.1rem; }
</style>
