<script lang="ts">
  // Verdict of « Vérifier l'énoncé » (S-K): fidèle / douteux / faux, the reasons, the Lean evidence, and the two
  // one-click ways on: correct the statement with the proposed fix, or prove it anyway.
  import type { CheckIssue, CheckVerdict } from '../../lib/api/types';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { prefs } from '../../lib/prefs.svelte';
  import Md from '../../components/Md.svelte';
  import { follow, run } from './actions';

  let { id, params, actions = true, busy = false }: {
    id: string; params: Record<string, unknown>; actions?: boolean; busy?: boolean;
  } = $props();
  const verdict = $derived((params.verdict as CheckVerdict) ?? 'unknown');
  const issues = $derived((params.issues as CheckIssue[] | undefined) ?? []);
  const fix = $derived((params.fix as string | undefined) ?? '');
  const evidence = $derived(params.evidence as { kind?: string; code?: string; idea?: string } | undefined);
  // Learn mode: the explanations are open by default (they are written for a student)
  let open = $state(prefs.mode === 'learn');
</script>

<div class="verdict {verdict}" role="status">
  <span class="chip">{tk(`check.${verdict}`, verdict)}</span>
  {#if issues.length || evidence?.code}
    <details bind:open>
      <summary class="xs">{t('check.why')}</summary>
      <ul class="issues">
        {#each issues as i}
          <li><strong>{tk(`check.kind.${i.kind}`, i.kind)}</strong>{#if i.severity === 'low'} <span class="xs muted">({t('check.minor')})</span>{/if}
            {#if i.checked === 'lean'} <span class="chip proved xs">{t('check.byLean')}</span>{/if} — <Md src={i.explanation} /></li>
        {/each}
      </ul>
      {#if evidence?.code}
        <p class="xs">{t('check.evidence')}{#if evidence.idea} ({evidence.idea}){/if}</p>
        <pre class="lean"><code>{evidence.code}</code></pre>
      {/if}
    </details>
  {/if}
  {#if actions && verdict !== 'faithful' && verdict !== 'unknown'}
    <div class="row">
      {#if fix}<button class="btn small primary" disabled={busy} onclick={() => follow(id, fix, 'statement')}>{t('check.fixWith', { fix })}</button>{#if params.changes_statement}<span class="chip running">{t('check.changes')}</span>{/if}{/if}
      <button class="btn small" disabled={busy} onclick={() => run(id, [{ stage: 'proof', force: true }, 'explanation'])}>{t('check.proveAnyway')}</button>
    </div>
  {/if}
</div>

<style>
  .verdict { display: grid; gap: var(--s-1); margin-top: var(--s-1); }
  .verdict .chip { justify-self: start; }
  .verdict.faithful .chip { background: var(--proved-soft, var(--surface-2)); }
  .verdict.doubtful .chip { background: var(--warn-soft, var(--surface-2)); }
  .verdict.false .chip { background: var(--failed-soft); }
  .issues { margin: var(--s-1) 0; padding-left: 1.2em; }
  .lean { max-height: 14rem; overflow: auto; font-size: var(--fs-xs, 12px); white-space: pre-wrap; overflow-wrap: anywhere; }
  .row { display: flex; flex-wrap: wrap; gap: var(--s-2); }
  details summary { cursor: pointer; color: var(--text-2); }
</style>
