<script lang="ts">
  // « Ce que Madalean a appris » (S-AY, D57b): lessons learned from verified work only, whatever the model — renames
  // of Mathlib names, fixes after a Lean error, approaches that failed, strategies that worked. Each one shows its
  // evidence and counters; delete one, clear all, export / import as a file.
  import { graphApi, type Lesson } from '../../lib/api/graph';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';

  let lessons = $state<Lesson[] | null>(null);
  let max = $state(0);
  let busy = $state(false);
  let file: HTMLInputElement | undefined = $state();

  async function load() {
    try { const r = await graphApi.lessons(); lessons = r.lessons; max = r.max; } catch (e) { lessons = []; toast('error', errorText(e)); }
  }
  $effect(() => { void load(); });

  function what(l: Lesson): string {
    if (l.kind === 'rename') return t('lessons.rename', { old: l.old ?? '', new: l.new ?? '' });
    if (l.kind === 'fix') return t('lessons.fix', { pattern: l.pattern ?? '', tactics: (l.tactics ?? []).join(', ') });
    if (l.kind === 'approach') return t('lessons.approach', { approach: l.approach ?? '', reason: l.reason ?? '' });
    if (l.kind === 'split') return t('lessons.split', { pattern: l.pattern ?? '', parts: (l.parts ?? []).join(' ; ') });
    return t('lessons.strategy', { strategy: l.strategy ?? '', tactics: (l.tactics ?? []).join(', ') });
  }
  async function del(l: Lesson) {
    try { await graphApi.deleteLesson(l.id); lessons = (lessons ?? []).filter((x) => x.id !== l.id); } catch (e) { toast('error', errorText(e)); }
  }
  async function clear() {
    if (!confirm(t('lessons.clearConfirm'))) return;
    try { await graphApi.clearLessons(); lessons = []; } catch (e) { toast('error', errorText(e)); }
  }
  async function exportFile() {
    try {
      const data = await graphApi.exportLessons();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url; a.download = 'madalean-lecons.json'; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { toast('error', errorText(e)); }
  }
  async function importFile(ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    if (!f) return;
    busy = true;
    try {
      const r = await graphApi.importLessons(JSON.parse(await f.text()));
      toast('ok', t('lessons.imported', { n: r.imported }));
      await load();
    } catch (e) { toast('error', errorText(e)); } finally { busy = false; if (file) file.value = ''; }
  }
</script>

<div class="ls">
  <p class="lead">{t('lessons.lead')}</p>
  <div class="row acts">
    <button class="btn small" onclick={exportFile}><Icon name="download" size={14} />{t('lessons.export')}</button>
    {#if app.m.local}
      <label class="btn small"><Icon name="file" size={14} />{t('lessons.import')}<input bind:this={file} class="sr-only" type="file" accept="application/json,.json" onchange={importFile} disabled={busy} /></label>
    {/if}
    {#if lessons?.length}<button class="btn small danger quiet" onclick={clear}><Icon name="trash" size={14} />{t('lessons.clear')}</button>{/if}
  </div>
  {#if lessons === null}<p class="muted" aria-busy="true">{t('common.loading')}</p>
  {:else if !lessons.length}<p class="muted">{t('lessons.empty')}</p>
  {:else}
    <p class="xs muted">{t('lessons.count', { n: lessons.length, max })}</p>
    <ul class="list">
      {#each lessons as l (l.id)}
        <li>
          <div class="txt">
            <span class="kind xs">{tk(`lessons.kind.${l.kind}`, l.kind)}</span>
            <span class="what small">{what(l)}</span>
            <span class="ev xs muted">{t('lessons.evidence', { ok: l.ok, bad: l.bad, n: l.evidence.length, when: fmtTime(l.updated) })}{#if l.mathlib} · Mathlib {l.mathlib}{/if}</span>
          </div>
          <button class="btn quiet icon small" aria-label={t('lessons.delete')} onclick={() => del(l)}><Icon name="trash" size={14} /></button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .ls { display: grid; gap: var(--s-3); max-width: 760px; }
  .lead { margin: 0; color: var(--text-2); }
  .acts { gap: var(--s-2); flex-wrap: wrap; }
  .list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
  .list li { display: flex; gap: var(--s-2); align-items: flex-start; border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2); background: var(--surface); }
  .txt { display: grid; gap: 2px; min-width: 0; flex: 1; }
  .kind { font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.04em; }
  .what { overflow-wrap: anywhere; }
</style>
