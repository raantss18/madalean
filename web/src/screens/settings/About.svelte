<script lang="ts">
  import { app } from '../../lib/store/app.svelte';
  import { api, shell } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  const sh = shell();
</script>

<div class="about">
  <img src="/brand/icon.svg" alt="" width="64" height="64" />
  <p><strong class="word">Madalean</strong> {app.m.version}</p>
  <p class="small">{t('about.host', { host: app.m.host_name })} · {app.m.local ? t('about.local') : t('about.remote', { name: app.m.device?.name ?? '' })}{app.m.demo ? ` · ${t('about.demo')}` : ''}</p>
  <p class="small">{t('about.what')}</p>
  <p class="small">{t('about.lean')}</p>
  {#if sh}
    <p class="small">{t('about.shell', { kind: sh.kind, v: sh.version ?? '' })}</p>
    {#if sh.changeServer}<button class="btn" onclick={() => sh.changeServer?.()}>{t('devices.changeServer')}</button>{/if}
  {/if}
  {#if !app.m.local}<button class="btn" onclick={async () => { try { await api.forgetSelf(); } catch { /* leave anyway */ } location.assign('/pair'); }}>{t('devices.forget')}</button>{/if}
  <h3>{t('about.licences')}</h3>
  <p class="small">{t('about.licencesText')}</p>
</div>

<style>
  .about img { border-radius: 14px; }
  .word { font-family: var(--font-serif); font-size: 1.3rem; }
  h3 { margin-top: var(--s-4); }
</style>
