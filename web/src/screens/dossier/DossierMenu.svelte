<script lang="ts">
  // « Exporter » and « ⋯ » of a dossier. Renaming is done on the title itself (S-AK: autosaved, no dialog).
  import type { Dossier } from '../../lib/api/types';
  import { t } from '../../lib/i18n/index.svelte';
  import Menu, { type MenuItem } from '../../components/Menu.svelte';
  import ExportMenu from './ExportMenu.svelte';
  import SplitDialog from './SplitDialog.svelte';
  import { patch, removeDossier } from './actions';
  import { toast } from '../../lib/ui/toasts.svelte';

  let { dossier, busy }: { dossier: Dossier; busy: boolean } = $props();
  let splitting = $state(false);

  const items = $derived<MenuItem[]>([
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
<SplitDialog {dossier} bind:open={splitting} />
