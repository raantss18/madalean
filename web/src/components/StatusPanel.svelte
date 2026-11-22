<script lang="ts">
  // The model status button of the top bar (session S-AK, docs/UI.md §14.2; it replaced the « Qui reçoit quoi » pill
  // and the activity drawer). Button: online / local icon, the mode in a word, the number of running jobs. Panel:
  // where the work goes and on which model, the host's resources, tokens and cost, running jobs. GET /api/usage is
  // polled every 3 s only while the panel is open; nothing is polled when it is closed.
  import { app } from '../lib/store/app.svelte';
  import { api } from '../lib/api/client';
  import type { UsageStatus, UsageTotals } from '../lib/api/types';
  import { route } from '../lib/router.svelte';
  import { t, tk, i18n } from '../lib/i18n/index.svelte';
  import { jobModel, modelLabel, providerName, roleOfStage } from '../lib/status';
  import { dismiss } from '../lib/ui/dismiss';
  import Icon from './Icon.svelte';
  import JobRow from './JobRow.svelte';

  let open = $state(false);
  let btn: HTMLButtonElement | undefined = $state();
  let usage = $state<UsageStatus | null>(null);
  let failed = $state(false);
  const mode = $derived(app.m.settings?.mode ?? 'auto');
  const slots = $derived(app.m.system?.slots);

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
  const active = $derived(app.activeJobs);
  const online = $derived(flows.length ? flows.some((f) => !f.local) : mode !== 'local');
  const short = $derived(flows.length === 1 ? flows[0]!.model || tk(`status.mode.${mode}`, mode) : tk(`status.mode.${mode}`, mode));
  const summary = $derived(flows.length === 0 ? tk(`privacy.idle.${mode}`, mode)
    : flows.length === 1 ? (flows[0]!.local ? t('privacy.oneLocal', { model: flows[0]!.model || t('privacy.localModel') }) : t('privacy.oneOnline', { model: flows[0]!.model, provider: providerName(flows[0]!.provider) }))
      : t('privacy.many', { n: flows.length }));

  // the requests whose tokens are shown: running jobs, else the current dossier's latest job
  const requestIds = $derived.by<{ id: string; title: string }[]>(() => {
    if (active.length) return active.slice(0, 5).map((j) => ({ id: j.id, title: app.m.dossiers[j.dossier_id]?.title ?? '' }));
    const did = route.name === 'dossier' ? route.params['id'] ?? '' : '';
    if (!did) return [];
    const last = Object.values(app.m.jobs).filter((j) => j.dossier_id === did).sort((a, b) => b.created - a.created)[0];
    return last ? [{ id: last.id, title: app.m.dossiers[did]?.title ?? '' }] : [];
  });

  $effect(() => {
    if (!open) return;
    const ids = requestIds.map((r) => r.id);
    let stop = false;
    const tick = async () => {
      try { const u = await api.usage(ids); if (!stop) { usage = u; failed = false; } } catch { if (!stop) failed = true; }
    };
    void tick();
    const h = setInterval(() => { if (document.visibilityState === 'visible') void tick(); }, 3000);
    return () => { stop = true; clearInterval(h); };
  });

  const nf = $derived(new Intl.NumberFormat(i18n.lang, { notation: 'compact', maximumFractionDigits: 1 }));
  const usd = $derived(new Intl.NumberFormat(i18n.lang, { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  const pct = (n: number | null | undefined) => (n == null ? '—' : `${Math.round(n)} %`);
  const gb = (mb: number) => (mb / 1024).toLocaleString(i18n.lang, { maximumFractionDigits: 1 });
  const tok = (x: UsageTotals | undefined) => (x ? nf.format(x.tokens_in + x.tokens_out) : '—');
  function close(refocus = false) { open = false; if (refocus) btn?.focus(); }
</script>

<div class="status">
  <button bind:this={btn} id="status-btn" class="sbtn" class:online class:local={!online} class:busy={active.length > 0}
    aria-expanded={open} aria-controls="status-panel" title={summary} onclick={() => (open = !open)}>
    <Icon name={online ? 'cloud' : 'cpu'} size={16} />
    <span class="txt">{short}</span>
    {#if active.length}<span class="count" aria-hidden="true">{active.length}</span>{/if}
    <span class="sr-only">— {summary}{active.length ? ` — ${t('activity.runningN', { n: active.length })}` : ''}</span>
  </button>
  {#if open}
    <div id="status-panel" class="panel" role="dialog" aria-modal="false" aria-labelledby="st-h" use:dismiss={{ onclose: () => close(), trigger: btn }}>
      <h2 id="st-h" class="sr-only">{t('status.title')}</h2>

      <section aria-labelledby="st-where">
        <h3 id="st-where">{t('privacy.title')}</h3>
        <p class="small">{tk(`privacy.mode.${mode}`, mode)}</p>
        {#if flows.length}
          <ul class="flows">
            {#each flows as f (f.job)}
              <li>
                <span class="chip {f.local ? 'local' : 'online'}">{f.local ? t('privacy.here') : providerName(f.provider)}</span>
                <span class="small"><strong>{f.title}</strong> — {`${tk(`stage.${f.stage}`, f.stage)}${f.model ? ` · ${f.model}` : ''}`}</span>
                <span class="xs muted">{f.local ? t('privacy.sentNothing') : tk(`privacy.sent.${f.stage}`, t('privacy.sent.default'))}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </section>

      <section aria-labelledby="st-res">
        <h3 id="st-res">{t('status.resources')}</h3>
        {#if !usage}
          <p class="xs muted" role="status">{failed ? t('status.unavailable') : t('common.loading')}</p>
        {:else}
          {@const r = usage.resources}
          <dl class="meters">
            <div><dt>{t('status.cpu')}</dt><dd><meter min="0" max="100" value={r.cpu_percent ?? 0} aria-hidden="true"></meter><span>{pct(r.cpu_percent)}{r.cpus ? ` · ${t('status.cores', { n: r.cpus })}` : ''}</span></dd></div>
            {#if r.memory}<div><dt>{t('status.ram')}</dt><dd><meter min="0" max={r.memory.total_mb} value={r.memory.used_mb} aria-hidden="true"></meter><span>{t('status.ofGb', { used: gb(r.memory.used_mb), total: gb(r.memory.total_mb) })}</span></dd></div>{/if}
            {#if r.gpu}
              <div><dt>{t('status.gpu')}</dt><dd><meter min="0" max="100" value={r.gpu.util} aria-hidden="true"></meter><span>{`${pct(r.gpu.util)} · ${r.gpu.temp} °C`}</span></dd></div>
              <div><dt>{t('status.vram')}</dt><dd><meter min="0" max={r.gpu.total} value={r.gpu.used} aria-hidden="true"></meter><span>{t('status.ofGb', { used: gb(r.gpu.used), total: gb(r.gpu.total) })}</span></dd></div>
            {/if}
          </dl>
          <p class="xs muted gpu-name">{r.gpu ? r.gpu.name : t('status.noGpu')}</p>
          {#if r.gpu_share}
            {@const g = r.gpu_share}
            <!-- S-AS (D51): « Partage de la carte graphique avec Ollama », in plain words -->
            <div class="share" aria-labelledby="st-share">
              <p class="xs"><strong id="st-share">{t('share.title')}</strong> — {#if !g.enabled}{t('share.off')}{:else if !g.ollama?.reachable}{t('share.noOllama')}{:else if g.ollama.busy}<span class="busy-txt">{t('share.busy')}</span>{:else if g.ollama.models.some((x) => x.vram_mib > 0)}{t('share.holds', { models: g.ollama.models.filter((x) => x.vram_mib > 0).map((x) => x.name).join(', '), gb: gb(g.ollama.models.reduce((a, x) => a + x.vram_mib, 0)) })}{:else}{t('share.idle')}{/if}</p>
              {#if g.enabled && g.ollama?.reachable}
                <p class="xs muted">{t('share.rule', { min: g.idle_unload_minutes })}</p>
                {#if g.last_lend?.unloaded?.length}<p class="xs muted">{t('share.lent', { models: g.last_lend.unloaded.join(', ') })}</p>
                {:else if g.last_lend?.reason === 'ollama_busy'}<p class="xs muted">{t('share.waited')}</p>{/if}
              {/if}
            </div>
          {/if}
        {/if}
        {#if slots}
          <p class="xs slots"><span class="muted">{t('status.slots')}</span>
            {#each (['gpu', 'online', 'lean'] as const) as k, i}{i ? ' · ' : ' '}<span class="slot">{tk(`slot.${k}`, k)} {slots[k].used}/{slots[k].capacity}</span>{#if slots[k].waiting}<span class="wait"> (+{slots[k].waiting})</span>{/if}{/each}</p>
        {/if}
      </section>

      <section aria-labelledby="st-tok">
        <h3 id="st-tok">{t('status.tokens')}</h3>
        {#if usage}
          <table class="tok">
            <thead><tr><th scope="col"><span class="sr-only">{t('status.period')}</span></th><th scope="col">{t('status.tokensCol')}</th><th scope="col">{t('status.calls')}</th><th scope="col">{t('status.cost')}</th></tr></thead>
            <tbody>
              {#each requestIds as rq (rq.id)}
                {@const u = usage.requests[rq.id]}
                <tr><th scope="row" title={rq.title}>{requestIds.length > 1 ? rq.title : t('status.request')}</th><td>{tok(u)}</td><td>{u?.calls ?? 0}</td><td>{usd.format(u?.usd ?? 0)}</td></tr>
              {/each}
              <tr><th scope="row">{t('status.today')}</th><td>{tok(usage.tokens.today)}</td><td>{usage.tokens.today.calls}</td><td>{usd.format(Math.max(usage.spend.today_usd, usage.tokens.today.usd))}</td></tr>
              <tr><th scope="row">{t('status.month')}</th><td>{tok(usage.tokens.month)}</td><td>{usage.tokens.month.calls}</td><td>{usd.format(Math.max(usage.spend.month_usd, usage.tokens.month.usd))}</td></tr>
            </tbody>
          </table>
          <p class="xs muted">{t('status.capNote', { month: usd.format(usage.spend.cap_month_usd), request: usd.format(usage.spend.cap_request_usd) })}</p>
        {/if}
      </section>

      <section aria-labelledby="st-act">
        <h3 id="st-act">{t('status.running')}</h3>
        {#if active.length}
          <ul class="jobs">{#each active as job (job.id)}<JobRow {job} compact />{/each}</ul>
        {:else}<p class="small muted">{t('privacy.nothingRunning')}</p>{/if}
      </section>

      <div class="foot">
        <a class="btn small" href="/activite" onclick={() => close()}><Icon name="activity" size={14} />{t('status.allActivity')}</a>
        <a class="btn small" href="/reglages/modeles" onclick={() => close()}><Icon name="settings" size={14} />{t('privacy.change')}</a>
      </div>
    </div>
  {/if}
</div>

<style>
  .status { position: relative; flex: 0 1 auto; min-width: 0; }
  .sbtn { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; max-width: 220px; padding: 0 12px; border-radius: 999px; border: 1px solid var(--line-strong); background: var(--surface); color: var(--text-2); font: 600 var(--fs-xs) / 1.2 var(--font-ui); cursor: pointer; }
  @media (pointer: coarse) { .sbtn { min-height: 44px; } }
  .sbtn.online { background: var(--online-soft); color: var(--online); border-color: color-mix(in srgb, var(--online) 45%, transparent); }
  .sbtn.local { background: var(--local-soft); color: var(--local); border-color: color-mix(in srgb, var(--local) 45%, transparent); }
  .txt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .count { min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: var(--running-fill); color: #1a1200; font-size: 12px; font-weight: 700; display: inline-grid; place-items: center; }
  .panel { position: absolute; right: 0; top: calc(100% + 8px); z-index: 800; width: min(420px, calc(100vw - 24px)); max-height: calc(100dvh - var(--topbar-h) - 16px); overflow: auto; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); box-shadow: var(--shadow-2); padding: var(--s-3) var(--s-4) var(--s-4); }
  section + section { border-top: 1px solid var(--line); margin-top: var(--s-3); padding-top: var(--s-3); }
  h3 { margin: 0 0 6px; font-size: var(--fs-sm); color: var(--text-2); }
  .flows, .jobs { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: var(--s-2); }
  .flows li { display: grid; gap: 2px; justify-items: start; }
  .meters { margin: 0; display: grid; gap: 6px; }
  .meters div { display: grid; grid-template-columns: 7rem minmax(0, 1fr); align-items: center; gap: var(--s-2); font-size: var(--fs-sm); }
  dt { font-weight: 600; }
  dd { margin: 0; display: grid; grid-template-columns: minmax(60px, 1fr) auto; align-items: center; gap: var(--s-2); color: var(--text-2); font-variant-numeric: tabular-nums; }
  meter { width: 100%; height: 8px; }
  .gpu-name { margin: 0; }
  .share { margin-top: var(--s-2); display: grid; gap: 2px; }
  .share p { margin: 0; }
  .busy-txt { color: var(--running); font-weight: 600; }
  .slots { margin: var(--s-2) 0 0; }
  .slots .wait { color: var(--running); font-weight: 600; }
  .tok { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); font-variant-numeric: tabular-nums; }
  .tok th, .tok td { padding: 4px 6px; text-align: right; border-bottom: 1px solid var(--line); }
  .tok th[scope='row'], .tok thead th:first-child { text-align: left; font-weight: 600; max-width: 10rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tok thead th { color: var(--text-3); font-size: var(--fs-xs); font-weight: 600; }
  .foot { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-top: var(--s-4); }
  @media (max-width: 1279px) { .sbtn { max-width: 160px; } }
  @media (max-width: 767px) {
    .sbtn { padding: 0 10px; max-width: 30vw; }
    .sbtn:not(.busy) .txt { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .sbtn:not(.busy) { width: 44px; justify-content: center; padding: 0; }
    .panel { position: fixed; left: 0; right: 0; top: var(--topbar-h); width: auto; max-height: calc(100dvh - var(--topbar-h)); border-radius: 0 0 var(--r-3) var(--r-3); padding-bottom: calc(var(--s-4) + env(safe-area-inset-bottom)); }
  }
</style>
