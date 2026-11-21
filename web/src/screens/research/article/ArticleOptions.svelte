<script lang="ts">
  // « Options avancées » of the article (side drawer): class/template, packages (with their state in Madalean's TeX),
  // macros, theorem environments, bibliography, layout — saved in madalean.toml — and the per-device personalisation.
  import { articleApi, type TexSettings, type Packages, type TexFile, type ThmEnv } from '../../../lib/api/article';
  import { aprefs, setAPref, resetAPrefs, type ArticlePrefs } from '../../../lib/article/prefs.svelte';
  import { t, tk, i18n } from '../../../lib/i18n/index.svelte';
  import { toast } from '../../../lib/ui/toasts.svelte';
  import { errorText } from '../../../lib/ui/errors';
  import Icon from '../../../components/Icon.svelte';

  let { pid, open = $bindable(false), tab = $bindable('document'), settings, templates, fonts, macro = '', onsettings, onprefs, beforeChange }: {
    pid: string; open?: boolean; tab?: string; settings: TexSettings; templates: { id: string; fr: string; en: string; class: string }[];
    fonts: string[]; macro?: string; onsettings: (s: TexSettings, files: TexFile[]) => void; onprefs: (k: keyof ArticlePrefs) => void;
    beforeChange: () => Promise<void>;
  } = $props();

  let el: HTMLDialogElement | undefined = $state();
  let opener: Element | null = null;
  let pk = $state<Packages | null>(null);
  let newPkg = $state('');
  let newMacro = $state({ name: '', body: '' });
  let confirmTpl = $state('');
  let busy = $state(false);
  const TABS = ['document', 'packages', 'macros', 'theorems', 'bibliography', 'layout', 'personal'] as const;

  $effect(() => {
    if (!el) return;
    if (open && !el.open) { opener = document.activeElement; el.showModal(); queueMicrotask(() => el?.querySelector<HTMLElement>(`#ao-tab-${tab}`)?.focus()); }
    else if (!open && el.open) el.close();
  });
  $effect(() => { if (open && tab === 'packages') void loadPk(); });
  $effect(() => { if (open && macro) { newMacro = { name: macro, body: '' }; } });
  function closed() { open = false; if (opener instanceof HTMLElement) opener.focus(); }

  async function loadPk() { try { pk = await articleApi.packages(pid); } catch (e) { toast('error', errorText(e)); } }
  async function patch(p: Parameters<typeof articleApi.settings>[1]) {
    busy = true;
    try { await beforeChange(); const r = await articleApi.settings(pid, p); onsettings(r.settings, r.files); toast('ok', t('ae.opt.saved')); if (tab === 'packages') void loadPk(); }
    catch (e) { toast('error', errorText(e)); }
    finally { busy = false; }
  }
  async function useTemplate(id: string) {
    busy = true;
    try { await beforeChange(); const r = await articleApi.template(pid, id); onsettings(r.settings, r.files); confirmTpl = ''; toast('ok', t('ae.opt.templateDone')); }
    catch (e) { toast('error', errorText(e)); }
    finally { busy = false; }
  }
  function tabKey(e: KeyboardEvent) {
    const i = TABS.indexOf(tab as typeof TABS[number]);
    let j = -1;
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') j = (i + 1) % TABS.length;
    else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') j = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === 'Home') j = 0; else if (e.key === 'End') j = TABS.length - 1;
    if (j >= 0) { e.preventDefault(); tab = TABS[j]!; queueMicrotask(() => el?.querySelector<HTMLElement>(`#ao-tab-${tab}`)?.focus()); }
  }
  const allPkgs = $derived([...settings.packages.base, ...settings.packages.extra]);
  function togglePkg(name: string, on: boolean) {
    const removed = on ? settings.packages.removed.filter((x) => x !== name) : [...new Set([...settings.packages.removed, name])];
    void patch({ packages: { ...settings.packages, removed } });
  }
  function addPkg(e: Event) {
    e.preventDefault();
    const n = newPkg.trim();
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,60}$/.test(n)) { toast('error', t('ae.opt.badPkg')); return; }
    newPkg = '';
    void patch({ packages: { ...settings.packages, extra: [...new Set([...settings.packages.extra, n])], removed: settings.packages.removed.filter((x) => x !== n) } });
  }
  function addMacro(e: Event) {
    e.preventDefault();
    const n = newMacro.name.replace(/^\\/, '').trim();
    if (!/^[A-Za-z]{1,30}$/.test(n) || !newMacro.body.trim()) { toast('error', t('ae.opt.badMacro')); return; }
    const m = { ...settings.macros, [n]: newMacro.body.trim() };
    newMacro = { name: '', body: '' };
    void patch({ macros: m });
  }
  function delMacro(n: string) { const m = { ...settings.macros }; delete m[n]; void patch({ macros: m }); }
  function setEnv(i: number, p: Partial<ThmEnv>) {
    const envs = settings.theorems.envs.map((e, k) => (k === i ? { ...e, ...p } : e));
    void patch({ theorems: { ...settings.theorems, envs } });
  }
  function delEnv(i: number) { void patch({ theorems: { ...settings.theorems, envs: settings.theorems.envs.filter((_e, k) => k !== i) } }); }
  let newEnv = $state('');
  function addEnv(e: Event) {
    e.preventDefault();
    const n = newEnv.trim().toLowerCase();
    if (!/^[a-z]{1,20}$/.test(n)) { toast('error', t('ae.opt.badEnv')); return; }
    const title = n.charAt(0).toUpperCase() + n.slice(1);
    newEnv = '';
    void patch({ theorems: { ...settings.theorems, envs: [...settings.theorems.envs, { env: n, fr: title, en: title, style: 'plain', counter: 'theorem' }] } });
  }
  function pref<K extends keyof ArticlePrefs>(k: K, v: ArticlePrefs[K]) { setAPref(k, v); onprefs(k); }
  const stateLabel = (s: string) => tk(`ae.pkg.${s}`, s);
