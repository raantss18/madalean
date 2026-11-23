<script lang="ts">
  // « Nouveautés » on Home (session S-AV): the number of unread items of the user's domains and the three newest
  // titles. Quiet: no toast, no animation; hidden when the user turned the badge off or when there is nothing yet.
  // Loaded when the browser is idle, so Home's first paint does not wait for it (D48).
  import { newsBadge, loadNewsOverview } from '../../lib/news.svelte';
  import { t, tn } from '../../lib/i18n/index.svelte';
  import Icon from '../../components/Icon.svelte';

  $effect(() => {
    const run = () => void loadNewsOverview();
    if ('requestIdleCallback' in window) { const id = requestIdleCallback(run, { timeout: 2500 }); return () => cancelIdleCallback(id); }
    const id = setTimeout(run, 400);
    return () => clearTimeout(id);
  });
  const ov = $derived(newsBadge.overview);
  const show = $derived(Boolean(ov && ov.badge && ov.items > 0));
  const plain = (s: string) => s.replace(/\$+/g, '');
</script>

{#if show && ov}
  <section class="newscard" aria-labelledby="nc-h">
    <div class="row">
      <h2 id="nc-h"><Icon name="globe" size={18} />{t('news.card.title')}</h2>
      <span class="spacer"></span>
      <a class="btn small" href="/actualites">{newsBadge.unread ? tn('news.card.unread', newsBadge.unread) : t('news.card.none')}<Icon name="chevronRight" size={14} /></a>
    </div>
    {#if ov.newest.length}
      <ul>
        {#each ov.newest as it (it.id)}
          <li><a href="/actualites" class="small"><span class="tt">{plain(it.title)}</span>{#if it.open}<span class="src xs muted">{t('news.openProblem')}</span>{/if}</a></li>
        {/each}
      </ul>
    {/if}
    {#if ov.for_projects}<p class="small muted">{tn('news.card.projects', ov.for_projects)}</p>{/if}
  </section>
{/if}

<style>
  .newscard { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-3) var(--s-4); display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-2); min-width: 0; }
  h2 { margin: 0; font-size: var(--fs-md); display: inline-flex; align-items: center; gap: 8px; }
  .row { gap: var(--s-2); flex-wrap: wrap; }
  ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; }
  li a { display: flex; gap: var(--s-2); align-items: baseline; min-height: 32px; padding: 4px 0; color: var(--text); text-decoration: none; min-width: 0; }
  li a:hover .tt { color: var(--accent); text-decoration: underline; }
  .tt { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-serif); }
  .src { flex: none; }
  p { margin: 0; }
  @media (pointer: coarse) { li a { min-height: var(--touch); align-items: center; } }
</style>
