<script lang="ts">
  // Manual edit of an AI output (proof, natural-language proof, explanation) saved as a NEW user version through
  // POST /dossiers/{id}/versions/{kind} — nothing is overwritten; a manual proof is re-checked by Lean (strict) and
  // only counts as proven when Lean accepts it. The text being typed is kept on this device until saved.
  import { untrack } from 'svelte';
  import type { CheckResult, Dossier } from '../../lib/api/types';
  import { api } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON, removeKey } from '../../lib/prefs.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import EnterHint from '../../components/EnterHint.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';
  import Md from '../../components/Md.svelte';
  import { reportError } from './actions';

  let { dossier: d, kind, server, open = $bindable(false) }: { dossier: Dossier; kind: 'proof' | 'informal' | 'explanation'; server: string; open?: boolean } = $props();
  const key = $derived(`editing.${d.id}.${kind}`);
  let draft = $state<{ base: string; text: string } | null>(null);
  let check = $state<CheckResult | null>(null);
  let saving = $state(false);
  let preview = $state(false);
  $effect(() => {
    const k = key;
    untrack(() => { draft = loadJSON<{ base: string; text: string } | null>(k, null); if (draft) open = true; });
  });
  $effect(() => { if (open && !untrack(() => draft)) draft = { base: untrack(() => server), text: untrack(() => server) }; });
  $effect(() => { if (draft) saveJSON(key, draft); });
  const stale = $derived(Boolean(draft && draft.base !== server));

  async function save() {
    if (!draft || saving || !draft.text.trim() || draft.text === server) return;   // Enter on an unchanged text does nothing
    saving = true; check = null;
    try {
      const r = await api.saveVersion(d.id, kind, draft.text, kind === 'proof');
      app.m.full[d.id] = r.dossier;
      check = r.check;
      if (kind !== 'proof' || r.check?.ok) {
        toast('ok', kind === 'proof' ? t('manual.proofAccepted') : t('manual.saved'));
        removeKey(key); draft = null; open = false;
      } else {
        toast('warn', t('manual.proofRejected'));
        draft = { base: r.dossier.current.proof, text: draft.text };
      }
    } catch (e) { reportError(e, d.id); } finally { saving = false; }
  }
  function cancel() {
    const old = draft;
    removeKey(key); draft = null; open = false;
    if (old && old.text !== old.base) toast('ok', t('draft.discarded'), { action: { label: t('common.undo'), run: () => { draft = old; open = true; } } });
  }
</script>

{#if draft && open}
  <div class="edit">
    <p class="note small" role="note">{kind === 'proof' ? t('manual.noteProof') : t('manual.note')}</p>
    {#if stale}
      <p class="stale small" role="status">{t('draft.stale')}
        <button class="btn small" onclick={() => draft && (draft = { base: server, text: draft.text })}>{t('draft.keepMine')}</button>
        <button class="btn small" onclick={() => (draft = { base: server, text: server })}>{t('draft.takeNew')}</button>
      </p>
    {/if}
    {#if kind === 'proof'}
      <CodeEditor bind:value={draft.text} language="lean" label={t('draft.editorProof')} minLines={8} onSubmit={save} describedby="me-e-{kind}" />
      <EnterHint id="me-e-{kind}" action="check" />
    {:else}
      <div class="seg" role="radiogroup" aria-label={t('draft.viewMode')}>
        <label><input type="radio" name="dm-{kind}" checked={!preview} onchange={() => (preview = false)} />{t('draft.edit')}</label>
        <label><input type="radio" name="dm-{kind}" checked={preview} onchange={() => (preview = true)} />{t('draft.preview')}</label>
      </div>
      {#if preview}<div class="pv"><Md src={draft.text} /></div>
      {:else}<CodeEditor bind:value={draft.text} language="natural" label={t('draft.editorText')} minLines={8} onSubmit={save} enterSubmits={false} />{/if}
    {/if}
    <div class="row" style="margin-top: var(--s-2)">
      <button class="btn primary" onclick={save} disabled={saving || draft.text.trim() === '' || draft.text === server}>{saving ? (kind === 'proof' ? t('lean.checking') : t('common.loading')) : kind === 'proof' ? t('manual.saveProof') : t('manual.save')}</button>
      <button class="btn quiet" onclick={cancel}>{t('common.cancel')}</button>
    </div>
    {#if check}<CheckResultView {check} mode="proof" />{/if}
  </div>
{/if}

<style>
  .edit { margin-top: var(--s-3); padding: var(--s-3); border: 1px dashed var(--line-strong); border-radius: var(--r-2); }
  .note { margin: 0 0 var(--s-2); color: var(--text-2); }
  .stale { background: var(--running-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); display: flex; gap: var(--s-2); align-items: center; flex-wrap: wrap; }
  .seg { margin-bottom: var(--s-2); }
  .pv { padding: var(--s-3); background: var(--surface-2); border-radius: var(--r-2); }
</style>
