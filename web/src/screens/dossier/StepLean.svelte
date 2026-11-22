<script lang="ts">
  import EnterHint from '../../components/EnterHint.svelte';
  import { enterSubmit } from '../../lib/ui/enter';
  // Step 2 « Traduction Lean »: what you meant (left) and what Lean will prove (right), side by side so the
  // translation can be checked; check with Lean, edit by hand, versions, « corriger l'énoncé »; learn panel with
  // the line-by-line gloss and the meaning of any token (hover or tap).
  import type { Dossier, Job, CheckResult } from '../../lib/api/types';
  import { api } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, i18n } from '../../lib/i18n/index.svelte';
  import { prefs } from '../../lib/prefs.svelte';
  import { modelLabel, jobRuns } from '../../lib/status';
  import type { GlossEntry } from '../../lib/lean/glossary';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import Md from '../../components/Md.svelte';
  import StreamView from '../../components/StreamView.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';
  import Versions from './Versions.svelte';
  import ExplainBack from './ExplainBack.svelte';
  import { follow, run, reportError, verify as verifyStatement } from './actions';
  import StatementVerdict from './StatementVerdict.svelte';
  import LeanExplain from '../../components/LeanExplain.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';

  let { dossier: d, job }: { dossier: Dossier; job: Job | undefined } = $props();
  let editing = $state(false);
  let code = $state('');
  let check = $state<CheckResult | null>(null);
  let checking = $state(false);
  let correcting = $state(false);
  let correction = $state('');
  let tapped = $state<{ token: string; entry: GlossEntry | null; server?: { title: string; body: string } | null; loading?: boolean } | null>(null);
  async function tap(token: string, entry: GlossEntry | null) {
    tapped = { token, entry, loading: !entry };
    if (entry) return;
    const { lookupToken } = await import('../../lib/lean/lookup');
    const r = await lookupToken(token, d.workspace);
    if (tapped?.token === token) tapped = { token, entry, server: r, loading: false };
  }
  let learnOpen = $state(prefs.mode === 'learn');
  let ctl: AbortController | null = null;

  const v = $derived(d.statements[d.cur_statement]);
  const statement = $derived(d.current.statement);
  const running = $derived(job && ['understand', 'route', 'statement', 'notes'].includes(job.stage));
  const notes = $derived(d.current.statement_notes);
  const errors = $derived((check?.errors ?? []).map((e) => ({ line: e.line, text: e.text, severity: e.severity })));
  // Keep the editor in sync with the server unless the user is editing (never overwrite their text).
  $effect(() => { if (!editing) code = statement; });
  let serverChangedWhileEditing = $state(false);
  let editBase = '';
  $effect(() => { if (editing && statement !== editBase) serverChangedWhileEditing = true; });

  function startEdit() { editBase = statement; code = statement; editing = true; serverChangedWhileEditing = false; check = null; }
  async function verify() {
    checking = true; check = null;
    ctl = new AbortController();
    try {
      if (editing) check = (await api.check(code, { workspace: d.workspace }, { signal: ctl.signal })).check;
      else check = (await api.checkDossier(d.id, 'statement', { signal: ctl.signal })).check;
    } catch (e) { if ((e as Error).name !== 'AbortError') reportError(e, d.id); } finally { checking = false; ctl = null; }
  }
  async function saveEdit() {
    checking = true;
    try {
      const r = await api.setStatement(d.id, code, true);
      app.m.full[d.id] = r.dossier;
      check = r.check;
      editing = false;
      toast(r.check?.statement_ok === false ? 'warn' : 'ok', r.check?.statement_ok === false ? t('lean.savedButRejected') : t('lean.saved'));
    } catch (e) { reportError(e, d.id); } finally { checking = false; }
  }
  // S-AM (D45): « Appliquer la correction » = a manual edit of the statement (new version, checked by Lean)
  async function applyFix(fix: string): Promise<boolean> {
    try {
      const r = await api.setStatement(d.id, fix, true);
      app.m.full[d.id] = r.dossier;
      check = r.check;
      editing = false;
      toast(r.check?.statement_ok === false ? 'warn' : 'ok', r.check?.statement_ok === false ? t('lx.appliedRejected') : t('lx.applied'));
      return true;
    } catch (e) { reportError(e, d.id); return false; }
  }
  async function sendCorrection() {
    if (!correction.trim()) return;
    if (await follow(d.id, correction.trim(), 'statement')) { correction = ''; correcting = false; }
  }
  async function prove() {
    if (await run(d.id, d.statement_notes.some((n) => n.parent === d.cur_statement) || !app.m.settings?.statement_notes ? ['proof', 'explanation'] : ['notes', 'proof', 'explanation'])) navigate(`/d/${encodeURIComponent(d.id)}/preuve`);
  }
  async function makeNotes() { await run(d.id, ['notes']); }
