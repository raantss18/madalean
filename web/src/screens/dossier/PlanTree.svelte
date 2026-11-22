<script lang="ts">
  // Proof plan as a mind map (S-L). One obvious path: « Découper ce théorème » → read and adjust the lemmas →
  // « Valider le plan » → « Prouver le plan » → Madalean proves each lemma and combines them; it only comes back
  // when a lemma fails (another track, split further, or leave a hole). A hole makes the theorem CONDITIONAL —
  // never shown as verified (badge + words + dashed border, not colour alone).
  import type { Dossier } from '../../lib/api/types';
  import { ApiError } from '../../lib/api/client';
  import { research, type Plan, type PlanNode } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { t, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import PlanMap from './PlanMap.svelte';
  import PlanOutline from './PlanOutline.svelte';
  import PlanPanel from './PlanPanel.svelte';

  let { dossier: d }: { dossier: Dossier } = $props();
  let plan = $state<Plan | null>(null);
  let missing = $state(false);
  let busy = $state('');
  let hint = $state('');
  let selected = $state('');
  let editing = $state<{ id: string; title: string; statement_nl: string; why: string; lean: string; combination: string | null } | null>(null);
  let adding = $state<{ parent: string; title: string; statement_nl: string; lean: string } | null>(null);
  let overwrite = $state(false);
  let versionsOpen = $state(false);
  function initialView(): 'map' | 'list' {
    try { const v = localStorage.getItem('madalean.planView'); if (v === 'map' || v === 'list') return v; } catch { /* storage blocked */ }
    return typeof window !== 'undefined' && window.matchMedia?.('(max-width: 767px)').matches ? 'list' : 'map';
  }
  let view = $state<'map' | 'list'>(initialView());
  function setView(v: 'map' | 'list') { view = v; try { localStorage.setItem('madalean.planView', v); } catch { /* ignore */ } }

  async function load() {
    try { plan = (await research.plan(d.id)).plan; missing = false; }
    catch (e) { if (e instanceof ApiError && e.status === 404) { plan = null; missing = true; } else toast('error', errorText(e)); }
  }
  $effect(() => { void d.id; void load(); });
  $effect(() => app.on('plan.updated', (ev) => { const e = ev as unknown as { dossier_id: string; plan: Plan }; if (e.dossier_id === d.id) { plan = e.plan; missing = false; } }));

  async function run(name: string, fn: () => Promise<unknown>, ok?: string) {
    busy = name;
    try {
      const r = await fn();
      if (r && typeof r === 'object' && 'plan' in r && (r as { plan: Plan | null }).plan) { plan = (r as { plan: Plan }).plan; missing = false; }
      if (ok) toast('ok', ok);
    } catch (e) {
      if (e instanceof ApiError && e.kind === 'conflict') { toast('warn', t('plan.changedElsewhere')); await load(); }
      else if (e instanceof ApiError && e.kind === 'would_overwrite') overwrite = true;
      else toast('error', errorText(e));
    } finally { busy = ''; }
  }
  const rev = () => plan?.rev ?? 0;
  // a lemma of a plan is split inside that plan (one tree, one set of limits)
  const link = $derived((d['extra'] as { plan?: { plan_dossier?: string } } | undefined)?.plan?.plan_dossier ?? '');
  const root = $derived(plan ? plan.nodes[plan.root] : undefined);
  const S = $derived(plan?.summary);
  const analysing = $derived(busy === 'analyse' || Boolean(S?.analysing));
  const running = $derived(Boolean(S?.run && !S.run.stopped && !S.run.finished));
  $effect(() => { if (plan && selected && !plan.nodes[selected.split('#')[0]!]) selected = ''; });

  function split(force = false) { void run('analyse', () => research.analysePlan(d.id, { hint, ...(force ? { force: true } : {}) }), t('plan.analysed')); }
  function counts(): string {
    if (!S) return '';
    const parts = [t('plan.count', { proved: S.proved, lemmas: S.lemmas })];
    if (S.running) parts.push(t('plan.countRunning', { n: S.running }));
    if (S.failed) parts.push(t('plan.countFailed', { n: S.failed }));
    if (S.holes) parts.push(t('plan.countHoles', { n: S.holes }));
    if (S.to_validate) parts.push(t('plan.countToValidate', { n: S.to_validate }));
    return parts.join(', ');
  }
  function edit(n: PlanNode) {
    const tr = (n.tracks ?? []).find((x) => x.id === n.active_track);
    editing = { id: n.id, title: n.title, statement_nl: n.statement_nl, why: n.why, lean: n.lean, combination: tr && n.children.length ? tr.combination : null };
    editOrig = { ...editing };
  }
  // S-AK: the node editor saves when it closes, however it is closed (« Fermer », Escape, a click outside):
  // nothing typed is lost, and nothing is sent when nothing changed.
  let editOrig: NonNullable<typeof editing> | null = null;
  function commitEdit() {
    const e = editing, o = editOrig;
    editing = null; editOrig = null;
    if (!e || !o) return;
    const changed = (['title', 'statement_nl', 'why', 'lean', 'combination'] as const).some((k) => e[k] !== o[k]);
    if (!changed) return;
    const p: Record<string, unknown> = { base_rev: rev(), title: e.title, statement_nl: e.statement_nl, why: e.why };
    if (e.lean !== o.lean) p['lean'] = e.lean;
    if (e.combination !== null && e.combination !== o.combination) p['combination'] = e.combination;
    void run('edit', () => research.patchPlanNode(d.id, e.id, p as { base_rev: number }));
  }
</script>

<section class="plan" aria-labelledby="plan-h">
  <div class="row"><h2 id="plan-h">{t('plan.title')}</h2><HelpLink page="proof-plans" />
    <span class="spacer"></span>
    {#if plan}<button class="btn small quiet" onclick={() => (versionsOpen = true)}><Icon name="history" size={14} />{t('versions.button', { n: plan.versions.length })}</button>{/if}
  </div>

  {#if link && missing}
    <div class="start">
      <p>{t('plan.inPlan')}</p>
      <div class="row"><a class="btn primary big" href="/d/{encodeURIComponent(link)}/plan"><Icon name="tree" size={18} />{t('plan.openParentPlan')}</a></div>
    </div>
  {:else if missing || (plan && root && !root.children.length && !(root.tracks ?? []).length)}
    <div class="start">
      <p class="lead">{t('plan.lead2')}</p>
      <div class="field"><label for="plan-hint">{t('plan.hint')}</label><input id="plan-hint" class="input" bind:value={hint} placeholder={t('plan.hintPlaceholder')} disabled={analysing} /></div>
      <div class="row">
        <button class="btn primary big" onclick={() => split(false)} disabled={!!busy || analysing || !d.statements.length}><Icon name="split" size={18} />{analysing ? t('plan.splitting') : t('plan.split')}</button>
        {#if missing}<button class="btn quiet" onclick={() => run('new', () => research.newPlan(d.id))} disabled={!!busy}>{t('plan.empty')}</button>{/if}
      </div>
      {#if analysing}<p class="small muted" role="status">{t('plan.splitting')}</p>{/if}
      {#if !d.statements.length}<p class="small muted">{t('proof.needStatement')}</p>{/if}
    </div>
  {/if}

  {#if plan && root && (root.children.length || (root.tracks ?? []).length)}
    <div class="where ui-{S?.next}" role="status">
      <p class="next"><Icon name={S?.next === 'done' ? 'check' : S?.next === 'fix' || S?.next === 'conditional' ? 'warn' : S?.next === 'wait' ? 'activity' : 'info'} size={18} />
        <span>{analysing ? t('plan.splitting') : S?.next === 'conditional' ? t('plan.where.conditional', { n: S.holes }) : t(`plan.where.${S?.next ?? 'validate'}` as 'plan.where.validate')}</span></p>
      <p class="small counts">{counts()}</p>
      <p class="xs muted">{t('plan.limits', { depth: S?.depth ?? 0, maxDepth: S?.max_depth ?? 3, nodes: S?.nodes ?? 0, maxNodes: S?.max_nodes ?? 30 })}</p>
    </div>
    {#if plan.verdict.state === 'proved_modulo'}
      <div class="verdict conditional" role="note"><span class="badge"><Icon name="warn" size={16} />{t('plan.conditionalBadge', { n: plan.verdict.admitted })}</span>
        <p class="small">{t('plan.conditionalText', { n: plan.verdict.admitted, names: (plan.verdict.admitted_names ?? []).join(', ') })}</p></div>
    {/if}

    <div class="row ctas">
      {#if S && S.to_validate > 0}
        <button class="btn primary big" disabled={!!busy || analysing} onclick={() => run('validate', () => research.validatePlan(d.id, rev()), t('plan.validatedToast'))}><Icon name="check" size={18} />{t('plan.validate')}</button>
      {/if}
      {#if S && !['done', 'wait'].includes(S.next) && !running}
        <button class="btn big {S.to_validate > 0 ? '' : 'primary'}" disabled={!!busy || analysing || S.lemmas === 0} onclick={() => run('prove', () => research.provePlan(d.id, rev()), t('plan.provingToast'))}><Icon name="play" size={18} />{t('plan.prove')}</button>
      {/if}
      {#if running}<button class="btn danger" disabled={!!busy} onclick={() => run('cancel', () => research.cancelPlanNode(d.id, plan!.root), t('plan.cancelled'))}><Icon name="stop" size={16} />{t('plan.stopRun')}</button>{/if}
      <span class="spacer"></span>
      <div class="seg" role="radiogroup" aria-label={t('plan.viewLabel')}>
        <label class:on={view === 'map'}><input type="radio" name="plan-view-{d.id}" checked={view === 'map'} onchange={() => setView('map')} /><Icon name="tree" size={14} />{t('plan.view.map')}</label>
        <label class:on={view === 'list'}><input type="radio" name="plan-view-{d.id}" checked={view === 'list'} onchange={() => setView('list')} /><Icon name="list" size={14} />{t('plan.view.list')}</label>
      </div>
    </div>

    <div class="body" class:with-panel={Boolean(selected)}>
      <div class="view">
        {#if view === 'map'}<PlanMap {plan} {selected} onselect={(k) => (selected = k)} />
        {:else}<PlanOutline {plan} {selected} onselect={(k) => (selected = k)} />{/if}
        {#if !selected}<p class="small muted pick">{t('plan.select')}</p>{/if}
      </div>
      {#if selected}
        <PlanPanel {plan} did={d.id} sel={selected} {busy} {run} onselect={(k) => (selected = k)} onedit={edit}
          onadd={(p) => (adding = { parent: p, title: '', statement_nl: '', lean: '' })} onclose={() => (selected = '')} />
      {/if}
    </div>
    <div class="row more">
      <button class="btn small quiet" disabled={!!busy || analysing} onclick={() => split(true)}><Icon name="split" size={14} />{t('plan.resplitRoot')}</button>
      <span class="xs muted">{t('plan.limit', { n: plan.limit })}</span>
    </div>
  {:else if !missing && !plan}
    <p class="muted" aria-busy="true">{t('common.loading')}</p>
  {/if}
</section>

<Dialog open={Boolean(editing)} title={t('plan.editTitle')} wide onclose={commitEdit}>
  {#if editing}
    <div class="field"><label for="pe-t">{t('plan.nodeTitle')}</label><input id="pe-t" class="input" bind:value={editing.title} /></div>
    <div class="field"><label for="pe-s">{t('plan.nodeStatement')}</label><textarea id="pe-s" class="input" rows="3" bind:value={editing.statement_nl}></textarea></div>
    <div class="field"><label for="pe-w">{t('plan.why2')}</label><input id="pe-w" class="input" bind:value={editing.why} /></div>
    <div class="field"><label for="pe-l">{t('plan.nodeLean')}</label><textarea id="pe-l" class="input mono" rows="3" bind:value={editing.lean}></textarea></div>
    {#if editing.combination !== null}<div class="field"><label for="pe-c">{t('plan.editCombination')}</label><textarea id="pe-c" class="input mono" rows="5" bind:value={editing.combination}></textarea></div>{/if}
  {/if}
  {#snippet actions()}
    <button class="btn primary" onclick={commitEdit}>{t('plan.closeSaves')}</button>
  {/snippet}
</Dialog>
<Dialog open={Boolean(adding)} title={t('plan.addChild')} onclose={() => (adding = null)}>
  {#if adding}
    <div class="field"><label for="pa-t">{t('plan.nodeTitle')}</label><input id="pa-t" class="input" bind:value={adding.title} /></div>
    <div class="field"><label for="pa-s">{t('plan.nodeStatement')}</label><textarea id="pa-s" class="input" rows="3" bind:value={adding.statement_nl}></textarea></div>
    <div class="field"><label for="pa-l">{t('plan.nodeLean')}</label><textarea id="pa-l" class="input mono" rows="2" bind:value={adding.lean}></textarea></div>
  {/if}
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (adding = null)}>{t('common.cancel')}</button>
    <button class="btn primary" onclick={() => { const a = adding!; adding = null; if (a.title.trim()) void run('add', () => research.addPlanNode(d.id, { base_rev: rev(), parent: a.parent, title: a.title.trim(), statement_nl: a.statement_nl, lean: a.lean })); }}>{t('plan.add')}</button>
  {/snippet}
</Dialog>
<Dialog bind:open={overwrite} title={t('plan.overwriteTitle')}>
  <p>{t('plan.overwriteText')}</p>
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (overwrite = false)}>{t('article.keepMine')}</button>
    <button class="btn primary" onclick={() => { overwrite = false; void run('analyse', () => research.analysePlan(d.id, { hint, force: true })); }}>{t('plan.redraftAnyway')}</button>
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
  .plan { container-type: inline-size; display: grid; gap: var(--s-3); }
  .plan h2 { margin: 0; }
  .start { display: grid; gap: var(--s-3); max-width: 60ch; }
  .lead { margin: 0; font-family: var(--font-serif); font-size: var(--fs-lg); line-height: 1.5; }
  .big { min-height: 48px; padding: 0 20px; font-size: var(--fs-md); font-weight: 700; }
  .where { border-left: 4px solid var(--accent); background: var(--surface); border-radius: 0 var(--r-2) var(--r-2) 0; padding: var(--s-2) var(--s-3); }
  .where p { margin: 0; }
  .where .next { display: flex; gap: 8px; align-items: flex-start; font-weight: 700; font-size: var(--fs-md); }
  .where .next :global(.ico) { flex: none; margin-top: 2px; }
  .where .counts { margin-top: 2px; color: var(--text-2); }
  .where.ui-done { border-left-color: var(--proved); }
  .where.ui-fix { border-left-color: var(--failed); }
  .where.ui-conditional, .where.ui-wait { border-left-color: var(--running-fill); }
  .verdict { border-radius: var(--r-2); padding: var(--s-2) var(--s-3); border: 2px solid; }
  .verdict p { margin: 4px 0 0; }
  .verdict.conditional { border: 2px dashed var(--running-fill); background: var(--running-soft); color: var(--running); }
  .badge { display: inline-flex; gap: 6px; align-items: center; font-weight: 800; }
  .ctas { gap: var(--s-2); align-items: center; }
  .seg { display: inline-flex; border: 1.5px solid var(--line-strong); border-radius: var(--r-2); overflow: hidden; }
  .seg label { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; min-height: 36px; cursor: pointer; font-size: var(--fs-sm); font-weight: 600; color: var(--text-2); }
  .seg label.on { background: var(--ink); color: var(--on-ink); }
  .seg input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .seg label:has(input:focus-visible) { outline: 3px solid var(--focus); outline-offset: -3px; }
  .body { display: grid; gap: var(--s-3); grid-template-columns: minmax(0, 1fr); align-items: start; }
  @container (min-width: 900px) { .body.with-panel { grid-template-columns: minmax(0, 1fr) 360px; } }
  .view { min-width: 0; }
  .pick { margin: var(--s-2) 0 0; }
  .more { gap: var(--s-2); }
  .vers { padding-left: 1.2em; display: grid; gap: 6px; }
</style>
