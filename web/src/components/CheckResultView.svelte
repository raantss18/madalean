<script lang="ts">
  import type { CheckResult } from '../lib/api/types';
  import { t } from '../lib/i18n/index.svelte';
  import Icon from './Icon.svelte';
  let { check, mode = 'statement' }: { check: CheckResult; mode?: 'statement' | 'proof' } = $props();
  const ok = $derived(mode === 'proof' ? check.ok : check.statement_ok);
</script>

<div class="check" class:ok class:bad={!ok} role="status">
  <p class="head"><Icon name={ok ? 'check' : 'warn'} size={16} />
    <strong>{ok ? (mode === 'proof' ? t('check.proofOk') : t('check.statementOk')) : check.timed_out ? t('check.timeout') : check.infra_error ? t('check.infra') : mode === 'proof' ? t('check.proofBad') : t('check.statementBad')}</strong>
    <span class="xs muted">{t('check.seconds', { s: check.seconds.toFixed(1) })}</span>
  </p>
  {#if check.infra_error}<p class="small">{check.infra_error}</p>{/if}
  {#if check.errors.length}
    <ul class="errs">
      {#each check.errors.slice(0, 20) as e}
        <li class={e.severity}><span class="mono xs">{t('check.line', { l: e.line })}</span> <span class="small">{e.text}</span></li>
      {/each}
    </ul>
  {/if}
  {#if mode === 'proof' && check.reasons.length && !check.ok}<p class="small">{check.reasons.join(' · ')}</p>{/if}
  {#if mode === 'proof' && check.axioms}<p class="xs muted">{t('check.axioms', { a: check.axioms.join(', ') || '—' })}</p>{/if}
</div>

<style>
  .check { border-radius: var(--r-2); padding: var(--s-3); margin-top: var(--s-3); border: 1px solid var(--line); }
  .check.ok { background: var(--proved-soft); border-color: color-mix(in srgb, var(--proved) 40%, transparent); }
  .check.bad { background: var(--failed-soft); border-color: color-mix(in srgb, var(--failed) 40%, transparent); }
  .head { display: flex; align-items: center; gap: 8px; margin: 0; flex-wrap: wrap; }
  .ok .head { color: var(--proved); }
  .bad .head { color: var(--failed); }
  .errs { margin: var(--s-2) 0 0; padding-left: 1.2em; max-height: 240px; overflow: auto; }
  .errs li { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text); }
</style>
