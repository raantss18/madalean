<script lang="ts">
  // « Mal compris » (D64): reason + text → the server stops what depends on it, redoes the step and learns from it.
  import type { Dossier, ReportReason } from '../../lib/api/types';
  import { flow, REASONS, type ReportTarget } from '../../lib/api/flow';
  import type { LocalReport } from '../../lib/flow';
  import { ApiError } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { keepDraft } from '../../lib/ui/drafts.svelte';
  import { enterSubmit } from '../../lib/ui/enter';
  import Dialog from '../../components/Dialog.svelte';
  import EnterHint from '../../components/EnterHint.svelte';
  import { applyAnswer, flowError } from './flowtext';

  let { dossier: d, target, ref, open = $bindable(false), onsent }: {
    dossier: Dossier; target: ReportTarget; ref?: number; open?: boolean; onsent: (r: LocalReport) => void;
  } = $props();
  let reason = $state<ReportReason | ''>('');
  let text = $state('');
  let busy = $state(false);
  keepDraft(() => `report.${d.id}`, () => text, (v) => { text = v; });

  async function send() {
    if (!reason || busy) return;
    busy = true;
    const body = { target, ...(ref !== undefined ? { ref } : {}), reason, ...(text.trim() ? { text: text.trim() } : {}) };
    try {
      const r = await flow.report(d.id, body);
      onsent({ target, reason, text: text.trim(), t: Date.now() / 1000 });
      reason = ''; text = ''; open = false;
      toast('ok', t('report.sent'));
      await applyAnswer(d.id, r);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 405)) toast('warn', t('report.unsupported'));
      else await flowError(e, d.id);
    } finally { busy = false; }
  }
</script>

<Dialog bind:open title={t('report.title')}>
  <p class="small">{t('report.about', { what: t(`report.target.${target}`) })}</p>
  <fieldset>
    <legend>{t('report.reason')}</legend>
    {#each REASONS as r (r)}<label><input type="radio" name="report-reason" value={r} bind:group={reason} />{t(`report.reason.${r}`)}</label>{/each}
  </fieldset>
  <div class="field">
    <label for="report-text">{t('report.text')}</label>
    <textarea id="report-text" class="input" rows="3" bind:value={text} use:enterSubmit={() => void send()} aria-describedby="report-e report-h"></textarea>
    <EnterHint id="report-e" />
  </div>
  <p class="hint" id="report-h">{t('report.hint')}</p>
  {#snippet actions()}
    <button class="btn" onclick={() => (open = false)}>{t('common.cancel')}</button>
    <button class="btn primary" disabled={!reason || busy} onclick={send}>{t('report.send')}</button>
  {/snippet}
</Dialog>

<style>
  fieldset { border: 0; padding: 0; margin: 0 0 var(--s-3); }
  legend { font-weight: 600; padding: 0; }
  fieldset label { display: flex; align-items: center; gap: 10px; min-height: 40px; cursor: pointer; }
  @media (pointer: coarse) { fieldset label { min-height: var(--touch); } }
  textarea.input { min-height: 80px; }
</style>
