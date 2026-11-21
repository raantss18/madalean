<script lang="ts">
  // Devices: start pairing (big code + countdown + QR madalean://pair?...), list, revoke. Host only.
  import { onDestroy } from 'svelte';
  import { api, shell } from '../../lib/api/client';
  import type { Device } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, fmtTime } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText, isHostOnly } from '../../lib/ui/errors';
  import QrCode from '../../components/QrCode.svelte';
  import HostLock from './HostLock.svelte';
  import Icon from '../../components/Icon.svelte';

  const local = $derived(app.m.local);
  let code = $state<{ code: string; expires: number } | null>(null);
  let left = $state(0);
  let timer: ReturnType<typeof setInterval> | null = null;
  let devices = $state<Device[] | null>(null);
  let browsers = $state<Device[] | null>(null);
  let idleMin = $state(120);
  let address = $state(loadJSON<string>('pair.address', ''));
  let confirmRevoke = $state<string | null>(null);

  $effect(() => { if (app.m.devices) devices = app.m.devices; });
  $effect(() => { if (app.m.browsers) browsers = app.m.browsers; });
  $effect(() => {
    if (!local) return;
    api.devices().then((r) => {
      devices = r.apps ?? r.devices; app.m.devices = devices; browsers = r.browsers ?? []; app.m.browsers = browsers;
      if (r.browser_idle_minutes) idleMin = r.browser_idle_minutes;
    }).catch((e) => { if (!isHostOnly(e)) toast('error', errorText(e)); });
  });
  onDestroy(() => { if (timer) clearInterval(timer); });

  async function start() {
    try {
      const r = await api.pairingStart();
      if (r.remote_url) address = r.remote_url.replace(/^https?:\/\//, '').replace(/\/$/, '');
      code = { code: r.code, expires: Date.now() / 1000 + r.expires_in };
      left = r.expires_in;
      if (timer) clearInterval(timer);
      timer = setInterval(() => { left = Math.max(0, Math.round(code!.expires - Date.now() / 1000)); if (left === 0 && timer) { clearInterval(timer); } }, 1000);
    } catch (e) { toast('error', errorText(e)); }
  }
  async function revoke(d: Device) {
    confirmRevoke = null;
    try { await api.revokeDevice(d.id); devices = (devices ?? []).filter((x) => x.id !== d.id); browsers = (browsers ?? []).filter((x) => x.id !== d.id); toast('ok', t('devices.revoked', { name: d.name })); }
    catch (e) { toast('error', errorText(e)); }
  }
  const link = $derived(code && address.trim() ? `madalean://pair?host=${encodeURIComponent(address.trim()).replace(/%3A/gi, ':')}&code=${code.code}` : '');
  async function forget() {
    try { await api.forgetSelf(); } catch { /* we leave anyway */ }
    location.assign('/pair');
  }
</script>

{#snippet item(d: Device)}
  <li class="row">
    <Icon name="device" />
    <span class="dn"><strong>{d.name}</strong><span class="xs muted">{t('devices.lastSeen', { t: fmtTime(d.last_seen) || '—', ip: d.last_ip || '—' })}{#if d.kind === 'browser' && d.expires_in != null} · {t('devices.browserExpires', { t: `${Math.floor(d.expires_in / 3600)} h ${String(Math.floor((d.expires_in % 3600) / 60)).padStart(2, '0')}` })}{/if}</span></span>
    {#if confirmRevoke === d.id}
      <button class="btn small danger" onclick={() => revoke(d)}>{t('devices.revokeConfirm')}</button>
      <button class="btn small quiet" onclick={() => (confirmRevoke = null)}>{t('common.cancel')}</button>
    {:else}
      <button class="btn small" onclick={() => (confirmRevoke = d.id)}>{t('devices.revoke')}</button>
    {/if}
  </li>
{/snippet}

{#if !local}
  <HostLock />
  <section class="panel">
    <h3>{t('devices.thisDevice')}</h3>
    <p class="small">{t('devices.thisDeviceText', { name: app.m.device?.name ?? '' })}</p>
    <div class="row">
      {#if shell()?.changeServer}<button class="btn" onclick={() => shell()?.changeServer?.()}>{t('devices.changeServer')}</button>{/if}
      <button class="btn danger" onclick={forget}>{t('devices.forget')}</button>
    </div>
  </section>
{:else}
  <section class="panel" aria-labelledby="pair-h">
    <h3 id="pair-h">{t('devices.add')}</h3>
    <p class="small">{t('devices.addLead')}</p>
    {#if code && left > 0}
      <div class="pairing">
        <div>
          <p class="big mono" aria-label={t('devices.codeIs', { code: code.code.split('').join(' ') })}>{code.code.slice(0, 3)} {code.code.slice(3)}</p>
          <p class="small" role="timer" aria-live="off">{t('devices.expiresIn', { m: Math.floor(left / 60), s: String(left % 60).padStart(2, '0') })}</p>
          <div class="field">
            <label for="pair-addr">{t('devices.address')}</label>
            <input id="pair-addr" class="input" bind:value={address} onchange={() => saveJSON('pair.address', address)} placeholder="nitro.tailXXXX.ts.net:10500" />
            <p class="hint">{t('devices.addressHint')}</p>
          </div>
          <button class="btn small" onclick={start}>{t('devices.newCode')}</button>
        </div>
        {#if link}<div class="qr-box"><QrCode text={link} label={t('devices.qrLabel')} /><p class="xs mono link">{link}</p></div>{/if}
      </div>
    {:else}
      {#if code}<p class="small muted">{t('devices.expired')}</p>{/if}
      <button class="btn primary" onclick={start}><Icon name="plus" size={16} />{t('devices.start')}</button>
    {/if}
  </section>

  <section class="panel" aria-labelledby="dev-h">
    <h3 id="dev-h">{t('devices.apps')}</h3>
    {#if devices === null}<p class="muted">{t('common.loading')}</p>
    {:else if devices.length === 0}<p class="muted small">{t('devices.none')}</p>
    {:else}
      <ul class="devs">
        {#each devices as d (d.id)}{@render item(d)}{/each}
      </ul>
      <p class="hint">{t('devices.revokeHint')}</p>
    {/if}
  </section>

  <section class="panel" aria-labelledby="brw-h">
    <h3 id="brw-h">{t('devices.browsers')}</h3>
    <p class="small muted">{t('pair.everyTime')} {t('pair.everyTimeHint', { h: Math.round(idleMin / 6) / 10 })}</p>
    {#if browsers === null}<p class="muted">{t('common.loading')}</p>
    {:else if browsers.length === 0}<p class="muted small">{t('devices.noBrowsers')}</p>
    {:else}
      <ul class="devs">
        {#each browsers as d (d.id)}{@render item(d)}{/each}
      </ul>
    {/if}
  </section>
{/if}

<style>
  h3 { margin-top: 0; }
  .pairing { display: flex; gap: var(--s-5); flex-wrap: wrap; align-items: flex-start; }
  .big { font-size: 3rem; font-weight: 700; letter-spacing: 0.12em; margin: 0; color: var(--text); }
  .qr-box { display: grid; gap: 4px; justify-items: center; }
  .link { max-width: 220px; overflow-wrap: anywhere; color: var(--text-3); }
  .devs { list-style: none; padding: 0; margin: 0; }
  .devs li { border-bottom: 1px solid var(--line); padding: var(--s-2) 0; }
  .dn { flex: 1; display: grid; min-width: 10rem; }
</style>
