<script lang="ts">
  // One exercise (S-BE, D63): answer in words or in Lean, hints after an attempt, the verified solution last, read line
  // by line by « Expliquer » (D45). The draft is kept in this browser (autosave rule of D43).
  import { LANGS, type Lang } from '../../lib/i18n/index.svelte';
  import { exercises, xt, xError, type Exercise, type Progress, type Tr, type Verdict } from '../../lib/exercises/strings';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Md from '../../components/Md.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';
  import LeanExplain from '../../components/LeanExplain.svelte';

  let { ex, lang, onprogress, onremoved }: { ex: Exercise; lang: Lang; onprogress: (p: Progress) => void; onremoved: () => void } = $props();
  // svelte-ignore state_referenced_locally
  const key = `madalean.exercise.${ex.id}`;
  function draft(k: string): string { try { return localStorage.getItem(`${key}.${k}`) ?? ''; } catch { return ''; } }
  let kind = $state<'words' | 'lean'>(draft('kind') === 'lean' ? 'lean' : 'words');
  let words = $state(draft('words'));
  let lean = $state(draft('lean'));
  $effect(() => {
    try { localStorage.setItem(`${key}.kind`, kind); localStorage.setItem(`${key}.words`, words); localStorage.setItem(`${key}.lean`, lean); } catch { /* private mode */ }
  });
  // svelte-ignore state_referenced_locally
  let shownLang = $state<Lang>(ex.statement[lang] ? lang : 'fr');
  let busy = $state(false);
  let verdict = $state<(Verdict & { kind: 'words' | 'lean' }) | null>(null);
  let hints = $state<Tr[]>([]);
  let tried = $state('');
  let sol = $state<{ code: string; workspace: string } | null>(null);
  let hinting = $state(false);
  const pick = (x: Tr) => x[shownLang] ?? x.fr;
  const lang_ = (x: Tr) => (x[shownLang] ? shownLang : 'fr');
  const tk = (k: string) => xt(k as Parameters<typeof xt>[0]);
  const p = $derived(ex.progress);
  const mayShow = $derived(Boolean(p?.solved || (p?.tried && (p?.hints ?? 0) >= ex.hints)));

  // the hints already revealed on this device
  // svelte-ignore state_referenced_locally
  if (ex.progress?.hints) void exercises.hint(ex.id, { again: true }).then((r) => { hints = r.hints; }, () => { /* asked again on click */ });

  async function submit() {
    const text = kind === 'words' ? words : lean;
    if (busy) return;
    if (!text.trim()) { toast('error', xt('err.empty')); return; }
    busy = true; verdict = null;
    const k = kind;
    try { const r = await exercises.submit(ex.id, k, text); verdict = { ...r, kind: k }; onprogress(r.progress); }
    catch (e) { toast('error', xError(e)); } finally { busy = false; }
  }
  async function nextHint() {
    if (hinting) return;
    hinting = true;
    try { const r = await exercises.hint(ex.id, { tried }); hints = r.hints; onprogress(r.progress); }
    catch (e) { toast('error', xError(e)); } finally { hinting = false; }
  }
  async function showSolution() {
    if (hinting) return;
    hinting = true;
    try { const r = await exercises.solution(ex.id); sol = r; onprogress(r.progress); }
    catch (e) { toast('error', xError(e)); } finally { hinting = false; }
  }
  async function remove() {
    try { await exercises.remove(ex.id); onremoved(); } catch (e) { toast('error', xError(e)); }
  }
</script>

