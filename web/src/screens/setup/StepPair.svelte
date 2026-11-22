<script lang="ts">
  // Step 9 (optional): link a phone, a tablet or another computer — Réglages › Appareils itself (code + QR code,
  // POST /api/pairing/start), so there is one pairing flow.
  import { t } from '../../lib/i18n/index.svelte';
  import type { SetupStatus } from '../../lib/setup/api';
  import Devices from '../settings/Devices.svelte';

  let _p: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
</script>

<div class="stack">
  <ol class="how small">
    <li>{t('setup.pair.how1')}</li>
    <li>{t('setup.pair.how2')}</li>
    <li>{t('setup.pair.how3')}</li>
  </ol>
  <Devices />
  <p class="xs muted">{t('setup.optional')}</p>
</div>

<style>
  .how { margin: 0; padding-left: 1.4rem; display: grid; gap: 4px; }
</style>
