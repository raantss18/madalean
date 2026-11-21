<script lang="ts">
  import type { Dossier } from '../../lib/api/types';
  import { downloadExport, type ExportFormat } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import Menu, { type MenuItem } from '../../components/Menu.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';

  let { dossier }: { dossier: Dossier } = $props();
  async function exp(f: ExportFormat) {
    try {
      const r = await downloadExport(dossier.id, f);
      if (r.fallback === 'html') toast('warn', t('export.htmlFallback'), { timeout: 12000 });
      else if (f === 'pdf') toast('info', t('export.building'));
    } catch (e) { toast('error', errorText(e)); }
  }
  const items = $derived<MenuItem[]>([
    { label: t('export.pdf'), icon: 'file', run: () => void exp('pdf'), hint: dossier.status === 'proved' ? '' : t('export.notProved') },
    { label: t('export.tex'), icon: 'file', run: () => void exp('tex') },
    { label: t('export.lean'), icon: 'file', run: () => void exp('lean') },
    { label: t('export.md'), icon: 'file', run: () => void exp('md') },
    { label: t('export.zip'), icon: 'download', run: () => void exp('zip') },
  ]);
</script>

<Menu label={t('export.title')} icon="download" text={t('export.short')} items={items} />
