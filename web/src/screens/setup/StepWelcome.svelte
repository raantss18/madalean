<script lang="ts">
  // Step 1: what the assistant will go through, this machine at a glance, the language.
  import { t, fmtBytes } from '../../lib/i18n/index.svelte';
  import type { SetupStatus } from '../../lib/setup/api';
  import Language from '../settings/Language.svelte';

  let { status }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  const hw = $derived(status?.detected?.hardware);
  const gpu = $derived(hw?.gpus?.[0]);
  const plan = ['tools', 'local', 'keys', 'hf', 'claude', 'modes', 'auto', 'pair'] as const;
</script>

<div class="stack">
  <section class="panel" aria-labelledby="w-plan">
    <h2 id="w-plan">{t('setup.welcome.plan')}</h2>
    <ol class="plan">
      {#each plan as s (s)}<li>{t(`setup.welcome.item.${s}`)}</li>{/each}
    </ol>
    <p class="small">{t('setup.welcome.noKeyNeeded')}</p>
  </section>

  {#if hw}
    <section class="panel" aria-labelledby="w-machine">
      <h2 id="w-machine">{t('setup.welcome.machine')}</h2>
      <ul class="facts small">
        {#if hw.ram_bytes}<li>{t('setup.welcome.ram', { n: fmtBytes(hw.ram_bytes) })}</li>{/if}
        <li>{gpu ? t('setup.welcome.gpu', { name: gpu.name, n: (gpu.vram_mib / 1024).toFixed(0) }) : t('setup.welcome.noGpu')}</li>
        {#if hw.disk?.free_bytes}<li>{t('setup.welcome.disk', { n: fmtBytes(hw.disk.free_bytes) })}</li>{/if}
      </ul>
    </section>
  {/if}

  <section class="panel" aria-labelledby="w-lang">
    <h2 id="w-lang">{t('setup.welcome.language')}</h2>
    <Language />
  </section>
</div>

<style>
  .plan { margin: 0 0 var(--s-2); padding-left: 1.4rem; display: grid; gap: 2px; }
  .facts { margin: 0; padding-left: 1.2rem; }
</style>
