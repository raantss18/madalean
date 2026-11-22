<script lang="ts">
  import EnterHint from '../components/EnterHint.svelte';
  import { enterSubmit } from '../lib/ui/enter';
  // Notebook: JupyterLab (Python, SageMath) embedded, with the assistant beside it. The assistant reads the open
  // notebook through the contents API and can append a cell. Remote devices: only when the host allows it.
  import { api } from '../lib/api/client';
  import { app } from '../lib/store/app.svelte';
  import { t, tk } from '../lib/i18n/index.svelte';
  import { errorText, isHostOnly } from '../lib/ui/errors';
  import { toast } from '../lib/ui/toasts.svelte';
  import Md from '../components/Md.svelte';
  import Icon from '../components/Icon.svelte';
  import HelpLink from '../components/HelpLink.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  const j = $derived(app.m.jupyter);
  let hostOnly = $state(false);
  let starting = $state(false);
  let books = $state<{ name: string; path: string }[]>([]);
  let current = $state('');
  let msgs = $state<{ role: 'user' | 'assistant'; content: string }[]>([]);
  let input = $state('');
  let busy = $state(false);
  let streaming = $state('');
  let reqId = '';

  async function refresh() {
    try { books = (await api.notebooks('')).notebooks.filter((n) => n.type === 'notebook'); hostOnly = false; }
    catch (e) { if (isHostOnly(e)) hostOnly = true; }
  }
  $effect(() => { if (j?.state === 'ready') void refresh(); });
  $effect(() => { api.jupyter().then((s) => { app.m.jupyter = s; }).catch((e) => { if (isHostOnly(e)) hostOnly = true; }); });

  async function start() {
    starting = true;
    try { app.m.jupyter = await api.jupyterStart(); } catch (e) { if (isHostOnly(e)) hostOnly = true; else toast('error', errorText(e)); } finally { starting = false; }
  }
  async function ask() {
    if (!input.trim() || busy) return;
    msgs.push({ role: 'user', content: input.trim() });
    input = ''; busy = true; streaming = '';
    try {
      let context: Record<string, unknown> = {};
      if (current) {
        const nb = await api.notebook(current);
        context = { notebook: current, cells: nb.cells.slice(-20).map((c) => `[${c.cell_type}] ${c.source}${c.outputs_text ? `\n→ ${c.outputs_text.slice(0, 500)}` : ''}`) };
      }
      const r = await api.assistant(msgs.slice(-20), context);
      reqId = r.request_id;
      await new Promise<void>((resolve) => {
        app.listenAssistant(r.request_id, (ev) => {
          if (ev.type === 'assistant.token') streaming += ev.text;
          else { if (ev.type === 'assistant.done') msgs.push({ role: 'assistant', content: ev.text || streaming }); else toast('error', ev.text || t('err.generic', { code: ev.error ?? '' })); resolve(); }
        });
      });
    } catch (e) { toast('error', errorText(e)); } finally { busy = false; streaming = ''; reqId = ''; }
  }
  function codeOf(s: string): string {
    const m = /```(?:python|sage|py)?\n([\s\S]*?)```/.exec(s);
    return m?.[1] ?? '';
  }
  async function append(code: string) {
    if (!current) return;
    try { await api.appendCell(current, code, 'code'); toast('ok', t('notebook.appended')); } catch (e) { toast('error', errorText(e)); }
  }
</script>

<div class="nb">
  <div class="row head">
    <h1>{t('notebook.title')}</h1><HelpLink page="jupyter" />
    <span class="chip {j?.state === 'ready' ? 'proved' : j?.state === 'failed' ? 'failed' : ''}">{tk(`jupyter.${j?.state ?? 'stopped'}`, j?.state ?? '')}</span>
    <span class="spacer"></span>
    {#if j?.state === 'ready'}<a class="btn small" href="/jupyter/lab" target="_blank" rel="noopener"><Icon name="external" size={14} />{t('notebook.newTab')}</a>{/if}
  </div>
  {#if hostOnly}
    <div class="panel"><h2>{t('notebook.hostOnlyTitle')}</h2><p>{t('notebook.hostOnlyText')}</p></div>
  {:else if !j?.available}
    <div class="panel"><h2>{t('notebook.unavailableTitle')}</h2><p>{t('notebook.unavailableText')}</p><a class="btn" href="/reglages/systeme">{t('notebook.toHealth')}</a></div>
  {:else if j.state !== 'ready'}
    <div class="panel">
      <p>{t('notebook.intro')}</p>
      {#if j.error}<p class="error-text">{j.error}</p>{/if}
      <button class="btn primary" onclick={start} disabled={starting || j.state === 'starting'}>{starting || j.state === 'starting' ? t('notebook.starting') : t('notebook.start')}</button>
      <p class="hint">{t('notebook.kernels', { k: j.kernels.join(', ') || 'python3' })} {j.lean_kernel?.available ? '' : t('notebook.noLeanKernel')}</p>
    </div>
  {:else}
    <div class="split">
      <iframe src="/jupyter/lab" title={t('notebook.frameTitle')}></iframe>
      <aside class="assistant panel" aria-labelledby="as-h">
        <h2 id="as-h">{t('notebook.assistant')}</h2>
        <label class="label" for="nb-cur">{t('notebook.context')}</label>
        <select id="nb-cur" class="input" bind:value={current}>
          <option value="">{t('notebook.noContext')}</option>
          {#each books as b}<option value={b.path}>{b.path}</option>{/each}
        </select>
        <ol class="msgs">
          {#each msgs as m}
            <li class={m.role}>{#if m.role === 'user'}<p>{m.content}</p>{:else}<Md src={m.content} />{#if current && codeOf(m.content)}<button class="btn small" onclick={() => append(codeOf(m.content))}>{t('notebook.appendCell')}</button>{/if}{/if}</li>
          {/each}
          {#if busy}<li class="assistant">{#if streaming}<Md src={streaming} />{:else}<p class="muted small">{t('learn.thinking')}</p>{/if}</li>{/if}
        </ol>
        <label class="sr-only" for="nb-in">{t('notebook.ask')}</label>
        <textarea id="nb-in" class="input" rows="3" bind:value={input} use:enterSubmit={() => void ask()} placeholder={t('notebook.ask')} aria-describedby="nb-e"></textarea>
        <EnterHint id="nb-e" />
        <div class="row">
          <button class="btn primary" onclick={ask} disabled={busy || !input.trim()}>{t('thread.send')}</button>
          {#if busy}<button class="btn quiet" onclick={() => reqId && api.stopAssistant(reqId)}>{t('common.stop')}</button>{/if}
        </div>
      </aside>
    </div>
  {/if}
  <p class="hint">{t('notebook.hostNote')}</p>
</div>

<style>
  .head h1 { margin: 0; }
  .split { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: var(--s-3); height: calc(100dvh - var(--topbar-h) - 140px); min-height: 480px; }
  iframe { width: 100%; height: 100%; border: 1px solid var(--line); border-radius: var(--r-2); background: #fff; }
  .assistant { display: flex; flex-direction: column; gap: var(--s-2); overflow: auto; }
  .msgs { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-2); flex: 1; align-content: start; }
  .msgs li { padding: var(--s-2) var(--s-3); border-radius: var(--r-2); font-size: var(--fs-sm); }
  .msgs .user { background: var(--accent-soft); }
  .msgs .assistant { background: var(--surface-2); }
  @media (max-width: 1023px) { .split { grid-template-columns: minmax(0, 1fr); height: auto; } iframe { height: 70vh; } }
</style>
