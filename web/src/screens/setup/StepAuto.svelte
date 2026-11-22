<script lang="ts">
  // Step 8: what Madalean does by itself and what waits for the user — real settings only (madalean/config.py),
  // saved as they change. The host-only ones (experiments_auto, updates_auto) are changed here because the
  // assistant only runs on the host.
  import { app } from '../../lib/store/app.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import type { SetupStatus } from '../../lib/setup/api';
  import { saveSettings } from '../settings/save';

  let _p: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  const s = $derived(app.m.settings);
  type K = 'experiments_auto' | 'pause_after_translation' | 'parallel_stages' | 'lean_warm' | 'conductor' | 'check_updates' | 'updates_auto';
  const GROUPS: { title: 'setup.auto.code' | 'setup.auto.proof' | 'setup.auto.updates'; keys: K[] }[] = [
    { title: 'setup.auto.code', keys: ['experiments_auto'] },
    { title: 'setup.auto.proof', keys: ['conductor', 'parallel_stages', 'lean_warm', 'pause_after_translation'] },
    { title: 'setup.auto.updates', keys: ['check_updates', 'updates_auto'] },
  ];
  const DEFAULTS: Record<K, boolean> = { experiments_auto: false, pause_after_translation: false, parallel_stages: true,
    lean_warm: true, conductor: true, check_updates: true, updates_auto: true };
</script>

{#if s}
  <div class="stack">
    {#each GROUPS as g, gi (g.title)}
      <section class="panel" aria-labelledby="a-g{gi}">
        <h2 id="a-g{gi}">{t(g.title)}</h2>
        {#each g.keys as k (k)}
          <div class="opt">
            <label class="switch"><input type="checkbox" checked={Boolean(s[k] ?? DEFAULTS[k])} aria-describedby="a-h-{k}"
              onchange={(e) => saveSettings({ [k]: (e.currentTarget as HTMLInputElement).checked }, true)} />{t(`setup.auto.${k}`)}</label>
            <p class="hint" id="a-h-{k}">{t(`setup.auto.${k}.hint`)} <span class="xs">{t(DEFAULTS[k] ? 'setup.auto.defaultOn' : 'setup.auto.defaultOff')}</span></p>
          </div>
        {/each}
      </section>
    {/each}
  </div>
{/if}
