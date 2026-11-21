<script lang="ts">
  import { app } from '../../lib/store/app.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { saveSettings } from './save';
  let text = $state(app.m.settings?.profile ?? '');
  let saved = $state(true);
</script>

<p class="lead">{t('profile.lead')}</p>
<div class="field">
  <label for="profile">{t('profile.label')}</label>
  <textarea id="profile" class="input" rows="8" bind:value={text} oninput={() => (saved = false)} placeholder={t('profile.placeholder')} aria-describedby="profile-h"></textarea>
  <p class="hint" id="profile-h">{t('profile.hint')}</p>
</div>
<div class="row">
  <button class="btn primary" disabled={saved} onclick={async () => { if (await saveSettings({ profile: text })) saved = true; }}>{t('common.save')}</button>
  {#if !saved}<span class="small muted">{t('profile.unsaved')}</span>{/if}
</div>

<style>.lead { color: var(--text-2); max-width: var(--measure); }</style>
