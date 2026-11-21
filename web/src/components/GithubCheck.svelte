<script lang="ts">
  // « Tester la connexion GitHub »: read-only (who am I, token kind, scopes, can it create / push / enable Pages).
  // Nothing is created on GitHub. Results in plain words, with the exact permission to add when one is missing.
  import { research, type GithubCheck } from '../lib/api/research';
  import { t, tk } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import Icon from './Icon.svelte';

  let { repo = '', priv = false, auto = false }: { repo?: string; priv?: boolean; auto?: boolean } = $props();
  let res = $state<GithubCheck | null>(null);
  let busy = $state(false);
  let err = $state('');

  export async function run() {
    busy = true; err = ''; res = null;
    try { res = await research.githubCheck(/^[\w.-]+\/[\w.-]+$/.test(repo.trim()) ? repo.trim() : '', priv); }
    catch (e) { err = errorText(e); } finally { busy = false; }
  }
  $effect(() => { if (auto) void run(); });
  const kindText = $derived(res ? tk(`gh.kind.${res.token_kind || 'none'}`, res.token_kind) : '');
</script>

<div class="ghc">
  <button class="btn small" type="button" onclick={run} disabled={busy}><Icon name="refresh" size={14} />{busy ? t('gh.testing') : t('gh.test')}</button>
  <div role="status" aria-live="polite">
    {#if res}
      <p class="small head {res.ok ? 'ok' : 'bad'}">
        {#if res.login}{t('gh.as', { login: res.login })}{:else}{t('gh.notConnected')}{/if}
        {#if kindText}<span class="chip">{kindText}</span>{/if}
        {#if res.source === 'gh'}<span class="chip">{t('gh.fromCli')}</span>{/if}
      </p>
      <ul class="checks">
        {#each res.checks as c (c.id + c.code)}
          <li class="small">
            <span class="mark {c.ok === true ? 'ok' : c.ok === false ? 'bad' : 'unk'}" aria-hidden="true">{c.ok === true ? '✓' : c.ok === false ? '✗' : '?'}</span>
            <span class="sr-only">{c.ok === true ? t('gh.yes') : c.ok === false ? t('gh.no') : t('gh.unknown')}</span>
            <span><strong>{tk(`gh.step.${c.id}`, c.id)}</strong> — {tk(`gh.code.${c.code}`, c.code, c.params)}</span>
          </li>
        {/each}
      </ul>
      {#if res.token_kind === 'fine_grained'}<p class="hint">{t('gh.fineHint')}</p>{/if}
    {/if}
    {#if err}<p class="error-text small">{err}</p>{/if}
  </div>
</div>

<style>
  .ghc { display: grid; gap: var(--s-2); justify-items: start; }
  .head { margin: 0; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .head.ok { color: var(--proved); }
  .head.bad { color: var(--failed); }
  .checks { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
  .checks li { display: flex; gap: 6px; align-items: baseline; overflow-wrap: anywhere; }
  .mark { font-weight: 700; width: 1em; flex: none; text-align: center; }
  .mark.ok { color: var(--proved); }
  .mark.bad { color: var(--failed); }
  .mark.unk { color: var(--running); }
</style>
