<script lang="ts">
  // Merge view for a 409 conflict on a note: for each hunk changed on both devices, pick « mine », « theirs » or
  // « both »; the result is shown (editable) before it is sent with base_rev = the current revision.
  import type { NoteConflict } from '../../lib/api/research';
  import { t } from '../../lib/i18n/index.svelte';
  import { resolveConflicts } from '../../lib/notes';

  let { conflict, mineTitle, onresolve, oncancel }: {
    conflict: NoteConflict; mineBody?: string; mineTitle: string; onresolve: (body: string, title: string) => void; oncancel: () => void;
  } = $props();
  let choice = $state<('mine' | 'theirs' | 'both')[]>([]);
  let titlePick = $state<'mine' | 'theirs'>('mine');
  let result = $state('');
  let touched = $state(false);
  $effect(() => { choice = conflict.conflicts.map(() => 'mine'); touched = false; });
  $effect(() => { if (!touched) result = resolveConflicts(conflict.current.body, conflict.conflicts, choice); });
</script>

<section class="conflict" aria-labelledby="cf-h" aria-describedby="cf-d">
  <h2 id="cf-h">{t('conflict.title')}</h2>
  <p id="cf-d" class="small">{t('conflict.text', { n: conflict.conflicts.length })}</p>
  {#if conflict.fields.includes('title')}
    <fieldset class="hunk"><legend class="small">{t('conflict.titleField')}</legend>
      <label class="switch"><input type="radio" bind:group={titlePick} value="mine" />{t('conflict.mine')} : « {mineTitle} »</label>
      <label class="switch"><input type="radio" bind:group={titlePick} value="theirs" />{t('conflict.theirs')} : « {conflict.current.title} »</label>
    </fieldset>
  {/if}
  {#each conflict.conflicts as c, i}
    <fieldset class="hunk">
      <legend class="small">{t('conflict.hunk', { i: i + 1, line: c.base_start + 1 })}</legend>
      <div class="cols">
        <div><p class="xs lab">{t('conflict.mine')}</p><pre>{c.mine || t('conflict.deleted')}</pre></div>
        <div><p class="xs lab">{t('conflict.theirs')}</p><pre>{c.theirs || t('conflict.deleted')}</pre></div>
      </div>
      <div class="seg" role="radiogroup" aria-label={t('conflict.keep')}>
        {#each [['mine', 'conflict.mine'], ['theirs', 'conflict.theirs'], ['both', 'conflict.both']] as [v, k]}
          <label><input type="radio" name="cf-{i}" checked={choice[i] === v} onchange={() => { choice[i] = v as 'mine'; touched = false; }} />{t(k as 'conflict.mine')}</label>
        {/each}
      </div>
    </fieldset>
  {/each}
  <label class="label" for="cf-res">{t('conflict.result')}</label>
  <textarea id="cf-res" class="input mono" rows="8" bind:value={result} oninput={() => (touched = true)}></textarea>
  <div class="row">
    <button class="btn primary" onclick={() => onresolve(result, titlePick === 'mine' ? mineTitle : conflict.current.title)}>{t('conflict.save')}</button>
    <button class="btn quiet" onclick={oncancel}>{t('conflict.discardMine')}</button>
  </div>
</section>

<style>
  .conflict { border: 2px solid var(--running-fill); background: var(--running-soft); border-radius: var(--r-3); padding: var(--s-3) var(--s-4); margin-bottom: var(--s-3); }
  .conflict h2 { margin: 0 0 4px; font-size: var(--fs-md); color: var(--running); }
  .hunk { border: 1px solid var(--line); border-radius: var(--r-2); background: var(--surface); margin: 0 0 var(--s-2); padding: var(--s-2) var(--s-3); }
  .cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--s-2); }
  @media (max-width: 700px) { .cols { grid-template-columns: minmax(0, 1fr); } }
  .lab { margin: 0; font-weight: 700; color: var(--text-2); }
  pre { margin: 2px 0 var(--s-2); font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); }
</style>
