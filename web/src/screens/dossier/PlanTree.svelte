<script lang="ts">
  // Proof plan: a tree of claims the AI proposes and you curate (accept, edit, reorder, add, delete), run in parallel
  // as sub-dossiers, follow live, cancel a subtree, re-plan a failed node, or admit a lemma « for now ».
  // A proof that relies on admitted lemmas is CONDITIONAL: it is never shown as verified (badge + text + colour).
  import type { Dossier } from '../../lib/api/types';
  import { ApiError } from '../../lib/api/client';
  import { research, type Plan, type PlanNode } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { dossier: d }: { dossier: Dossier } = $props();
  let plan = $state<Plan | null>(null);
  let missing = $state(false);
  let busy = $state('');
  let hint = $state('');
  let editing = $state<{ id: string; title: string; statement_nl: string; why: string; lean: string } | null>(null);
  let adding = $state<{ parent: string; title: string; statement_nl: string } | null>(null);
  let overwrite = $state(false);
  let versionsOpen = $state(false);

  async function load() {
    try { plan = (await research.plan(d.id)).plan; missing = false; }
    catch (e) { if (e instanceof ApiError && (e.status === 404)) { plan = null; missing = true; } else toast('error', errorText(e)); }
  }
  $effect(() => { void d.id; void load(); });
  $effect(() => app.on('plan.updated', (ev) => { const e = ev as unknown as { dossier_id: string; plan: Plan }; if (e.dossier_id === d.id) plan = e.plan; }));

  async function run(name: string, fn: () => Promise<{ plan: Plan } | unknown>, ok?: string) {
    busy = name;
    try {
      const r = await fn();
      if (r && typeof r === 'object' && 'plan' in r) plan = (r as { plan: Plan }).plan;
      if (ok) toast('ok', ok);
    } catch (e) {
      if (e instanceof ApiError && e.kind === 'conflict') { toast('warn', t('plan.changedElsewhere')); await load(); }
      else if (e instanceof ApiError && e.kind === 'would_overwrite') overwrite = true;
      else toast('error', errorText(e));
    } finally { busy = ''; }
  }
  const rev = () => plan?.rev ?? 0;
  const nodes = $derived(plan?.nodes ?? {});
  const root = $derived(plan ? nodes[plan.root] : undefined);
  const drafts = $derived(Object.values(nodes).filter((n) => n.state === 'draft').map((n) => n.id));
  const accepted = $derived(Object.values(nodes).filter((n) => n.state === 'accepted' && n.id !== plan?.root));
  function stateClass(n: PlanNode): string {
    if (n.admitted) return 'admitted';
    if (n.state === 'proved_modulo') return 'conditional';
    return n.state;
  }
  function move(n: PlanNode, delta: number) {
    if (!n.parent) return;
    const sib = nodes[n.parent]!.children;
    const i = sib.indexOf(n.id) + delta;
    if (i < 0 || i >= sib.length) return;
    void run('move', () => research.movePlanNode(d.id, n.id, { base_rev: rev(), parent: n.parent!, index: i }));
  }
</script>

