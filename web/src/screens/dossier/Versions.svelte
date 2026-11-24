<script lang="ts">
  // « Versions (n) »: the list in a dialog (the pane's « Versions » tab shows the same lists).
  import type { Dossier, VersionKind } from '../../lib/api/types';
  import { t } from '../../lib/i18n/index.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import VersionList from './VersionList.svelte';

  let { dossier: d, kind, busy = false }: { dossier: Dossier; kind: VersionKind; busy?: boolean } = $props();
  const n = $derived((kind === 'statement' ? d.statements : kind === 'proof' ? d.proofs : d.explanations).length);
  let open = $state(false);
</script>

{#if n > 1}
  <button class="btn small" onclick={() => (open = true)}>{t('versions.button', { n })}</button>
{/if}

<Dialog bind:open title={t(`versions.title.${kind}`)} wide>
  <VersionList dossier={d} {kind} {busy} />
  {#if busy}<p class="hint">{t('versions.busy')}</p>{/if}
</Dialog>
