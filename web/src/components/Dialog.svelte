<script lang="ts">
  // Native <dialog> (showModal): focus trap, Escape, inert background — returns focus to the opener.
  import type { Snippet } from 'svelte';
  import { t } from '../lib/i18n/index.svelte';
  import Icon from './Icon.svelte';
  let {
    open = $bindable(false), title, children, actions, wide = false, onclose,
  }: { open?: boolean; title: string; children: Snippet; actions?: Snippet; wide?: boolean; onclose?: () => void } = $props();
  let el: HTMLDialogElement | undefined = $state();
  let opener: Element | null = null;
  const id = `dlg-${Math.random().toString(36).slice(2, 8)}`;
  $effect(() => {
    if (!el) return;
    if (open && !el.open) { opener = document.activeElement; el.showModal(); }
    else if (!open && el.open) el.close();
  });
  function closed() {
    open = false;
    onclose?.();
    if (opener instanceof HTMLElement) opener.focus();
  }
</script>

<dialog bind:this={el} class:wide aria-labelledby={id} onclose={closed} onclick={(e) => { if (e.target === el) open = false; }}>
  {#if open}
    <div class="dlg">
      <header>
        <h2 id={id}>{title}</h2>
        <button class="btn quiet icon" onclick={() => (open = false)} aria-label={t('common.close')}><Icon name="x" /></button>
      </header>
      <div class="body">{@render children()}</div>
      {#if actions}<footer class="row">{@render actions()}</footer>{/if}
    </div>
  {/if}
</dialog>

<style>
  dialog { border: 0; padding: 0; border-radius: var(--r-3); background: var(--surface); color: var(--text); box-shadow: var(--shadow-2); width: min(560px, calc(100vw - 24px)); max-height: calc(100dvh - 24px); }
  dialog.wide { width: min(880px, calc(100vw - 24px)); }
  dialog::backdrop { background: rgba(10, 14, 24, 0.45); }
  .dlg { display: flex; flex-direction: column; max-height: calc(100dvh - 24px); }
  header { display: flex; align-items: center; gap: var(--s-2); padding: var(--s-3) var(--s-3) var(--s-2) var(--s-5); border-bottom: 1px solid var(--line); }
  header h2 { margin: 0; flex: 1; font-size: var(--fs-lg); }
  .body { padding: var(--s-4) var(--s-5); overflow: auto; }
  footer { padding: var(--s-3) var(--s-5) var(--s-4); justify-content: flex-end; border-top: 1px solid var(--line); }
  @media (max-width: 767px) { .body { padding: var(--s-4); } header { padding-left: var(--s-4); } footer { padding: var(--s-3) var(--s-4); } }
  /* Phones: a sheet anchored to the bottom, full width, actions within thumb reach and above the system bar. */
  @media (max-width: 599px) {
    dialog, dialog.wide { width: 100vw; max-width: 100vw; margin: auto 0 0; border-radius: var(--r-3) var(--r-3) 0 0; max-height: calc(100dvh - 16px); }
    .dlg { max-height: calc(100dvh - 16px); }
    footer { padding-bottom: calc(var(--s-3) + env(safe-area-inset-bottom)); flex-wrap: wrap-reverse; }
    footer :global(.btn) { flex: 1 1 auto; }
    .dlg:not(:has(footer)) .body { padding-bottom: calc(var(--s-4) + env(safe-area-inset-bottom)); }
  }
</style>
