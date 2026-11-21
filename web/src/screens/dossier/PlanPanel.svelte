<script lang="ts">
  // Detail of the selected node (or alternative track): where it sits (breadcrumb), what it says (words, Lean), why
  // it helps, what Lean said, and the actions. A failed lemma lists the three ways out, in order.
  import type { Plan, PlanNode } from '../../lib/api/research';
  import { research } from '../../lib/api/research';
  import { t } from '../../lib/i18n/index.svelte';
  import { pathTo, otherTracks } from '../../lib/plan/layout';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import PlanStatus from './PlanStatus.svelte';

  let { plan, did, sel, busy, run, onselect, onedit, onadd, onclose }: {
    plan: Plan; did: string; sel: string; busy: string;
    run: (name: string, fn: () => Promise<unknown>, ok?: string) => Promise<void>;
    onselect: (key: string) => void; onedit: (n: PlanNode) => void; onadd: (parent: string) => void; onclose: () => void;
  } = $props();

  const owner = $derived(sel.includes('#') ? sel.split('#')[0]! : sel);
  const n = $derived(plan.nodes[owner]);
  const tr = $derived(sel.includes('#') && n ? (n.tracks ?? []).find((x) => x.id === sel.split('#')[1]) : undefined);
  const isRoot = $derived(owner === plan.root);
  const crumbs = $derived(n ? pathTo(plan, n.id) : []);
  const active = $derived(n ? (n.tracks ?? []).find((x) => x.id === n.active_track) : undefined);
  const altOwner = $derived(!n ? null : otherTracks(plan, n.id).length ? n.id : n.parent && otherTracks(plan, n.parent).length ? n.parent : null);
  const canSplit = $derived(Boolean(n && !n.obvious && !n.off && !['proved', 'running', 'hole'].includes(n.ui) && n.depth < plan.limits.depth && (isRoot || n.lean)));
  const canHole = $derived(Boolean(n && !isRoot && !n.off && !['proved', 'hole', 'running'].includes(n.ui) && n.lean_ok !== false));
  const rev = () => plan.rev;
  function plain(s: string): string { return s.replace(/\$([^$]*)\$/g, '$1'); }
  const split = () => run('analyse', () => research.analysePlan(did, { node: isRoot ? undefined : n!.id, base_rev: rev(), force: true }), t('plan.analysed'));
  const other = () => run('track', () => research.switchTrack(did, altOwner!, rev()), t('plan.trackSwitched'));
  const hole = () => run('hole', () => research.admitNode(did, n!.id, rev()), t('plan.holeSet'));
</script>

