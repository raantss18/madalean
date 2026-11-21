<script lang="ts">
  // Import a .tex file → pick one of the candidate statements (theorem-like environments).
  import { api } from '../lib/api/client';
  import { t } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import Dialog from './Dialog.svelte';
  import Md from './Md.svelte';

  let { onpick }: { onpick: (text: string, title: string) => void } = $props();
  let open = $state(false);
  let busy = $state(false);
  let err = $state('');
  let items = $state<{ title: string; body: string }[]>([]);
  let input: HTMLInputElement | undefined = $state();
  let choice = $state(0);

  async function file(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (!f) return;
    busy = true; err = ''; items = []; open = true;
    try {
      const r = await api.importTex(f);
      items = r.statements;
      choice = 0;
      if (!items.length) err = t('tex.none');
    } catch (x) { err = errorText(x); } finally { busy = false; if (input) input.value = ''; }
  }
  function use() {
    const it = items[choice];
    if (!it) return;
    onpick(it.body, it.title);
    open = false;
  }
</script>

<input bind:this={input} type="file" accept=".tex,text/x-tex,text/plain" class="sr-only" id="tex-file" onchange={file} tabindex="-1" aria-label={t('tex.import')} />
<button class="btn" type="button" onclick={() => input?.click()}>{t('tex.import')}</button>

<Dialog bind:open title={t('tex.pickTitle')} wide>
  {#if busy}<p aria-busy="true">{t('tex.reading')}</p>{/if}
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  {#if items.length}
    <fieldset class="cands">
      <legend class="hint">{t('tex.pickHint', { n: items.length })}</legend>
      {#each items as it, i}
        <label class="cand" class:sel={choice === i}>
          <input type="radio" name="tex-cand" value={i} bind:group={choice} />
          <span><strong>{it.title || t('tex.untitled', { i: i + 1 })}</strong><Md src={it.body.slice(0, 600)} /></span>
        </label>
      {/each}
    </fieldset>
  {/if}
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (open = false)}>{t('common.cancel')}</button>
    <button class="btn primary" disabled={!items.length} onclick={use}>{t('tex.use')}</button>
  {/snippet}
</Dialog>

<style>
  .cands { border: 0; padding: 0; margin: 0; display: grid; gap: var(--s-2); }
  .cand { display: flex; gap: var(--s-3); padding: var(--s-3); border: 1px solid var(--line); border-radius: var(--r-2); cursor: pointer; }
  .cand.sel { border-color: var(--accent); background: var(--accent-soft); }
  .cand input { margin-top: 4px; width: 18px; height: 18px; flex: none; }
  .cand :global(.md) { font-size: var(--fs-sm); margin-top: 4px; }
</style>
