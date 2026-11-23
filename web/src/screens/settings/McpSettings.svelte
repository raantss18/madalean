<script lang="ts">
  // Réglages › Outils (MCP) (session S-AZ, DECISIONS D58, docs/MCP.md). Two things, both on the host only:
  // « Madalean comme serveur MCP » — let another assistant of this computer use Madalean's tools (the command / JSON
  // to copy, the switches) — and « Serveurs MCP externes » — tools of other programs that Madalean's models may call
  // (add, test, switch on, tick the allowed tools). Every change is saved at once (D43); nothing needs « Save ».
  import { mcp, type McpInfo, type McpExternal, type McpActivity } from '../../lib/api/mcp';
  import { ApiError } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, tn, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { saveSettings } from './save';
  import HostLock from './HostLock.svelte';
  import Icon from '../../components/Icon.svelte';

  const local = $derived(app.m.local);
  let info = $state<McpInfo | null>(null);
  let activity = $state<McpActivity[]>([]);
  let copied = $state('');
  let name = $state('');
  let kind = $state<'stdio' | 'http'>('stdio');
  let target = $state('');
  let adding = $state(false);
  let addErr = $state('');
  let busy = $state<Record<string, boolean>>({});
  let confirmDel = $state<string | null>(null);

  async function load() {
    try { info = await mcp.info(); activity = (await mcp.activity()).activity.slice(0, 20); }
    catch (e) { toast('error', errorText(e)); }
  }
  $effect(() => { if (local) void load(); });

  async function sw(key: 'mcp_server' | 'mcp_server_http' | 'mcp_server_sage', on: boolean) {
    if (await saveSettings({ [key]: on }, true)) await load();
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); copied = text; } catch { toast('info', text); }
  }
  function replace(s: McpExternal) {
    if (info) info.servers = info.servers.map((x) => (x.id === s.id ? s : x));
  }
  async function add(e: SubmitEvent) {
    e.preventDefault();
    if (!target.trim() || adding) return;
    adding = true; addErr = '';
    try {
      const body = kind === 'stdio' ? { name: name.trim(), transport: kind, command: target.trim() }
        : { name: name.trim(), transport: kind, url: target.trim() };
      const r = await mcp.add(body);
      info?.servers.push(r.server);
      name = ''; target = '';
      await test(r.server.id);
    } catch (err) {
      addErr = err instanceof ApiError ? tk(`mcp.err.${err.kind}`, errorText(err)) : errorText(err);
    } finally { adding = false; }
  }
  async function test(id: string) {
    busy = { ...busy, [id]: true };
    try {
      const r = await mcp.test(id);
      replace(r.server);
      toast(r.server.status.ok ? 'ok' : 'warn', r.server.status.ok ? tn('mcp.ext.tested', r.server.tools.length) : t('mcp.ext.testFailed'));
      activity = (await mcp.activity()).activity.slice(0, 20);
    } catch (err) { toast('error', errorText(err)); }
    finally { busy = { ...busy, [id]: false }; }
  }
  async function patch(s: McpExternal, b: Partial<Pick<McpExternal, 'enabled' | 'allowed'>>) {
    const before = { ...s };
    replace({ ...s, ...b });                                   // optimistic
    try { replace((await mcp.patch(s.id, b)).server); }
    catch (err) { replace(before); toast('error', errorText(err)); }
  }
  function allow(s: McpExternal, tool: string, on: boolean) {
    void patch(s, { allowed: on ? [...s.allowed, tool] : s.allowed.filter((x) => x !== tool) });
  }
  async function remove(id: string) {
    confirmDel = null;
    try { await mcp.remove(id); if (info) info.servers = info.servers.filter((x) => x.id !== id); toast('ok', t('mcp.ext.removed')); }
    catch (err) { toast('error', errorText(err)); }
  }
  const json = $derived(info ? JSON.stringify(info.server.connect.json, null, 2) : '');
</script>

