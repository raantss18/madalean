<script lang="ts">
  import ActivityPanel from '../components/ActivityPanel.svelte';
  import { t } from '../lib/i18n/index.svelte';
  let { params: _p }: { params: Record<string, string> } = $props();
</script>

<h1 class="sr-only">{t('activity.title')}</h1>
<div style="max-width: 760px"><ActivityPanel /></div>
