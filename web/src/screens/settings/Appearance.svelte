<script lang="ts">
  import { t } from '../../lib/i18n/index.svelte';
  import { prefs, setTheme, setMode, setTextSize, setTourDone } from '../../lib/prefs.svelte';
  import { navigate } from '../../lib/router.svelte';
</script>

<p class="hint">{t('appearance.perDevice')}</p>
<fieldset class="f">
  <legend class="label">{t('appearance.theme')}</legend>
  <div class="seg">
    {#each [['system', 'appearance.system'], ['light', 'appearance.light'], ['dark', 'appearance.dark']] as [v, k]}
      <label><input type="radio" name="theme" value={v} checked={prefs.theme === v} onchange={() => setTheme(v as 'system')} />{t(k as 'appearance.system')}</label>
    {/each}
  </div>
</fieldset>
<fieldset class="f">
  <legend class="label">{t('mode.label')}</legend>
  <div class="seg">
    <label><input type="radio" name="uim" checked={prefs.mode === 'learn'} onchange={() => setMode('learn')} />{t('mode.learn')}</label>
    <label><input type="radio" name="uim" checked={prefs.mode === 'research'} onchange={() => setMode('research')} />{t('mode.research')}</label>
  </div>
  <p class="hint">{prefs.mode === 'learn' ? t('mode.learnHint') : t('mode.researchHint')}</p>
</fieldset>
<fieldset class="f">
  <legend class="label">{t('appearance.textSize')}</legend>
  <div class="seg">
    {#each [100, 112, 125] as v}<label><input type="radio" name="ts" checked={prefs.textSize === v} onchange={() => setTextSize(v)} />{v} %</label>{/each}
  </div>
</fieldset>
<button class="btn" onclick={() => { setTourDone(false); setMode('learn'); navigate('/'); }}>{t('appearance.replayTour')}</button>

<style>.f { border: 0; padding: 0; margin: 0 0 var(--s-4); }</style>
