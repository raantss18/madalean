<script lang="ts" module>
  export interface KeyProvider { id: string; name: string; url: string; prefix: RegExp | null; paid: boolean; search?: boolean }
</script>

<script lang="ts">
  // One key, as easy as L Katta (moved from Keys.svelte, S-U): « Créer une clé » opens the provider's page, paste →
  // saved in the host's keyring → tested automatically → « ça marche » with the models it unlocks, or a clear reason.
  // Never displayed again.
  import { api, openExternalOrTab } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, tn } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Icon from '../../components/Icon.svelte';
  import GithubCheck from '../../components/GithubCheck.svelte';

  let { p, set, onchange }: { p: KeyProvider; set: boolean; onchange?: () => void } = $props();
  let value = $state('');
  let status = $state<{ level: 'busy' | 'ok' | 'warn' | 'error'; text: string } | null>(null);
  let confirmRemove = $state(false);

  function countModels(provider: string): number {
    const seen = new Set<string>();
    for (const r of Object.values(app.m.models?.roles ?? {})) for (const c of r.candidates) if (c.provider === provider) seen.add(c.key);
    return seen.size;
  }

  async function save() {
    const key = value.trim();
    value = '';                      // never keep the key in the page
    if (!key) return;
    if (/\s/.test(key) || key.length < 16) { status = { level: 'error', text: t('keys.malformed') }; return; }
    // providers change their key formats: an unusual shape never blocks — the real test decides
    const oddShape = !!(p.prefix && !p.prefix.test(key));
    status = { level: 'busy', text: t('keys.saving') };
    try {
      await api.setKey(p.id, key, false);   // the test below runs here (S-AO: the server unpaused the provider)
      if (app.m.models) app.m.models.keys = { ...app.m.models.keys, [p.id]: true };
      onchange?.();
      status = { level: 'busy', text: t('keys.testing') };
      if (p.search) {
        // an Internet search provider: one tiny real search (1 credit at most)
        const r = await api.testSearchKey(p.id).catch(() => null);
        if (!r) { status = { level: 'warn', text: t('hub.searchUnreachable') }; return; }
        if (r.ok === null) { status = { level: 'warn', text: t('keys.localMode') }; return; }
        status = r.ok ? { level: 'ok', text: t('hub.searchWorks') }
          : { level: 'error', text: t('keys.refused', { reason: tk(`hub.reason.${r.reason ?? ''}`, r.reason ?? '') }) + (oddShape ? ' ' + t('keys.wrongShape', { name: p.name }) : '') };
        return;
      }
      if (p.id === 'github') {
        const g = await api.testKey(p.id).catch(() => null) as { ok: boolean; login?: string; reason?: string } | null;
        const code = (g?.reason ?? '').replace(/^github:/, '');
        status = g?.ok ? { level: 'ok', text: t('gh.as', { login: g.login ?? '' }) }
          : { level: 'error', text: g ? tk(`gh.code.${code}`, t('gh.code.unknown')) : t('gh.code.github_unreachable') };
        return;
      }
      if (p.id === 'huggingface') {
        const h = await api.testKey(p.id).catch(() => null) as { ok: boolean | null; login?: string; reason?: string; warning?: string; names?: string[]; model?: string } | null;
        app.m.models = await api.refreshModels().catch(() => app.m.models);
        if (!h || h.reason === 'network' || h.reason === 'offline') { status = { level: 'warn', text: t('hf.unreachable') }; return; }
        if (h.ok === null && h.reason === 'local_mode') { status = { level: 'warn', text: t('keys.localMode') }; return; }
        if (!h.ok) { status = { level: 'error', text: t('keys.refused', { reason: tk(`keys.reason.${h.reason ?? ''}`, h.reason ?? '') }) + (oddShape ? ' ' + t('keys.wrongShape', { name: p.name }) : '') }; return; }
        const goedel = (h.names ?? []).find((n) => /32B/.test(n)) ?? h.names?.[0];
        const parts = [t('hf.as', { login: h.login ?? '' }), goedel ? t('hf.goedel', { name: goedel.replace(/ \(.*$/, '') }) : t('hf.noLive')];
        if (h.warning === 'inference_permission') parts.push(t('hf.permission'));
        status = { level: h.warning || !goedel ? 'warn' : 'ok', text: parts.join(' ') };
        return;
      }
      const test = await api.testKey(p.id).catch(() => ({ ok: null as boolean | null, reason: 'not_supported', models: undefined as number | undefined, model: '' }));
      app.m.models = await api.refreshModels().catch(() => app.m.models);
      const n = test.models ?? countModels(p.id);
      if (test.ok === false && (test.reason ?? '') === 'no_model') { status = { level: 'warn', text: t('keys.savedNoModel') }; return; }
      if (test.ok === false) {
        const reason = (test.reason ?? '').split(':')[0] ?? '';
        status = { level: 'error', text: t('keys.refused', { reason: tk(`keys.reason.${reason}`, test.reason ?? '') }) + (oddShape ? ' ' + t('keys.wrongShape', { name: p.name }) : '') };
        return;
      }
      status = test.ok === true
        ? { level: 'ok', text: (n ? tn('keys.worksN', n) : t('keys.works')) + (test.model ? ' ' + t('keys.testedWith', { model: test.model.split(':').slice(1).join(':') || test.model }) : '') }
        : test.reason === 'local_mode' ? { level: 'warn', text: t('keys.localMode') }
        : n ? { level: 'ok', text: tn('keys.savedN', n) } : { level: 'warn', text: t('keys.savedNoModel') };
    } catch (e) {
      status = { level: 'error', text: errorText(e) };
    } finally {
      onchange?.();
    }
  }
  async function remove() {
    confirmRemove = false;
    status = { level: 'busy', text: t('keys.removing') };
    try {
      await api.deleteKey(p.id);
      if (app.m.models) { const k = { ...app.m.models.keys }; delete k[p.id]; app.m.models.keys = k; }
      status = { level: 'ok', text: t('keys.removed') };
      toast('ok', t('keys.removedToast', { name: p.name }));
      onchange?.();
    } catch (e) { status = { level: 'error', text: errorText(e) }; }
  }
  function getKey() {
    openExternalOrTab(p.url);
    status = { level: 'ok', text: t('keys.pageOpened', { name: p.name }) };
    queueMicrotask(() => document.getElementById(`key-${p.id}`)?.focus());
  }
</script>

{#if set}
  {#if confirmRemove}
    <div class="row confirm" role="group" aria-label={t('keys.confirmRemove', { name: p.name })}>
      <span class="small">{t('keys.confirmRemove', { name: p.name })}</span>
      <button class="btn small danger" onclick={remove}>{t('keys.remove')}</button>
      <button class="btn small quiet" onclick={() => (confirmRemove = false)}>{t('keys.keep')}</button>
    </div>
  {:else}
    <div class="row"><button class="btn small" onclick={() => (confirmRemove = true)}>{t('keys.remove')}</button><span class="xs muted">{t('keys.neverShown')}</span></div>
    {#if p.id === 'github'}<GithubCheck />{/if}
  {/if}
{:else}
  <form class="row add" onsubmit={(e) => { e.preventDefault(); void save(); }}>
    {#if p.url}<button class="btn small" type="button" onclick={getKey}><Icon name="external" size={14} />{t('hub.create')}</button>{/if}
    <label class="sr-only" for="key-{p.id}">{t('keys.pasteLabel', { name: p.name })}</label>
    <input id="key-{p.id}" class="input" type="password" autocomplete="off" spellcheck="false" placeholder={t('keys.paste')} bind:value aria-describedby="key-st-{p.id}" />
    <button class="btn small primary" type="submit" disabled={!value.trim() || status?.level === 'busy'}>{t('keys.save')}</button>
  </form>
{/if}
<p class="st {status?.level ?? ''}" id="key-st-{p.id}" role="status" aria-live="polite">{status?.text ?? ''}</p>

<style>
  .add .input { flex: 1; min-width: 10rem; min-height: 36px; }
  @media (pointer: coarse) { .add .input { min-height: 44px; } }
  .st { margin: var(--s-2) 0 0; font-size: var(--fs-sm); min-height: 1.4em; }
  .st:empty { min-height: 0; margin: 0; }
  .st.ok { color: var(--proved); }
  .st.warn { color: var(--running); }
  .st.error { color: var(--failed); }
  .st.busy { color: var(--text-2); }
  .confirm { background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-2); }
</style>