</script>

<dialog bind:this={el} class="drawer" aria-labelledby="ao-title" onclose={closed} onclick={(e) => { if (e.target === el) open = false; }}>
  {#if open}
    <div class="wrap">
      <header class="row">
        <h2 id="ao-title">{t('ae.opt.title')}</h2>
        <span class="spacer"></span>
        <button class="btn quiet icon" onclick={() => (open = false)} aria-label={t('common.close')}><Icon name="x" /></button>
      </header>
      <div class="cols">
        <div class="tabs" role="tablist" aria-orientation="vertical" aria-label={t('ae.opt.title')} tabindex="-1" onkeydown={tabKey}>
          {#each TABS as k}
            <button role="tab" id="ao-tab-{k}" aria-selected={tab === k} aria-controls="ao-panel" tabindex={tab === k ? 0 : -1} onclick={() => (tab = k)}>{tk(`ae.opt.tab.${k}`, k)}</button>
          {/each}
        </div>
        <div class="panel" id="ao-panel" role="tabpanel" aria-labelledby="ao-tab-{tab}" aria-busy={busy}>
          {#if tab === 'document'}
            <h3>{t('ae.opt.templates')}</h3>
            <ul class="tpls">
              {#each templates as tp (tp.id)}
                <li class:cur={settings.document.template === tp.id}>
                  <div class="tpl-name">{i18n.lang === 'fr' ? tp.fr : tp.en}</div>
                  <code class="xs">\documentclass{'{'}{tp.class}{'}'}</code>
                  {#if settings.document.template === tp.id}<span class="chip proved">{t('ae.opt.current')}</span>
                  {:else if confirmTpl === tp.id}
                    <span class="row"><button class="btn small primary" onclick={() => useTemplate(tp.id)}>{t('ae.opt.templateConfirm')}</button><button class="btn small quiet" onclick={() => (confirmTpl = '')}>{t('common.cancel')}</button></span>
                  {:else}<button class="btn small" onclick={() => (confirmTpl = tp.id)}>{t('ae.opt.use')}</button>{/if}
                </li>
              {/each}
            </ul>
            {#if confirmTpl}<p class="xs muted">{t('ae.opt.templateNote')}</p>{/if}
            <div class="field">
              <label for="ao-lang">{t('ae.opt.language')}</label>
              <select id="ao-lang" class="input" value={settings.document.language} onchange={(e) => patch({ document: { ...settings.document, language: (e.target as HTMLSelectElement).value as 'fr' } })}>
                <option value="fr">Français (babel french)</option><option value="en">English (babel english)</option>
              </select>
            </div>
            <div class="field">
              <label for="ao-opts">{t('ae.opt.classOptions')}</label>
              <input id="ao-opts" class="input" value={settings.document.options.join(', ')} aria-describedby="ao-opts-h"
                onchange={(e) => patch({ document: { ...settings.document, options: (e.target as HTMLInputElement).value.split(',').map((x) => x.trim()).filter(Boolean) } })} />
              <p class="xs muted" id="ao-opts-h">{t('ae.opt.classOptionsHint')}</p>
            </div>
          {:else if tab === 'packages'}
            <p class="xs muted">{t('ae.opt.pkgLead')}</p>
            <ul class="pkgs">
              {#each allPkgs as p}
                <li><label class="switch small"><input type="checkbox" checked={!settings.packages.removed.includes(p)} onchange={(e) => togglePkg(p, (e.target as HTMLInputElement).checked)} />{p}</label>
                  {#if pk}{@const st = pk.packages.find((x) => x.name === p)?.state}{#if st}<span class="chip st-{st}">{stateLabel(st)}</span>{/if}{/if}</li>
              {/each}
            </ul>
            <form class="row" onsubmit={addPkg}>
              <label class="sr-only" for="ao-pkg">{t('ae.opt.addPkg')}</label>
              <input id="ao-pkg" class="input" bind:value={newPkg} placeholder="tikz, siunitx…" style="max-width: 220px" />
              <button class="btn small">{t('ae.opt.addPkg')}</button>
            </form>
            {#if pk}
              {#if pk.needed.length}<h3>{t('ae.opt.needed')}</h3><ul class="plain">{#each pk.needed as n}<li><code>{n.why}</code> → <strong>{n.name}</strong> <span class="chip st-{n.state}">{stateLabel(n.state)}</span> <button class="btn small" onclick={() => patch({ packages: { ...settings.packages, extra: [...new Set([...settings.packages.extra, n.name])] } })}>{t('ae.opt.add')}</button></li>{/each}</ul>{/if}
              {#if pk.redundant.length}<h3>{t('ae.opt.redundant')}</h3><ul class="plain">{#each pk.redundant as r}<li><strong>{r.name}</strong> — {r.reason === 'twice' ? t('ae.opt.twice') : r.reason === 'order' ? t('ae.opt.order') : t('ae.opt.impliedBy', { by: r.reason.split(':').pop() ?? '' })}</li>{/each}</ul>{/if}
              <h3>{t('ae.opt.inProject')}</h3>
              <ul class="plain small">{#each pk.packages as p}<li><code>{p.file}</code> <span class="chip st-{p.state}">{stateLabel(p.state)}</span></li>{/each}</ul>
              <p class="xs muted">{pk.engine === 'tectonic' ? t('ae.opt.engineTectonic', { digest: pk.digest.slice(0, 12) }) : pk.engine === 'system' ? t('ae.opt.engineSystem') : t('ae.opt.engineNone')}</p>
            {/if}
          {:else if tab === 'macros'}
            <p class="xs muted">{t('ae.opt.macrosLead')}</p>
            <table class="tbl">
              <thead><tr><th scope="col">{t('ae.opt.macroName')}</th><th scope="col">{t('ae.opt.macroBody')}</th><th scope="col"><span class="sr-only">{t('ae.opt.actions')}</span></th></tr></thead>
              <tbody>{#each Object.entries(settings.macros) as [n, b] (n)}<tr><td><code>\{n}</code></td><td><code>{b}</code></td><td><button class="btn quiet icon small" onclick={() => delMacro(n)} aria-label={t('ae.opt.delMacro', { name: n })}><Icon name="trash" size={14} /></button></td></tr>{/each}</tbody>
            </table>
            <form class="row" onsubmit={addMacro}>
              <label class="sr-only" for="ao-mn">{t('ae.opt.macroName')}</label><input id="ao-mn" class="input" bind:value={newMacro.name} placeholder="\eps" style="max-width: 120px" />
              <label class="sr-only" for="ao-mb">{t('ae.opt.macroBody')}</label><input id="ao-mb" class="input" bind:value={newMacro.body} placeholder={'\\varepsilon'} style="max-width: 220px" />
              <button class="btn small">{t('ae.opt.add')}</button>
            </form>
          {:else if tab === 'theorems'}
            <div class="field">
              <label for="ao-num">{t('ae.opt.numbering')}</label>
              <select id="ao-num" class="input" value={settings.theorems.numbering} onchange={(e) => patch({ theorems: { ...settings.theorems, numbering: (e.target as HTMLSelectElement).value as 'section' } })}>
                <option value="section">{t('ae.opt.numSection')}</option><option value="global">{t('ae.opt.numGlobal')}</option><option value="none">{t('ae.opt.numNone')}</option>
              </select>
            </div>
            <table class="tbl">
              <thead><tr><th scope="col">{t('ae.opt.env')}</th><th scope="col">{t('ae.opt.titleFr')}</th><th scope="col">{t('ae.opt.titleEn')}</th><th scope="col">{t('ae.opt.style')}</th><th scope="col"><span class="sr-only">{t('ae.opt.actions')}</span></th></tr></thead>
              <tbody>
                {#each settings.theorems.envs as e, i (e.env)}
                  <tr>
                    <td><code>{e.env}</code></td>
                    <td><input class="input" aria-label={t('ae.opt.titleFrOf', { env: e.env })} value={e.fr} onchange={(x) => setEnv(i, { fr: (x.target as HTMLInputElement).value })} /></td>
                    <td><input class="input" aria-label={t('ae.opt.titleEnOf', { env: e.env })} value={e.en} onchange={(x) => setEnv(i, { en: (x.target as HTMLInputElement).value })} /></td>
                    <td><select class="input" aria-label={t('ae.opt.styleOf', { env: e.env })} value={e.style} onchange={(x) => setEnv(i, { style: (x.target as HTMLSelectElement).value as 'plain' })}>
                      <option value="plain">{t('ae.opt.stylePlain')}</option><option value="definition">{t('ae.opt.styleDefinition')}</option><option value="remark">{t('ae.opt.styleRemark')}</option></select></td>
                    <td><button class="btn quiet icon small" onclick={() => delEnv(i)} aria-label={t('ae.opt.delEnv', { env: e.env })}><Icon name="trash" size={14} /></button></td>
                  </tr>
                {/each}
              </tbody>
            </table>
            <form class="row" onsubmit={addEnv}>
              <label class="sr-only" for="ao-env">{t('ae.opt.env')}</label><input id="ao-env" class="input" bind:value={newEnv} placeholder="hypothesis" style="max-width: 200px" />
              <button class="btn small">{t('ae.opt.add')}</button>
            </form>
          {:else if tab === 'bibliography'}
            <div class="field">
              <label for="ao-bst">{t('ae.opt.bibStyle')}</label>
              <select id="ao-bst" class="input" value={settings.bibliography.style} onchange={(e) => patch({ bibliography: { style: (e.target as HTMLSelectElement).value } })}>
                {#each ['amsalpha', 'amsplain', 'alpha', 'plain', 'abbrv', 'unsrt', 'elsarticle-num', 'elsarticle-harv'] as s}<option value={s}>{s}</option>{/each}
              </select>
              <p class="xs muted">{t('ae.opt.bibLead')}</p>
            </div>
            <label class="switch"><input type="checkbox" checked={settings.madalean.verification_table} onchange={(e) => patch({ madalean: { ...settings.madalean, verification_table: (e.target as HTMLInputElement).checked } })} />{t('ae.opt.verifTable')}</label>
            <label class="switch"><input type="checkbox" checked={settings.madalean.lean_appendix} onchange={(e) => patch({ madalean: { ...settings.madalean, lean_appendix: (e.target as HTMLInputElement).checked } })} />{t('ae.opt.leanAppendix')}</label>
          {:else if tab === 'layout'}
            <div class="grid2">
              <div class="field"><label for="ao-paper">{t('ae.opt.paper')}</label>
                <select id="ao-paper" class="input" value={settings.layout.paper} onchange={(e) => patch({ layout: { ...settings.layout, paper: (e.target as HTMLSelectElement).value as 'a4' } })}><option value="a4">A4</option><option value="letter">US Letter</option></select></div>
              <div class="field"><label for="ao-margin">{t('ae.opt.margin')}</label>
                <select id="ao-margin" class="input" value={settings.layout.margin} onchange={(e) => patch({ layout: { ...settings.layout, margin: (e.target as HTMLSelectElement).value } })}>{#each ['2cm', '2.5cm', '3cm', '3.5cm', '1in'] as m}<option value={m}>{m}</option>{/each}</select></div>
              <div class="field"><label for="ao-font">{t('ae.opt.font')}</label>
                <select id="ao-font" class="input" value={settings.layout.font} onchange={(e) => patch({ layout: { ...settings.layout, font: (e.target as HTMLSelectElement).value } })}>{#each fonts as f}<option value={f}>{tk(`ae.font.${f}`, f)}</option>{/each}</select></div>
              <div class="field"><label for="ao-ls">{t('ae.opt.linespread')}</label>
                <select id="ao-ls" class="input" value={String(settings.layout.linespread)} onchange={(e) => patch({ layout: { ...settings.layout, linespread: Number((e.target as HTMLSelectElement).value) } })}>{#each ['1', '1.1', '1.25', '1.5', '2'] as l}<option value={l}>{l}</option>{/each}</select></div>
            </div>
            <p class="xs muted">{t('ae.opt.fontNote')}</p>
          {:else}
            <p class="xs muted">{t('ae.opt.personalLead')}</p>
            <div class="grid2">
              <div class="field"><label for="ap-size">{t('ae.p.size')}</label>
                <select id="ap-size" class="input" value={String(aprefs.fontSize)} onchange={(e) => pref('fontSize', Number((e.target as HTMLSelectElement).value))}>{#each [90, 100, 112, 125, 140] as s}<option value={String(s)}>{s} %</option>{/each}</select></div>
              <div class="field"><label for="ap-width">{t('ae.p.width')}</label>
                <select id="ap-width" class="input" value={aprefs.width} onchange={(e) => pref('width', (e.target as HTMLSelectElement).value as 'normal')}><option value="narrow">{t('ae.p.narrow')}</option><option value="normal">{t('ae.p.normal')}</option><option value="wide">{t('ae.p.wide')}</option></select></div>
              <div class="field"><label for="ap-paper">{t('ae.p.look')}</label>
                <select id="ap-paper" class="input" value={aprefs.paper} onchange={(e) => pref('paper', (e.target as HTMLSelectElement).value as 'paper')}><option value="paper">{t('ae.p.paper')}</option><option value="plain">{t('ae.p.plain')}</option></select></div>
              <div class="field"><label for="ap-keys">{t('ae.p.keys')}</label>
                <select id="ap-keys" class="input" value={aprefs.keymap} onchange={(e) => pref('keymap', (e.target as HTMLSelectElement).value as 'default')}><option value="default">{t('ae.p.keysDefault')}</option><option value="vim">Vim</option><option value="emacs">Emacs</option></select></div>
              <div class="field"><label for="ap-auto">{t('ae.p.autosave')}</label>
                <select id="ap-auto" class="input" value={String(aprefs.autosave)} onchange={(e) => pref('autosave', Number((e.target as HTMLSelectElement).value))}>{#each [500, 1500, 3000, 10000] as s}<option value={String(s)}>{s / 1000} s</option>{/each}</select></div>
              <div class="field"><label for="ap-prev">{t('ae.p.preview')}</label>
                <select id="ap-prev" class="input" value={aprefs.preview} onchange={(e) => pref('preview', (e.target as HTMLSelectElement).value as 'right')}><option value="right">{t('ae.p.right')}</option><option value="below">{t('ae.p.below')}</option><option value="off">{t('ae.p.off')}</option></select></div>
            </div>
            <label class="switch"><input type="checkbox" checked={aprefs.autoCompile} onchange={(e) => pref('autoCompile', (e.target as HTMLInputElement).checked)} />{t('ae.p.autoCompile')}</label>
            <label class="switch"><input type="checkbox" checked={aprefs.lineNumbers} onchange={(e) => pref('lineNumbers', (e.target as HTMLInputElement).checked)} />{t('ae.p.lineNumbers')}</label>
            <p><button class="btn small quiet" onclick={() => { resetAPrefs(); for (const k of ['keymap', 'lineNumbers'] as const) onprefs(k); }}>{t('ae.p.reset')}</button></p>
            <p class="xs muted">{t('ae.p.where')}</p>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</dialog>

<style>
  .drawer { margin: 0 0 0 auto; height: 100dvh; max-height: 100dvh; width: min(720px, 100vw); border: 0; padding: 0; background: var(--surface); color: var(--text); box-shadow: var(--shadow-2); }
  .drawer::backdrop { background: rgba(10, 14, 24, 0.35); }
  .wrap { display: flex; flex-direction: column; height: 100%; }
  header { padding: var(--s-3) var(--s-4); border-bottom: 1px solid var(--line); }
  h2 { margin: 0; font-size: var(--fs-lg); }
  h3 { font-size: var(--fs-sm); margin: var(--s-4) 0 var(--s-2); }
  .cols { display: grid; grid-template-columns: 170px 1fr; flex: 1; min-height: 0; }
  .tabs { display: flex; flex-direction: column; border-right: 1px solid var(--line); padding: var(--s-2); gap: 2px; }
  .tabs button { text-align: left; background: none; border: none; padding: 8px 10px; border-radius: var(--r-1); color: var(--text-2); font: 600 var(--fs-sm) var(--font-ui); cursor: pointer; min-height: 36px; }
  .tabs button[aria-selected='true'] { background: var(--accent-soft); color: var(--text); box-shadow: inset 2px 0 0 var(--accent); }
  .tabs button:focus-visible { outline: 2px solid var(--focus); }
  .panel { padding: var(--s-3) var(--s-4) var(--s-6); overflow-y: auto; }
  .tpls { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--s-2); }
  .tpls li { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); display: grid; gap: 6px; align-content: start; }
  .tpls li.cur { border-color: var(--proved); }
  .tpl-name { font: 600 var(--fs-sm) var(--font-serif); }
  .pkgs { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 4px var(--s-3); }
  .pkgs li { display: flex; gap: 6px; align-items: center; }
  .plain { list-style: none; padding: 0; display: grid; gap: 4px; font-size: var(--fs-sm); }
  .plain.small { font-size: var(--fs-xs); grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
  .chip.st-cached, .chip.st-system { color: var(--proved); background: var(--proved-soft); }
  .chip.st-bundle { color: var(--running); background: var(--running-soft); }
  .chip.st-missing { color: var(--failed); background: var(--failed-soft); }
  .tbl { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); margin-bottom: var(--s-2); }
  .tbl th { text-align: left; font-size: var(--fs-xs); color: var(--text-2); padding: 4px; }
  .tbl td { padding: 3px 4px; border-top: 1px solid var(--line); }
  .tbl .input { min-height: 32px; padding: 0 6px; }
  .grid2 { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0 var(--s-3); }
  @media (max-width: 640px) { .cols { grid-template-columns: 1fr; } .tabs { flex-direction: row; overflow-x: auto; border-right: none; border-bottom: 1px solid var(--line); } }
</style>
