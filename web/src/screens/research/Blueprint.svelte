<script lang="ts">
  // Blueprint of a paper: its definitions / lemmas / theorems as a dependency graph, each node with an honest status
  // (stated → Lean statement → proved → verified only if every dependency is verified; blocked; failed), the paper's
  // text beside the Lean statement, and « formalise selected ». Status = colour + border pattern + text.
  import { research, type Blueprint, type BpNode, type NodeState, type PaperPlanStatus } from '../../lib/api/research';
  import { api } from '../../lib/api/client';
  import type { Dossier } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { navigate, route } from '../../lib/router.svelte';
  import { i18n, t, tk } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import { layeredLayout } from '../../lib/graph/layout';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import SvgGraph from '../../components/SvgGraph.svelte';
  import Md from '../../components/Md.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());
  let list = $state<{ source_id: string; paper_key: string; nodes: number; method: string; warnings: string[] }[]>([]);
  let sid = $state(route.query.get('source') ?? '');
  let bp = $state<Blueprint | null>(null);
  let status = $state<Record<string, NodeState>>({});
  let selected = $state('');
  let checked = $state<string[]>([]);
  let dossier = $state<Dossier | null>(null);
  let busy = $state(false);
  let asList = $state(typeof matchMedia !== 'undefined' && matchMedia('(max-width: 767px)').matches);
  let err = $state('');
  let rev = $state(0);
  // « Plan formel » (D60): the paper's own statuses — proved / in Mathlib / to prove / formalised / not formalised
  let view = $state<'dossiers' | 'plan'>(route.query.get('view') === 'plan' ? 'plan' : 'dossiers');
  let plan = $state<PaperPlanStatus | null>(null);
  let budget = $state(6);
  $effect(() => app.on('blueprint.updated', () => rev++));
  $effect(() => { void app.m.dossiers; });

  async function loadList() {
    if (!pid) return;
    try { list = (await research.blueprints(pid)).blueprints; if (!sid && list[0]) sid = list[0].source_id; } catch (e) { err = errorText(e); }
  }
  async function load() {
    if (!pid || !sid) { bp = null; return; }
    try {
      const [r, pl] = await Promise.all([research.blueprint(pid, sid), research.paperPlan(pid, sid)]);
      bp = r.blueprint; status = r.status; plan = pl; err = '';
    } catch (e) { err = errorText(e); }
  }
  $effect(() => { void pid; void rev; void loadList(); });
  $effect(() => { void sid; void rev; void load(); });
  // dossier status changes (proofs found) refresh the statuses
  let lastSig = '';
  $effect(() => {
    const sig = Object.values(app.m.dossiers).map((d) => d.status).join();
    if (lastSig && sig !== lastSig) rev++;
    lastSig = sig;
  });

  const node = $derived(bp?.nodes.find((n) => n.id === selected));
  $effect(() => {
    const did = node?.dossier_id;
    dossier = null;
    if (did) api.dossier(did).then((r) => (dossier = r.dossier)).catch(() => {});
  });
  const PATTERN: Record<string, string> = { stated: 'dashed', not_created: 'dotted', statement: '', proved: '', verified: '', defined: '', blocked: 'dashed', failed: '' };
  const PLAN_ST = ['proved', 'in_mathlib', 'to_prove', 'formalised', 'unformalised'] as const;
  const PLAN_PATTERN: Record<string, string> = { proved: '', in_mathlib: '', to_prove: '', formalised: 'dashed', unformalised: 'dotted' };
  // dependency closure of the selection, as the server computes it: explicit edges, proposed ones once accepted
  function closure(ids: string[]): string[] {
    const by = new Map((bp?.nodes ?? []).map((n) => [n.id, n]));
    const seen = new Set<string>();
    const stack = [...ids];
    while (stack.length) {
      const x = stack.pop()!;
      if (seen.has(x) || !by.has(x)) continue;
      seen.add(x);
      for (const u of by.get(x)!.uses) if (!u.rejected && (!u.proposed || u.accepted)) stack.push(u.to);
    }
    return [...seen];
  }
  const closureN = $derived(closure(checked).length);
  const running = $derived(!!plan?.run?.running);
  const gnodes = $derived((bp?.nodes ?? []).map((n) => {
    if (view === 'plan') {
      const ps = plan?.nodes[n.id]?.status ?? 'unformalised';
      return { id: n.id, label: `${n.name} ${n.number}`.trim(), kind: n.kind, cls: `ps-${ps}`, pattern: PLAN_PATTERN[ps], title: `${n.title || n.text.slice(0, 80)} — ${tk(`bp.ps.${ps}`, ps)}` };
    }
    const st = status[n.id]?.state ?? 'not_created';
    return { id: n.id, label: `${n.name} ${n.number}`.trim(), kind: n.kind, cls: `st-${st}`, pattern: PATTERN[st], title: `${n.title || n.text.slice(0, 80)} — ${tk(`bp.state.${st}`, st)}` };
  }));
  const gedges = $derived((bp?.nodes ?? []).flatMap((n) => n.uses.filter((u) => !u.rejected).map((u) => ({ source: n.id, target: u.to, dashed: u.proposed && !u.accepted }))));
  const layout = $derived(layeredLayout(gnodes, gedges, { dx: 250, dy: 70 }));
  const counts = $derived(Object.values(status).reduce((m, s) => ({ ...m, [s.state]: (m[s.state] ?? 0) + 1 }), {} as Record<string, number>));

  async function createDossiers(nodes?: string[]) {
    busy = true;
    try { const r = await research.nodeDossiers(pid, sid, nodes); bp = r.blueprint; toast('ok', t('bp.dossiersMade', { n: r.dossiers.length })); rev++; }
    catch (e) { toast('error', errorText(e)); } finally { busy = false; }
  }
  async function formalise(ids: string[]) {
    const dids = ids.map((id) => bp?.nodes.find((n) => n.id === id)?.dossier_id).filter(Boolean) as string[];
    if (!dids.length) { toast('info', t('bp.needDossiers')); return; }
    busy = true;
    try {
      const r = await research.formalise(pid, dids);
      for (const j of r.jobs) app.m.jobs[j.id] = j;
      toast('ok', t('bp.formaliseStarted', { n: r.jobs.length, b: r.busy.length }));
    } catch (e) { toast('error', errorText(e)); } finally { busy = false; }
  }
  async function planStart() {
    if (!checked.length) return;
    busy = true;
    try { const r = await research.paperPlanStart(pid, sid, checked, budget); if (plan) plan.run = r.run; toast('ok', t('bp.planStarted', { n: r.order.length })); rev++; }
    catch (e) { toast('error', errorText(e)); } finally { busy = false; }
  }
  async function planStop() {
    try { await research.paperPlanStop(pid, sid); rev++; } catch (e) { toast('error', errorText(e)); }
  }
  async function edge(n: BpNode, to: string, action: 'accept' | 'reject' | 'remove') {
    try { bp = (await research.edge(pid, sid, n.id, to, action)).blueprint; rev++; } catch (e) { toast('error', errorText(e)); }
  }
  const titleOf = (id: string) => { const n = bp?.nodes.find((x) => x.id === id); return n ? `${n.name} ${n.number}` : id; };
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="bp">
      <div class="row head">
        <h1>{t('bp.title')}</h1><HelpLink page="sources" />
        <span class="spacer"></span>
        {#if list.length > 1}
          <label class="sr-only" for="bpsel">{t('bp.paper')}</label>
          <select id="bpsel" class="input" style="width:auto" bind:value={sid}>{#each list as b (b.source_id)}<option value={b.source_id}>@{b.paper_key} ({b.nodes})</option>{/each}</select>
        {/if}
      </div>
      <p class="lead">{view === 'plan' ? t('bp.planLead') : t('bp.lead')}</p>
      <div class="seg" role="group" aria-label={t('bp.views')}>
        <button class="btn small" aria-pressed={view === 'dossiers'} onclick={() => (view = 'dossiers')}>{t('bp.viewDossiers')}</button>
        <button class="btn small" aria-pressed={view === 'plan'} onclick={() => (view = 'plan')}>{t('bp.viewPlan')}</button>
      </div>
      {#if err}<p class="error-text">{err}</p>
      {:else if !list.length}
        <div class="empty"><h2>{t('bp.emptyTitle')}</h2><p>{t('bp.emptyText')}</p><a class="btn primary" href="/sources">{t('nav.sources')}</a></div>
      {:else if bp}
        {#if view === 'plan' && plan}
          {@const p = plan.progress}
          <p class="progress"><strong>{t('bp.progress', { done: p.done ?? 0, total: p.total ?? 0 })}</strong>
            <progress max={p.total || 1} value={p.done ?? 0} aria-label={t('bp.progressLabel')}></progress></p>
          <ul class="legend" aria-label={t('bp.planLegend')}>
            {#each PLAN_ST as st}
              <li class="ps-{st}"><span class="sw" aria-hidden="true"></span>{tk(`bp.ps.${st}`, st)}&nbsp;({p[st] ?? 0})</li>
            {/each}
          </ul>
          <div class="row tools">
            <label class="small" for="bpbudget">{t('bp.budget')}</label>
            <input id="bpbudget" class="input" type="number" min="1" max="40" style="width:5em" bind:value={budget} />
            <button class="btn primary" onclick={planStart} disabled={busy || running || !checked.length}>{t('bp.planN', { n: checked.length, c: closureN })}</button>
            {#if running}<button class="btn" onclick={planStop}>{t('bp.planStop')}</button>
              <span class="small" role="status">{t('bp.planRunning', { done: plan.run?.done ?? 0, skipped: plan.run?.skipped ?? 0, total: plan.run?.total ?? 0 })}</span>
            {:else if plan.run?.reason}<span class="small muted" role="status">{tk(`bp.reason.${plan.run.reason}`, plan.run.reason)}</span>{/if}
            <span class="spacer"></span>
            <label class="switch small"><input type="checkbox" bind:checked={asList} />{t('graph.asList')}</label>
            <a class="btn small" href={research.planExportUrl(pid, sid, 'tex')} download>{t('bp.exportTex')}</a>
            <a class="btn small" href={research.planExportUrl(pid, sid, 'html', i18n.base === 'en' ? 'en' : 'fr')} download>{t('bp.exportHtml')}</a>
          </div>
        {:else}
        <ul class="legend" aria-label={t('bp.legend')}>
          {#each ['verified', 'proved', 'defined', 'statement', 'stated', 'blocked', 'failed', 'not_created'] as st}
            <li class="st-{st}"><span class="sw" aria-hidden="true"></span>{tk(`bp.state.${st}`, st)}{#if counts[st]}&nbsp;({counts[st]}){/if}</li>
          {/each}
        </ul>
        {#if bp.warnings.length}<p class="small muted">{bp.warnings.join(' · ')}</p>{/if}
        <div class="row tools">
          <button class="btn" onclick={() => createDossiers()} disabled={busy}>{t('bp.createAll')}</button>
          <button class="btn primary" onclick={() => formalise(checked)} disabled={busy || !checked.length}>{t('bp.formaliseN', { n: checked.length })}</button>
          <label class="switch small"><input type="checkbox" bind:checked={asList} />{t('graph.asList')}</label>
          <span class="xs muted">{t('bp.method', { m: bp.method })}</span>
        </div>
        {/if}
        <div class="split">
          {#if asList}
            <table class="tbl">
              <caption class="sr-only">{t('bp.title')}</caption>
              <thead><tr><th scope="col"><span class="sr-only">{t('bp.select')}</span></th><th scope="col">{t('bp.node')}</th><th scope="col">{t('bp.status')}</th><th scope="col">{t('bp.uses')}</th></tr></thead>
              <tbody>
                {#each bp.nodes as n (n.id)}
                  <tr class:sel={selected === n.id}>
                    <td><label class="cbx"><input type="checkbox" value={n.id} bind:group={checked} aria-label={t('bp.selectOne', { n: `${n.name} ${n.number}` })} /></label></td>
                    <td><button class="linkish" onclick={() => (selected = n.id)}>{n.name} {n.number}</button> <span class="small">{n.title}</span></td>
                    <td>{#if view === 'plan'}<span class="stlabel ps-{plan?.nodes[n.id]?.status ?? 'unformalised'}">{tk(`bp.ps.${plan?.nodes[n.id]?.status ?? 'unformalised'}`, '')}</span>
                      {:else}<span class="stlabel st-{status[n.id]?.state ?? 'not_created'}">{tk(`bp.state.${status[n.id]?.state ?? 'not_created'}`, '')}</span>{/if}</td>
                    <td class="small">{n.uses.filter((u) => !u.rejected).map((u) => titleOf(u.to)).join(', ')}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <SvgGraph nodes={gnodes} edges={gedges} pos={layout.pos} {selected} onselect={(id) => (selected = id)} onopen={(id) => (selected = id)} label={t('bp.title')} arrows nodeW={190} height="60vh" minFit={0.85} />
          {/if}
          <aside class="panel side" aria-live="polite">
            {#if node && view === 'plan'}
              {@const pn = plan?.nodes[node.id]}
              {@const ps = pn?.status ?? 'unformalised'}
              <div class="row"><h2>{node.name} {node.number}{node.title ? ` — ${node.title}` : ''}</h2></div>
              <p><span class="stlabel ps-{ps}">{tk(`bp.ps.${ps}`, '')}</span>
                <label class="switch small"><input type="checkbox" value={node.id} bind:group={checked} />{t('bp.select')}</label></p>
              {#if pn?.rests_on.length}<p class="small warn">{t('bp.restsOn', { d: pn.rests_on.map(titleOf).join(', ') })}</p>{/if}
              {#if pn?.note}<p class="small muted">{tk(`bp.note.${pn.note.split(':')[0]}`, pn.note)}</p>{/if}
              <h3>{t('bp.verbatim')} <span class="xs muted">{pn?.location ?? node.locator}</span></h3>
              <pre class="verbatim">{pn?.verbatim || node.verbatim || node.text}</pre>
              <h3>{t('lean.leanStatement')}</h3>
              {#if pn?.lean && pn.compiled}
                <CodeEditor value={pn.lean} language="lean" readonly label={t('lean.leanStatement')} minLines={3} lineNumbers={false} />
                <p class="xs muted">{t('bp.leanToReread')}{pn.mathlib_name ? ` · ${t('bp.mathlibName', { n: pn.mathlib_name })}` : ''}</p>
              {:else}<p class="small muted">{t('bp.noLeanYet')}</p>{/if}
              {#if pn?.dossier_id}<div class="row"><button class="btn primary small" onclick={() => navigate(`/d/${encodeURIComponent(pn.dossier_id)}`)}>{t('bp.openDossier')}</button></div>{/if}
            {:else if node}
              {@const st = status[node.id]}
              <div class="row"><h2>{node.name} {node.number}{node.title ? ` — ${node.title}` : ''}</h2></div>
              <p><span class="stlabel st-{st?.state ?? 'not_created'}">{tk(`bp.state.${st?.state ?? 'not_created'}`, '')}</span>
                <label class="switch small"><input type="checkbox" value={node.id} bind:group={checked} />{t('bp.select')}</label></p>
              {#if st?.missing_definitions.length}<p class="small warn">{t('bp.missingDefs', { d: st.missing_definitions.map(titleOf).join(', ') })}</p>{/if}
              {#if st?.unverified_uses.length}<p class="small warn">{t('bp.unverifiedUses', { d: st.unverified_uses.map(titleOf).join(', ') })}</p>{/if}
              <div class="cmp">
                <div><h3>{t('bp.paperText')} <span class="xs muted">{node.locator}</span></h3><div class="theorem"><Md src={node.text} cls="th-body" /></div>
                  {#if node.proof}<details><summary class="small">{t('bp.paperProof')}</summary><Md src={node.proof} /></details>{/if}</div>
                <div><h3>{t('lean.leanStatement')}</h3>
                  {#if dossier?.current.statement}<CodeEditor value={dossier.current.statement} language="lean" readonly label={t('lean.leanStatement')} minLines={3} lineNumbers={false} workspace={dossier.workspace} />
                  {:else}<p class="small muted">{node.dossier_id ? t('bp.noLeanYet') : t('bp.noDossier')}</p>{/if}
                </div>
              </div>
              {#if node.uses.length}
                <h3>{t('bp.uses')}</h3>
                <ul class="uses">
                  {#each node.uses as u}
                    <li class:rejected={u.rejected}>{titleOf(u.to)} <span class="xs muted">{tk(`bp.via.${u.via}`, u.via)}{u.proposed && !u.accepted ? ` · ${t('bp.proposed')}` : ''}</span>
                      {#if u.proposed && !u.accepted && !u.rejected}<button class="btn small" onclick={() => edge(node, u.to, 'accept')}>{t('bp.accept')}</button><button class="btn small quiet" onclick={() => edge(node, u.to, 'reject')}>{t('bp.reject')}</button>{/if}
                    </li>
                  {/each}
                </ul>
              {/if}
              <div class="row">
                {#if node.dossier_id}<button class="btn primary small" onclick={() => navigate(`/d/${encodeURIComponent(node.dossier_id)}`)}>{t('bp.openDossier')}</button>
                  <button class="btn small" onclick={() => formalise([node.id])} disabled={busy}>{t('bp.formaliseOne')}</button>
                {:else}<button class="btn small" onclick={() => createDossiers([node.id])} disabled={busy}>{t('bp.createOne')}</button>{/if}
              </div>
              <p class="xs muted">{t('bp.paperHintNote')}</p>
            {:else}<p class="small muted">{t('bp.pick')}</p>{/if}
          </aside>
        </div>
      {/if}
    </div>
  {/snippet}
</ProjectGate>

<style>
  .head h1 { margin: 0; }
  .lead { color: var(--text-2); max-width: var(--measure); }
  .legend { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: var(--fs-xs); margin: 0 0 var(--s-2); }
  .legend li { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 22px; height: 12px; border-radius: 3px; border: 1.5px solid var(--line-strong); }
  .seg { display: inline-flex; gap: 4px; margin-bottom: var(--s-2); }
  .seg .btn[aria-pressed='true'] { background: var(--accent-soft); border-color: var(--accent); font-weight: 700; }
  .progress { display: flex; align-items: center; gap: var(--s-2); flex-wrap: wrap; margin: 0 0 var(--s-2); }
  .progress progress { width: min(240px, 40vw); }
  .verbatim { white-space: pre-wrap; overflow-wrap: anywhere; font-size: var(--fs-xs); background: var(--accent-soft); padding: 6px 8px; border-radius: 6px; margin: 0; }
  .ps-proved .sw, .ps-in_mathlib .sw { background: var(--proved-soft); border-color: var(--proved); }
  .ps-in_mathlib .sw { border-width: 2.5px; }
  .ps-to_prove .sw { background: var(--running-soft); border-color: var(--running); }
  .ps-formalised .sw { background: var(--accent-soft); border-color: var(--accent); border-style: dashed; }
  .ps-unformalised .sw { border-style: dotted; }
  .stlabel.ps-proved, .stlabel.ps-in_mathlib { color: var(--proved); border-color: var(--proved); }
  .stlabel.ps-to_prove { color: var(--running); border-color: var(--running); }
  .stlabel.ps-formalised { color: var(--accent); border-color: var(--accent); border-style: dashed; }
  .stlabel.ps-unformalised { border-style: dotted; color: var(--text-2); }
  .st-verified .sw { background: var(--proved-soft); border: 2.5px solid var(--proved); }
  .st-proved .sw { background: var(--proved-soft); border-color: var(--proved); }
  .st-defined .sw { background: var(--local-soft); border-color: var(--local); }
  .st-statement .sw { background: var(--accent-soft); border-color: var(--accent); }
  .st-stated .sw { border-style: dashed; }
  .st-not_created .sw { border-style: dotted; }
  .st-blocked .sw { background: var(--running-soft); border-color: var(--running); border-style: dashed; }
  .st-failed .sw { background: var(--failed-soft); border-color: var(--failed); }
  .stlabel { font-size: var(--fs-xs); font-weight: 700; padding: 2px 8px; border-radius: 999px; border: 1.5px solid var(--line-strong); }
  .stlabel.st-verified, .stlabel.st-proved { color: var(--proved); border-color: var(--proved); }
  .stlabel.st-statement { color: var(--accent); border-color: var(--accent); }
  .stlabel.st-defined { color: var(--local); border-color: var(--local); }
  .stlabel.st-blocked { color: var(--running); border-color: var(--running); border-style: dashed; }
  .stlabel.st-failed { color: var(--failed); border-color: var(--failed); }
  .stlabel.st-stated, .stlabel.st-not_created { border-style: dashed; color: var(--text-2); }
  .tools { margin-bottom: var(--s-2); }
  .split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, 420px); gap: var(--s-3); align-items: start; }
  @media (max-width: 1100px) { .split { grid-template-columns: minmax(0, 1fr); } }
  .side h2 { font-size: var(--fs-md); margin: 0; }
  .side h3 { font-size: var(--fs-sm); margin: var(--s-3) 0 4px; }
  .warn { color: var(--running); }
  .cmp { display: grid; gap: var(--s-2); }
  .uses { padding-left: 1.2em; margin: 0; }
  .uses li.rejected { text-decoration: line-through; color: var(--text-3); }
  .tbl { width: 100%; border-collapse: collapse; table-layout: fixed; overflow-wrap: anywhere; }
  .tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .tbl tr.sel { background: var(--accent-soft); }
  .linkish { background: none; border: 0; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; }
  .cbx { display: inline-grid; place-items: center; min-width: 32px; min-height: 32px; cursor: pointer; }
  @media (pointer: coarse) { .cbx { min-width: var(--touch); min-height: var(--touch); } .linkish { min-height: var(--touch); text-align: left; } }
  .empty { max-width: 34rem; }
</style>
