<script lang="ts">
  // Step 2: the tools. What is installed and what is missing (components of the prefix, with « Installer » /
  // « Réparer » and live progress through POST /api/deps/{c}/install + `deps.progress`), which SageMath and which
  // LaTeX to use (the system's or Madalean's own copy, recommended choice with its reason, checked by the server),
  // and what only the user can install (bubblewrap: a package command, Madalean never uses sudo).
  import { onDestroy } from 'svelte';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { ApiError } from '../../lib/api/client';
  import { setupApi, type Component, type SetupStatus } from '../../lib/setup/api';
  import { recommendedSage, recommendedTex, type SageSource, type TexEngine } from '../../lib/setup/wizard';
  import { errorText } from '../../lib/ui/errors';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Icon from '../../components/Icon.svelte';

  let { status, reload }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();

  type Job = { phase: string; done?: number; total?: number; message?: string };
  let jobs = $state<Record<string, Job>>({});
  let reuseMsg = $state<{ field: string; level: 'ok' | 'error'; text: string } | null>(null);
  let checking = $state(false);
  const off = app.on('deps.progress', (ev) => {
    const e = ev as unknown as Job & { component: string };
    jobs = { ...jobs, [e.component]: { phase: e.phase, done: e.done, total: e.total, message: e.message } };
    if (e.phase === 'done' || e.phase === 'error') {
      toast(e.phase === 'done' ? 'ok' : 'error', t(e.phase === 'done' ? 'setup.tools.installed' : 'setup.tools.failed', { name: e.component }));
      void reload();
    }
  });
  onDestroy(off);
  // An install started earlier (or from another screen) is still followed.
  $effect(() => {
    setupApi.componentJobs().then((r) => {
      for (const [k, j] of Object.entries(r.jobs ?? {})) if (j.running) jobs = { ...jobs, [k]: { phase: j.phase ?? 'running', done: j.done, total: j.total, message: j.message } };
    }).catch(() => {});
  });

  const comps = $derived((status?.components ?? []).filter((c) => c.state !== 'dev'));
  const busy = (c: Component) => { const j = jobs[c.component]; return !!j && j.phase !== 'done' && j.phase !== 'error'; };
  function action(c: Component): string {
    if (c.state === 'missing') return t('setup.tools.install');
    if (c.state === 'outdated') return t('setup.tools.update');
    if (c.state === 'on_demand') return t('setup.tools.installNow');
    return '';
  }
  async function install(c: Component) {
    jobs = { ...jobs, [c.component]: { phase: 'queued' } };
    try { await setupApi.installComponent(c.component); }
    catch (e) {
      const { [c.component]: _drop, ...rest } = jobs;
      jobs = rest;
      toast('error', e instanceof ApiError && e.kind === 'busy' ? t('setup.tools.busy') : errorText(e));
    }
  }
  function pct(j: Job): number { return j.total ? Math.round(((j.done ?? 0) / j.total) * 100) : 0; }

  // ---- reuse of system SageMath / TeX Live
  const rec = $derived(Object.fromEntries((status?.recommended?.items ?? []).map((i) => [i.id, i])));
  const sageSys = $derived(status?.reuse.sage.system);
  const texSys = $derived(status?.reuse.tex.system);
  const sageRec = $derived(recommendedSage(sageSys, !!status?.detected?.madalean?.sage_own));
  const texRec = $derived(recommendedTex());
  async function setReuse(field: 'sage_source' | 'tex_engine', value: string) {
    reuseMsg = null;
    try {
      const r = await setupApi.reuse({ [field]: value });
      if (status) { status.prefs = r.prefs; status.reuse = r.reuse; }
      reuseMsg = { field, level: 'ok', text: t('setup.tools.saved') };
    } catch (e) {
      const why = e instanceof ApiError ? String(e.body['reason'] ?? '') : '';
      reuseMsg = { field, level: 'error', text: why ? tk(`setup.reuse.${why}`, errorText(e)) : errorText(e) };
      await reload();
    }
  }
  function usedText(used: string): string { return used ? tk(`setup.used.${used}`, used) : t('setup.used.none'); }
  async function recheck() { checking = true; await reload(true); checking = false; }
</script>

