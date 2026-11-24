<script lang="ts">
  // « Préparer pour Mathlib » (S-BC, D61): a verified result → a contribution package the user reviews. Steps with
  // their status, the checklist, the file, the PR text. Nothing leaves the machine without two explicit clicks: the
  // exact requests are shown first (« Créer une branche sur mon fork »), the PR needs its own confirmation. Lazy-loaded
  // by the library and the proof step.
  import { onDestroy } from 'svelte';
  import { app } from '../lib/store/app.svelte';
  import { t, tk, i18n } from '../lib/i18n/index.svelte';
  import { mathlib, type MlSource, type MlState, type MlPlan, type MlCheck } from '../lib/api/mathlib';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import { navigate } from '../lib/router.svelte';
  import Icon from './Icon.svelte';

  let { source, onclose }: { source: MlSource; onclose: () => void } = $props();
  const uid = Math.random().toString(36).slice(2, 8);
  let st = $state<MlState | null>(null);
  let err = $state('');
  let busy = $state('');
  let author = $state(readAuthor());
  let plan = $state<MlPlan | null>(null);
  let timer: ReturnType<typeof setInterval> | null = null;

  function readAuthor(): string { try { return localStorage.getItem('madalean.mathlib.author') ?? ''; } catch { return ''; } }
  function saveAuthor() { try { localStorage.setItem('madalean.mathlib.author', author.trim()); } catch { /* ignore */ } }

  async function load() {
    try { st = await mathlib.get(source); err = ''; if (!author) author = st.package?.author || st.default_author; }
    catch (e) { err = errorText(e); }
    poll();
  }
  function poll() {
    const running = Boolean(st?.running || st?.package?.state === 'running');
    if (running && !timer) timer = setInterval(() => { void load(); }, 1500);
    if (!running && timer) { clearInterval(timer); timer = null; }
  }
  $effect(() => { void source.kind; void source.id; plan = null; void load(); });
  $effect(() => app.on('mathlib.contrib', () => { void load(); }));
  onDestroy(() => { if (timer) clearInterval(timer); });

  async function start() {
    busy = 'start'; saveAuthor();
    try { st = await mathlib.start(source, author.trim()); poll(); } catch (e) { toast('error', errorText(e)); }
    finally { busy = ''; }
  }
  async function reprove() {
    busy = 'reprove';
    try { const r = await mathlib.reprove(source); toast('ok', t('ml.reproveStarted')); navigate(`/d/${encodeURIComponent(r.dossier)}`); }
    catch (e) { toast('error', errorText(e)); } finally { busy = ''; }
  }
  async function askPlan(step: 'branch' | 'pr') {
    busy = 'plan';
    try { plan = (await mathlib.plan(source, step)).plan; } catch (e) { toast('error', errorText(e)); } finally { busy = ''; }
  }
  async function send() {
    if (!plan) return;
    busy = 'send';
    try {
      const r = await mathlib.send(source, plan.id);
      if (st) st.package = r.package;
      toast('ok', plan.kind === 'pr' ? t('ml.gh.prDone') : t('ml.gh.branchDone'));
      plan = null;
    } catch (e) { toast('error', errorText(e)); plan = null; } finally { busy = ''; }
  }
  function copy(text: string) { void navigator.clipboard?.writeText(text).then(() => toast('ok', t('ml.copied'))); }

  const pkg = $derived(st?.package ?? null);
  const running = $derived(Boolean(st?.running || pkg?.state === 'running'));
  const counts = $derived({
    errors: (pkg?.checks ?? []).filter((c) => c.severity === 'error').length,
    warnings: (pkg?.checks ?? []).filter((c) => c.severity === 'warning').length,
  });
  const MARK: Record<string, string> = { pending: '○', running: '…', ok: '✓', warn: '!', fail: '✗' };
  function detail(c: MlCheck): string {
    const p = c.params as Record<string, unknown>;
    const parts: string[] = [];
    for (const k of ['lines', 'names', 'imports']) if (Array.isArray(p[k]) && (p[k] as unknown[]).length) parts.push((p[k] as unknown[]).join(', '));
    if (Array.isArray(p['items']) && (p['items'] as unknown[]).length)
      parts.push((p['items'] as Record<string, unknown>[]).map((i) => i['kind'] ? `${i['kind']} (${i['line']})` : `${i['decl']}: ${(i['names'] as string[]).join(' ')}`).join(' · '));
    if (p['taken']) parts.push(String(p['taken']));
    if (p['axioms']) parts.push((p['axioms'] as string[]).join(', '));
    return parts.join(' — ');
  }
