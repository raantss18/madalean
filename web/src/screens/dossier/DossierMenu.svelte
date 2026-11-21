<script lang="ts">
  import type { Dossier } from '../../lib/api/types';
  import { t } from '../../lib/i18n/index.svelte';
  import Menu, { type MenuItem } from '../../components/Menu.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import ExportMenu from './ExportMenu.svelte';
  import SplitDialog from './SplitDialog.svelte';
  import { patch, removeDossier } from './actions';
  import { toast } from '../../lib/ui/toasts.svelte';

  let { dossier, busy }: { dossier: Dossier; busy: boolean } = $props();
  let renaming = $state(false);
  let newTitle = $state('');
  let splitting = $state(false);

  const items = $derived<MenuItem[]>([
    { label: t('dossier.rename'), icon: 'edit', run: () => { newTitle = dossier.title; renaming = true; } },
    { label: t('dossier.split'), icon: 'split', run: () => (splitting = true), disabled: !dossier.statements.length || busy },
    { label: dossier.archived ? t('dossier.unarchive') : t('dossier.archive'), icon: 'folder', run: async () => {
      const was = dossier.archived;
      if (await patch(dossier.id, { archived: !was })) toast('ok', was ? t('dossier.unarchived') : t('dossier.archived'), { action: { label: t('common.undo'), run: () => void patch(dossier.id, { archived: was }) } });
    } },
    { label: t('dossier.delete'), icon: 'trash', danger: true, disabled: busy, hint: busy ? t('dossier.busyHint') : '', run: () => void removeDossier(dossier.id) },
  ]);
</script>

<ExportMenu {dossier} />
<Menu label={t('dossier.more')} items={items} />

<Dialog bind:open={renaming} title={t('dossier.rename')}>
  <form id="rename-f" onsubmit={async (e) => { e.preventDefault(); if (newTitle.trim() && (await patch(dossier.id, { title: newTitle.trim() }))) renaming = false; }}>
    <div class="field"><label for="rn">{t('dossier.titleLabel')}</label><input id="rn" class="input" bind:value={newTitle} /></div>
  </form>
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (renaming = false)}>{t('common.cancel')}</button>
    <button class="btn primary" type="submit" form="rename-f">{t('common.save')}</button>
  {/snippet}
</Dialog>
<SplitDialog {dossier} bind:open={splitting} />
