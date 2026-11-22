<script lang="ts" module>
  export interface MenuItem { label: string; icon?: string; run: () => void; danger?: boolean; disabled?: boolean; hint?: string }
</script>

<script lang="ts">
  // Disclosure menu (ARIA menu button pattern): arrows move, Escape closes and returns focus.
  import Icon from './Icon.svelte';
  let { label, icon = 'more', items, text = '', align = 'right' }: { label: string; icon?: string; items: MenuItem[]; text?: string; align?: 'left' | 'right' } = $props();
  let open = $state(false);
  let btn: HTMLButtonElement | undefined = $state();
  let list: HTMLUListElement | undefined = $state();
  const mid = `m-${Math.random().toString(36).slice(2, 8)}`;

  function toggle() {
    open = !open;
    if (open) queueMicrotask(() => list?.querySelector<HTMLElement>('[role=menuitem]:not([disabled])')?.focus());
  }
  function key(e: KeyboardEvent) {
    const els = [...(list?.querySelectorAll<HTMLElement>('[role=menuitem]:not([disabled])') ?? [])];
    const i = els.indexOf(document.activeElement as HTMLElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); els[(i + 1) % els.length]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); els[(i - 1 + els.length) % els.length]?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); els[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); els[els.length - 1]?.focus(); }
    else if (e.key === 'Escape' || e.key === 'Tab') { open = false; if (e.key === 'Escape') btn?.focus(); }
  }
  function pick(it: MenuItem) { open = false; btn?.focus(); it.run(); }
</script>

<svelte:window onclick={(e) => { if (open && !(e.target as Element).closest?.(`#${mid}-wrap`)) open = false; }} />
{#if open}<div class="sheet-scrim" aria-hidden="true"></div>{/if}
<div class="menu" id="{mid}-wrap">
  <button bind:this={btn} class="btn small" class:icon={!text} aria-haspopup="menu" aria-expanded={open} aria-controls={mid} aria-label={text ? undefined : label} onclick={toggle}>
    <Icon name={icon} size={16} />{#if text}<span>{text}</span>{/if}
  </button>
  {#if open}
    <ul bind:this={list} id={mid} role="menu" aria-label={label} class={align} tabindex="-1" onkeydown={key}>
      {#each items as it}
        <li role="none"><button role="menuitem" class:danger={it.danger} disabled={it.disabled} onclick={() => pick(it)}>{#if it.icon}<Icon name={it.icon} size={16} />{/if}<span>{it.label}</span>{#if it.hint}<span class="xs muted h">{it.hint}</span>{/if}</button></li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .menu { position: relative; display: inline-block; }
  ul { position: absolute; z-index: 400; top: calc(100% + 4px); min-width: 230px; margin: 0; padding: 4px; list-style: none; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); box-shadow: var(--shadow-2); }
  ul.right { right: 0; }
  ul.left { left: 0; }
  button[role='menuitem'] { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 40px; padding: 0 10px; border: 0; background: none; color: var(--text); font: inherit; font-size: var(--fs-sm); text-align: left; border-radius: var(--r-1); cursor: pointer; }
  @media (pointer: coarse) { button[role='menuitem'] { min-height: 44px; } }
  button[role='menuitem']:hover, button[role='menuitem']:focus-visible { background: var(--surface-2); outline-offset: -2px; }
  button[role='menuitem'].danger { color: var(--failed); }
  button[role='menuitem']:disabled { opacity: 0.5; cursor: not-allowed; }
  .h { margin-left: auto; }
  .sheet-scrim { display: none; }
  /* Below 768 px (phones and small tablets, i.e. wherever the bottom bar is shown — docs/UI.md §12) the menu becomes a
     bottom sheet: thumb reach, never cut off at the screen edge, never hidden by the bottom bar. Capped at 560 px and
     centred on wide phones / small tablets. */
  @media (max-width: 767px) {
    /* Clicking the scrim is an outside click: the window handler closes the menu. Above the bottom bar, which may
       sit in a higher stacking context than the toolbar holding this menu. */
    .sheet-scrim { display: block; position: fixed; inset: 0; z-index: 760; background: rgba(10, 14, 24, 0.4); }
    ul, ul.left, ul.right { position: fixed; z-index: 770; left: max(8px, calc(50% - 280px)); right: max(8px, calc(50% - 280px)); top: auto; bottom: calc(var(--bottomnav-h) + 8px + env(safe-area-inset-bottom)); min-width: 0; max-height: min(70dvh, 520px); overflow: auto; padding: 6px; border-radius: var(--r-3); }
    button[role='menuitem'] { min-height: 48px; font-size: var(--fs-md); }
    /* On-screen keyboard up (the bottom bar is hidden): the sheet sits directly on the keyboard, and fits above it. */
    /* Editor bubbles (formula preview, completions) live in other layers: hide them while a sheet is open. */
    :global(body:has(.sheet-scrim) .cm-tooltip) { visibility: hidden; }
    :global(html[data-kb='open']) ul { bottom: calc(var(--kb-inset, 0px) + 8px); max-height: min(520px, calc(var(--kb-vh, 100dvh) - 16px)); }
  }
</style>
