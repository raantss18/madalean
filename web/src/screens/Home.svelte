<script lang="ts">
  // « Énoncé » for a NEW dossier: write in natural language/LaTeX (live preview) or directly in Lean, import .tex,
  // examples; send → the dossier opens on its Lean step.
  import { app } from '../lib/store/app.svelte';
  import { api } from '../lib/api/client';
  import type { Mode, Strategy } from '../lib/api/types';
  import { navigate } from '../lib/router.svelte';
  import { t, i18n } from '../lib/i18n/index.svelte';
  import { prefs, loadJSON, saveJSON, removeKey } from '../lib/prefs.svelte';
  import { EXAMPLES, type Example } from '../lib/examples';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import CodeEditor from '../components/CodeEditor.svelte';
  import Md from '../components/LazyMd.svelte';
  import TexImport from '../components/TexImport.svelte';
  import Icon from '../components/Icon.svelte';
  import HelpLink from '../components/HelpLink.svelte';
  import EnterHint from '../components/EnterHint.svelte';
  import DossierList from '../components/DossierList.svelte';
  import SetupReminder from './setup/SetupReminder.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  const draft = loadJSON<{ text: string; lean: string; asLean: boolean; title?: string }>('draft.new', { text: '', lean: '', asLean: false });
  let text = $state(draft.text);
  let lean = $state(draft.lean);
  let asLean = $state(draft.asLean);
  let title = $state(draft.title ?? '');
  let mode = $state<Mode | ''>('');
  let strategy = $state<Strategy | ''>('');
  let busy = $state(false);
  let err = $state('');
  let showOptions = $state(false);

  $effect(() => { saveJSON('draft.new', { text, lean, asLean, title }); });   // the unsent problem survives a reload
  // One source for examples: the server's list (GET /examples); the built-in copy only if the server lacks it.
  let examples = $state<Example[]>(EXAMPLES);
  $effect(() => {
    api.examples().then((r) => {
      if (r.examples?.length) examples = r.examples.map((x) => ({ key: x.key, statement: x.statement,
        level: { fr: x.fr.level, en: x.en.level }, title: { fr: x.fr.title, en: x.en.title }, problem: { fr: x.fr.blurb, en: x.en.blurb } }));
    }).catch(() => {});
  });

  const hasDossiers = $derived(Object.values(app.m.dossiers).some((d) => !prefs.lastProject || d.project_id === prefs.lastProject));
  const project = $derived(prefs.lastProject ? app.m.projects[prefs.lastProject] : undefined);
  const canSend = $derived(asLean ? lean.trim().length > 0 : text.trim().length > 2);

  async function send() {
    if (!canSend || busy) return;
    busy = true; err = '';
    try {
      const r = await api.createDossier({
        ...(asLean ? { statement: lean, problem: text.trim() || undefined } : { problem: text.trim() }),
        title: title.trim() || undefined, project_id: prefs.lastProject || undefined, start: true,
        ...(mode ? { mode } : {}), ...(strategy ? { strategy } : {}),
      });
      app.m.full[r.dossier.id] = r.dossier;
      if (r.job) app.m.jobs[r.job.id] = r.job;
      removeKey('draft.new');
      text = ''; lean = ''; title = '';
      navigate(`/d/${encodeURIComponent(r.dossier.id)}/${asLean ? 'preuve' : 'lean'}`);
    } catch (e) {
      err = errorText(e);
      toast('error', err);
    } finally { busy = false; }
  }
  function useExample(i: number) {
    const ex = examples[i]!;
    if (asLean) lean = ex.statement;
    else text = ex.problem[i18n.lang];
    title = ex.title[i18n.lang].replace(/\$[^$]*\$/g, '').trim();
    document.getElementById('statement-input')?.focus();
  }
</script>

