<script lang="ts">
  // « Exercices » (Apprendre, S-BE, DECISIONS D63): the list with its filters and the learner's progress, one exercise
  // (/exercices/:id), and the teacher's tools. Lean decides; a proof in words is translated first, and said so.
  import { onMount } from 'svelte';
  import { api } from '../../lib/api/client';
  import type { LibEntry } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { route, navigate } from '../../lib/router.svelte';
  import { i18n, t, LANGS, type Lang } from '../../lib/i18n/index.svelte';
  import { exercises, xt, xError, type Exercise } from '../../lib/exercises/strings';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import ExerciseView from './ExerciseView.svelte';

  let { params }: { params: Record<string, string> } = $props();
  let list = $state<Exercise[] | null>(null);
  let levels = $state<string[]>([]);
  let domains = $state<string[]>([]);
  let err = $state('');
  let level = $state('');
  let domain = $state('');
  let state_ = $state('');
  let q = $state('');
  let lang = $state<Lang>(i18n.lang);
  $effect(() => { lang = i18n.lang; });

  async function load() {
    try { const r = await exercises.list(); list = r.exercises; levels = r.levels; domains = r.domains; } catch (e) { err = xError(e); }
  }
  onMount(load);

  const pick = (x: { fr: string; mg?: string; en?: string }) => x[lang] ?? x.fr;
  const tk = (k: string) => xt(k as Parameters<typeof xt>[0]);
  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const stateOf = (e: Exercise) => (e.progress?.solved ? (e.progress.how === 'after_solution' ? 'solvedAfter' : 'solved') : e.progress?.tried ? 'tried' : 'todo');
  const shown = $derived((list ?? []).filter((e) => (!level || e.level === level) && (!domain || e.domain === domain) &&
    (!state_ || stateOf(e) === state_) && (!q.trim() || fold(`${pick(e.title)} ${pick(e.statement)}`).includes(fold(q.trim())))));
  const current = $derived(params['id'] ? list?.find((e) => e.id === params['id']) : undefined);
  const solved = $derived((list ?? []).filter((e) => e.progress?.solved).length);

  // teacher
  let chosen = $state<Record<string, boolean>>({});
  let sheetTitle = $state('');
  let withSol = $state(false);
  let withLean = $state(false);
  const ids = $derived((list ?? []).filter((e) => chosen[e.id]).map((e) => e.id));
  const sheet = (format: 'pdf' | 'tex') => exercises.sheetUrl({ ids, title: sheetTitle.trim(), lang, solutions: withSol, lean: withLean, format });
  let file = $state<HTMLInputElement>();
  async function importFile() {
    const f = file?.files?.[0];
    if (!f) return;
    try { const r = await exercises.importBank(await f.text()); toast('ok', xt('imported', { n: r.ids.length })); await load(); }
    catch (e) { toast('error', xError(e)); }
    if (file) file.value = '';
  }
  // svelte-ignore state_referenced_locally
  let teacherOpen = $state(route.query.has('dossier') || route.query.has('library'));
  let source = $state(route.query.get('library') ? 'library:' + route.query.get('library') : route.query.get('dossier') ? 'dossier:' + route.query.get('dossier') : '');
  let mk = $state({ level: 'licence', domain: 'autre', fr: '', mg: '', en: '' });
  let creating = $state(false);
  let lib = $state<LibEntry[]>([]);
  $effect(() => { if (teacherOpen) api.library().then((r) => { lib = r.entries; }, () => { /* dossiers only */ }); });
  const dossiers = $derived(Object.values(app.m.dossiers).filter((d) => !d.archived).sort((a, b) => b.updated - a.updated));
  async function make(ev: Event) {
    ev.preventDefault();
    if (creating) return;
    creating = true;
    const [kind, id] = [source.slice(0, source.indexOf(':')), source.slice(source.indexOf(':') + 1)];
    const statement: Record<string, string> = {};
    for (const l of ['fr', 'mg', 'en'] as const) if (mk[l].trim()) statement[l] = mk[l].trim();
    try {
      const r = await exercises.create({ [kind]: id, level: mk.level, domain: mk.domain, statement });
      await load();
      toast('ok', xt('created'));
      navigate(`/exercices/${r.exercise.id}`);
    } catch (e) { toast('error', xError(e)); } finally { creating = false; }
  }
  async function removed() { toast('ok', xt('removed')); navigate('/exercices'); await load(); }
</script>

