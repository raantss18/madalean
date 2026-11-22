<script lang="ts">
  // A screen's <h1> that edits in place (S-AK, docs/UI.md §14.5): click the title (or the pencil) → a field; every
  // change is saved automatically (debounced, and on Enter / blur / leaving). Escape puts the title back as it was.
  import { onDestroy, tick } from 'svelte';
  import { Autosave } from '../lib/ui/autosave.svelte';
  import Icon from './Icon.svelte';
  import SaveState from './SaveState.svelte';

  let { value, save, label, id = 'inline-title', disabled = false }: {
    value: string; save: (v: string) => Promise<unknown>; label: string; id?: string; disabled?: boolean;
  } = $props();
  let editing = $state(false);
  let draft = $state('');
  let before = '';
  let input: HTMLInputElement | undefined = $state();
  const saver = new Autosave(async () => { const v = draft.trim(); if (v && v !== value) await save(v); }, { delay: 800 });
  onDestroy(() => saver.destroy());

  async function start() {
    if (disabled) return;
    draft = value; before = value; editing = true;
    await tick();
    input?.focus(); input?.select();
  }
  async function done() { editing = false; await saver.flush(); }
  async function cancel() { draft = before; saver.touch(); editing = false; await saver.flush(); }
</script>

<div class="it">
  {#if editing}
    <label class="sr-only" for={id}>{label}</label>
    <input bind:this={input} {id} class="it-in" bind:value={draft} oninput={() => saver.touch()} onblur={done} autocomplete="off"
      onkeydown={(e) => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); void done(); } else if (e.key === 'Escape') { e.preventDefault(); void cancel(); } }} />
  {:else}
    <h1 class="it-h"><button class="it-btn" type="button" onclick={start} {disabled} title={label}>{value}</button></h1>
    {#if !disabled}<button class="btn quiet icon small pen" type="button" tabindex="-1" aria-hidden="true" onclick={start}><Icon name="edit" size={16} /></button>{/if}
  {/if}
  {#if saver.status !== 'saved' || editing}<SaveState state={saver} />{/if}
</div>

<style>
  .it { display: flex; align-items: baseline; gap: var(--s-2); min-width: 0; flex: 1; }
  .it-h { margin: 0; min-width: 0; overflow-wrap: anywhere; }
  .it-btn { all: unset; cursor: text; border-radius: var(--r-1); }
  .it-btn:hover { text-decoration: underline dotted var(--line-strong); text-underline-offset: 6px; }
  .it-btn:focus-visible { outline: 2px solid var(--focus, var(--accent)); outline-offset: 2px; }
  .it-in { flex: 1 1 20ch; min-width: 0; font: 700 var(--fs-xl) / 1.25 var(--font-serif); color: var(--text); padding: 2px 8px; border: 1px solid var(--line-strong); border-radius: var(--r-2); background: var(--surface); }
  .pen { align-self: center; opacity: 0.6; }
  .it:hover .pen, .pen:focus-visible { opacity: 1; }
  @media (pointer: coarse) { .pen { opacity: 1; } }
</style>
