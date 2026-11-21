<script lang="ts">
  // Gentle first-run tour (Learn mode only, once per device): one idea per step, skippable at any time.
  import { t, type Key } from '../lib/i18n/index.svelte';
  import { onMount } from 'svelte';
  import { setTourDone } from '../lib/prefs.svelte';
  const steps: { title: Key; text: Key }[] = [
    { title: 'tour.1.title', text: 'tour.1.text' },
    { title: 'tour.2.title', text: 'tour.2.text' },
    { title: 'tour.3.title', text: 'tour.3.text' },
    { title: 'tour.4.title', text: 'tour.4.text' },
  ];
  let i = $state(0);
  const s = $derived(steps[i]!);
  // Phones: the page gets extra room at the bottom so nothing stays hidden behind the card.
  onMount(() => { document.documentElement.dataset['tour'] = '1'; return () => { delete document.documentElement.dataset['tour']; }; });
</script>

<section class="tour kb-hide" aria-labelledby="tour-h" aria-live="polite">
  <p class="step xs">{t('tour.step', { i: i + 1, n: steps.length })}</p>
  <h2 id="tour-h">{t(s.title)}</h2>
  <p>{t(s.text)}</p>
  <div class="row">
    <button class="btn quiet small" onclick={() => setTourDone(true)}>{t('tour.skip')}</button>
    <span class="spacer"></span>
    {#if i > 0}<button class="btn small" onclick={() => i--}>{t('common.back')}</button>{/if}
    {#if i < steps.length - 1}
      <button class="btn small primary" onclick={() => i++}>{t('common.next')}</button>
    {:else}
      <button class="btn small primary" onclick={() => setTourDone(true)}>{t('tour.done')}</button>
    {/if}
  </div>
</section>

<style>
  .tour { position: fixed; z-index: 800; right: var(--s-4); bottom: var(--s-4); width: min(380px, calc(100vw - 24px)); background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--laterite-mark); border-radius: var(--r-3); box-shadow: var(--shadow-2); padding: var(--s-4); }
  .tour h2 { font-size: var(--fs-md); }
  .tour p { font-size: var(--fs-sm); color: var(--text-2); }
  .step { margin: 0 0 4px; color: var(--text-3); font-weight: 600; }
  @media (max-width: 767px) { .tour { right: 12px; bottom: calc(var(--bottomnav-h) + 12px + env(safe-area-inset-bottom)); } }
</style>
