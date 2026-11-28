<script lang="ts">
  // « Problèmes ouverts » (S-BK, D70; contract docs/ATTACK.md, D69): Madalean works on lefttosolve.com problems in the
  // background, within a daily budget. The header says the state in words; « En ce moment » = one card per problem
  // (its dossier is the one-thread screen, D66); « Prêtes à envoyer » = the prepared submissions, each sent only after
  // a confirmation; « Historique ». Live through `attack.state` / `attack.submission`.
  import { app } from '../../lib/store/app.svelte';
  import { attack, ATTACK_KINDS, type AttackStatus, type AttackSubmission, type AttackHistoryItem } from '../../lib/api/attack';
  import { headline, isOn, needsAgreement, money, gb, downloaded, spentRatio, statusFromEvent, submissionFromEvent,
    upsertSubmission, filterHistory, totalUsd, outcomeMark, planLogin, ago } from '../../lib/attack';
  import { t, tk, tn, i18n, fmtTime } from '../../lib/i18n/index.svelte';
  import { clock } from '../../lib/ui/clock.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import StatusMark from '../../components/StatusMark.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Icon from '../../components/Icon.svelte';
  import { say } from './say';
  import SubmissionCard from './SubmissionCard.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  let st = $state<AttackStatus | null>(null);
  let subs = $state<AttackSubmission[]>([]);
  let hist = $state<AttackHistoryItem[]>([]);
  let loadErr = $state('');
  let busy = $state('');
  let agreeOpen = $state(false);
  let confirmOpen = $state(false);
  let confirmOf = $state<{ kind: 'send' | 'discard'; sub: AttackSubmission } | null>(null);
  let kind = $state('');
  const lang = $derived(i18n.lang);
  const host = $derived(app.m.local);

  async function loadStatus() {
    try { st = await attack.get(); loadErr = ''; } catch (e) { loadErr = errorText(e); }
  }
  async function loadSubs() { try { subs = (await attack.submissions()).slice().sort((a, b) => (b.created ?? 0) - (a.created ?? 0)); } catch { /* the header says it */ } }
  async function loadHist() { try { hist = await attack.history(); } catch { /* idem */ } }
  $effect(() => { void loadStatus(); void loadSubs(); void loadHist(); });
  $effect(() => app.on('attack.state', (ev) => {
    const s = statusFromEvent(ev as unknown as Record<string, unknown>);
    if (s) { st = s; loadErr = ''; }
  }));
  $effect(() => app.on('attack.submission', (ev) => {
    const s = submissionFromEvent(ev as unknown as Record<string, unknown>);
    if (!s) return;
    subs = upsertSubmission(subs, s);
    if (s.state !== 'ready') void loadHist();
  }));

  const line = $derived(st ? headline(st, lang) : null);
  const text = $derived(line ? say(line) : '');
  // the visible line is hidden from screen readers: this polite status says the state once, not every downloaded
  // megabyte (the progress bar carries the numbers)
  const spoken = $derived(line?.key === 'attack.state.downloading' ? t('attack.state.downloadingNoSize') : text);
  const mark = $derived(!st ? 'draft' : st.state === 'running' || st.state === 'setup' ? 'running' : st.state === 'error' ? 'failed' : st.state === 'off' ? 'draft' : 'stopped');
  const on = $derived(isOn(st));
  const dl = $derived(st && st.state === 'setup' && st.workspace.state === 'downloading' ? downloaded(st.workspace) : null);
  const ready = $derived(subs.filter((s) => s.state === 'ready'));
  const done = $derived(subs.filter((s) => s.state !== 'ready'));
  const kinds = $derived([...new Set([...ATTACK_KINDS, ...hist.map((h) => h.kind).filter(Boolean)])]);
  const shown = $derived(filterHistory(hist, kind));
  const kindLabel = (k: string) => tk(`attack.kind.${k}`, tk(`attack.sub.kind.${k}`, k));
  const phaseText = (p: string) => tk(`attack.phase.${p}`, '') || t('attack.phase.unknown');
  const sizeGb = $derived(st && st.workspace.size > 0 ? gb(st.workspace.size, lang) : '10');
  const cap = $derived(money(Number(st?.today.cap ?? (app.m.settings as Record<string, unknown> | null)?.['attack_usd_per_day'] ?? 5), lang));

  function remember(s: AttackStatus) {
    st = s;
    const set = app.m.settings as Record<string, unknown> | null;
    if (set) set['attack_enabled'] = isOn(s);
  }
  async function run(name: string, fn: () => Promise<AttackStatus>) {
    busy = name;
    try {
      const r = await fn();
      if (r && typeof r.state === 'string') remember(r); else await loadStatus();
    } catch (e) { toast('error', errorText(e)); } finally { busy = ''; }
  }
  function onStart() {
    if (needsAgreement(st)) { agreeOpen = true; return; }
    void run('start', attack.start);
  }
  async function accept() {
    agreeOpen = false;
    await run('start', async () => { remember(await attack.workspace()); return attack.start(); });
  }
  function ask(k: 'send' | 'discard', sub: AttackSubmission) { confirmOf = { kind: k, sub }; confirmOpen = true; }
  async function confirm() {
    const c = confirmOf;
    confirmOpen = false;
    if (!c) return;
    busy = c.sub.id;
    try {
      const r = c.kind === 'send' ? await attack.send(c.sub.id, c.sub.plan?.id ?? '') : await attack.discard(c.sub.id);
      if (c.kind === 'discard') subs = subs.filter((x) => x.id !== c.sub.id);
      else if (r?.submission && typeof r.submission.id === 'string') subs = upsertSubmission(subs, r.submission);
      toast('ok', c.kind === 'send' ? t('attack.sent') : t('attack.discarded'));
      await loadSubs(); void loadHist();
    } catch (e) { toast('error', errorText(e)); } finally { busy = ''; }
  }
