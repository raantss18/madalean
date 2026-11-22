<script lang="ts">
  // Home card (host only) while « Premiers pas » is not finished: « Reprendre » opens it where the user stopped;
  // « Ne plus afficher » hides the card (the assistant stays in the logo menu and in Réglages).
  import { app } from '../../lib/store/app.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { setup, saveWizard } from '../../lib/setup/state.svelte';
  import { showReminder, STEPS, indexOf, isStep } from '../../lib/setup/wizard';
  import Icon from '../../components/Icon.svelte';

  const shown = $derived(showReminder(app.m.local, setup.info));
  const at = $derived(setup.info && isStep(setup.info.step) ? setup.info.step : 'welcome');
</script>

{#if shown}
  <aside class="reminder" aria-labelledby="sr-h">
    <Icon name="sparkle" size={20} />
    <div class="txt">
      <p class="ttl" id="sr-h"><strong>{t('setup.reminder.title')}</strong></p>
      <p class="small">{at === 'welcome' ? t('setup.reminder.text') : t('setup.reminder.resume', { step: tk(`setup.step.${at}`, at), i: indexOf(at) + 1, n: STEPS.length })}</p>
    </div>
    <div class="row">
      <a class="btn primary small" href="/premiers-pas">{at === 'welcome' ? t('setup.reminder.start') : t('setup.reminder.continue')}</a>
      <button class="btn quiet small" onclick={() => saveWizard({ reminder: false })}>{t('setup.reminder.hide')}</button>
    </div>
  </aside>
{/if}

<style>
  .reminder { display: flex; gap: var(--s-3); align-items: center; flex-wrap: wrap; max-width: 960px; margin: 0 0 var(--s-4); padding: var(--s-3) var(--s-4); background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--laterite-mark); border-radius: var(--r-3); }
  .reminder > :global(.ico) { color: var(--laterite); flex: none; }
  .txt { flex: 1 1 16rem; min-width: 0; }
  p { margin: 2px 0 0; color: var(--text-2); }
  p.ttl { margin: 0; color: var(--text); }
  @media (pointer: coarse) { .row .btn { min-height: 44px; } }
</style>