<div class="page">
  {#if err}<p class="error-text" role="alert">{err}</p>
  {:else if !list}<h1>{xt('title')}</h1><p class="muted" role="status">{t('common.loading')}</p>
  {:else if params['id']}
    <p><a href="/exercices"><Icon name="chevronLeft" size={14} /> {xt('back')}</a></p>
    {#if current}
      {#key current.id}<ExerciseView ex={current} {lang} onprogress={(p) => { current.progress = p; }} onremoved={removed} />{/key}
    {:else}<h1>{xt('missing')}</h1>{/if}
  {:else}
    <h1>{xt('title')}</h1>
    <p class="lead">{xt('lead')}</p>
    <p class="small muted" role="status">{xt('progress', { n: solved, total: list.length })}</p>
    <div class="filters" role="search">
      <label>{xt('search')}<input class="input" type="search" bind:value={q} autocomplete="off" /></label>
      <label>{xt('level')}<select class="input" bind:value={level}><option value="">{xt('all')}</option>{#each levels as l}<option value={l}>{tk(`l.${l}`)}</option>{/each}</select></label>
      <label>{xt('domain')}<select class="input" bind:value={domain}><option value="">{xt('all')}</option>{#each domains as d}<option value={d}>{tk(`d.${d}`)}</option>{/each}</select></label>
      <label>{xt('state')}<select class="input" bind:value={state_}><option value="">{xt('all')}</option>{#each ['todo', 'tried', 'solved', 'solvedAfter'] as s}<option value={s}>{tk(s)}</option>{/each}</select></label>
      <label>{xt('lang')}<select class="input" bind:value={lang}>{#each LANGS as [l, name]}<option value={l} lang={l}>{name}</option>{/each}</select></label>
    </div>
    {#if !shown.length}
      <p>{xt('none')} <button class="btn small" onclick={() => { level = ''; domain = ''; state_ = ''; q = ''; }}>{xt('reset')}</button></p>
    {/if}
    <ul class="list">
      {#each shown as e (e.id)}
        {@const s = stateOf(e)}
        <li>
          {#if teacherOpen}<input class="pick" type="checkbox" bind:checked={chosen[e.id]} aria-label={xt('pick', { t: pick(e.title) })} />{/if}
          <a href={`/exercices/${e.id}`}>
            <span class="t" lang={e.title[lang] ? lang : 'fr'}><Md inline src={pick(e.title)} /></span>
            <span class="small muted">{tk(`l.${e.level}`)} · {tk(`d.${e.domain}`)}{#if e.origin !== 'seed'} · {xt(e.origin)}{/if}</span>
            <span class="small st" class:done={e.progress?.solved}>{#if e.progress?.solved}<span aria-hidden="true">✓ </span>{/if}{tk(s)}</span>
          </a>
        </li>
      {/each}
    </ul>

    <details class="teacher" bind:open={teacherOpen}>
      <summary>{xt('teacher')}</summary>
      <section aria-labelledby="x-make">
        <h2 id="x-make">{xt('make')}</h2>
        <form onsubmit={make}>
          <label>{xt('from')}
            <select class="input" bind:value={source} required>
              <option value="">{xt('choose')}</option>
              <optgroup label={xt('fromDossier')}>{#each dossiers as d (d.id)}<option value={`dossier:${d.id}`}>{d.title}</option>{/each}</optgroup>
              <optgroup label={xt('fromLibrary')}>{#each lib as l (l.name)}<option value={`library:${l.name}`}>{l.title || l.name}</option>{/each}</optgroup>
            </select></label>
          <label>{xt('level')}<select class="input" bind:value={mk.level}>{#each levels as l}<option value={l}>{tk(`l.${l}`)}</option>{/each}</select></label>
          <label>{xt('domain')}<select class="input" bind:value={mk.domain}>{#each domains as d}<option value={d}>{tk(`d.${d}`)}</option>{/each}</select></label>
          <label class="wide">{xt('stFr')}<textarea class="input" rows="3" lang="fr" bind:value={mk.fr} required></textarea></label>
          <label class="wide">{xt('stMg')}<textarea class="input" rows="2" lang="mg" bind:value={mk.mg}></textarea></label>
          <label class="wide">{xt('stEn')}<textarea class="input" rows="2" lang="en" bind:value={mk.en}></textarea></label>
          <button class="btn primary" type="submit" disabled={creating || !source || !mk.fr.trim()}>{creating ? xt('creating') : xt('create')}</button>
        </form>
      </section>
      <section aria-labelledby="x-sheet">
        <h2 id="x-sheet">{xt('sheet')}</h2>
        <p class="small muted" role="status">{xt('sheetHint', { n: ids.length })}</p>
        <label>{xt('sheetTitle')}<input class="input" bind:value={sheetTitle} maxlength="150" /></label>
        <label class="chk"><input type="checkbox" bind:checked={withSol} />{xt('withSol')}</label>
        <label class="chk"><input type="checkbox" bind:checked={withLean} />{xt('withLean')}</label>
        {#if ids.length}<p class="row"><a class="btn" href={sheet('pdf')} download>{xt('pdf')}</a> <a class="btn" href={sheet('tex')} download>{xt('tex')}</a></p>{/if}
      </section>
      <section aria-labelledby="x-bank">
        <h2 id="x-bank">{xt('bank')}</h2>
        <label>{xt('importFile')}<input class="input" type="file" accept=".json,application/json" bind:this={file} onchange={importFile} /></label>
        {#if list.some((e) => e.origin !== 'seed')}<p><a class="btn" href={exercises.exportUrl} download>{xt('exportFile')}</a></p>{/if}
      </section>
    </details>
  {/if}
</div>

<style>
  .page { max-width: 900px; margin: 0 auto; padding: var(--s-4) 16px var(--s-6, 48px); }
  .filters, form { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(170px, 100%), 1fr)); gap: 12px; margin: var(--s-3) 0; align-items: end; }
  label { display: grid; gap: 4px; font-size: var(--fs-sm); font-weight: 600; min-width: 0; }
  label .input { width: 100%; min-width: 0; min-height: var(--touch); font-weight: 400; }
  .wide { grid-column: 1 / -1; }
  .chk { display: flex; align-items: center; gap: 10px; min-height: var(--touch); }
  .list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
  .list li { display: flex; align-items: center; gap: 8px; }
  .pick { width: 22px; height: 22px; flex: none; }
  .list a { flex: 1; min-width: 0; display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; padding: 10px 14px; border: 1px solid var(--line); border-radius: var(--r-2); background: var(--surface); color: var(--text); text-decoration: none; }
  .list a:hover { background: var(--surface-2); }
  .t { font-weight: 600; grid-column: 1 / -1; overflow-wrap: anywhere; }
  .st.done { font-weight: 700; }
  .teacher { margin-top: var(--s-5, 32px); border-top: 1px solid var(--line); padding-top: 12px; }
  summary { min-height: var(--touch); display: list-item; line-height: var(--touch); font-weight: 600; cursor: pointer; }
  section h2 { font-size: var(--fs-lg, 1.1rem); margin: 16px 0 8px; }
</style>