<section class="plan" aria-labelledby="plan-h">
  <div class="row"><h2 id="plan-h">{t('plan.title')}</h2><HelpLink page="proof-plans" />
    <span class="spacer"></span>
    {#if plan}<button class="btn small quiet" onclick={() => (versionsOpen = true)}><Icon name="history" size={14} />{t('versions.button', { n: plan.versions.length })}</button>{/if}
  </div>
  <p class="hint">{t('plan.lead')}</p>

  {#if missing}
    <div class="panel">
      <p>{t('plan.none')}</p>
      <div class="field"><label for="plan-hint">{t('plan.hint')}</label><input id="plan-hint" class="input" bind:value={hint} placeholder={t('plan.hintPlaceholder')} /></div>
      <div class="row">
        <button class="btn primary" onclick={() => run('draft', () => research.draftPlan(d.id, { hint }), t('plan.drafted'))} disabled={!!busy || !d.statements.length}>{busy === 'draft' ? t('plan.drafting') : t('plan.draft')}</button>
        <button class="btn" onclick={() => run('new', () => research.newPlan(d.id))} disabled={!!busy}>{t('plan.empty')}</button>
      </div>
      {#if !d.statements.length}<p class="small muted">{t('proof.needStatement')}</p>{/if}
    </div>
  {:else if plan && root}
    {#if plan.verdict.state === 'proved_modulo'}
      <div class="verdict conditional" role="status">
        <span class="badge"><Icon name="warn" size={16} />{t('plan.conditional')}</span>
        <p>{t('plan.conditionalText', { n: plan.verdict.admitted, names: (plan.verdict.admitted_names ?? []).join(', ') })}</p>
      </div>
    {:else if plan.verdict.state === 'proved' && plan.verdict.verified}
      <div class="verdict proved" role="status"><span class="badge"><Icon name="check" size={16} />{t('plan.verified')}</span></div>
    {/if}

    <div class="row tools">
      {#if drafts.length}<button class="btn small" onclick={() => run('accept', () => research.acceptPlan(d.id, rev(), drafts))} disabled={!!busy}>{t('plan.acceptAll', { n: drafts.length })}</button>{/if}
      <button class="btn small primary" onclick={() => run('submit', () => research.submitPlan(d.id, rev()), t('plan.submitted'))} disabled={!!busy || !accepted.length}>{t('plan.submit', { n: accepted.length })}</button>
      <button class="btn small" onclick={() => run('modulo', () => research.proveModulo(d.id), t('plan.moduloTried'))} disabled={!!busy}>{t('plan.proveModulo')}</button>
      <button class="btn small quiet" onclick={() => run('draft', () => research.draftPlan(d.id, { hint }))} disabled={!!busy}>{t('plan.redraft')}</button>
      <span class="xs muted">{t('plan.limit', { n: plan.limit })}</span>
    </div>

    <ul class="tree" role="tree" aria-label={t('plan.title')}>
      {@render nodeView(root, 0)}
    </ul>
  {:else}
    <p class="muted" aria-busy="true">{t('common.loading')}</p>
  {/if}
</section>

{#snippet nodeView(n: PlanNode, depth: number)}
  <li role="treeitem" aria-expanded={n.children.length ? true : undefined} aria-selected="false" class="node s-{stateClass(n)}">
    <div class="card">
      <div class="row">
        <span class="st s-{stateClass(n)}">{n.admitted ? t('plan.admittedBadge') : tk(`plan.state.${n.state}`, n.state)}</span>
        <strong>{n.title}</strong>
        {#if n.edited}<span class="xs muted">{t('plan.edited')}</span>{/if}
        <span class="spacer"></span>
        {#if n.dossier_id && n.dossier_id !== d.id}<a class="btn small quiet" href="/d/{encodeURIComponent(n.dossier_id)}">{t('plan.openDossier')}</a>{/if}
      </div>
      {#if n.statement_nl}<div class="small stmt"><Md src={n.statement_nl} /></div>{/if}
      {#if n.why}<p class="xs muted">{t('plan.why')} : {n.why}</p>{/if}
      {#if n.lean}<pre class="lean">{n.lean}</pre>{/if}
      {#if n.admitted}<p class="xs warn">{t('plan.admittedNote')}</p>{/if}
      <div class="row acts">
        {#if n.state === 'draft'}
          <button class="btn small" onclick={() => run('acc', () => research.acceptPlan(d.id, rev(), [n.id]))}>{t('plan.accept')}</button>
          <button class="btn small quiet" onclick={() => run('rej', () => research.rejectPlan(d.id, rev(), [n.id]))}>{t('plan.reject')}</button>
        {/if}
        <button class="btn small quiet" onclick={() => (editing = { id: n.id, title: n.title, statement_nl: n.statement_nl, why: n.why, lean: n.lean })}>{t('common.edit')}</button>
        <button class="btn small quiet" onclick={() => (adding = { parent: n.id, title: '', statement_nl: '' })}>{t('plan.addChild')}</button>
        {#if n.parent}
          <button class="btn small quiet icon" onclick={() => move(n, -1)} aria-label={t('plan.up')}><Icon name="chevronUp" size={14} /></button>
          <button class="btn small quiet icon" onclick={() => move(n, 1)} aria-label={t('plan.down')}><Icon name="chevronDown" size={14} /></button>
        {/if}
        {#if ['queued', 'proving', 'submitted'].includes(n.state)}<button class="btn small danger" onclick={() => run('cancel', () => research.cancelPlanNode(d.id, n.id), t('plan.cancelled'))}><Icon name="stop" size={12} />{t('plan.cancelSubtree')}</button>{/if}
        {#if n.state === 'failed' || n.state === 'stopped'}<button class="btn small" onclick={() => run('replan', () => research.replanNode(d.id, n.id, rev()))}>{t('plan.replan')}</button>{/if}
        {#if n.parent && !n.proved}
          {#if n.admitted}<button class="btn small quiet" onclick={() => run('unadmit', () => research.admitNode(d.id, n.id, rev(), true))}>{t('plan.unadmit')}</button>
          {:else}<button class="btn small quiet" onclick={() => run('admit', () => research.admitNode(d.id, n.id, rev()))} title={t('plan.admitHint')}>{t('plan.admit')}</button>{/if}
        {/if}
        {#if n.parent}<button class="btn small quiet icon" onclick={() => run('del', () => research.deletePlanNode(d.id, n.id, rev()), t('plan.deleted'))} aria-label={t('plan.delete', { title: n.title })}><Icon name="trash" size={14} /></button>{/if}
      </div>
    </div>
    {#if n.children.length}
      <ul role="group">
        {#each n.children as cid (cid)}{#if nodes[cid]}{@render nodeView(nodes[cid]!, depth + 1)}{/if}{/each}
      </ul>
    {/if}
  </li>
{/snippet}

<Dialog open={Boolean(editing)} title={t('plan.editTitle')} onclose={() => (editing = null)}>
  {#if editing}
    <div class="field"><label for="pe-t">{t('plan.nodeTitle')}</label><input id="pe-t" class="input" bind:value={editing.title} /></div>
    <div class="field"><label for="pe-s">{t('plan.nodeStatement')}</label><textarea id="pe-s" class="input" rows="3" bind:value={editing.statement_nl}></textarea></div>
    <div class="field"><label for="pe-w">{t('plan.why')}</label><input id="pe-w" class="input" bind:value={editing.why} /></div>
    <div class="field"><label for="pe-l">{t('plan.nodeLean')}</label><textarea id="pe-l" class="input mono" rows="3" bind:value={editing.lean}></textarea></div>
  {/if}
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (editing = null)}>{t('common.cancel')}</button>
    <button class="btn primary" onclick={() => { const e = editing!; editing = null; void run('edit', () => research.patchPlanNode(d.id, e.id, { base_rev: rev(), title: e.title, statement_nl: e.statement_nl, why: e.why, lean: e.lean })); }}>{t('common.save')}</button>
  {/snippet}
</Dialog>
<Dialog open={Boolean(adding)} title={t('plan.addChild')} onclose={() => (adding = null)}>
  {#if adding}
    <div class="field"><label for="pa-t">{t('plan.nodeTitle')}</label><input id="pa-t" class="input" bind:value={adding.title} /></div>
    <div class="field"><label for="pa-s">{t('plan.nodeStatement')}</label><textarea id="pa-s" class="input" rows="3" bind:value={adding.statement_nl}></textarea></div>
  {/if}
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (adding = null)}>{t('common.cancel')}</button>
    <button class="btn primary" onclick={() => { const a = adding!; adding = null; if (a.title.trim()) void run('add', () => research.addPlanNode(d.id, { base_rev: rev(), parent: a.parent, title: a.title.trim(), statement_nl: a.statement_nl })); }}>{t('plan.add')}</button>
  {/snippet}
</Dialog>
<Dialog bind:open={overwrite} title={t('plan.overwriteTitle')}>
  <p>{t('plan.overwriteText')}</p>
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (overwrite = false)}>{t('article.keepMine')}</button>
    <button class="btn primary" onclick={() => { overwrite = false; void run('draft', () => research.draftPlan(d.id, { hint, force: true })); }}>{t('plan.redraftAnyway')}</button>
  {/snippet}
</Dialog>
<Dialog bind:open={versionsOpen} title={t('plan.versionsTitle')}>
  {#if plan}
    <ol class="vers" reversed>
      {#each [...plan.versions].reverse() as v (v.rev)}
        <li>{t('notes.rev', { rev: v.rev })} · {fmtTime(v.t)} · {v.source}{v.model ? ` (${v.model})` : ''}
          {#if v.rev !== plan.rev}<button class="btn small" onclick={() => { versionsOpen = false; void run('restore', () => research.restorePlanVersion(d.id, v.rev)); }}>{t('versions.restore')}</button>{/if}</li>
      {/each}
    </ol>
  {/if}
</Dialog>

<style>
  .plan h2 { margin: 0; }
  .tools { margin: var(--s-2) 0 var(--s-3); }
  .verdict { border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin: var(--s-2) 0; border: 2px solid; }
  .verdict p { margin: 4px 0 0; }
  .verdict.conditional { border-color: var(--running-fill); background: var(--running-soft); color: var(--running); }
  .verdict.proved { border-color: var(--proved); background: var(--proved-soft); color: var(--proved); }
  .badge { display: inline-flex; gap: 6px; align-items: center; font-weight: 800; text-transform: none; }
  .tree, .tree ul { list-style: none; margin: 0; padding: 0; }
  .tree ul { margin-left: var(--s-4); padding-left: var(--s-3); border-left: 2px solid var(--line); }
  .card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin: var(--s-2) 0; }
  .node.s-draft > .card { border-style: dashed; }
  .node.s-proved > .card { border-color: var(--proved); }
  .node.s-failed > .card { border-color: var(--failed); }
  .node.s-admitted > .card, .node.s-conditional > .card { border: 2px dashed var(--running-fill); }
  .st { font-size: var(--fs-xs); font-weight: 700; padding: 1px 8px; border-radius: 999px; border: 1.5px solid var(--line-strong); color: var(--text-2); }
  .st.s-proved { color: var(--proved); border-color: var(--proved); }
  .st.s-failed { color: var(--failed); border-color: var(--failed); }
  .st.s-proving, .st.s-queued, .st.s-submitted { color: var(--running); border-color: var(--running); }
  .st.s-admitted, .st.s-conditional { color: var(--running); border: 1.5px dashed var(--running); background: var(--running-soft); }
  .stmt { margin: 4px 0; }
  .lean { font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2); padding: 4px 8px; border-radius: var(--r-1); margin: 4px 0; }
  .warn { color: var(--running); font-weight: 600; }
  .acts { gap: 2px; }
  .vers { padding-left: 1.2em; display: grid; gap: 6px; }
</style>
