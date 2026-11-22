<script lang="ts">
  // Step 7: where the models work (setting `mode`: local | auto | online, recommended for this machine) and the
  // way of working on this device (Apprendre / Recherche, a per-device preference).
  import { app } from '../../lib/store/app.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { prefs, setMode, type UiMode } from '../../lib/prefs.svelte';
  import type { SetupStatus } from '../../lib/setup/api';
  import { saveSettings } from '../settings/save';
  import Icon from '../../components/Icon.svelte';

  let { status }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  const s = $derived(app.m.settings);
  const rec = $derived(status?.recommended?.items.find((i) => i.id === 'mode'));
</script>

{#if s}
  <div class="stack">
    <fieldset class="panel" aria-describedby="m-why">
      <legend>{t('settings.mode')}</legend>
      <div class="choices">
        {#each ['local', 'auto', 'online'] as v (v)}
          <label class="choice" class:sel={s.mode === v}>
            <input type="radio" name="wiz-mode" value={v} checked={s.mode === v} onchange={() => saveSettings({ mode: v }, true)} />
            <span><strong>{tk(`mode.${v}`, v)}</strong>{#if v === rec?.recommended}<span class="rec"><Icon name="check" size={12} />{t('setup.recommended')}</span>{/if}
              <span class="small muted">{tk(`mode.${v}.desc`, '')}</span></span>
          </label>
        {/each}
      </div>
      <p class="why" id="m-why">{rec?.why ?? t('setup.modes.whyDefault')}</p>
    </fieldset>

    <fieldset class="panel" aria-describedby="m-ui">
      <legend>{t('setup.modes.ui')}</legend>
      <div class="choices">
        {#each [['learn', 'graduate'], ['research', 'microscope']] as [v, icon] (v)}
          <label class="choice" class:sel={prefs.mode === v}>
            <input type="radio" name="wiz-ui" value={v} checked={prefs.mode === v} onchange={() => setMode(v as UiMode)} />
            <span><strong><Icon name={icon!} size={16} /> {t(v === 'learn' ? 'mode.learn' : 'mode.research')}</strong>
              <span class="small muted">{t(v === 'learn' ? 'setup.modes.learn' : 'setup.modes.research')}</span></span>
          </label>
        {/each}
      </div>
      <p class="hint" id="m-ui">{t('setup.modes.uiHint')}</p>
    </fieldset>
    <p class="small"><a href="/reglages/profil">{t('setup.modes.profile')}</a></p>
  </div>
{/if}
