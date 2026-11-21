<script lang="ts">
  // Command palette (Ctrl/⌘+K): jump to any dossier or screen, run global actions. ARIA combobox + listbox.
  import { app } from '../lib/store/app.svelte';
  import { navigate, routes } from '../lib/router.svelte';
  import { t, i18n } from '../lib/i18n/index.svelte';
  import { prefs, setMode, setTheme } from '../lib/prefs.svelte';
  import { api } from '../lib/api/client';
  import { phaseOf } from '../lib/status';
  import StatusMark from './StatusMark.svelte';
  import type { Phase } from '../lib/status';

  let { open = $bindable(false) }: { open?: boolean } = $props();
  let q = $state('');
  let sel = $state(0);
  let input: HTMLInputElement | undefined = $state();
  let dlg: HTMLDialogElement | undefined = $state();
  let opener: Element | null = null;

  interface Cmd { id: string; label: string; hint?: string; phase?: Phase; run: () => void }
  const commands = $derived.by<Cmd[]>(() => {
    const list: Cmd[] = [
      { id: 'new', label: t('cmd.new'), hint: 'N', run: () => navigate('/') },
      ...routes.filter((r) => r.nav).sort((a, b) => a.nav!.order - b.nav!.order).map((r) => ({
        id: `go-${r.name}`, label: t('cmd.goto', { name: t(r.nav!.label) }), run: () => navigate(r.pattern.replace(/\/:[^/]+\??/g, '')),
      })),
      { id: 'mode', label: prefs.mode === 'learn' ? t('cmd.toResearch') : t('cmd.toLearn'), run: () => setMode(prefs.mode === 'learn' ? 'research' : 'learn') },
      { id: 'theme', label: t('cmd.theme'), run: () => setTheme(document.documentElement.dataset['theme'] === 'dark' || (prefs.theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches) ? 'light' : 'dark') },
      { id: 'lang', label: i18n.lang === 'fr' ? 'Switch to English' : 'Passer en français', run: () => void api.patchSettings({ language: i18n.lang === 'fr' ? 'en' : 'fr' }).then((r) => i18n.set(r.settings.language)).catch(() => i18n.set(i18n.lang === 'fr' ? 'en' : 'fr')) },
    ];
    for (const d of Object.values(app.m.dossiers).sort((a, b) => b.updated - a.updated)) {
      list.push({ id: `d-${d.id}`, label: d.title || d.theorem, hint: d.theorem, phase: phaseOf(d.status, app.activeJob(d.id)), run: () => navigate(`/d/${encodeURIComponent(d.id)}`) });
    }
    return list;
  });
  const results = $derived.by(() => {
    const s = q.trim().toLowerCase();
    if (!s) return commands.slice(0, 30);
    const words = s.split(/\s+/);
    return commands.filter((c) => words.every((w) => (c.label + ' ' + (c.hint ?? '')).toLowerCase().includes(w))).slice(0, 30);
  });

  $effect(() => {
    if (!dlg) return;
    if (open && !dlg.open) { opener = document.activeElement; q = ''; sel = 0; dlg.showModal(); queueMicrotask(() => input?.focus()); }
    else if (!open && dlg.open) dlg.close();
  });
  function run(c: Cmd | undefined) {
    if (!c) return;
    open = false;
    c.run();
  }
  function key(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(results.length - 1, sel + 1); scroll(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); scroll(); }
    else if (e.key === 'Enter') { e.preventDefault(); run(results[sel]); }
  }
  function scroll() { queueMicrotask(() => document.getElementById(`cp-${sel}`)?.scrollIntoView({ block: 'nearest' })); }
</script>

<dialog bind:this={dlg} class="palette" aria-label={t('cmd.title')} onclose={() => { open = false; if (opener instanceof HTMLElement) opener.focus(); }} onclick={(e) => { if (e.target === dlg) open = false; }}>
  {#if open}
    <input bind:this={input} class="q" type="text" role="combobox" aria-expanded="true" aria-controls="cp-list" aria-autocomplete="list"
      aria-activedescendant={results.length ? `cp-${sel}` : undefined} aria-label={t('cmd.title')} placeholder={t('cmd.placeholder')}
      bind:value={q} oninput={() => (sel = 0)} onkeydown={key} autocomplete="off" spellcheck="false" />
    <ul id="cp-list" role="listbox" aria-label={t('cmd.results')}>
      {#each results as c, i (c.id)}
        <li id="cp-{i}" role="option" aria-selected={i === sel} class:sel={i === sel} onclick={() => run(c)} onmousemove={() => (sel = i)} onkeydown={() => {}}>
          {#if c.phase}<StatusMark phase={c.phase} />{/if}
          <span class="lbl">{c.label}</span>
          {#if c.hint}<span class="hint mono xs">{c.hint}</span>{/if}
        </li>
      {:else}
        <li class="none muted">{t('cmd.none')}</li>
      {/each}
    </ul>
    <p class="keys xs muted"><kbd>↑</kbd><kbd>↓</kbd> {t('cmd.keysMove')} · <kbd>Entrée</kbd> {t('cmd.keysOpen')} · <kbd>Échap</kbd> {t('cmd.keysClose')}</p>
  {/if}
</dialog>

<style>
  .palette { border: 0; padding: 0; width: min(620px, calc(100vw - 24px)); margin-top: 12vh; border-radius: var(--r-3); background: var(--surface); color: var(--text); box-shadow: var(--shadow-2); }
  .palette::backdrop { background: rgba(10, 14, 24, 0.4); }
  .q { width: 100%; border: 0; border-bottom: 1px solid var(--line); padding: var(--s-4); font: 400 var(--fs-lg) var(--font-ui); background: transparent; color: var(--text); }
  .q:focus-visible { outline: none; box-shadow: inset 0 -2px 0 var(--focus); }
  ul { list-style: none; margin: 0; padding: var(--s-2); max-height: 50vh; overflow: auto; }
  li { display: flex; align-items: center; gap: var(--s-2); min-height: 40px; padding: 0 var(--s-3); border-radius: var(--r-2); cursor: pointer; }
  li.sel { background: var(--accent-soft); }
  .lbl { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hint { color: var(--text-3); max-width: 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .none { cursor: default; }
  .keys { padding: var(--s-2) var(--s-4); border-top: 1px solid var(--line); margin: 0; }
</style>
