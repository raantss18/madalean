<script lang="ts">
  import { t, i18n } from '../../lib/i18n/index.svelte';
  import { saveSettings } from './save';
  async function set(l: 'fr' | 'en') {
    const prev = i18n.lang;
    i18n.set(l);
    if (!(await saveSettings({ language: l }, true))) i18n.set(prev);
  }
</script>

<fieldset class="lang">
  <legend class="label">{t('language.label')}</legend>
  <div class="seg">
    <label lang="fr"><input type="radio" name="lang" value="fr" checked={i18n.lang === 'fr'} onchange={() => set('fr')} />Français</label>
    <label lang="en"><input type="radio" name="lang" value="en" checked={i18n.lang === 'en'} onchange={() => set('en')} />English</label>
  </div>
</fieldset>
<p class="hint">{t('language.hint')}</p>

<style>.lang { border: 0; padding: 0; margin: 0 0 var(--s-3); }</style>
