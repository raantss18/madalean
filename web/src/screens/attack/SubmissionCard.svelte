<script lang="ts">
  // One prepared submission (D69 / D70): the Lean file read only, the three local checks, the exact plan of what goes
  // to GitHub and under which account, then « Envoyer… » / « Écarter… » — each opens a confirmation (the screen owns
  // the dialog). After sending: its state and the link to the request. Nothing here sends by itself.
  import type { AttackSubmission } from '../../lib/api/attack';
  import { readCheck, allChecksPass, fileText, filePath, planLogin, submissionMark, requestWords } from '../../lib/attack';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import StatusMark from '../../components/StatusMark.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import Icon from '../../components/Icon.svelte';

  let { sub, canAct, busy, onsend, ondiscard }: {
    sub: AttackSubmission; canAct: boolean; busy: boolean; onsend: () => void; ondiscard: () => void;
  } = $props();
  const hid = $derived(`sub-${sub.id.replace(/[^\w-]/g, '_')}`);
  const ready = $derived(sub.state === 'ready');
  const pass = $derived(allChecksPass(sub));
  const login = $derived(planLogin(sub));
  const checks = $derived((['local', 'rules', 'axioms'] as const).map((k) => ({ k, ...readCheck(sub.check?.[k], k) })));
  const text = $derived(fileText(sub.file));
  const path = $derived(filePath(sub));
  const markOf = (ok: boolean | null) => (ok === true ? 'proved' : ok === false ? 'failed' : 'queued');
</script>

<article class="sub" aria-labelledby="{hid}-h">
  <header>
    <h3 id="{hid}-h">{sub.title || sub.problem}</h3>
    <p class="state small"><span aria-hidden="true"><StatusMark phase={submissionMark(sub.state)} /></span>{tk(`attack.sub.state.${sub.state}`, sub.state)}</p>
  </header>
  <p class="meta xs">{tk(`attack.sub.kind.${sub.kind}`, sub.kind)} · <span lang="en">{sub.problem}</span>{#if sub.created}{' · '}{fmtTime(sub.created)}{/if}
    {#if sub.dossier_id}{' · '}<a href="/d/{encodeURIComponent(sub.dossier_id)}">{t('attack.sub.dossier')}</a>{/if}</p>

  <details open={ready}>
    <summary>{t('attack.sub.file')}{#if path}{' — '}<code>{path}</code>{/if}</summary>
    <CodeEditor value={text} language="lean" readonly label={t('attack.sub.fileLabel', { title: sub.title || sub.problem })} minLines={4} />
  </details>

  <h4 id="{hid}-c">{t('attack.sub.checks')}</h4>
  <ul class="checks" aria-labelledby="{hid}-c">
    {#each checks as c (c.k)}
      <li class={c.ok === true ? 'ok' : c.ok === false ? 'bad' : 'none'}>
        <span aria-hidden="true"><StatusMark phase={markOf(c.ok)} /></span>
        <span class="name">{t(`attack.check.${c.k}`)}</span> :
        <strong>{c.ok === true ? t('attack.check.ok') : c.ok === false ? t('attack.check.fail') : t('attack.check.none')}</strong>
        {#if c.detail}<span class="detail xs">{c.detail}</span>{/if}
      </li>
    {/each}
  </ul>

  {#if ready}
    {#if pass}
      <div class="plan" role="region" aria-labelledby="{hid}-p">
        <h4 id="{hid}-p">{t('attack.sub.plan')}</h4>
        <p class="small">{login ? t('attack.sub.planIntro', { login }) : t('attack.sub.planIntroNoLogin')}</p>
        <ol class="small">
          {#each sub.plan?.requests ?? [] as rq, i (i)}
            {@const w = requestWords(rq)}
            <li>{tk(w.key, '', w.params)}
              <code class="xs exact">{rq.method} {rq.url}</code>
              {#if rq.body}<details class="xs"><summary>{t('attack.sub.body')}</summary><pre class="code">{JSON.stringify(rq.body, null, 1)}</pre></details>{/if}
            </li>
          {/each}
        </ol>
      </div>
    {/if}
    {#if !pass}<p class="small warn" id="{hid}-np">{t('attack.sub.notReady')}</p>{/if}
    <div class="row acts">
      <button class="btn primary" onclick={onsend} disabled={!canAct || !pass || busy} aria-describedby={!pass ? `${hid}-np` : undefined}><Icon name="send" size={16} />{t('attack.sub.send')}</button>
      <button class="btn quiet" onclick={ondiscard} disabled={!canAct || busy}><Icon name="trash" size={16} />{t('attack.sub.discard')}</button>
    </div>
  {:else if sub.pr_url}
    <p class="small"><a href={sub.pr_url} target="_blank" rel="noopener noreferrer">{t('attack.sub.pr')}<Icon name="external" size={14} /></a></p>
  {/if}
</article>

<style>
  .sub { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-2); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-4); min-width: 0; }
  header { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s-2) var(--s-3); }
  h3 { margin: 0; font-family: var(--font-serif); font-size: var(--fs-lg); flex: 1 1 16em; min-width: 0; overflow-wrap: anywhere; }
  h4 { margin: var(--s-2) 0 0; font-size: var(--fs-sm); }
  .state { margin: 0; display: inline-flex; align-items: center; gap: 6px; font-weight: 600; color: var(--text-2); }
  .meta { margin: 0; color: var(--text-3); }
  summary { cursor: pointer; font-weight: 600; padding: 6px 0; }
  summary code { font-weight: 400; font-size: var(--fs-xs); overflow-wrap: anywhere; }
  .checks { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: var(--fs-sm); }
  .checks li { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .checks .ok strong { color: var(--proved); }
  .checks .bad strong { color: var(--failed); }
  .checks .none strong { color: var(--text-3); font-weight: 600; }
  .detail { flex-basis: 100%; padding-left: 20px; color: var(--text-2); overflow-wrap: anywhere; }
  .plan { border: 1px solid var(--line-strong); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); min-width: 0; }
  .plan h4 { margin-top: 0; }
  .plan p { margin: 4px 0; }
  .plan ol { margin: 0; padding-left: 1.4em; display: grid; gap: 4px; }
  .plan code { overflow-wrap: anywhere; }
  .exact { display: block; color: var(--text-3); margin-top: 2px; }
  .code { font-family: var(--font-mono); font-size: var(--fs-xs); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2); border-radius: var(--r-1); padding: 6px; max-height: 16em; overflow: auto; margin: 4px 0; }
  .warn { color: var(--failed); margin: 0; }
  .acts { gap: var(--s-2); flex-wrap: wrap; }
  a :global(.ico) { vertical-align: -2px; margin-left: 4px; }
</style>
