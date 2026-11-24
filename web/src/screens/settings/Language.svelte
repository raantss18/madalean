<script lang="ts">
  import { t, i18n, LANGS, type Lang } from '../../lib/i18n/index.svelte';
  import { saveSettings } from './save';
  async function set(l: Lang) {
    const prev = i18n.lang;
    i18n.set(l);
    if (!(await saveSettings({ language: l }, true))) i18n.set(prev);
  }
</script>

<fieldset class="lang">
  <legend class="label">{t('language.label')}</legend>
  <div class="seg">
    {#each LANGS as [l, name] (l)}<label lang={l}><input type="radio" name="lang" value={l} checked={i18n.lang === l} onchange={() => set(l)} />{name}</label>{/each}
  </div>
</fieldset>
<p class="hint">{t('language.hint')}</p>
{#if i18n.lang === 'mg'}<p class="hint">{t('language.mgNote')}</p>{/if}

<style>.lang { border: 0; padding: 0; margin: 0 0 var(--s-3); }</style>