<section class="panel-node" aria-labelledby="pn-h">
  <div class="row head">
    <nav aria-label={t('plan.breadcrumb')} class="crumbs small">
      {#each crumbs as c, i (c.id)}
        {#if i > 0}<Icon name="chevronRight" size={12} />{/if}
        {#if c.id === owner && !tr}<span aria-current="location">{i === 0 ? t('plan.theorem') : plain(c.title)}</span>
        {:else}<button class="linklike" onclick={() => onselect(c.id)}>{i === 0 ? t('plan.theorem') : plain(c.title)}</button>{/if}
      {/each}
    </nav>
    <span class="spacer"></span>
    <button class="btn quiet icon small" onclick={onclose} aria-label={t('plan.closePanel')}><Icon name="x" size={16} /></button>
  </div>

  {#if tr && n}
    <PlanStatus ui={tr.abandoned ? 'abandoned' : 'alternative'} />
    <h3 id="pn-h">{plain(tr.idea || '—')}</h3>
    <p class="small comb-{tr.check.state}">{tr.check.state === 'ok' ? t('plan.comb.ok') : tr.check.state === 'failed' ? t('plan.comb.failed', { why: tr.check.why.slice(0, 300) }) : t('plan.comb.unchecked')}</p>
    <ol class="lemmas">
      {#each tr.lemmas as x (x)}
        {@const c = plan.nodes[x]}
        {#if c}<li><strong>{plain(c.title)}</strong>{#if c.obvious} <span class="xs ok">({t('plan.obviousTag')})</span>{/if}{#if c.statement_nl}<div class="small"><Md src={c.statement_nl} /></div>{/if}{#if c.lean}<pre class="lean">{c.lean}</pre>{/if}</li>{/if}
      {/each}
    </ol>
    {#if tr.combination}<details><summary class="small">{t('plan.combination')}</summary><pre class="lean">{tr.combination}</pre></details>{/if}
    <div class="row acts"><button class="btn primary" disabled={!!busy} onclick={() => run('track', () => research.switchTrack(did, n.id, rev(), tr.id), t('plan.trackSwitched'))}><Icon name="split" size={16} />{t('plan.actChoose')}</button></div>
  {:else if n}
    <div class="row"><PlanStatus ui={n.ui} obvious={n.obvious} />{#if n.edited}<span class="xs muted">{t('plan.edited')}</span>{/if}</div>
    <h3 id="pn-h">{plain(n.title)}</h3>
    {#if n.statement_nl}<div class="stmt"><Md src={n.statement_nl} /></div>{/if}
    {#if n.why && !isRoot}<div class="why"><strong>{t('plan.why2')}</strong><Md src={n.why} /></div>{/if}
    {#if n.uses?.length}<p class="small muted">{t('plan.uses', { names: n.uses.map((u) => plain(plan.nodes[u]?.title ?? u)).join(', ') })}</p>{/if}

    {#if n.ui === 'failed'}
      <div class="fix" role="group" aria-labelledby="fix-h">
        <h4 id="fix-h"><Icon name="warn" size={16} /> {t('plan.whatNow')}</h4>
        <ol>
          <li><button class="btn primary" disabled={!!busy || !altOwner} onclick={other}>{t('plan.actOther')}</button>
            <span class="small">{altOwner ? t('plan.fixOtherDesc') : t('plan.noOther')}</span></li>
          <li><button class="btn" disabled={!!busy || !canSplit} onclick={split}>{t('plan.actResplit')}</button>
            <span class="small">{canSplit ? t('plan.fixSplitDesc', { n: plan.limits.depth }) : t('plan.tooDeep')}</span></li>
          <li><button class="btn" disabled={!!busy || !canHole} onclick={hole}>{t('plan.actHole')}</button>
            <span class="small">{t('plan.fixHoleDesc')}</span></li>
        </ol>
      </div>
    {/if}

    {#if n.lean}
      <h4>{t('plan.leanStatement')}</h4>
      <pre class="lean">{n.lean}</pre>
      {#if n.lean_ok === true}<p class="xs ok"><Icon name="check" size={12} /> {t('plan.leanOk')}</p>
      {:else if n.lean_ok === false}<p class="xs bad"><Icon name="x" size={12} /> {t('plan.leanBad', { why: n.lean_error.slice(0, 300) })}</p>{/if}
    {/if}
    {#if n.obvious && n.obvious_proof}<p class="xs ok">{t('plan.obvious')}</p><details><summary class="small">{t('plan.proofOf')}</summary><pre class="lean">{n.obvious_proof}</pre></details>{/if}
    {#if active && n.children.length}
      <h4>{t('plan.combination')} <span class="cb comb-{active.check.state}">{t(`plan.comb.badge.${active.check.state}` as 'plan.comb.badge.ok')}</span></h4>
      <p class="small">{active.check.state === 'ok' ? t('plan.comb.ok') : active.check.state === 'failed' ? t('plan.comb.failed', { why: active.check.why.slice(0, 300) }) : t('plan.comb.unchecked')}</p>
      {#if n.combine?.state === 'failed' && n.combine.why}<p class="xs bad">{n.combine.why}</p>{/if}
      {#if active.combination}<details><summary class="small">{t('plan.combination')}</summary><pre class="lean">{active.combination}</pre></details>{/if}
      {#if active.check.state !== 'ok' && n.ui !== 'running'}<button class="btn small" disabled={!!busy} onclick={() => run('recheck', () => research.recheckNode(did, n.id, rev()))}><Icon name="refresh" size={14} />{t('plan.recheck')}</button>{/if}
    {/if}
    {#if n.refused_tracks?.length}<p class="xs muted">{t('plan.refused')}</p>{/if}

    <div class="row acts">
      {#if n.ui === 'to_validate'}<button class="btn primary" disabled={!!busy} onclick={() => run('acc', () => research.acceptPlan(did, rev(), [n.id]))}><Icon name="check" size={16} />{t('plan.actValidate')}</button>{/if}
      {#if n.ui !== 'failed'}
        {#if canSplit}<button class="btn" disabled={!!busy} onclick={split}><Icon name="split" size={16} />{n.children.length ? t('plan.actResplit') : isRoot ? t('plan.split') : t('plan.actSplit')}</button>{/if}
        {#if altOwner && !isRoot}<button class="btn" disabled={!!busy} onclick={other}>{t('plan.actOther')}</button>{/if}
        {#if canHole && n.ui !== 'to_validate'}<button class="btn" disabled={!!busy} onclick={hole} title={t('plan.fixHoleDesc')}>{t('plan.actHole')}</button>{/if}
      {/if}
      {#if n.ui === 'hole'}<button class="btn" disabled={!!busy} onclick={() => run('unadmit', () => research.admitNode(did, n.id, rev(), true))}>{t('plan.unadmit')}</button>{/if}
      <button class="btn quiet" onclick={() => onedit(n)}><Icon name="edit" size={16} />{t('common.edit')}</button>
      {#if n.depth < plan.limits.depth && !n.off}<button class="btn quiet" onclick={() => onadd(n.id)}><Icon name="plus" size={16} />{t('plan.addChild')}</button>{/if}
      {#if n.dossier_id && !isRoot}<a class="btn quiet" href="/d/{encodeURIComponent(n.dossier_id)}"><Icon name="external" size={16} />{t('plan.openDossier')}</a>{/if}
      {#if !isRoot}<button class="btn quiet icon" disabled={!!busy} onclick={() => run('del', () => research.deletePlanNode(did, n.id, rev()), t('plan.deleted'))} aria-label={t('plan.delete', { title: n.title })}><Icon name="trash" size={16} /></button>{/if}
    </div>
  {/if}
</section>

<style>
  .panel-node { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-3) var(--s-4); display: grid; gap: var(--s-2); align-content: start; min-width: 0; }
  .head { flex-wrap: nowrap; align-items: flex-start; }
  .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 4px; color: var(--text-2); min-width: 0; }
  .crumbs span[aria-current] { font-weight: 700; color: var(--text); }
  .linklike { background: none; border: 0; padding: 4px 2px; min-height: 24px; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; text-align: left; }
  h3 { margin: 0; font-size: var(--fs-lg); overflow-wrap: anywhere; }
  h4 { margin: var(--s-2) 0 0; font-size: var(--fs-md); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .why { margin: 0; border-left: 3px solid var(--accent); padding: 2px 0 2px 10px; color: var(--text-2); }
  .why :global(p) { margin: 0.1em 0 0; }
  .stmt :global(p) { margin: 0.2em 0; }
  .lean { font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2); padding: 6px 8px; border-radius: var(--r-1); margin: 0; }
  .ok { color: var(--proved); }
  .bad { color: var(--failed); overflow-wrap: anywhere; }
  .cb { font-size: var(--fs-xs); font-weight: 700; padding: 1px 8px; border-radius: 999px; border: 1.5px solid currentColor; }
  .comb-ok { color: var(--proved); }
  .comb-failed { color: var(--failed); }
  .comb-unchecked { color: var(--running); }
  .cb.comb-unchecked { border-style: dashed; }
  .fix { border: 2px solid var(--failed); background: var(--failed-soft); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); }
  .fix h4 { margin: 0 0 var(--s-2); color: var(--failed); }
  .fix ol { margin: 0; padding-left: 1.4em; display: grid; gap: var(--s-2); }
  .fix li { display: grid; gap: 2px; justify-items: start; }
  .lemmas { margin: 0; padding-left: 1.3em; display: grid; gap: var(--s-2); }
  .acts { gap: 6px; margin-top: var(--s-2); }
</style>
