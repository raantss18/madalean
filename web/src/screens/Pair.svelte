<script lang="ts">
  // Pairing screen for remote browsers (tailnet / LAN): code shown on the host + a name for this device.
  import { onMount } from 'svelte';
  import { api, ApiError } from '../lib/api/client';
  import type { Hello } from '../lib/api/types';
  import { navigate, route } from '../lib/router.svelte';
  import { t, i18n } from '../lib/i18n/index.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  let hello = $state<Hello | null>(null);
  let code = $state('');
  let name = $state(defaultName());
  let busy = $state(false);
  let err = $state('');
  let codeEl: HTMLInputElement | undefined = $state();
  const reason = $derived(route.query.get('reason') ?? '');
  // QR code of the host = https://<host>/pair?code=XXXXXX: prefill, and on Android offer the app (intent:// link,
  // camera apps ignore custom schemes). Inside the app itself (window.madaleanShell) the shell takes over.
  const qrCode = (route.query.get('code') ?? '').replace(/\D/g, '').slice(0, 6);
  if (qrCode.length === 6) code = qrCode;
  const isAndroid = typeof navigator !== 'undefined' && /Android/.test(navigator.userAgent)
    && !(typeof window !== 'undefined' && (window as unknown as { madaleanShell?: unknown }).madaleanShell);
  const appLink = $derived(isAndroid
    ? `intent://pair?host=${encodeURIComponent(location.host)}&code=${qrCode.length === 6 ? qrCode : ''}`
      + `#Intent;scheme=madalean;package=mg.madalean.app;`
      + `S.browser_fallback_url=${encodeURIComponent('https://raantss18.github.io/madalean/download.html')};end`
    : '');

  function defaultName(): string {
    if (typeof navigator === 'undefined') return '';
    const ua = navigator.userAgent;
    const os = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac/.test(ua) ? 'Mac' : /Windows/.test(ua) ? 'Windows' : /Linux/.test(ua) ? 'Linux' : '';
    const br = /Firefox/.test(ua) ? 'Firefox' : /Edg\//.test(ua) ? 'Edge' : /Chrome/.test(ua) ? 'Chrome' : /Safari/.test(ua) ? 'Safari' : 'Navigateur';
    return os ? `${br} — ${os}` : br;
  }
  onMount(async () => {
    try { hello = await api.hello(); if (hello.lang === 'fr' || hello.lang === 'en') i18n.set(hello.lang); } catch { /* offline */ }
    codeEl?.focus();
  });

  async function submit(e: Event) {
    e.preventDefault();
    const c = code.replace(/\D/g, '');
    if (c.length !== 6) { err = t('pair.codeFormat'); codeEl?.focus(); return; }
    if (!name.trim()) { err = t('pair.nameRequired'); return; }
    busy = true; err = '';
    try {
      await api.pair(c, name.trim());
      navigate('/', { replace: true });
    } catch (x) {
      if (x instanceof ApiError) {
        const m = (x.body['message'] as { params?: { m?: number } } | undefined)?.params?.m ?? Math.ceil(Number(x.body['retry_after'] ?? 600) / 60);
        err = x.kind === 'wrong' || x.kind === 'bad_code' ? t('pair.wrong')
          : x.kind === 'expired' ? t('pair.expired')
          : x.kind === 'no_code' ? t('pair.noCode')
          : x.kind === 'locked' ? t('pair.locked', { m })
          : x.kind === 'rate_limited' ? t('pair.rateLimited')
          : x.status === 0 ? t('err.network') : x.serverText || t('err.generic', { code: x.kind });
      } else err = t('err.network');
      code = '';
      codeEl?.focus();
    } finally { busy = false; }
  }
  async function logout() {
    try { await api.logout(); } catch { /* ignore */ }
    location.assign('/pair');
  }
</script>

<main class="pair" id="main">
  <div class="card">
    <img src="/brand/icon.svg" alt="" width="56" height="56" />
    <h1>{t('pair.title')}</h1>
    {#if hello?.paired && !hello.local}
      <p>{t('pair.already', { host: hello.host_name })}</p>
      <div class="row"><a class="btn primary" href="/">{t('pair.open')}</a><button class="btn" onclick={logout}>{t('pair.logout')}</button></div>
    {:else if hello?.local}
      <p>{t('pair.local')}</p>
      <a class="btn primary" href="/">{t('pair.open')}</a>
    {:else}
      {#if reason === 'auth'}<p class="notice" role="status">{t('pair.reasonAuth')}</p>{/if}
      <p>{t('pair.lead', { host: hello?.host_name ?? '…' })}</p>
      {#if appLink}
        <a class="btn primary wide app" href={appLink}>{t('pair.openApp')}</a>
        <p class="small muted">{t('pair.openAppHint')}</p>
        <p class="small">{t('pair.orBrowser')}</p>
      {/if}
      <p class="notice small" role="note"><strong>{t('pair.everyTime')}</strong> {t('pair.everyTimeHint', { h: 2 })}</p>
      <ol class="steps small">
        <li>{t('pair.step1')}</li>
        <li>{t('pair.step2')}</li>
      </ol>
      <form onsubmit={submit} novalidate>
        <div class="field">
          <label for="pair-code">{t('pair.code')}</label>
          <input bind:this={codeEl} id="pair-code" class="input code" inputmode="numeric" autocomplete="one-time-code" maxlength="7" pattern="[0-9 ]*"
            bind:value={code} aria-invalid={err ? 'true' : undefined} aria-describedby={err ? 'pair-err' : 'pair-code-h'} />
          <p class="hint" id="pair-code-h">{t('pair.codeHint')}</p>
        </div>
        <div class="field">
          <label for="pair-name">{t('pair.name')}</label>
          <input id="pair-name" class="input" bind:value={name} autocomplete="off" maxlength="60" />
          <p class="hint">{t('pair.nameHint')}</p>
        </div>
        {#if err}<p class="error-text" id="pair-err" role="alert">{err}</p>{/if}
        <button class="btn primary wide" type="submit" disabled={busy}>{busy ? t('pair.pairing') : t('pair.submit')}</button>
      </form>
    {/if}
    <div class="lang row">
      <button class="btn quiet small" lang="fr" aria-pressed={i18n.lang === 'fr'} onclick={() => i18n.set('fr')}>Français</button>
      <button class="btn quiet small" lang="en" aria-pressed={i18n.lang === 'en'} onclick={() => i18n.set('en')}>English</button>
    </div>
  </div>
</main>

<style>
  .pair { min-height: 100dvh; display: grid; place-items: center; padding: var(--s-4); }
  .card { width: min(440px, 100%); background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--laterite-mark); border-radius: var(--r-3); padding: var(--s-5); box-shadow: var(--shadow-1); }
  .card img { border-radius: 12px; display: block; margin-bottom: var(--s-3); }
  .code { font: 600 1.75rem/1 var(--font-mono); letter-spacing: 0.35em; text-align: center; max-width: 14rem; }
  .steps { padding-left: 1.2em; color: var(--text-2); }
  .notice { background: var(--running-soft); color: var(--running); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); font-weight: 600; }
  .wide { width: 100%; min-height: 48px; }
  .app { display: flex; align-items: center; justify-content: center; font-size: 1.1rem; margin: var(--s-3) 0 var(--s-1); text-decoration: none; }
  .lang { justify-content: center; margin-top: var(--s-4); }
</style>
