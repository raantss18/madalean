<script lang="ts">
  // Step 10: the final checklist (GET /api/setup next_steps, checked again now) and a summary of the choices.
  import { onMount } from 'svelte';
  import { app } from '../../lib/store/app.svelte';
  import { i18n, t, tk } from '../../lib/i18n/index.svelte';
  import { prefs } from '../../lib/prefs.svelte';
  import type { SetupStatus } from '../../lib/setup/api';
  import { checklist, checklistSummary } from '../../lib/setup/wizard';
  import Icon from '../../components/Icon.svelte';

  let { status, reload }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  onMount(() => { void reload(); });               // what changed in the previous steps
  const rows = $derived(status ? checklist(status.next_steps, i18n.lang === 'en' ? 'en' : 'fr') : []);
  const sum = $derived(checklistSummary(rows));
  const s = $derived(app.m.settings);
  const present = $derived((status?.models.files ?? []).filter((f) => f.present).length);
</script>

{#if status}
  <div class="stack">
    <section class="panel" aria-labelledby="d-list">
      <h2 id="d-list">{t('setup.done.checklist')}</h2>
      <p class="small" role="status">{sum.essentialLeft ? t('setup.done.left', { n: sum.essentialLeft }) : t('setup.done.allGood')}</p>
      <ul class="check">
        {#each rows as r (r.id)}
          <li class:ok={r.done}>
            <Icon name={r.done ? 'check' : r.optional ? 'info' : 'warn'} size={16} label={r.done ? t('setup.done.ok') : t('setup.done.todo')} />
            <span class="txt">{r.title}{#if r.optional}{' '}<span class="xs muted">({t('common.optional')})</span>{/if}</span>
            <a class="xs" href="/aide/{r.help}">{t('help.short')}<span class="sr-only"> : {r.title}</span></a>
          </li>
        {/each}
      </ul>
    </section>

    {#if s}
      <section class="panel" aria-labelledby="d-sum">
        <h2 id="d-sum">{t('setup.done.summary')}</h2>
        <dl class="sum small">
          <dt>{t('settings.mode')}</dt><dd>{tk(`mode.${s.mode}`, s.mode)}</dd>
          <dt>{t('setup.done.ui')}</dt><dd>{t(prefs.mode === 'learn' ? 'mode.learn' : 'mode.research')}</dd>
          <dt>{t('setup.done.keys')}</dt><dd>{status.keys.length ? status.keys.join(', ') : t('setup.done.noKeys')}</dd>
          <dt>{t('setup.done.local')}</dt><dd>{present ? t('setup.done.localN', { n: present }) : t('setup.done.noLocal')}</dd>
          <dt>{t('setup.sage.title')}</dt><dd>{t(`setup.sage.${status.prefs.sage_source as 'auto' | 'own' | 'system'}`)}</dd>
          <dt>{t('setup.tex.title')}</dt><dd>{t(`setup.tex.${status.prefs.tex_engine as 'auto' | 'tectonic' | 'system'}`)}</dd>
          <dt>{t('setup.done.devices')}</dt><dd>{status.devices}</dd>
        </dl>
        <p class="hint">{t('setup.done.changeLater')}</p>
      </section>
    {/if}
  </div>
{:else}
  <p class="muted" aria-busy="true">{t('setup.loading')}</p>
{/if}

<style>
  .check { list-style: none; margin: 0; padding: 0; }
  .check li { display: flex; gap: var(--s-2); align-items: center; padding: 6px 0; border-bottom: 1px solid var(--line); }
  .check li:last-child { border-bottom: 0; }
  .check li > :global(.ico) { flex: none; color: var(--running); }
  .check li.ok > :global(.ico) { color: var(--proved); }
  .txt { flex: 1; min-width: 0; }
  .sum { display: grid; grid-template-columns: max-content 1fr; gap: 4px var(--s-3); margin: 0 0 var(--s-2); }
  .sum dt { color: var(--text-2); font-weight: 600; }
  .sum dd { margin: 0; overflow-wrap: anywhere; }
  @media (max-width: 479px) { .sum { grid-template-columns: minmax(0, 1fr); } .sum dd { margin-bottom: 6px; } }
</style>