{#if !local}
  <HostLock text={t('mcp.hostOnly')} />
{:else if info}
  <section class="panel" aria-labelledby="mcp-srv">
    <h3 id="mcp-srv">{t('mcp.srv.title')}</h3>
    <p class="hint">{t('mcp.srv.intro')}</p>
    <label class="switch"><input type="checkbox" checked={info.server.enabled} aria-describedby="mcp-srv-h" onchange={(e) => sw('mcp_server', e.currentTarget.checked)} /><span>{t('mcp.srv.enable')}</span></label>
    <p class="hint" id="mcp-srv-h">{t('mcp.srv.enableHint')}</p>
    {#if info.server.enabled}
      <h4>{t('mcp.srv.claudeCode')}</h4>
      <pre class="cmd" aria-label={t('mcp.srv.claudeCode')}>{info.server.connect.claude_code}</pre>
      <button class="btn small quiet" onclick={() => copy(info!.server.connect.claude_code)}><Icon name="check" size={14} />{copied === info.server.connect.claude_code ? t('draft.copied') : t('draft.copy')}</button>
      <h4>{t('mcp.srv.other')}</h4>
      <p class="hint">{t('mcp.srv.otherHint')}</p>
      <pre class="cmd" aria-label={t('mcp.srv.other')}>{json}</pre>
      <button class="btn small quiet" onclick={() => copy(json)}>{copied === json ? t('draft.copied') : t('draft.copy')}</button>
      <p class="hint">{t('mcp.srv.running')}</p>

      <label class="switch"><input type="checkbox" checked={info.server.http} aria-describedby="mcp-http-h" onchange={(e) => sw('mcp_server_http', e.currentTarget.checked)} /><span>{t('mcp.srv.http')}</span></label>
      <p class="hint" id="mcp-http-h">{t('mcp.srv.httpHint')}</p>
      {#if info.server.http}
        <pre class="cmd" aria-label={t('mcp.srv.http')}>{info.server.connect.claude_code_http}</pre>
        <button class="btn small quiet" onclick={() => copy(info!.server.connect.claude_code_http)}>{copied === info.server.connect.claude_code_http ? t('draft.copied') : t('draft.copy')}</button>
      {/if}
      <label class="switch"><input type="checkbox" checked={info.server.sage} aria-describedby="mcp-sage-h" onchange={(e) => sw('mcp_server_sage', e.currentTarget.checked)} /><span>{t('mcp.srv.sage')}</span></label>
      <p class="hint" id="mcp-sage-h">{t('mcp.srv.sageHint')}</p>
    {/if}
    <details>
      <summary>{tn('mcp.srv.tools', info.server.tools.filter((x) => x.available).length)}</summary>
      <ul class="tools">
        {#each info.server.tools as tool (tool.name)}
          <li class:off={!tool.available}><strong>{tool.title}</strong> <code>{tool.name}</code>{#if !tool.available} — {t('mcp.srv.toolOff')}{/if}<br /><span class="small">{tool.description}</span></li>
        {/each}
      </ul>
    </details>
  </section>

  <section class="panel" aria-labelledby="mcp-ext">
    <h3 id="mcp-ext">{t('mcp.ext.title')}</h3>
    <p class="hint">{t('mcp.ext.intro')}</p>
    <form class="add" onsubmit={add}>
      <fieldset class="f">
        <legend class="label">{t('mcp.ext.kind')}</legend>
        <div class="seg">
          <label><input type="radio" name="mcpkind" checked={kind === 'stdio'} onchange={() => (kind = 'stdio')} />{t('mcp.ext.stdio')}</label>
          <label><input type="radio" name="mcpkind" checked={kind === 'http'} onchange={() => (kind = 'http')} />{t('mcp.ext.http')}</label>
        </div>
      </fieldset>
      <div class="grid">
        <div class="field">
          <label for="mcp-name">{t('mcp.ext.name')} <span class="small">({t('common.optional')})</span></label>
          <input id="mcp-name" class="input" bind:value={name} maxlength="80" autocomplete="off" />
        </div>
        <div class="field">
          <label for="mcp-target">{kind === 'stdio' ? t('mcp.ext.command') : t('mcp.ext.url')}</label>
          <input id="mcp-target" class="input mono" bind:value={target} aria-describedby="mcp-target-h" aria-invalid={addErr ? 'true' : undefined}
            placeholder={kind === 'stdio' ? 'uvx lean-lsp-mcp' : 'http://127.0.0.1:8000/mcp'} autocomplete="off" spellcheck="false" />
        </div>
      </div>
      <p class="hint" id="mcp-target-h">{kind === 'stdio' ? t('mcp.ext.commandHint') : t('mcp.ext.urlHint')}</p>
      {#if addErr}<p class="err" role="alert">{addErr}</p>{/if}
      <button class="btn" type="submit" disabled={adding || !target.trim()}><Icon name="plus" size={16} />{adding ? t('mcp.ext.adding') : t('mcp.ext.add')}</button>
    </form>

    {#if info.servers.length === 0}
      <p class="hint">{t('mcp.ext.none')}</p>
    {:else}
      <ul class="servers">
        {#each info.servers as s (s.id)}
          <li>
            <div class="head">
              <label class="switch"><input type="checkbox" checked={s.enabled} disabled={!s.status.ok} onchange={(e) => patch(s, { enabled: e.currentTarget.checked })} /><span class="nm">{s.name}</span></label>
              <span class="small state" class:bad={s.status.ok === false}>
                {#if s.status.ok}{t('mcp.ext.ok', { when: fmtTime(s.status.t), n: s.tools.length })}
                {:else if s.status.error}{t('mcp.ext.error', { error: s.status.error })}
                {:else}{t('mcp.ext.untested')}{/if}
              </span>
            </div>
            <p class="small mono where">{s.transport === 'stdio' ? s.command.join(' ') : s.url}</p>
            {#if s.tools.length}
              <fieldset class="f">
                <legend class="small">{t('mcp.ext.allowed')}</legend>
                <ul class="toolchecks">
                  {#each s.tools as tool (tool.name)}
                    <li>
                      <label class="check"><input type="checkbox" checked={s.allowed.includes(tool.name)} disabled={!tool.safe} onchange={(e) => allow(s, tool.name, e.currentTarget.checked)} /><span><code>{tool.name}</code>{#if tool.description} — {tool.description}{/if}</span></label>
                      {#if !tool.safe}<p class="small bad">{t('mcp.ext.unsafe')}</p>{/if}
                    </li>
                  {/each}
                </ul>
              </fieldset>
            {/if}
            <div class="row">
              <button class="btn small" onclick={() => test(s.id)} disabled={busy[s.id]}><Icon name="refresh" size={14} />{busy[s.id] ? t('mcp.ext.testing') : t('mcp.ext.test')}</button>
              {#if confirmDel === s.id}
                <button class="btn small danger" onclick={() => remove(s.id)}>{t('mcp.ext.confirmRemove')}</button>
                <button class="btn small quiet" onclick={() => (confirmDel = null)}>{t('common.cancel')}</button>
              {:else}
                <button class="btn small quiet" onclick={() => (confirmDel = s.id)}>{t('mcp.ext.remove')}</button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}
    <p class="hint">{t('mcp.ext.safety')}</p>
  </section>

  <section class="panel" aria-labelledby="mcp-act">
    <h3 id="mcp-act">{t('mcp.act.title')}</h3>
    {#if activity.length === 0}<p class="hint">{t('mcp.act.none')}</p>
    {:else}
      <div class="table-wrap">
        <table class="act">
          <thead><tr><th scope="col">{t('mcp.act.when')}</th><th scope="col">{t('mcp.act.dir')}</th><th scope="col">{t('mcp.act.tool')}</th><th scope="col">{t('mcp.act.result')}</th></tr></thead>
          <tbody>
            {#each activity as a, i (i)}
              <tr>
                <td>{fmtTime(a.t)}</td>
                <td>{a.dir === 'in' ? t('mcp.act.in') : t('mcp.act.out')}</td>
                <td><code>{a.dir === 'out' ? `${a.server}/${a.tool}` : a.tool}</code></td>
                <td class:bad={!a.ok}>{a.ok ? t('mcp.act.ok', { ms: a.ms }) : a.error || t('mcp.act.failed')}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
    <button class="btn small quiet" onclick={load}><Icon name="refresh" size={14} />{t('mcp.act.refresh')}</button>
  </section>
{:else}
  <p class="hint">{t('common.loading')}</p>
{/if}

<style>
  .panel h3 { margin: 0 0 var(--s-2); }
  .panel h4 { margin: var(--s-3) 0 var(--s-1); font-size: var(--fs-md, 1rem); }
  .cmd { font: 0.8125rem/1.45 var(--font-mono); background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); white-space: pre-wrap; overflow-wrap: anywhere; margin: 0 0 var(--s-1); }
  .mono { font-family: var(--font-mono); }
  .f { border: 0; padding: 0; margin: 0 0 var(--s-2); }
  .grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: var(--s-3); }
  .tools, .servers, .toolchecks { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: var(--s-2); }
  .tools .off { color: var(--text-2); }
  .servers > li { border-top: 1px solid var(--line); padding-top: var(--s-2); }
  .head { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; justify-content: space-between; }
  .nm { font-weight: 600; }
  .where { color: var(--text-2); overflow-wrap: anywhere; margin: var(--s-1) 0; }
  .bad { color: var(--failed); }
  .err { color: var(--failed); }
  .row { display: flex; gap: var(--s-2); flex-wrap: wrap; margin-top: var(--s-2); }
  .table-wrap { overflow-x: auto; }
  .act { border-collapse: collapse; width: 100%; font-size: var(--fs-sm); }
  .act th, .act td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); }
  @media (max-width: 767px) { .grid { grid-template-columns: minmax(0, 1fr); } }
</style>