</script>

<div class="attack">
  <section class="head" aria-labelledby="atk-h">
    <div class="row top">
      <h1 id="atk-h">{t('attack.title')}</h1>
      <span class="spacer"></span>
      {#if st}
        {#if on}
          <button class="btn" onclick={() => run('stop', attack.stop)} disabled={!host || busy !== ''}><Icon name="stop" size={16} />{t('attack.stop')}</button>
        {:else}
          <button class="btn primary" onclick={onStart} disabled={!host || busy !== ''}><Icon name="play" size={16} />{t('attack.start')}</button>
        {/if}
      {/if}
    </div>
    <p class="lead">{t('attack.lead')} <a href="https://lefttosolve.com" target="_blank" rel="noopener noreferrer">{t('attack.site')}<Icon name="external" size={14} /></a></p>
    {#if loadErr && !st}<p class="error-text" role="alert">{t('attack.loadError', { e: loadErr })}</p>{/if}
    {#if st}
      <p class="state" aria-hidden="true"><span><StatusMark phase={mark} size={16} /></span><span>{text}</span></p>
      <p class="sr-only" role="status">{spoken}</p>
      {#if dl}<progress class="bar" max="1" value={dl.ratio} aria-label={t('attack.download')} aria-valuetext={text}></progress>{/if}
      {#if st.state === 'running' && st.queue > 0}<p class="small muted q">{tn('attack.queue', st.queue)}</p>{/if}
      <div class="stats">
        <div class="spend">
          <p class="small"><strong>{t('attack.spend')}</strong> : {t('attack.spendOf', { usd: money(st.today.usd, lang), cap: money(st.today.cap, lang) })}</p>
          <progress class="bar" class:full={spentRatio(st) >= 1} max="1" value={spentRatio(st)} aria-label={t('attack.spend')}></progress>
        </div>
        <dl class="counts" aria-label={t('attack.counts')}>
          <div><dt>{t('attack.count.taken')}</dt><dd>{st.today.taken}</dd></div>
          <div><dt>{t('attack.count.proofs')}</dt><dd>{st.today.proofs}</dd></div>
          <div><dt>{t('attack.count.released')}</dt><dd>{st.today.released}</dd></div>
        </dl>
      </div>
      {#if !host}<p class="small muted"><Icon name="lock" size={14} /> {t('attack.hostOnly')}</p>{/if}
      <p class="small"><a href="/reglages/problemes-ouverts"><Icon name="sliders" size={14} />{t('nav.settings')}</a></p>
    {/if}
  </section>

  {#if st}
    <section aria-labelledby="now-h">
      <h2 id="now-h">{t('attack.now.title')}</h2>
      {#if st.current.length}
        <ul class="cards">
          {#each st.current as c (c.problem)}
            <li class="card">
              <h3><a href="/d/{encodeURIComponent(c.dossier_id)}">{c.title || c.problem}</a></h3>
              <p class="xs meta">{kindLabel(c.kind)}{#if c.difficulty !== null && c.difficulty !== undefined}{' · '}{t('attack.difficulty', { n: c.difficulty })}{/if}</p>
              <p class="small ph"><span aria-hidden="true"><StatusMark phase="running" /></span><span>{phaseText(c.phase)} · {t('attack.now.since', { d: ago(clock.now - c.since) })}</span></p>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted">{t('attack.now.empty')}</p>
      {/if}
    </section>
  {/if}

  <section aria-labelledby="ready-h">
    <h2 id="ready-h">{t('attack.ready.title')}{#if ready.length}{' '}<span class="n">({ready.length})</span>{/if}</h2>
    {#if ready.length || done.length}
      <ul class="subs">
        {#each [...ready, ...done] as s (s.id)}
          <li><SubmissionCard sub={s} canAct={host} busy={busy !== ''} onsend={() => ask('send', s)} ondiscard={() => ask('discard', s)} /></li>
        {/each}
      </ul>
    {:else}
      <p class="muted">{t('attack.ready.empty')}</p>
    {/if}
  </section>

  <section aria-labelledby="hist-h">
    <div class="row hh">
      <h2 id="hist-h">{t('attack.hist.title')}</h2>
      <span class="spacer"></span>
      <label for="hist-kind" class="small">{t('attack.hist.filter')}</label>
      <select id="hist-kind" class="input kind" bind:value={kind}>
        <option value="">{t('attack.hist.all')}</option>
        {#each kinds as k (k)}<option value={k}>{kindLabel(k)}</option>{/each}
      </select>
    </div>
    {#if shown.length}
      <ul class="hist">
        {#each shown as h, i (h.problem + h.t + i)}
          <li>
            <span class="out small"><span aria-hidden="true"><StatusMark phase={outcomeMark(h.outcome)} /></span>{tk(`attack.hist.outcome.${h.outcome}`, h.outcome)}</span>
            <span class="what">
              {#if h.dossier_id}<a href="/d/{encodeURIComponent(h.dossier_id)}">{h.title || h.problem}</a>{:else}{h.title || h.problem}{/if}
              <span class="xs meta">{kindLabel(h.kind)} · {fmtTime(h.t)} · {t('attack.hist.spent', { usd: money(h.usd, lang) })}</span>
              {#if h.reason}<span class="xs why">{t('attack.hist.why', { reason: tk(`attack.reason.${h.reason}`, h.reason) })}</span>{/if}
            </span>
          </li>
        {/each}
      </ul>
      <p class="small muted">{t('attack.hist.total', { usd: money(totalUsd(shown), lang) })}</p>
    {:else}
      <p class="muted">{t('attack.hist.empty')}</p>
    {/if}
  </section>
</div>

<Dialog bind:open={agreeOpen} title={t('attack.agree.title')}>
  <p>{t('attack.agree.intro')}</p>
  <ul class="agree">
    <li>{t('attack.agree.work')}</li>
    <li>{t('attack.agree.spend', { cap })}</li>
    <li>{t('attack.agree.download', { size: sizeGb })}</li>
    <li>{t('attack.agree.public')}</li>
    <li>{t('attack.agree.notes')}</li>
    <li>{t('attack.agree.email')} <a href="https://github.com/settings/emails" target="_blank" rel="noopener noreferrer">{t('attack.agree.emailLink')}</a></li>
  </ul>
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (agreeOpen = false)}>{t('common.cancel')}</button>
    <button class="btn primary" onclick={accept}>{t('attack.agree.accept')}</button>
  {/snippet}
</Dialog>

<Dialog bind:open={confirmOpen} title={confirmOf?.kind === 'discard' ? t('attack.confirm.discardTitle') : t('attack.confirm.sendTitle')}>
  {#if confirmOf}
    {@const title = confirmOf.sub.title || confirmOf.sub.problem}
    {#if confirmOf.kind === 'send'}
      <p>{t('attack.confirm.sendText', { title, login: planLogin(confirmOf.sub) || t('attack.confirm.yourAccount') })}</p>
    {:else}
      <p>{t('attack.confirm.discardText', { title })}</p>
    {/if}
  {/if}
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (confirmOpen = false)}>{t('common.cancel')}</button>
    {#if confirmOf?.kind === 'discard'}
      <button class="btn danger" onclick={confirm}><Icon name="trash" size={16} />{t('attack.confirm.discard')}</button>
    {:else}
      <button class="btn primary" onclick={confirm}><Icon name="send" size={16} />{t('attack.confirm.send')}</button>
    {/if}
  {/snippet}
</Dialog>

<style>
  .attack { max-width: 1100px; display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-6); }
  h1 { margin: 0; }
  h2 { margin: 0 0 var(--s-3); font-size: var(--fs-lg); }
  .head { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-2); }
  .top { gap: var(--s-3); flex-wrap: wrap; }
  .lead { color: var(--text-2); max-width: var(--measure); margin: 0; }
  .lead a { white-space: nowrap; }
  a :global(.ico) { vertical-align: -2px; margin: 0 4px; }
  .state { margin: var(--s-2) 0 0; display: flex; align-items: center; gap: 10px; font-size: var(--fs-lg); font-weight: 600; font-family: var(--font-serif); }
  .q { margin: 0; }
  .bar { width: 100%; height: 8px; accent-color: var(--accent); }
  .bar.full { accent-color: var(--failed); }
  .stats { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--s-3) var(--s-6); align-items: end; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-3) var(--s-4); }
  .spend p { margin: 0 0 4px; }
  .counts { display: flex; gap: var(--s-5); margin: 0; }
  .counts div { display: flex; flex-direction: column-reverse; }
  .counts dt { font-size: var(--fs-xs); color: var(--text-3); }
  .counts dd { margin: 0; font-size: var(--fs-xl); font-weight: 650; font-variant-numeric: tabular-nums; }
  .cards { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); gap: var(--s-3); }
  .card { background: var(--surface); border: 1px solid var(--line); border-left: 3px solid var(--running-fill); border-radius: var(--r-2); padding: var(--s-3) var(--s-4); display: grid; gap: 4px; min-width: 0; }
  .card h3 { margin: 0; font-family: var(--font-serif); font-size: var(--fs-md); overflow-wrap: anywhere; }
  .meta { color: var(--text-3); margin: 0; }
  .ph { margin: 0; display: flex; align-items: baseline; gap: 6px; color: var(--text-2); }
  .ph > span:first-child { flex: none; align-self: center; }
  .subs { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-4); }
  .n { color: var(--text-3); font-weight: 500; }
  .hh { gap: var(--s-2); flex-wrap: wrap; margin-bottom: var(--s-3); }
  .hh h2 { margin: 0; }
  .kind { width: auto; min-width: 12em; }
  .hist { list-style: none; margin: 0 0 var(--s-2); padding: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); }
  .hist li { display: grid; grid-template-columns: 13em minmax(0, 1fr); gap: var(--s-3); padding: var(--s-2) var(--s-4); border-bottom: 1px solid var(--line); align-items: baseline; }
  .hist li:last-child { border-bottom: 0; }
  .out { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }
  .what { display: grid; gap: 2px; min-width: 0; overflow-wrap: anywhere; }
  .why { color: var(--text-2); }
  .agree { display: grid; gap: var(--s-2); padding-left: 1.2em; margin: 0; }
  @media (max-width: 699px) {
    .stats { grid-template-columns: minmax(0, 1fr); }
    .counts { justify-content: space-between; }
    .hist li { grid-template-columns: minmax(0, 1fr); gap: 2px; }
    .state { font-size: var(--fs-md); }
  }
</style>
