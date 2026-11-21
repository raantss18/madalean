<script lang="ts">
  // « Qui reçoit quoi » (ARCHITECTURE §14): permanently shows where the current work goes — this machine or an
  // online provider — and which model. Click → details and a link to the models settings.
  import { app } from '../lib/store/app.svelte';
  import { t, tk } from '../lib/i18n/index.svelte';
  import { jobModel, modelLabel, providerName, roleOfStage } from '../lib/status';
  import Icon from './Icon.svelte';

  let open = $state(false);
  let btn: HTMLButtonElement | undefined = $state();
  const mode = $derived(app.m.settings?.mode ?? 'auto');

  interface Flow { job: string; title: string; stage: string; model: string; provider: string; local: boolean }
  const flows = $derived.by<Flow[]>(() => app.activeJobs.filter((j) => j.state === 'running').map((j) => {
    const key = app.liveModel[j.id] || jobModel(j) || predicted(roleOfStage(j.stage));
    const ml = modelLabel(key);
    return { job: j.id, title: app.m.dossiers[j.dossier_id]?.title ?? '', stage: j.stage, model: ml.name, provider: ml.provider, local: ml.local || key === '' };
  }));
  function predicted(role: string): string {
    if (!role) return '';
    const r = app.m.models?.roles?.[role];
    return r?.preferred || r?.candidates?.[0]?.key || '';
  }
  const anyOnline = $derived(flows.some((f) => !f.local));
  const summary = $derived(
    flows.length === 0
      ? tk(`privacy.idle.${mode}`, mode)
      : flows.length === 1
        ? (flows[0]!.local ? t('privacy.oneLocal', { model: flows[0]!.model || t('privacy.localModel') }) : t('privacy.oneOnline', { model: flows[0]!.model, provider: providerName(flows[0]!.provider) }))
        : t('privacy.many', { n: flows.length }),
  );
  function onKey(e: KeyboardEvent) { if (e.key === 'Escape' && open) { open = false; btn?.focus(); } }
</script>

<svelte:window onkeydown={onKey} />
<div class="privacy">
  <button bind:this={btn} class="pill" class:idle={flows.length === 0} class:online={anyOnline || (flows.length === 0 && mode !== 'local')} class:local={!anyOnline && (flows.length > 0 || mode === 'local')}
    aria-expanded={open} aria-controls="privacy-pop" onclick={() => (open = !open)}>
    <Icon name={anyOnline || (flows.length === 0 && mode !== 'local') ? 'cloud' : 'cpu'} size={16} />
    <span class="txt">{summary}</span>
  </button>
  {#if open}
    <div id="privacy-pop" class="pop" role="region" aria-label={t('privacy.title')}>
      <h2>{t('privacy.title')}</h2>
      <p class="small">{tk(`privacy.mode.${mode}`, mode)}</p>
      {#if flows.length}
        <ul>
          {#each flows as f (f.job)}
            <li>
              <span class="chip {f.local ? 'local' : 'online'}">{f.local ? t('privacy.here') : providerName(f.provider)}</span>
              <span class="small"><strong>{f.title}</strong> — {tk(`stage.${f.stage}`, f.stage)}{#if f.model} · {f.model}{/if}</span>
              <span class="xs muted">{f.local ? t('privacy.sentNothing') : tk(`privacy.sent.${f.stage}`, t('privacy.sent.default'))}</span>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="small muted">{t('privacy.nothingRunning')}</p>
      {/if}
      <a class="btn small" href="/reglages/modeles" onclick={() => (open = false)}>{t('privacy.change')}</a>
    </div>
  {/if}
</div>

<style>
  .privacy { position: relative; }
  .pill { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; max-width: 280px; padding: 0 12px; border-radius: 999px; border: 1px solid var(--line-strong); background: var(--surface); color: var(--text-2); font: 600 var(--fs-xs) / 1.2 var(--font-ui); cursor: pointer; }
  @media (pointer: coarse) { .pill { min-height: 44px; } }
  .pill.online { background: var(--online-soft); color: var(--online); border-color: color-mix(in srgb, var(--online) 45%, transparent); }
  .pill.local { background: var(--local-soft); color: var(--local); border-color: color-mix(in srgb, var(--local) 45%, transparent); }
  .txt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pop { position: absolute; right: 0; top: calc(100% + 8px); z-index: 600; width: min(380px, calc(100vw - 24px)); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); box-shadow: var(--shadow-2); padding: var(--s-4); }
  .pop h2 { font-size: var(--fs-md); }
  ul { list-style: none; padding: 0; margin: 0 0 var(--s-3); display: grid; gap: var(--s-2); }
  li { display: grid; gap: 2px; justify-items: start; }
  @media (max-width: 767px) { .privacy { min-width: 0; flex: 0 1 auto; } .pill { max-width: 34vw; padding: 0 8px; } .pill.idle .txt { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); } .pill.idle { width: 44px; justify-content: center; } .pop { position: fixed; left: 12px; right: 12px; top: calc(var(--topbar-h) + 4px); width: auto; } }
</style>
