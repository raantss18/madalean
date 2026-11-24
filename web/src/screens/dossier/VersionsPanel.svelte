<script lang="ts">
  // Pane « Versions »: every version of the statement, the proof and the explanation.
  import type { Dossier } from '../../lib/api/types';
  import { t } from '../../lib/i18n/index.svelte';
  import VersionList from './VersionList.svelte';
  let { dossier: d, busy = false }: { dossier: Dossier; busy?: boolean } = $props();
  const KINDS = ['statement', 'proof', 'explanation'] as const;
  const n = (k: (typeof KINDS)[number]) => (k === 'statement' ? d.statements : k === 'proof' ? d.proofs : d.explanations).length;
</script>

{#each KINDS.filter((k) => n(k)) as k (k)}
  <section class="panel" aria-labelledby="vp-{k}">
    <h2 id="vp-{k}">{t(`versions.title.${k}`)}</h2>
    <VersionList dossier={d} kind={k} {busy} />
  </section>
{:else}<p class="muted">{t('pane.noVersions')}</p>{/each}
{#if busy}<p class="hint">{t('versions.busy')}</p>{/if}