{#if !status}
  <p class="muted" aria-busy="true">{t('setup.loading')}</p>
{:else}
  <div class="stack">
    <section class="panel" aria-labelledby="t-comp">
      <div class="row"><h2 id="t-comp">{t('setup.tools.components')}</h2><span class="spacer"></span>
        <button class="btn small" onclick={recheck} disabled={checking}><Icon name="refresh" size={14} />{checking ? t('setup.tools.checking') : t('setup.tools.recheck')}</button></div>
      <p class="hint">{t('setup.tools.componentsHint')}</p>
      <ul class="comps">
        {#each comps as c (c.component)}
          {@const j = jobs[c.component]}
          <li>
            <Icon name={c.state === 'ok' ? 'check' : c.state === 'on_demand' ? 'clock' : 'warn'} size={16} />
            <span class="txt">
              <strong>{tk(`setup.comp.${c.component}`, c.title || c.component)}</strong>
              <span class="xs muted">{tk(`setup.state.${c.state}`, c.state)}{c.version ? ` · ${c.version}` : ''}</span>
              {#if j && busy(c)}
                <span class="meter" role="progressbar" aria-label={t('setup.tools.progress', { name: c.component })} aria-valuemin="0" aria-valuemax="100" aria-valuenow={pct(j)}><span style="width: {pct(j)}%"></span></span>
                <span class="xs" role="status">{tk(`setup.phase.${j.phase}`, j.phase)}{j.total ? ` · ${pct(j)} %` : ''}{j.message ? ` — ${j.message}` : ''}</span>
              {:else if j?.phase === 'error'}<span class="xs st error" role="status">{j.message || t('setup.tools.failed', { name: c.component })}</span>{/if}
            </span>
            {#if action(c)}<button class="btn small" class:primary={c.state === 'missing'} disabled={busy(c)} onclick={() => install(c)}>{busy(c) ? t('setup.tools.installing') : action(c)}<span class="sr-only">{' '}{tk(`setup.comp.${c.component}`, c.title || c.component)}</span></button>{/if}
          </li>
        {:else}<li class="muted small">{t('setup.tools.devCheckout')}</li>{/each}
      </ul>
    </section>

    <fieldset class="panel" aria-describedby="t-sage-why">
      <legend>{t('setup.sage.title')}</legend>
      <div class="choices">
      {#each ['auto', 'own', 'system'] as v (v)}
        {@const offOpt = v === 'system' && !sageSys?.compatible}
        <label class="choice" class:sel={status.prefs.sage_source === v} class:off={offOpt}>
          <input type="radio" name="sage" value={v} checked={status.prefs.sage_source === v} disabled={offOpt} onchange={() => setReuse('sage_source', v)} />
          <span><strong>{t(`setup.sage.${v as SageSource}`)}</strong>{#if v === sageRec}<span class="rec"><Icon name="check" size={12} />{t('setup.recommended')}</span>{/if}
            <span class="small muted">{t(`setup.sage.${v as SageSource}.desc`)}</span>
            {#if offOpt}<span class="xs muted">{sageSys?.found ? t('setup.sage.systemIncompatible', { v: sageSys?.version ?? '?' }) : t('setup.sage.systemAbsent')}</span>{/if}</span>
        </label>
      {/each}
      </div>
      <p class="why" id="t-sage-why">{rec['sage']?.why ?? t('setup.sage.whyDefault')} <span class="xs">{t('setup.nowUsed', { what: usedText(status.reuse.sage.used) })}</span></p>
      {#if reuseMsg?.field === 'sage_source'}<p class="small st {reuseMsg.level}" role="status">{reuseMsg.text}</p>{/if}
    </fieldset>

    <fieldset class="panel" aria-describedby="t-tex-why">
      <legend>{t('setup.tex.title')}</legend>
      <div class="choices">
      {#each ['auto', 'tectonic', 'system'] as v (v)}
        {@const offOpt = v === 'system' && !texSys?.found}
        <label class="choice" class:sel={status.prefs.tex_engine === v} class:off={offOpt}>
          <input type="radio" name="tex" value={v} checked={status.prefs.tex_engine === v} disabled={offOpt} onchange={() => setReuse('tex_engine', v)} />
          <span><strong>{t(`setup.tex.${v as TexEngine}`)}</strong>{#if v === texRec}<span class="rec"><Icon name="check" size={12} />{t('setup.recommended')}</span>{/if}
            <span class="small muted">{t(`setup.tex.${v as TexEngine}.desc`)}</span>
            {#if offOpt}<span class="xs muted">{t('setup.tex.systemAbsent')}</span>{/if}</span>
        </label>
      {/each}
      </div>
      <p class="why" id="t-tex-why">{rec['tex']?.why ?? t('setup.tex.whyDefault')} <span class="xs">{t('setup.nowUsed', { what: usedText(status.reuse.tex.used) })}</span></p>
      {#if reuseMsg?.field === 'tex_engine'}<p class="small st {reuseMsg.level}" role="status">{reuseMsg.text}</p>{/if}
    </fieldset>

    {#if status.recommended?.advice?.length}
      <section class="panel" aria-labelledby="t-adv">
        <h2 id="t-adv">{t('setup.tools.yourTurn')}</h2>
        <ul class="adv">
          {#each status.recommended.advice as a (a.id)}
            <li class="small">{a.text}{#if a.command} <code class="cmd" lang="en">{a.command}</code>
              <button class="btn small quiet" onclick={() => navigator.clipboard?.writeText(a.command).then(() => toast('ok', t('setup.copied')), () => {})}><Icon name="copy" size={14} />{t('setup.copy')}</button>{/if}</li>
          {/each}
        </ul>
      </section>
    {/if}
    <p class="xs muted">{t('setup.tools.later')}</p>
  </div>
{/if}

<style>
  .comps { list-style: none; margin: 0; padding: 0; }
  .comps li { display: flex; gap: var(--s-3); align-items: center; padding: var(--s-2) 0; border-bottom: 1px solid var(--line); }
  .comps li:last-child { border-bottom: 0; }
  .comps li > :global(.ico) { flex: none; color: var(--text-2); }
  .txt { flex: 1; display: grid; min-width: 0; overflow-wrap: anywhere; }
  .adv { margin: 0; padding-left: 1.2rem; display: grid; gap: var(--s-2); }
  h2 { font-size: var(--fs-lg); margin: 0; }
</style>
