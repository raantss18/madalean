<script lang="ts">
  // Manual edit of an AI output (proof, natural-language proof, explanation). The server has no endpoint yet to
  // store a user version of these (docs/UI.md « Requests to the server »), so the edit is a DRAFT kept on this
  // device: never overwritten by a new AI version without asking, checkable by Lean (proof), copyable, exportable.
  import type { CheckResult, Dossier } from '../../lib/api/types';
  import { api } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON, removeKey } from '../../lib/prefs.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { toast } from '../../lib/ui/toasts.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';
  import Md from '../../components/Md.svelte';

  let { dossier: d, kind, server, open = $bindable(false) }: { dossier: Dossier; kind: 'proof' | 'informal' | 'explanation'; server: string; open?: boolean } = $props();
  const key = $derived(`localdraft.${d.id}.${kind}`);
  let draft = $state<{ base: string; text: string } | null>(null);
  let check = $state<CheckResult | null>(null);
  let checking = $state(false);
  let preview = $state(false);
  $effect(() => { draft = loadJSON<{ base: string; text: string } | null>(key, null); });
  $effect(() => { if (open && !draft) { draft = { base: server, text: server }; } });
  $effect(() => { if (draft) saveJSON(key, draft); });
  const stale = $derived(Boolean(draft && draft.base !== server));
  const exists = $derived(Boolean(draft && draft.text !== draft.base));

  async function verify() {
    if (!draft) return;
    checking = true; check = null;
    try { check = (await api.check(draft.text, { workspace: d.workspace, strict: true })).check; }
    catch (e) { toast('error', errorText(e)); } finally { checking = false; }
  }
  function discard() {
    const old = draft;
    draft = null; open = false; removeKey(key);
    toast('ok', t('draft.discarded'), { action: { label: t('common.undo'), run: () => { draft = old; open = true; } } });
  }
  async function copy() {
    try { await navigator.clipboard.writeText(draft?.text ?? ''); toast('ok', t('draft.copied')); } catch { toast('error', t('draft.copyFailed')); }
  }
</script>

{#if draft && (open || exists)}
  <div class="draft">
    <p class="note small" role="note"><strong>{t('draft.title')}</strong> {t('draft.localNote')}</p>
    {#if stale}
      <p class="stale small" role="status">{t('draft.stale')}
        <button class="btn small" onclick={() => draft && (draft = { base: server, text: draft.text })}>{t('draft.keepMine')}</button>
        <button class="btn small" onclick={() => (draft = { base: server, text: server })}>{t('draft.takeNew')}</button>
      </p>
    {/if}
    {#if kind === 'proof'}
      <CodeEditor bind:value={draft.text} language="lean" label={t('draft.editorProof')} minLines={8} onSubmit={verify} />
    {:else}
      <div class="seg" role="radiogroup" aria-label={t('draft.viewMode')}>
        <label><input type="radio" name="dm-{kind}" checked={!preview} onchange={() => (preview = false)} />{t('draft.edit')}</label>
        <label><input type="radio" name="dm-{kind}" checked={preview} onchange={() => (preview = true)} />{t('draft.preview')}</label>
      </div>
      {#if preview}<div class="pv"><Md src={draft.text} /></div>
      {:else}<CodeEditor bind:value={draft.text} language="natural" label={t('draft.editorText')} minLines={8} />{/if}
    {/if}
    <div class="row" style="margin-top: var(--s-2)">
      {#if kind === 'proof'}<button class="btn primary" onclick={verify} disabled={checking}>{checking ? t('lean.checking') : t('lean.checkProof')}</button>{/if}
      <button class="btn" onclick={copy}>{t('draft.copy')}</button>
      <button class="btn quiet" onclick={() => (open = false)}>{t('draft.close')}</button>
      <button class="btn quiet danger" onclick={discard}>{t('draft.discard')}</button>
    </div>
    {#if check}<CheckResultView {check} mode="proof" />{/if}
  </div>
{/if}

<style>
  .draft { margin-top: var(--s-3); padding: var(--s-3); border: 1px dashed var(--line-strong); border-radius: var(--r-2); }
  .note { margin: 0 0 var(--s-2); }
  .stale { background: var(--running-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); display: flex; gap: var(--s-2); align-items: center; flex-wrap: wrap; }
  .seg { margin-bottom: var(--s-2); }
  .pv { padding: var(--s-3); background: var(--surface-2); border-radius: var(--r-2); }
</style>
