<script lang="ts">
  // Graph of a project: notes, dossiers and sources with their links (Obsidian-like), filters, and a list version.
  import { research, type GraphEdge, type GraphNode } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { forceLayout, type Pos } from '../../lib/graph/layout';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import SvgGraph from '../../components/SvgGraph.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());
  let data = $state<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  let err = $state('');
  let kinds = $state<string[]>(['note', 'dossier', 'source']);
  let edgeKinds = $state<string[]>(['link', 'uses', 'cites']);
  let tag = $state('');
  let orphans = $state(true);
  let find = $state('');
  let selected = $state('');
  let pos = $state<Pos>({});
  let asList = $state(typeof matchMedia !== 'undefined' && matchMedia('(max-width: 767px)').matches);
  let tags = $state<{ tag: string; count: number }[]>([]);
  let rev = $state(0);
  $effect(() => app.on('note.updated', () => rev++));

  async function load() {
    if (!pid) return;
    try {
      data = await research.graph(pid, { kinds: kinds.join(','), edges: edgeKinds.join(','), tag, orphans });
      pos = forceLayout(data.nodes, data.edges);
      err = '';
    } catch (e) { err = errorText(e); }
  }
  $effect(() => { void kinds; void edgeKinds; void tag; void orphans; void rev; void pid; void load(); });
  $effect(() => { if (pid) research.tags(pid).then((r) => (tags = r.tags)).catch(() => {}); });
  const gnodes = $derived((data?.nodes ?? []).map((n) => ({ id: n.id, label: n.title, kind: n.kind, cls: [n.proved ? 'proved' : '', n.missing ? 'missing' : ''].join(' '), title: `${tk(`graph.kind.${n.kind}`, n.kind)}${n.status ? ' · ' + tk(`phase.${n.status}`, n.status) : ''}` })));
  const gedges = $derived((data?.edges ?? []).map((e) => ({ source: e.source, target: e.target, kind: e.kind })));
  $effect(() => {
    const s = find.trim().toLowerCase();
    if (!s) return;
    const hit = data?.nodes.find((n) => n.title.toLowerCase().includes(s));
    if (hit) selected = hit.id;
  });
  function openNode(id: string) {
    const n = data?.nodes.find((x) => x.id === id);
    if (!n || n.missing) return;
    if (n.kind === 'note') navigate(`/notes/${encodeURIComponent(n.ref)}`);
    else if (n.kind === 'dossier') navigate(`/d/${encodeURIComponent(n.ref)}`);
    else navigate(`/sources?tab=library&key=${encodeURIComponent(n.ref)}`);
  }
  const sel = $derived(data?.nodes.find((n) => n.id === selected));
  const links = (id: string) => (data?.edges ?? []).filter((e) => e.source === id || e.target === id);
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="g">
      <div class="row head"><h1>{t('graph.title')}</h1><HelpLink page="notes" /></div>
      <div class="row filters">
        <fieldset class="row"><legend class="sr-only">{t('graph.kinds')}</legend>
          {#each ['note', 'dossier', 'source'] as k}<label class="switch small"><input type="checkbox" value={k} bind:group={kinds} />{tk(`graph.kind.${k}`, k)}</label>{/each}</fieldset>
        <fieldset class="row"><legend class="sr-only">{t('graph.edges')}</legend>
          {#each ['link', 'uses', 'cites'] as k}<label class="switch small"><input type="checkbox" value={k} bind:group={edgeKinds} />{tk(`graph.edge.${k}`, k)}</label>{/each}</fieldset>
        <label class="switch small"><input type="checkbox" bind:checked={orphans} />{t('graph.orphans')}</label>
        <label class="sr-only" for="gtag">{t('sources.tag')}</label>
        <select id="gtag" class="input" style="width:auto" bind:value={tag}><option value="">{t('sources.allTags')}</option>{#each tags as tg}<option value={tg.tag}>#{tg.tag} ({tg.count})</option>{/each}</select>
        <label class="sr-only" for="gfind">{t('graph.find')}</label>
        <input id="gfind" class="input" type="search" placeholder={t('graph.find')} bind:value={find} style="max-width: 220px" />
        <label class="switch small"><input type="checkbox" bind:checked={asList} />{t('graph.asList')}</label>
      </div>
      {#if err}<p class="error-text">{err}</p>{:else if !data}<p class="muted" aria-busy="true">{t('common.loading')}</p>
      {:else if !data.nodes.length}<p class="muted">{t('graph.empty')}</p>
      {:else if asList}
        <table class="tbl">
          <caption class="sr-only">{t('graph.title')}</caption>
          <thead><tr><th scope="col">{t('graph.node')}</th><th scope="col">{t('graph.kindCol')}</th><th scope="col">{t('graph.linksCol')}</th></tr></thead>
          <tbody>
            {#each data.nodes as n (n.id)}
              <tr><td><button class="linkish" onclick={() => openNode(n.id)} disabled={n.missing}>{n.title}</button></td><td>{tk(`graph.kind.${n.kind}`, n.kind)}</td>
                <td class="small">{links(n.id).map((e) => data!.nodes.find((x) => x.id === (e.source === n.id ? e.target : e.source))?.title ?? '?').join(', ')}</td></tr>
            {/each}
          </tbody>
        </table>
      {:else}
        <div class="split">
          <SvgGraph nodes={gnodes} edges={gedges} {pos} {selected} onselect={(id) => (selected = id)} onopen={openNode} label={t('graph.title')} />
          <aside class="panel side" aria-live="polite">
            {#if sel}
              <p class="xs muted">{tk(`graph.kind.${sel.kind}`, sel.kind)}{sel.missing ? ` · ${t('graph.missing')}` : ''}</p>
              <h2>{sel.title}</h2>
              {#if sel.tags?.length}<p class="small">{sel.tags.map((x) => '#' + x).join(' ')}</p>{/if}
              <ul class="small">{#each links(sel.id) as e}{@const o = data.nodes.find((x) => x.id === (e.source === sel.id ? e.target : e.source))}<li>{tk(`graph.edge.${e.kind}`, e.kind)} → <button class="linkish" onclick={() => (selected = o?.id ?? '')}>{o?.title ?? '?'}</button></li>{/each}</ul>
              {#if !sel.missing}<button class="btn small primary" onclick={() => openNode(sel.id)}>{t('graph.open')}</button>{/if}
            {:else}<p class="small muted">{t('graph.pick')}</p>{/if}
            <ul class="legend xs">
              <li><span class="lg note"></span>{t('graph.kind.note')}</li><li><span class="lg dossier"></span>{t('graph.kind.dossier')}</li>
              <li><span class="lg proved"></span>{t('graph.provedDossier')}</li><li><span class="lg source"></span>{t('graph.kind.source')}</li>
            </ul>
          </aside>
        </div>
      {/if}
    </div>
  {/snippet}
</ProjectGate>

<style>
  .head h1 { margin: 0; }
  .filters { margin: var(--s-2) 0 var(--s-3); }
  fieldset { border: 0; padding: 0; margin: 0; }
  .split { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: var(--s-3); }
  @media (max-width: 900px) { .split { grid-template-columns: minmax(0, 1fr); } }
  .side h2 { font-size: var(--fs-md); }
  .legend { list-style: none; padding: 0; display: grid; gap: 4px; margin-top: var(--s-3); }
  .lg { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; border: 2px solid var(--text-2); vertical-align: -2px; }
  .lg.note { background: var(--accent-soft); border-color: var(--accent); } .lg.proved { background: var(--proved); border-color: var(--proved); }
  .lg.source { background: var(--online-soft); border-color: var(--online); }
  .tbl { width: 100%; border-collapse: collapse; table-layout: fixed; overflow-wrap: anywhere; }
  .tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); }
  .linkish { background: none; border: 0; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; text-align: left; }
</style>
