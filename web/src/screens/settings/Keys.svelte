<script lang="ts">
  // Keys, as easy as L Katta: « Obtenir une clé » opens the provider's page, paste → saved in the host's keyring →
  // tested automatically → « ça marche » with the models it unlocks, or a clear reason. Never displayed again.
  import { api, openExternalOrTab } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, tn } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Icon from '../../components/Icon.svelte';

  interface P { id: string; name: string; url: string; prefix: RegExp | null; paid: boolean }
  const PROVIDERS: P[] = [
    { id: 'anthropic', name: 'Anthropic (Claude)', url: 'https://console.anthropic.com/settings/keys', prefix: /^sk-ant-/, paid: true },
    { id: 'gemini', name: 'Google Gemini', url: 'https://aistudio.google.com/apikey', prefix: /^AIza/, paid: false },
    { id: 'openrouter', name: 'OpenRouter', url: 'https://openrouter.ai/settings/keys', prefix: /^sk-or-/, paid: false },
    { id: 'groq', name: 'Groq', url: 'https://console.groq.com/keys', prefix: /^gsk_/, paid: false },
    { id: 'mistral', name: 'Mistral', url: 'https://console.mistral.ai/api-keys', prefix: null, paid: false },
    { id: 'cerebras', name: 'Cerebras', url: 'https://cloud.cerebras.ai/', prefix: /^csk-/, paid: false },
    { id: 'openai', name: 'OpenAI', url: 'https://platform.openai.com/api-keys', prefix: /^sk-/, paid: true },
    { id: 'deepseek', name: 'DeepSeek', url: 'https://platform.deepseek.com/api_keys', prefix: /^sk-/, paid: true },
    { id: 'github', name: 'GitHub (publication)', url: 'https://github.com/settings/tokens?type=beta', prefix: /^(ghp_|github_pat_|gho_)/, paid: false },
  ];
  const keys = $derived(app.m.models?.keys ?? {});
  let values = $state<Record<string, string>>({});
  let status = $state<Record<string, { level: 'busy' | 'ok' | 'warn' | 'error'; text: string }>>({});
  let confirmRemove = $state<string | null>(null);

  function countModels(provider: string): number {
    const seen = new Set<string>();
    for (const r of Object.values(app.m.models?.roles ?? {})) for (const c of r.candidates) if (c.provider === provider) seen.add(c.key);
    return seen.size;
  }

  async function save(p: P) {
    const key = (values[p.id] ?? '').trim();
    values[p.id] = '';                      // never keep the key in the page
    if (!key) return;
    if (/\s/.test(key) || key.length < 16) { status[p.id] = { level: 'error', text: t('keys.malformed') }; return; }
    // providers change their key formats (Google issued new Gemini key shapes): an unusual shape never blocks — the
    // real test call below decides, and only then is the shape mentioned
    const oddShape = !!(p.prefix && !p.prefix.test(key));
    status[p.id] = { level: 'busy', text: t('keys.saving') };
    try {
      await api.setKey(p.id, key);
      if (app.m.models) app.m.models.keys = { ...app.m.models.keys, [p.id]: true };
      status[p.id] = { level: 'busy', text: t('keys.testing') };
      const test = await api.testKey(p.id).catch(() => ({ ok: null as boolean | null, reason: 'not_supported', models: undefined as number | undefined, model: '' }));
      app.m.models = await api.refreshModels().catch(() => app.m.models);
      const n = test.models ?? countModels(p.id);
      if (test.ok === false && (test.reason ?? '') === 'no_model') { status[p.id] = { level: 'warn', text: t('keys.savedNoModel') }; return; }
      if (test.ok === false) {
        const reason = (test.reason ?? '').split(':')[0] ?? '';
        status[p.id] = { level: 'error', text: t('keys.refused', { reason: tk(`keys.reason.${reason}`, test.reason ?? '') }) + (oddShape ? ' ' + t('keys.wrongShape', { name: p.name }) : '') };
        return;
      }
      status[p.id] = test.ok === true
        ? { level: 'ok', text: (n ? tn('keys.worksN', n) : t('keys.works')) + (test.model ? ' ' + t('keys.testedWith', { model: test.model.split(':').slice(1).join(':') || test.model }) : '') }
        : test.reason === 'local_mode' ? { level: 'warn', text: t('keys.localMode') }
        : n ? { level: 'ok', text: tn('keys.savedN', n) } : { level: 'warn', text: t('keys.savedNoModel') };
    } catch (e) {
      status[p.id] = { level: 'error', text: errorText(e) };
    }
  }
  async function remove(p: P) {
    confirmRemove = null;
    status[p.id] = { level: 'busy', text: t('keys.removing') };
    try {
      await api.deleteKey(p.id);
      if (app.m.models) { const k = { ...app.m.models.keys }; delete k[p.id]; app.m.models.keys = k; }
      status[p.id] = { level: 'ok', text: t('keys.removed') };
      toast('ok', t('keys.removedToast', { name: p.name }));
    } catch (e) { status[p.id] = { level: 'error', text: errorText(e) }; }
  }
  function getKey(p: P) {
    openExternalOrTab(p.url);
    status[p.id] = { level: 'ok', text: t('keys.pageOpened', { name: p.name }) };
    queueMicrotask(() => document.getElementById(`key-${p.id}`)?.focus());
  }