</script>

<section class="ml panel" aria-labelledby="ml-h-{uid}">
  <div class="row head">
    <h2 id="ml-h-{uid}">{t('ml.title')}</h2>
    <span class="spacer"></span>
    <button class="btn small quiet" onclick={onclose} aria-label={t('common.close')}><Icon name="x" size={16} /></button>
  </div>
  <p class="small muted">{t('ml.intro')}</p>
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}

  {#if st && !running}
    <form class="row author" onsubmit={(e) => { e.preventDefault(); void start(); }}>
      <label for="ml-author-{uid}">{t('ml.author')}</label>
      <input id="ml-author-{uid}" type="text" bind:value={author} autocomplete="name" maxlength="120" />
      <button class="btn small primary" type="submit" disabled={busy !== '' || !author.trim()}>
        <Icon name="play" size={14} />{pkg ? t('ml.restart') : t('ml.start')}</button>
    </form>
    <p class="xs muted">{t('ml.authorHint')}</p>
  {/if}

  {#if pkg}
    <ol class="steps" aria-label={t('ml.steps')} aria-live="polite">
      {#each pkg.steps as s (s.id)}
        <li class="step {s.state}"><span class="mark" aria-hidden="true">{MARK[s.state]}</span>
          {tk(`ml.step.${s.id}`, s.id)} <span class="xs muted">— {tk(`ml.state.${s.state}`, s.state)}</span></li>
      {/each}
    </ol>

    {#if pkg.state === 'in_mathlib' && pkg.in_mathlib}
      <p class="notice ok" role="status">{t('ml.inMathlib', { name: pkg.in_mathlib.lemma })}</p>
      <p class="small"><code>{pkg.in_mathlib.tactic}</code></p>
    {:else if pkg.state === 'port_failed'}
      <p class="notice warn" role="status">{t('ml.portFailed')}</p>
      {#if pkg.port?.renames.length}<p class="small">{t('ml.renamesTried', { list: pkg.port.renames.map((r) => `${r.old} → ${r.new}`).join(', ') })}</p>{/if}
      {#if pkg.port?.errors}<details><summary>{t('ml.leanErrors')}</summary><pre class="code">{pkg.port.errors}</pre></details>{/if}
      <button class="btn small" onclick={reprove} disabled={busy !== ''}><Icon name="refresh" size={14} />{t('ml.reprove')}</button>
    {:else if pkg.state === 'failed'}
      <p class="notice warn" role="status">{pkg.steps[0]?.params['code'] === 'target_missing' ? t('ml.targetMissing') : t('ml.failed')}</p>
    {:else if pkg.state === 'ready' && pkg.file && pkg.name && pkg.pr && pkg.target}
      <p class="notice {counts.errors ? 'warn' : 'ok'}" role="status">
        {counts.errors ? t('ml.readyWithErrors', { e: counts.errors, w: counts.warnings }) : t('ml.ready', { w: counts.warnings })}</p>
      {#if pkg.port && pkg.port.from !== pkg.port.to}
        <p class="small">{t('ml.ported', { from: pkg.port.from, to: pkg.port.to, n: pkg.port.renames.length })}
          {#if pkg.port.renames.length}<span class="xs muted">({pkg.port.renames.map((r) => `${r.old} → ${r.new}`).join(', ')})</span>{/if}</p>
      {/if}
      {#if pkg.in_mathlib}<p class="small">{t('ml.closeToMathlib', { tactic: pkg.in_mathlib.tactic })}</p>{/if}

      <h3>{t('ml.name')}</h3>
      <p><code class="name">{pkg.name.full}</code> <span class="xs muted">({t('ml.was', { name: pkg.name.original })})</span></p>
      {#if pkg.name.words.length && !pkg.name.fallback}
        <p class="small">{t('ml.nameWhy')}
          {#each pkg.name.words as w, i (i)}<span class="word">{#if w.token}<code>{w.token}</code> → {/if}<code>{w.word}</code></span>{/each}</p>
      {:else}<p class="small">{t('ml.nameFallback')}</p>{/if}
      {#if pkg.name.rules.length}<ul class="xs muted rules">{#each pkg.name.rules as r (r)}{#if tk(`ml.rule.${r}`, '')}<li>{tk(`ml.rule.${r}`, '', { ns: pkg.name.namespace })}</li>{/if}{/each}</ul>{/if}

      <h3>{t('ml.where')}</h3>
      <p class="small">{t('ml.whereText', { path: pkg.target.path, closest: pkg.target.closest_path })}</p>

      <h3>{t('ml.checklist')}</h3>
      <table class="checks">
        <caption class="sr-only">{t('ml.checklist')}</caption>
        <thead><tr><th scope="col">{t('ml.col.result')}</th><th scope="col">{t('ml.col.rule')}</th><th scope="col">{t('ml.col.detail')}</th></tr></thead>
        <tbody>
          {#each pkg.checks as c (c.id)}
            <tr class={c.severity}><td><span aria-hidden="true">{c.severity === 'ok' ? '✓' : c.severity === 'unknown' ? '?' : c.severity === 'error' ? '✗' : '!'}</span>
              {tk(`ml.sev.${c.severity}`, c.severity)}</td>
              <th scope="row">{tk(`ml.check.${c.id}`, c.id)}</th><td class="xs">{detail(c)}</td></tr>
          {/each}
        </tbody>
      </table>

      <h3>{t('ml.file')} <code class="xs">{pkg.file.path}</code></h3>
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <pre class="code file" tabindex="0" aria-label={t('ml.file')}>{pkg.file.text}</pre>
      <div class="row">
        <button class="btn small" onclick={() => copy(pkg.file?.text ?? '')}><Icon name="copy" size={14} />{t('ml.copy')}</button>
        <a class="btn small" href={mathlib.fileUrl(source)} download><Icon name="download" size={14} />{t('ml.download')}</a>
      </div>

      <h3>{t('ml.pr')}</h3>
      <p class="small">{i18n.base === 'en' ? pkg.pr.explain.en : pkg.pr.explain.fr}</p>
      <p><strong lang="en">{pkg.pr.title}</strong></p>
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <pre class="code" lang="en" tabindex="0" aria-label={t('ml.prBody')}>{pkg.pr.body}</pre>
      <button class="btn small" onclick={() => copy(`${pkg.pr?.title}\n\n${pkg.pr?.body}`)}><Icon name="copy" size={14} />{t('ml.copyPr')}</button>

      <h3>{t('ml.gh.title')}</h3>
      {#if !st?.github.configured}
        <p class="small muted">{t('ml.gh.noKey')}</p>
      {:else if !st.github.host}
        <p class="small muted">{t('ml.gh.hostOnly')}</p>
      {:else}
        {#if pkg.github?.branch}
          <p class="small">{t('ml.gh.branchIs')} <a href={pkg.github.branch.branch_url} target="_blank" rel="noopener noreferrer">{pkg.github.branch.fork}:{pkg.github.branch.branch}</a></p>
        {/if}
        {#if pkg.github?.pr}
          <p class="small">{t('ml.gh.prIs')} <a href={pkg.github.pr.url} target="_blank" rel="noopener noreferrer">#{pkg.github.pr.number}</a></p>
        {:else if !plan}
          <div class="row">
            {#if !pkg.github?.branch}<button class="btn small" onclick={() => askPlan('branch')} disabled={busy !== ''}><Icon name="github" size={14} />{t('ml.gh.branch')}</button>
            {:else}<button class="btn small" onclick={() => askPlan('pr')} disabled={busy !== ''}><Icon name="github" size={14} />{t('ml.gh.pr')}</button>{/if}
          </div>
        {/if}
        {#if plan}
          <div class="plan" role="region" aria-label={t('ml.gh.planTitle')}>
            <p class="small"><strong>{t('ml.gh.planTitle')}</strong> — {t('ml.gh.planIntro', { login: plan.login })}</p>
            <ol class="xs">
              {#each plan.requests as rq, i (i)}<li><code>{rq.method} {rq.url}</code>{#if rq.body}<pre class="code">{JSON.stringify(rq.body, null, 1)}</pre>{/if}</li>{/each}
            </ol>
            {#if plan.content}<details><summary>{t('ml.gh.content', { path: plan.path ?? '' })}</summary><pre class="code">{plan.content}</pre></details>{/if}
            <div class="row">
              <button class="btn small primary" onclick={send} disabled={busy !== ''}><Icon name="send" size={14} />{plan.kind === 'pr' ? t('ml.gh.confirmPr') : t('ml.gh.confirmBranch')}</button>
              <button class="btn small quiet" onclick={() => (plan = null)}>{t('common.cancel')}</button>
            </div>
          </div>
        {/if}
      {/if}

      <h3>{t('ml.links')}</h3>
      <ul class="small links">{#each pkg.links as l (l.id)}<li><a href={l.url} target="_blank" rel="noopener noreferrer">{tk(`ml.link.${l.id}`, l.url)}</a></li>{/each}</ul>
    {/if}
  {:else if st && !running}
    <p class="small">{t('ml.none')}</p>
  {/if}
</section>

<style>
  .ml { display: grid; gap: 8px; margin-top: 12px; }
  .head h2 { margin: 0; font-size: var(--fs-lg); }
  .spacer { flex: 1; }
  .author { gap: 8px; flex-wrap: wrap; align-items: center; }
  .author input { min-width: 14em; flex: 1; }
  .steps { list-style: none; padding: 0; margin: 0; display: grid; gap: 2px; }
  .step .mark { display: inline-block; width: 1.4em; text-align: center; font-weight: 600; }
  .step.ok .mark { color: var(--proved); }
  .step.warn .mark, .step.running .mark { color: var(--running); }
  .step.fail .mark { color: var(--failed); }
  .notice { padding: 6px 10px; border-radius: 6px; margin: 4px 0; }
  .notice.ok { background: var(--proved-soft); }
  .notice.warn { background: var(--failed-soft); }
  .word { margin-right: 8px; white-space: nowrap; }
  .rules { margin: 0; padding-left: 1.2em; }
  .checks { border-collapse: collapse; width: 100%; font-size: var(--fs-sm); }
  .checks th, .checks td { text-align: left; padding: 3px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .checks th[scope='row'] { font-weight: 500; }
  .checks tr.error td:first-child { color: var(--failed); }
  .checks tr.warning td:first-child { color: var(--running); }
  .checks tr.ok td:first-child { color: var(--proved); }
  .code { font-family: var(--font-mono); font-size: var(--fs-xs); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface);
    border: 1px solid var(--line); border-radius: 6px; padding: 8px; max-height: 24em; overflow: auto; margin: 4px 0; }
  .file { max-height: 32em; }
  .plan { border: 1px solid var(--line-strong); border-radius: 6px; padding: 8px; }
  .links { margin: 0; padding-left: 1.2em; }
  code.name { font-size: var(--fs-md); }
</style>
