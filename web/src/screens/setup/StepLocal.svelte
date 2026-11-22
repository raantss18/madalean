<script lang="ts">
  // Step 3: a local model or not, and which one for this machine (assistant.recommend(): graphics memory and RAM),
  // with what it downloads. The choice is remembered (wizard progress); « Télécharger » fetches the missing files
  // the way install.sh does (pinned, SHA-256 checked) with live progress (`setup.models`), refused in Local mode.
  import { onDestroy } from 'svelte';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtBytes } from '../../lib/i18n/index.svelte';
  import { ApiError } from '../../lib/api/client';
  import { setupApi, type FetchJob, type SetupStatus } from '../../lib/setup/api';
  import { saveWizard } from '../../lib/setup/state.svelte';
  import { modelChoice, modelsMissing, type ModelSet } from '../../lib/setup/wizard';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';

  let { status, reload }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  const rec = $derived(status?.recommended?.items.find((i) => i.id === 'models'));
  let picked = $state<ModelSet | null>(null);
  const choice = $derived<ModelSet>(picked ?? modelChoice(status?.models.choice ?? '', rec?.recommended));
  const files = $derived(status?.models.files ?? []);
  const missing = $derived(modelsMissing(files, choice));
  let job = $state<FetchJob | null>(null);
  let msg = $state<{ level: 'ok' | 'warn' | 'error'; text: string } | null>(null);
  $effect(() => { if (status?.models.fetch && Object.keys(status.models.fetch).length && !job) job = status.models.fetch; });
  const off = app.on('setup.models', (ev) => {
    job = (ev as unknown as { fetch: FetchJob }).fetch;
    if (job && !job.running && job.phase === 'done') { msg = { level: 'ok', text: t('setup.local.downloaded') }; void reload(); }
    else if (job && !job.running && job.phase === 'error') msg = { level: 'error', text: t('setup.local.failed') };
  });
  onDestroy(off);

  function pick(v: ModelSet) { picked = v; msg = null; void saveWizard({ models: v }); }
  function sizeOf(v: ModelSet): string {
    const n = status?.models.download_bytes[v] ?? 0;
    return v === 'none' ? t('setup.local.nothing') : n ? t('setup.local.toDownload', { n: fmtBytes(n) }) : t('setup.local.present');
  }
  async function download() {
    if (choice === 'none') return;
    msg = null;
    try {
      const r = await setupApi.fetchModels(choice);
      if (!r.started) { msg = { level: 'ok', text: t('setup.local.present') }; return; }
      job = r.models.fetch;
    } catch (e) {
      const k = e instanceof ApiError ? e.kind : '';
      msg = { level: 'warn', text: tk(`setup.local.err.${k}`, errorText(e)) };
    }
  }
  async function cancel() { try { await setupApi.cancelModels(); } catch (e) { msg = { level: 'error', text: errorText(e) }; } }
  const running = $derived(!!job?.running);
  const pct = $derived(job?.total_gb ? Math.round(((job.done_gb ?? 0) / job.total_gb) * 100) : 0);
</script>

{#if !status}
  <p class="muted" aria-busy="true">{t('setup.loading')}</p>
{:else}
  <div class="stack">
    <fieldset class="panel" aria-describedby="l-why">
      <legend>{t('setup.local.question')}</legend>
      <div class="choices">
        {#each ['none', 'prover', 'all'] as v (v)}
          <label class="choice" class:sel={choice === v}>
            <input type="radio" name="models" value={v} checked={choice === v} disabled={running} onchange={() => pick(v as ModelSet)} />
            <span><strong>{t(`setup.local.${v as ModelSet}`)}</strong>{#if v === rec?.recommended}<span class="rec"><Icon name="check" size={12} />{t('setup.recommended')}</span>{/if}
              <span class="small muted">{t(`setup.local.${v as ModelSet}.desc`)}</span>
              <span class="xs">{sizeOf(v as ModelSet)}</span></span>
          </label>
        {/each}
      </div>
      <p class="why" id="l-why">{rec?.why ?? t('setup.local.whyDefault')}</p>
    </fieldset>

    <section class="panel" aria-labelledby="l-files">
      <h2 id="l-files">{t('setup.local.files', { dir: status.models.dir })}</h2>
      <ul class="files small">
        {#each files as f (f.key)}
          <li><Icon name={f.present ? 'check' : 'download'} size={14} /> <span class="mono xs">{f.file}</span>
            <span class="muted xs">{f.present ? fmtBytes(f.bytes) : t('setup.local.missing')}</span></li>
        {/each}
      </ul>
      {#if choice !== 'none' && missing.length}
        <div class="row">
          <button class="btn primary" onclick={download} disabled={running}><Icon name="download" size={16} />{t('setup.local.download', { n: fmtBytes(missing.reduce((a, f) => a + f.download_bytes, 0)) })}</button>
          {#if running}<button class="btn" onclick={cancel}>{t('setup.local.cancel')}</button>{/if}
        </div>
      {/if}
      {#if job && running}
        <span class="meter" role="progressbar" aria-label={t('setup.local.progressLabel')} aria-valuemin="0" aria-valuemax="100" aria-valuenow={pct}><span style="width: {pct}%"></span></span>
        <p class="small" role="status">{t('setup.local.progress', { i: Math.min((job.index ?? 0) + 1, job.keys?.length ?? 1), n: job.keys?.length ?? 1, done: (job.done_gb ?? 0).toFixed(1), total: (job.total_gb ?? 0).toFixed(1) })}</p>
      {/if}
      {#if msg}<p class="small st {msg.level}" role="status">{msg.text}</p>{/if}
      <p class="hint">{t('setup.local.hint')}</p>
    </section>
  </div>
{/if}

<style>
  .files { list-style: none; padding: 0; margin: 0 0 var(--s-3); display: grid; gap: 4px; }
  .files li { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .mono { font-family: var(--font-mono); overflow-wrap: anywhere; }
</style>