</script>

<div class="lean-step">
  <div class="compare">
    <section class="panel" aria-labelledby="meant-h">
      <h2 id="meant-h">{t('lean.youMeant')}</h2>
      {#if d.problem}<div class="theorem"><Md src={d.problem} cls="th-body" /></div>{/if}
      {#if d.understood_display}
        <h3 class="sub">{t('lean.understoodAs')}</h3>
        <div class="theorem understood"><Md src={d.understood_display} cls="th-body" /></div>
      {/if}
      {#if !d.problem && !d.understood_display}<p class="muted small">{t('lean.noNatural')}</p>{/if}
      <p class="hint verify">{t('lean.verifyHint')}</p>
    </section>

    <section class="panel" aria-labelledby="lean-h">
      <div class="row"><h2 id="lean-h">{t('lean.leanStatement')}</h2><span class="spacer"></span>
        {#if v}<span class="chip {v.ok ? 'proved' : 'failed'}">{v.ok ? t('lean.accepted') : t('lean.rejected')}</span>{/if}
      </div>
      {#if running && job && (job.stage === 'statement' || !statement)}
        <p class="small">{tk(`stage.${job.stage}`, '')}…</p>
        <StreamView jobId={job.id} stage={job.stage} maxHeight="300px" />
      {:else if statement}
        {#if v}<p class="xs muted">{v.source === 'user' ? t('versions.byYou') : t('common.by', { model: modelLabel(v.model).name || t('versions.byAi') })}{#if v.note} — {v.note}{/if}</p>{/if}
        {#if editing && serverChangedWhileEditing}<p class="notice small" role="status">{t('lean.serverChanged')} <button class="btn small" onclick={() => { code = statement; editBase = statement; serverChangedWhileEditing = false; }}>{t('lean.takeServer')}</button></p>{/if}
        <CodeEditor bind:value={code} language="lean" readonly={!editing} label={t('lean.leanStatement')} {errors} gloss={prefs.mode === 'learn' || learnOpen}
          onTokenTap={tap} workspace={d.workspace} minLines={4} onSubmit={editing ? saveEdit : undefined} />
        <div class="row tools">
          {#if editing}
            <button class="btn primary" onclick={saveEdit} disabled={checking}>{checking ? t('lean.checking') : t('lean.saveAndCheck')}</button>
            <button class="btn" onclick={verify} disabled={checking}>{t('lean.checkOnly')}</button>
            <button class="btn quiet" onclick={() => { editing = false; check = null; }}>{t('common.cancel')}</button>
          {:else}
            <button class="btn" onclick={verify} disabled={checking}>{checking ? t('lean.checking') : t('lean.check')}</button>
            {#if checking}<button class="btn quiet" onclick={() => ctl?.abort()}>{t('common.cancel')}</button>{/if}
            <button class="btn" onclick={startEdit} disabled={Boolean(job)}>{t('lean.editByHand')}</button>
            <button class="btn" aria-expanded={correcting} onclick={() => (correcting = !correcting)} disabled={Boolean(job)}>{t('lean.fix')}</button>
            {#if v?.ok}<button class="btn" onclick={() => verifyStatement(d.id, prefs.mode === 'learn')} disabled={Boolean(job)} title={t('check.buttonHint')}>{jobRuns(job, 'verify') ? t('check.running') : t('check.button')}</button>{/if}
            <Versions dossier={d} kind="statement" busy={Boolean(job)} />
          {/if}
          <LeanExplain where={{ dossier: d.id, part: 'statement' }} code={editing ? code : undefined}
            errors={check && !check.statement_ok ? check.errors : null} canError={editing ? Boolean(check && !check.statement_ok) : !(check?.statement_ok ?? v?.ok ?? true)}
            onApply={applyFix} disabled={Boolean(job)} />
        </div>
        {#if correcting}
          <div class="field correction">
            <label for="corr">{t('lean.fixLabel')}</label>
            <textarea id="corr" class="input" rows="2" bind:value={correction} use:enterSubmit={() => void sendCorrection()} placeholder={t('lean.fixPlaceholder')} aria-describedby="corr-e"></textarea>
            <EnterHint id="corr-e" />
            <div class="row"><button class="btn primary" onclick={sendCorrection} disabled={!correction.trim()}>{t('lean.fixSend')}</button></div>
          </div>
        {/if}
        {#if check}<CheckResultView {check} />{/if}
        {#if v?.meta?.check}<StatementVerdict id={d.id} params={v.meta.check as Record<string, unknown>} busy={Boolean(job)} actions={!d.proofs.some((p) => p.parent === d.cur_statement && p.ok)} />{/if}
        {#if !job && !d.proofs.some((p) => p.parent === d.cur_statement) && v?.ok}
          <div class="next">
            <button class="btn primary" onclick={prove}>{t('lean.prove')}</button>
            <span class="hint">{t('lean.proveHint')}</span>
          </div>
        {/if}
      {:else}
        <p class="muted">{job ? t('lean.waiting') : t('lean.none')}</p>
        {#if !job && d.problem}<button class="btn primary" onclick={() => run(d.id, ['understand', 'statement'])}>{t('enonce.translate')}</button>{/if}
      {/if}
    </section>
  </div>

  {#if statement}
    <section class="panel learn" aria-labelledby="learn-h">
      <div class="row">
        <h2 id="learn-h">{t('learn.title')}</h2>
        <span class="spacer"></span>
        {#if prefs.mode === 'research'}<button class="btn small" aria-expanded={learnOpen} onclick={() => (learnOpen = !learnOpen)}>{learnOpen ? t('common.hide') : t('common.show')}</button>{/if}
      </div>
      {#if learnOpen}
        <div class="learn-grid">
          <div>
            <h3>{t('learn.gloss')}</h3>
            {#if job && jobRuns(job, 'notes')}<StreamView jobId={job.id} stage="notes" maxHeight="220px" />
            {:else if notes}<Md src={notes} cls="gloss" />
            {:else}<p class="muted small">{t('learn.noGloss')}</p>{#if !job}<button class="btn small" onclick={makeNotes}>{t('learn.makeGloss')}</button>{/if}{/if}
          </div>
          <div>
            <h3>{t('learn.token')}</h3>
            <div class="token-box" aria-live="polite">
              {#if tapped}
                <p><code>{tapped.token}</code>{#if tapped.entry} <span class="chip">{tk(`gloss.kind.${tapped.entry.kind}`, tapped.entry.kind)}</span>{/if}</p>
                {#if tapped.entry}<p class="small">{tapped.entry[i18n.lang]}</p>
                {:else if tapped.loading}<p class="small muted">{t('common.loading')}</p>
                {:else if tapped.server}<pre class="sig">{tapped.server.body}</pre>
                {:else}<p class="small">{t('learn.tokenUnknown')}</p>{/if}
              {:else}
                <p class="muted small">{t('learn.tokenHint')}</p>
              {/if}
            </div>
            <a class="small" href="/glossaire">{t('learn.openGlossary')}</a>
          </div>
        </div>
        {#if prefs.mode === 'learn'}<ExplainBack dossier={d} target="statement" />{/if}
      {/if}
    </section>
  {/if}
</div>

<style>
  .compare { display: grid; grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr); gap: var(--s-4); align-items: start; }
  @media (max-width: 1023px) { .compare { grid-template-columns: minmax(0, 1fr); } }
  h2 { margin: 0; }
  .sub { margin: var(--s-3) 0 4px; font-size: var(--fs-sm); color: var(--text-2); }
  .theorem { margin-top: var(--s-2); }
  .understood { border-left: 3px solid var(--line-strong); padding-left: var(--s-3); }
  .verify { margin-top: var(--s-3); }
  .tools { margin-top: var(--s-2); }
  .correction { margin-top: var(--s-3); }
  .next { display: flex; align-items: center; gap: var(--s-3); flex-wrap: wrap; margin-top: var(--s-4); padding-top: var(--s-3); border-top: 1px solid var(--line); }
  .notice { background: var(--running-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
  .learn { margin-top: var(--s-4); }
  .learn-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: var(--s-4); margin-top: var(--s-2); }
  @media (max-width: 899px) { .learn-grid { grid-template-columns: minmax(0, 1fr); } }
  .learn :global(.gloss li) { margin-bottom: 4px; }
  .token-box { background: var(--surface-2); border-radius: var(--r-2); padding: var(--s-3); min-height: 5.5rem; margin-bottom: var(--s-2); }
  .token-box p { margin: 0 0 4px; }
  .sig { font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
</style>