<article>
  <h1 lang={lang_(ex.title)}><Md inline src={pick(ex.title)} /></h1>
  <p class="small muted">{tk(`l.${ex.level}`)} · {tk(`d.${ex.domain}`)}{#if ex.source} · {xt('source', { s: ex.source })}{/if}{#if ex.licence} · {xt('licence', { l: ex.licence })}{/if}</p>
  <label class="inline small">{xt('lang')}
    <select class="input" bind:value={shownLang}>{#each LANGS.filter(([l]) => ex.statement[l]) as [l, name]}<option value={l} lang={l}>{name}</option>{/each}</select></label>
  <div class="theorem" lang={lang_(ex.statement)}><Md src={pick(ex.statement)} /></div>
  <details><summary>{xt('leanStatement')}</summary><pre class="code" tabindex="-1"><code>{ex.lean}</code></pre></details>

  <section aria-labelledby="x-how">
    <h2 id="x-how">{xt('how')}</h2>
    <div class="seg" role="radiogroup" aria-labelledby="x-how">
      {#each ['words', 'lean'] as const as k}<label><input type="radio" name="x-kind" value={k} bind:group={kind} />{xt(k)}</label>{/each}
    </div>
    {#if kind === 'words'}
      <label class="fieldl">{xt('wordsLabel')}<textarea class="input" rows="6" bind:value={words} maxlength="8000" aria-describedby="x-note"></textarea></label>
      <p id="x-note" class="small muted">{xt('wordsNote')}</p>
    {:else}
      <p class="small">{xt('leanLabel')}</p>
      <CodeEditor bind:value={lean} label={xt('leanLabel')} gloss minLines={5} onSubmit={() => void submit()} enterSubmits={false} />
    {/if}
    <button class="btn primary" onclick={submit} disabled={busy}>{busy ? xt('checking') : xt('check')}</button>
    <div role="status" aria-live="polite">
      {#if verdict}
        <p class="verdict" class:ok={verdict.ok}><strong>{verdict.ok ? xt(verdict.kind === 'words' ? 'okWords' : 'okLean') : xt(verdict.kind === 'words' ? 'koWords' : 'koLean')}</strong></p>
      {/if}
    </div>
    {#if verdict}
      {#if verdict.check && verdict.kind === 'lean' && !verdict.ok}<CheckResultView check={verdict.check} mode="proof" />{/if}
      {#if verdict.lean}<h3>{xt('formal')}</h3><pre class="code" tabindex="-1"><code>{verdict.lean}</code></pre>{/if}
      {#if verdict.review}<h3>{xt('review')}</h3><Md src={verdict.review} />{/if}
    {/if}
  </section>

  <section aria-labelledby="x-hints">
    <h2 id="x-hints">{xt('hints')}</h2>
    {#if hints.length}<ol class="hints" aria-live="polite">{#each hints as h, i}<li><span class="small muted">{xt('hint', { n: i + 1 })}</span> <span lang={lang_(h)}><Md inline src={pick(h)} /></span></li>{/each}</ol>{/if}
    {#if (p?.hints ?? 0) < ex.hints}
      {#if !p?.tried}<label class="fieldl">{xt('triedLabel')}<textarea class="input" rows="2" bind:value={tried} maxlength="2000"></textarea></label>{/if}
      <button class="btn" onclick={nextHint} disabled={hinting || (!p?.tried && tried.trim().length < 3)}>{xt('nextHint', { n: (p?.hints ?? 0) + 1, total: ex.hints })}</button>
    {/if}
  </section>

  <section aria-labelledby="x-sol">
    <h2 id="x-sol">{xt('solution')}</h2>
    {#if !ex.has_solution}<p class="muted">{xt('noSolution')}</p>
    {:else if sol}
      <p>{xt('solutionOk')}</p>
      <pre class="code" tabindex="-1"><code>{sol.code}</code></pre>
      <LeanExplain where={{ workspace: sol.workspace }} code={sol.code} />
    {:else if mayShow}<button class="btn" onclick={showSolution} disabled={hinting}>{xt('showSolution')}</button>
    {:else}<p class="small muted">{xt('solutionLater')}</p>{/if}
  </section>
  {#if ex.origin !== 'seed'}<p><button class="btn quiet" onclick={remove}>{xt('remove')}</button></p>{/if}
</article>

<style>
  h2 { font-size: var(--fs-lg, 1.1rem); margin: 24px 0 8px; }
  h3 { font-size: 1rem; margin: 12px 0 4px; }
  .theorem { margin: 12px 0; }
  .inline { display: inline-flex; gap: 8px; align-items: center; }
  .inline .input { min-height: var(--touch); }
  .fieldl { display: grid; gap: 4px; font-size: var(--fs-sm); font-weight: 600; margin: 8px 0; }
  .fieldl .input { width: 100%; font-weight: 400; }
  .code { overflow: auto; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-1); background: var(--surface-2); font-size: var(--fs-sm); white-space: pre-wrap; overflow-wrap: anywhere; }
  .verdict { padding: 8px 12px; border-left: 4px solid var(--line); }
  .verdict.ok { border-left-color: var(--accent); }
  .hints { padding-left: 20px; display: grid; gap: 6px; }
  summary { min-height: var(--touch); line-height: var(--touch); cursor: pointer; }
</style>
