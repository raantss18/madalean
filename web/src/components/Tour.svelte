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
  // From 1024 px the card floats in a corner: the page gets extra room at the bottom so it can scroll clear of it.
  // Below, the card is part of the page, above the statement (S-AA: it used to cover the field and its buttons).
  onMount(() => { document.documentElement.dataset['tour'] = '1'; return () => { delete document.documentElement.dataset['tour']; }; });
</script>

<section class="tour" aria-labelledby="tour-h" aria-live="polite">
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
  .tour { margin: 0 0 var(--s-4); background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--laterite-mark); border-radius: var(--r-3); box-shadow: var(--shadow-1); padding: var(--s-3) var(--s-4); max-width: 46rem; }
  .tour h2 { font-size: var(--fs-md); margin: 0 0 4px; }
  .tour p { font-size: var(--fs-sm); color: var(--text-2); margin: 0 0 var(--s-2); }
  .step { margin: 0 0 4px; color: var(--text-3); font-weight: 600; }
  @media (min-width: 1024px) {
    .tour { position: fixed; z-index: 800; right: var(--s-4); bottom: var(--s-4); width: min(380px, calc(100vw - 24px)); margin: 0; box-shadow: var(--shadow-2); padding: var(--s-4); }
    .tour p { margin: revert; }
    :global(html[data-tour]) :global(main) { padding-bottom: 280px; }
    /* On-screen keyboard (touch tablets): no floating card over the text being typed. */
    :global(html[data-kb='open']) .tour { display: none; }
  }
</style>
