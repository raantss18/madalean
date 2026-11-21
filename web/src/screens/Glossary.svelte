<script lang="ts">
  // Lean glossary (S-M): one source (lib/lean/glossary.ts) for this screen, the hover help in the editors and the
  // manual. Organised by category and level, searchable, with an A–Z index; each entry: plain meaning, Lean form,
  // tiny example, related entries, Mathlib declarations (looked up on demand) and the user's dossiers that use it.
  import { GLOSSARY, GLOSS_CATS, type GlossCat, type GlossEntry, type GlossLevel } from '../lib/lean/glossary';
  import { ABBREVIATIONS } from '../lib/lean/abbrev';
  import { api } from '../lib/api/client';
  import { wb } from '../lib/api/workbench';
  import { app } from '../lib/store/app.svelte';
  import { t, tk, i18n } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import Md from '../components/Md.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  let q = $state('');
  let cat = $state<GlossCat | ''>('');
  let level = $state<GlossLevel | 0>(0);
  let open = $state<string | null>(null);
  let decl = $state<Record<string, { status: string; signature?: string; doc?: string; module?: string } | 'loading'>>({});
  let uses = $state<Record<string, { id: string; title: string; in: string }[] | 'loading' | string>>({});

  const all = Object.entries(GLOSSARY) as [string, GlossEntry][];
  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const sortKey = (k: string) => fold(k.replace(/^[^\p{L}\p{N}]+/u, '') || k);
  const initial = (k: string) => { const c = sortKey(k)[0] ?? '#'; return /[a-z]/.test(c) ? c.toUpperCase() : '#'; };

  const shown = $derived.by(() => {
    const needle = fold(q.trim());
    return all
      .filter(([k, e]) => (!cat || e.cat === cat) && (!level || e.level === level) &&
        (!needle || fold(`${k} ${e[i18n.lang]} ${e.lean ?? ''} ${(e.decls ?? []).join(' ')}`).includes(needle)))
      .sort(([a], [b]) => sortKey(a).localeCompare(sortKey(b), i18n.lang));
  });
  const groups = $derived.by(() => {
    const g = new Map<string, [string, GlossEntry][]>();
    for (const x of shown) { const l = initial(x[0]); if (!g.has(l)) g.set(l, []); g.get(l)!.push(x); }
    return [...g.entries()].sort(([a], [b]) => (a === '#' ? -1 : b === '#' ? 1 : a.localeCompare(b)));
  });
  const counts = $derived.by(() => {
    const c: Record<string, number> = {};
    for (const [, e] of all) if (!level || e.level === level) c[e.cat] = (c[e.cat] ?? 0) + 1;
    return c;
  });
  const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
  const abbr = $derived(Object.entries(ABBREVIATIONS).filter(([k, v]) => !q.trim() || k.includes(q.trim()) || v === q.trim()));

  function slug(k: string): string { return 'g-' + Array.from(k).map((c) => (/[A-Za-z0-9_-]/.test(c) ? c : c.codePointAt(0)!.toString(16))).join(''); }
  function jump(k: string) {
    if (!shown.some(([x]) => x === k)) { q = ''; cat = ''; level = 0; }
    open = k;
    queueMicrotask(() => { const el = document.getElementById(slug(k)); el?.scrollIntoView({ block: 'start' }); el?.querySelector<HTMLElement>('button.term')?.focus(); });
  }
  function toLetter(l: string) {
    const el = document.getElementById(`letter-${l}`);
    el?.scrollIntoView({ block: 'start' });
    el?.focus();
  }
  async function lookup(name: string) {
    decl[name] = 'loading';
    try {
      const r = await api.declaration(name);
      decl[name] = { status: r.status, ...(r.declaration ?? {}) };
    } catch (e) { decl[name] = { status: 'error', doc: errorText(e) }; }
  }
  async function findUses(k: string) {
    uses[k] = 'loading';
    try { uses[k] = (await wb.glossaryUses(k)).dossiers; } catch (e) { uses[k] = errorText(e); }
  }
</script>

