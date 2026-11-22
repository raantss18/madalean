<script lang="ts">
  // The profile text given to the models. Saved automatically like every other setting (S-AK: no « Enregistrer »).
  import { onDestroy } from 'svelte';
  import { app } from '../../lib/store/app.svelte';
  import { api } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import { Autosave } from '../../lib/ui/autosave.svelte';
  import SaveState from '../../components/SaveState.svelte';
  let text = $state(app.m.settings?.profile ?? '');
  const saver = new Autosave(async () => {
    const r = await api.patchSettings({ profile: text });
    app.m.settings = r.settings;
  });
  onDestroy(() => saver.destroy());
</script>

<p class="lead">{t('profile.lead')}</p>
<div class="field">
  <label for="profile">{t('profile.label')}</label>
  <textarea id="profile" class="input" rows="8" bind:value={text} oninput={() => saver.touch()} onblur={() => saver.flush()} placeholder={t('profile.placeholder')} aria-describedby="profile-h"></textarea>
  <p class="hint" id="profile-h">{t('profile.hint')} <SaveState state={saver} /></p>
</div>

<style>.lead { color: var(--text-2); max-width: var(--measure); }</style>
