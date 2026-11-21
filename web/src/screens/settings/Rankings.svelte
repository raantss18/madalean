<script lang="ts">
  // « Classement » (S-V, docs/BRAIN.md §12): per domain the best models usable now, each score with its evidence
  // (measured here, LMArena public signal with its date, catalogue estimate), the model news (« Nouveau »,
  // disappeared), and when the catalogue / public rankings refresh by themselves.
  import { api } from '../../lib/api/client';
  import type { Rankings, RankingRow } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { providerName } from '../../lib/status';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';

  let data = $state<Rankings | null>(null);
  let refreshing = $state(false);
  let domain = $state('lean');
  async function load() { try { data = await api.rankings(); } catch { data = null; } }
  $effect(() => { void load(); });
  $effect(() => app.on('models.rankings', () => void load()));
  async function refresh() {
    refreshing = true;
    try { data = await api.refreshRankings(); toast('ok', t('rank.refreshed')); } catch (e) { toast('error', errorText(e)); } finally { refreshing = false; }
  }
  const current = $derived(data?.domains.find((d) => d.domain === domain) ?? data?.domains[0]);
  function evidence(r: RankingRow): string {
    const bits: string[] = [];
    for (const s of r.sources) {
      if (s.kind === 'measured') bits.push(t('rank.measured', { ok: s.solved ?? 0, n: s.tasks ?? 0 }));
      else if (s.kind === 'public') for (const x of s.rows ?? []) bits.push(t('rank.public', { slice: tk(`rank.slice.${x.slice}`, x.slice), rank: x.rank ?? '?', total: x.total ?? '?', date: x.published }));
      else if (s.kind === 'estimate') bits.push(s.family ? t('rank.estimateFamily', { f: s.family }) : t('rank.estimate'));
    }
    return bits.join(' · ');
  }
</script>

<section class="panel" aria-labelledby="rank-h">
  <div class="row"><h3 id="rank-h">{t('rank.title')}</h3><span class="spacer"></span>
    {#if data?.auto}<button class="btn small" onclick={refresh} disabled={refreshing}><Icon name="refresh" size={14} />{t('rank.refresh')}</button>{/if}
  </div>
  <p class="hint">{t('rank.hint')}</p>
  {#if data && data.domains.length}
    <div class="tabs" role="group" aria-label={t('rank.domains')}>
      {#each data.domains as d (d.domain)}
        <button class="btn small" class:primary={d.domain === current?.domain} aria-pressed={d.domain === current?.domain} onclick={() => (domain = d.domain)}>{tk(`rank.domain.${d.domain}`, d.domain)}</button>
      {/each}
    </div>
    {#if current?.rows.length}
      <ol class="ranks">
        {#each current.rows as r (r.key)}
          <li>
            <div class="line"><strong>{r.name}</strong>
              <span class="chip {r.local ? 'local' : 'online'}">{r.local ? t('privacy.here') : providerName(r.provider)}</span>
              {#if r.new}<span class="chip new">{t('rank.new')}</span>{/if}
              {#if r.paid}<span class="chip">{t('models.paid')}</span>{/if}
              <span class="spacer"></span><span class="score" title={tk(`rank.evidence.${r.evidence}`, r.evidence)}>{Math.round(r.score * 100)}</span>
            </div>
            <p class="xs muted">{tk(`rank.evidence.${r.evidence}`, r.evidence)} — {evidence(r)}</p>
          </li>
        {/each}
      </ol>
    {:else}<p class="muted small">{t('models.noCandidate')}</p>{/if}
    <p class="xs muted">
      {#if data.public.fetched}{t('rank.source', { src: data.public.source ?? 'LMArena', lic: data.public.license ?? '', date: data.public.published ?? '?', fetched: fmtTime(data.public.fetched) })}
        <a href={data.public.url} target="_blank" rel="noopener noreferrer">{data.public.dataset}</a>
      {:else}{t('rank.noPublic')}{/if}
      {#if data.public.error} <span class="error-text">{t('rank.publicError')}</span>{/if}
    </p>
    <p class="xs muted">{data.auto ? t('rank.next', { cat: fmtTime(data.next.catalogue) || t('rank.soon'), pub: fmtTime(data.next.public) || t('rank.soon') }) : t('rank.noAuto')}</p>
  {:else if data}<p class="muted small">{t('rank.empty')}</p>{/if}

  {#if data?.news.length}
    <details>
      <summary><strong>{t('rank.news', { n: data.news.length })}</strong></summary>
      <ul class="news">
        {#each data.news as e, i (i)}
          <li class="small"><span class="xs muted">{fmtTime(e.t)}</span>
            {#if e.kind === 'new'}<span class="chip new">{t('rank.new')}</span> {e.name ?? e.key} <span class="xs muted">({providerName(e.provider)})</span>
            {:else if e.kind === 'gone'}<span class="chip">{t('rank.gone')}</span> <span class="mono xs">{e.key}</span>
            {:else}<span class="chip">{t('rank.providerAdded')}</span> {providerName(e.provider)} <span class="xs muted">({t('rank.models', { n: e.models ?? 0 })})</span>{/if}
          </li>
        {/each}
      </ul>
    </details>
  {/if}
</section>

<style>
  .tabs { display: flex; flex-wrap: wrap; gap: var(--s-1, 4px); margin-bottom: var(--s-2); }
  .ranks { margin: 0; padding-left: 1.6em; display: grid; gap: var(--s-2); }
  .ranks .line { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
  .ranks p { margin: 2px 0 0; overflow-wrap: anywhere; }
  .score { font-variant-numeric: tabular-nums; font-weight: 600; }
  .chip.new { background: var(--accent-soft); color: var(--accent); }
  .news { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: 4px; }
  summary { cursor: pointer; min-height: var(--touch); display: flex; align-items: center; }
</style>