<div class="glossary">
  <header class="intro">
    <h1>{t('glossary.title')}</h1>
    <p class="lead">{t('glossary.lead')}</p>
  </header>

  <div class="tools" role="search">
    <label class="sr-only" for="g-q">{t('glossary.search')}</label>
    <input id="g-q" class="input" type="search" placeholder={t('glossary.searchPh')} bind:value={q} autocomplete="off" />
    <label class="sr-only" for="g-cat">{t('glossary.kind')}</label>
    <select id="g-cat" class="input cat-select" bind:value={cat}>
      <option value="">{t('glossary.all')}</option>
      {#each GLOSS_CATS as c}<option value={c}>{tk(`gloss.cat.${c}`, c)}</option>{/each}
    </select>
    <div class="seg levels" role="radiogroup" aria-label={t('glossary.level')}>
      {#each [0, 1, 2, 3] as l}
        <label class:sel={level === l}><input type="radio" name="g-level" value={l} checked={level === l} onchange={() => (level = l as GlossLevel | 0)} />{l ? tk(`gloss.level.${l}`, String(l)) : t('glossary.allLevels')}</label>
      {/each}
    </div>
  </div>

  <div class="layout">
    <nav class="cats" aria-label={t('glossary.kind')}>
      <ul>
        <li><button class:sel={cat === ''} aria-pressed={cat === ''} onclick={() => (cat = '')}>{t('glossary.all')}<span class="n">{Object.values(counts).reduce((a, b) => a + b, 0)}</span></button></li>
        {#each GLOSS_CATS as c}
          <li><button class:sel={cat === c} aria-pressed={cat === c} onclick={() => (cat = c)}>{tk(`gloss.cat.${c}`, c)}<span class="n">{counts[c] ?? 0}</span></button></li>
        {/each}
      </ul>
    </nav>

    <div class="main">
      <nav class="az" aria-label={t('glossary.index')}>
        {#each letters as l}
          {@const has = groups.some(([g]) => g === l)}
          <button class="letter" disabled={!has} onclick={() => toLetter(l)} aria-label={t('glossary.jumpLetter', { l })}>{l}</button>
        {/each}
      </nav>
      <p class="count small muted" role="status" aria-live="polite">{t('glossary.count', { n: shown.length })}</p>

      {#each groups as [letter, list] (letter)}
        <section class="group" aria-labelledby="letter-{letter}">
          <h2 id="letter-{letter}" tabindex="-1" class="letter-h">{letter === '#' ? t('glossary.symbols') : letter}</h2>
          <ul class="entries">
            {#each list as [k, e] (k)}
              {@const isOpen = open === k}
              <li id={slug(k)} class="entry" class:open={isOpen}>
                <button class="term" aria-expanded={isOpen} aria-controls="{slug(k)}-body" onclick={() => (open = isOpen ? null : k)}>
                  <code class="key">{k}</code>
                  <span class="meaning"><Md inline src={e[i18n.lang]} /></span>
                  <span class="tags"><span class="chip">{tk(`gloss.cat.${e.cat}`, e.cat)}</span><span class="lvl lvl-{e.level}" title={tk(`gloss.level.${e.level}`, '')}><span class="sr-only">{tk(`gloss.level.${e.level}`, '')}</span>{#each [1, 2, 3] as d}<span class="dot" class:on={d <= e.level} aria-hidden="true"></span>{/each}</span></span>
                </button>
                {#if isOpen}
                  <div class="body" id="{slug(k)}-body">
                    <dl>
                      <div><dt>{t('glossary.meaning')}</dt><dd><Md inline src={e[i18n.lang]} /></dd></div>
                      {#if e.lean}<div><dt>{t('glossary.leanForm')}</dt><dd><code class="form">{e.lean}</code></dd></div>{/if}
                    </dl>
                    {#if e.example}
                      <p class="sub">{t('glossary.example')}</p>
                      <pre class="code">{e.example}</pre>
                    {/if}
                    {#if e.related?.length}
                      <p class="sub">{t('glossary.related')}</p>
                      <ul class="related">{#each e.related.filter((r) => GLOSSARY[r]) as r}<li><button class="btn small quiet" onclick={() => jump(r)}><code>{r}</code></button></li>{/each}</ul>
                    {/if}
                    {#if e.decls?.length}
                      <p class="sub">{t('glossary.mathlib')}</p>
                      <ul class="decls">
                        {#each e.decls as d}
                          {@const info = decl[d]}
                          <li>
                            <button class="btn small" onclick={() => lookup(d)} aria-expanded={!!info && info !== 'loading'}><code>{d}</code></button>
                            {#if info === 'loading'}<span class="xs muted" aria-busy="true">{t('common.loading')}</span>
                            {:else if info}
                              {#if info.signature}<pre class="code sig">{info.signature}</pre>{#if info.doc}<p class="small"><Md inline src={info.doc} /></p>{/if}{#if info.module}<p class="xs muted">{info.module}</p>{/if}
                              {:else}<p class="xs muted" role="status">{tk(`glossary.decl.${info.status}`, info.doc || info.status)}</p>{/if}
                            {/if}
                          </li>
                        {/each}
                      </ul>
                    {/if}
                    <div class="row uses">
                      <button class="btn small" onclick={() => findUses(k)}>{t('glossary.findUses')}</button>
                      {#if uses[k] === 'loading'}<span class="xs muted" aria-busy="true">{t('common.loading')}</span>
                      {:else if typeof uses[k] === 'string'}<span class="error-text xs" role="alert">{uses[k]}</span>
                      {:else if Array.isArray(uses[k])}
                        {@const list2 = uses[k] as { id: string; title: string; in: string }[]}
                        {#if list2.length}
                          <ul class="uses-list">{#each list2 as d (d.id)}<li><a href="/d/{encodeURIComponent(d.id)}">{app.m.dossiers[d.id]?.title ?? d.title}</a> <span class="xs muted">{tk(`glossary.in.${d.in}`, d.in)}</span></li>{/each}</ul>
                        {:else}<span class="xs muted" role="status">{t('glossary.noUses')}</span>{/if}
                      {/if}
                    </div>
                  </div>
                {/if}
              </li>
            {/each}
          </ul>
        </section>
      {:else}
        <div class="empty"><p>{t('glossary.none')}</p><button class="btn small" onclick={() => { q = ''; cat = ''; level = 0; }}>{t('glossary.reset')}</button></div>
      {/each}

      <section class="abbr-sec" aria-labelledby="abbr-h">
        <h2 id="abbr-h">{t('glossary.abbrevTitle')}</h2>
        <p class="small">{t('glossary.abbrevLead')}</p>
        <ul class="abbr">{#each abbr as [k, v] (k)}<li><kbd>\{k}</kbd> <span class="sym">{v}</span></li>{/each}</ul>
      </section>
    </div>
  </div>
</div>

<style>
  .glossary { max-width: 1120px; }
  .intro h1 { margin-bottom: var(--s-1); }
  .lead { color: var(--text-2); max-width: var(--measure); margin-top: 0; }
  .tools { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; position: sticky; top: 0; z-index: 2;
    background: var(--bg); padding: var(--s-2) 0; }
  .tools input[type='search'] { flex: 1 1 18rem; max-width: 28rem; }
  .cat-select { width: auto; display: none; }
  .levels { display: inline-flex; border: 1px solid var(--line-strong); border-radius: var(--r-2); overflow: hidden; }
  .levels label { padding: 6px 12px; cursor: pointer; font-size: var(--fs-sm); min-height: 36px; display: flex; align-items: center; }
  .levels label + label { border-left: 1px solid var(--line); }
  .levels label.sel { background: var(--ink); color: var(--on-ink); }
  .levels input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .levels label:has(input:focus-visible) { outline: 2px solid var(--focus); outline-offset: -2px; }
  .layout { display: grid; grid-template-columns: 13rem minmax(0, 1fr); gap: var(--s-5); align-items: start; }
  .cats { position: sticky; top: 64px; }
  .cats ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
  .cats button { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: var(--s-2);
    min-height: 36px; padding: 4px 10px; border: 0; border-left: 3px solid transparent; background: none; color: var(--text);
    font: inherit; font-size: var(--fs-sm); text-align: left; cursor: pointer; border-radius: 0 var(--r-1) var(--r-1) 0; }
  .cats button:hover { background: var(--surface-2); }
  .cats button.sel { border-left-color: var(--laterite); background: var(--surface); font-weight: 600; }
  .cats .n { color: var(--text-3); font-variant-numeric: tabular-nums; font-size: var(--fs-xs); }
  .az { display: flex; flex-wrap: wrap; gap: 2px; margin-bottom: var(--s-2); }
  .letter { width: 30px; height: 30px; border: 1px solid var(--line); background: var(--surface); color: var(--text);
    border-radius: var(--r-1); font: 600 var(--fs-xs)/1 var(--font-ui); cursor: pointer; }
  .letter:disabled { color: var(--text-3); background: transparent; border-color: transparent; cursor: default; }
  .letter:not(:disabled):hover { border-color: var(--accent); color: var(--accent); }
  .count { margin: 0 0 var(--s-2); }
  .group { margin-bottom: var(--s-4); }
  .letter-h { font-family: var(--font-serif); font-size: var(--fs-xl); color: var(--laterite); margin: var(--s-3) 0 var(--s-1);
    border-bottom: 1px solid var(--line); padding-bottom: 2px; scroll-margin-top: 64px; }
  .entries { list-style: none; margin: 0; padding: 0; }
  .entry { border-bottom: 1px solid var(--line); scroll-margin-top: 64px; }
  .entry.open { background: var(--surface); border-radius: var(--r-2); border-bottom-color: transparent; box-shadow: var(--shadow-1); margin: var(--s-1) 0; }
  .term { width: 100%; display: grid; grid-template-columns: minmax(7rem, 12rem) minmax(0, 1fr) auto; gap: var(--s-3); align-items: baseline;
    text-align: left; background: none; border: 0; color: var(--text); font: inherit; padding: var(--s-2) var(--s-2); cursor: pointer; min-height: var(--touch); }
  .term:hover .key { color: var(--accent); }
  .key { font-family: var(--font-mono); font-size: 0.95rem; font-weight: 600; overflow-wrap: anywhere; background: none; }
  .meaning { color: var(--text-2); font-size: var(--fs-sm); }
  .entry:not(.open) .meaning { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .tags { display: flex; gap: var(--s-2); align-items: center; white-space: nowrap; }
  .lvl { display: inline-flex; gap: 3px; }
  .dot { width: 7px; height: 7px; border-radius: 50%; border: 1px solid var(--line-strong); }
  .dot.on { background: var(--ink); border-color: var(--ink); }
  .body { padding: 0 var(--s-3) var(--s-3); }
  .body dl { margin: 0; display: grid; gap: var(--s-2); }
  .body dt { font-size: var(--fs-xs); color: var(--text-3); font-weight: 600; }
  .body dd { margin: 2px 0 0; }
  .form { font-family: var(--font-mono); background: var(--surface-2); padding: 2px 6px; border-radius: var(--r-1); white-space: pre-wrap; }
  .sub { font-size: var(--fs-xs); color: var(--text-3); font-weight: 600; margin: var(--s-3) 0 var(--s-1); }
  .code { font: 0.8125rem/1.5 var(--font-mono); background: var(--surface-2); padding: var(--s-2) var(--s-3); border-radius: var(--r-2);
    white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; border-left: 3px solid var(--local); }
  .sig { border-left-color: var(--accent); margin-top: var(--s-1); }
  .related, .decls, .uses-list { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: var(--s-1); }
  .decls { display: grid; }
  .uses { margin-top: var(--s-3); flex-wrap: wrap; }
  .empty { padding: var(--s-5) 0; }
  .abbr-sec { margin-top: var(--s-6); }
  .abbr { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 6px; }
  .sym { font-family: var(--font-mono); font-size: 1.1rem; }
  @media (max-width: 899px) {
    .layout { grid-template-columns: minmax(0, 1fr); }
    .cats { display: none; }
    .cat-select { display: block; }
  }
  @media (max-width: 599px) {
    .term { grid-template-columns: minmax(0, 1fr); gap: 2px; }
    .tags { order: -1; }
    .tools input[type='search'] { flex-basis: 100%; max-width: none; }
    .letter { width: 32px; height: 32px; }
  }
</style>