<div class="home">
  <SetupReminder />
  <section class="compose" aria-labelledby="home-h">
    <div class="row"><h1 id="home-h">{t('home.title')}</h1><HelpLink page="workflow" /></div>
    <p class="lead">{project ? t('home.inProject', { title: project.title }) : t('home.lead')}</p>

    <div class="seg kind" role="radiogroup" aria-label={t('home.inputKind')}>
      <label><input type="radio" name="kind" checked={!asLean} onchange={() => (asLean = false)} />{t('home.natural')}</label>
      <label><input type="radio" name="kind" checked={asLean} onchange={() => (asLean = true)} />{t('home.leanDirect')}</label>
    </div>

    {#if !asLean}
      <div class="editor-grid">
        <div>
          <label class="label" for="statement-input">{t('home.statementLabel')}</label>
          <CodeEditor id="statement-input" bind:value={text} language="natural" label={t('home.statementLabel')} placeholder={t('home.placeholder')} minLines={5} onSubmit={send} describedby="home-hint home-enter" />
          <p class="hint" id="home-hint">{t('home.hint')}</p>
          <EnterHint id="home-enter" />
        </div>
        <div class="preview" aria-live="off">
          <p class="label" id="pv-h">{t('home.preview')}</p>
          <div class="preview-box theorem" aria-labelledby="pv-h">
            {#if text.trim()}<span class="th-head">{t('home.statementWord')}. </span><Md src={text} cls="th-body" />{:else}<p class="muted small">{t('home.previewEmpty')}</p>{/if}
          </div>
        </div>
      </div>
    {:else}
      <label class="label" for="statement-input">{t('home.leanLabel')}</label>
      <CodeEditor id="statement-input" bind:value={lean} language="lean" label={t('home.leanLabel')} placeholder="theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry" minLines={4} onSubmit={send} gloss={prefs.mode === 'learn'} describedby="home-lean-hint home-enter" />
      <p class="hint" id="home-lean-hint">{t('home.leanHint')}</p>
      <EnterHint id="home-enter" />
      <div class="field" style="margin-top: var(--s-3)">
        <label for="nl-opt">{t('home.leanProblemLabel')}</label>
        <input id="nl-opt" class="input" bind:value={text} placeholder={t('home.leanProblemPlaceholder')} />
      </div>
    {/if}

    <div class="field title-field">
      <label for="d-title">{t('home.titleLabel')} <span class="muted">({t('common.optional')})</span></label>
      <input id="d-title" class="input" bind:value={title} />
    </div>

    <details class="opts" bind:open={showOptions}>
      <summary>{t('home.options')}</summary>
      <div class="opts-grid">
        <div class="field">
          <label for="run-mode">{t('settings.mode')}</label>
          <select id="run-mode" class="input" bind:value={mode}>
            <option value="">{t('home.default', { v: t(`mode.${app.m.settings?.mode ?? 'auto'}` as 'mode.auto') })}</option>
            <option value="local">{t('mode.local')}</option><option value="auto">{t('mode.auto')}</option><option value="online">{t('mode.online')}</option>
          </select>
        </div>
        <div class="field">
          <label for="run-strat">{t('settings.strategy')}</label>
          <select id="run-strat" class="input" bind:value={strategy}>
            <option value="">{t('home.default', { v: t(`strategy.${app.m.settings?.prove_strategy ?? 'auto'}` as 'strategy.auto') })}</option>
            <option value="auto">{t('strategy.auto')}</option><option value="agent">{t('strategy.agent')}</option><option value="goedel">{t('strategy.goedel')}</option>
          </select>
        </div>
      </div>
    </details>

    {#if err}<p class="error-text" role="alert">{err}</p>{/if}
    <div class="row actions">
      <button class="btn primary big" onclick={send} disabled={!canSend || busy} aria-keyshortcuts="Enter">
        <Icon name="send" />{busy ? t('home.sending') : asLean ? t('home.sendLean') : t('home.send')}
      </button>
      <TexImport onpick={(body, ttl) => { asLean = false; text = body; title = ttl; }} />
    </div>
    <p class="hint">{t('home.after')}</p>
  </section>

  {#if hasDossiers}
    <!-- S-AK: the project's full dossier list (it was in the rail / drawer), with search, status and lemmas -->
    <section class="recent" aria-labelledby="rec-h">
      <h2 id="rec-h">{prefs.lastProject ? t('home.dossiers') : t('home.allDossiers')}</h2>
      <DossierList uid="home" />
    </section>
  {/if}

  <section class="examples" aria-labelledby="ex-h">
    <h2 id="ex-h">{t('home.examples')}</h2>
    <ul>
      {#each examples as ex, i (ex.key)}
        <li>
          <button class="ex" onclick={() => useExample(i)}>
            <span class="lvl xs">{ex.level[i18n.lang]}</span>
            <span class="ex-title"><Md inline src={ex.title[i18n.lang]} /></span>
            <span class="ex-body small"><Md inline src={ex.problem[i18n.lang]} /></span>
          </button>
        </li>
      {/each}
    </ul>
  </section>

</div>

<style>
  .home { max-width: 1100px; display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-6); }
  .editor-grid > div { min-width: 0; }
  .lead { color: var(--text-2); max-width: var(--measure); }
  .kind { margin-bottom: var(--s-4); }
  .editor-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--s-4); }
  @media (max-width: 899px) { .editor-grid { grid-template-columns: minmax(0, 1fr); } }
  .label { display: block; margin-bottom: var(--s-1); }
  .preview-box { min-height: 8.5em; padding: var(--s-3) var(--s-4); border: 1px dashed var(--line-strong); border-radius: var(--r-2); background: var(--surface); }
  .preview-box :global(.md) { display: inline; }
  .preview-box :global(.md p:first-child) { display: inline; }
  .title-field { margin-top: var(--s-4); max-width: 520px; }
  .opts { margin-bottom: var(--s-4); }
  .opts summary { cursor: pointer; font-weight: 600; color: var(--text-2); padding: 10px 0; width: fit-content; }
  .opts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 280px)); gap: var(--s-4); }
  .actions { gap: var(--s-3); }
  .big { min-height: 48px; padding: 0 var(--s-5); font-size: var(--fs-md); }
  .examples ul { list-style: none; padding: 0; margin: 0; }
  .recent { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding-bottom: var(--s-2); }
  .recent h2 { margin: var(--s-3) var(--s-4) 0; }
  .examples ul { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--s-3); }
  .ex { display: grid; gap: 4px; width: 100%; height: 100%; text-align: left; padding: var(--s-3) var(--s-4); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); color: var(--text); cursor: pointer; font: inherit; }
  .ex:hover { border-color: var(--accent); }
  .lvl { color: var(--text-3); font-weight: 600; }
  .ex-title { font-family: var(--font-serif); font-weight: 600; }
  .ex-body { color: var(--text-2); }
</style>