</script>

<p class="lead">{t('keys.lead')}</p>
<p class="hint">{t('keys.where')}</p>
<ul class="providers">
  {#each PROVIDERS as p (p.id)}
    {@const set = Boolean(keys[p.id])}
    {@const st = status[p.id]}
    <li class="panel" class:set>
      <div class="row">
        <h3>{p.name}</h3>
        {#if p.paid}<span class="chip">{t('keys.paid')}</span>{:else}<span class="chip">{t('keys.freeTier')}</span>{/if}
        <span class="spacer"></span>
        {#if set}<span class="chip proved"><Icon name="check" size={12} />{t('keys.saved')}</span>{/if}
      </div>
      <p class="small muted">{tk(`keys.desc.${p.id}`, '')}</p>
      {#if set}
        {#if confirmRemove === p.id}
          <div class="row confirm" role="group" aria-label={t('keys.confirmRemove', { name: p.name })}>
            <span class="small">{t('keys.confirmRemove', { name: p.name })}</span>
            <button class="btn small danger" onclick={() => remove(p)}>{t('keys.remove')}</button>
            <button class="btn small quiet" onclick={() => (confirmRemove = null)}>{t('keys.keep')}</button>
          </div>
        {:else}
          <div class="row"><button class="btn small" onclick={() => (confirmRemove = p.id)}>{t('keys.remove')}</button><span class="xs muted">{t('keys.neverShown')}</span></div>
        {/if}
      {:else}
        <form class="row add" onsubmit={(e) => { e.preventDefault(); void save(p); }}>
          <button class="btn small" type="button" onclick={() => getKey(p)}><Icon name="external" size={14} />{t('keys.get')}</button>
          <label class="sr-only" for="key-{p.id}">{t('keys.pasteLabel', { name: p.name })}</label>
          <input id="key-{p.id}" class="input" type="password" autocomplete="off" spellcheck="false" placeholder={t('keys.paste')} bind:value={values[p.id]} aria-describedby="key-st-{p.id}" />
          <button class="btn small primary" type="submit" disabled={!values[p.id]?.trim() || st?.level === 'busy'}>{t('keys.save')}</button>
        </form>
      {/if}
      <p class="st {st?.level ?? ''}" id="key-st-{p.id}" role="status" aria-live="polite">{st?.text ?? ''}</p>
    </li>
  {/each}
</ul>

<style>
  .lead { color: var(--text-2); max-width: var(--measure); }
  .providers { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-3); grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
  @media (max-width: 767px) { .providers { grid-template-columns: minmax(0, 1fr); } }
  .providers li.panel + li.panel { margin-top: 0; }
  .set { border-color: color-mix(in srgb, var(--proved) 40%, var(--line)); }
  h3 { margin: 0; }
  .add .input { flex: 1; min-width: 10rem; min-height: 36px; }
  @media (pointer: coarse) { .add .input { min-height: 44px; } }
  .st { margin: var(--s-2) 0 0; font-size: var(--fs-sm); min-height: 1.4em; }
  .st.ok { color: var(--proved); }
  .st.warn { color: var(--running); }
  .st.error { color: var(--failed); }
  .st.busy { color: var(--text-2); }
  .confirm { background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-2); }
</style>
