<script lang="ts">
  import { app } from '../../lib/store/app.svelte';
  import { api, shell } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import Icon from '../../components/Icon.svelte';
  import Wordmark from '../../components/Wordmark.svelte';
  const sh = shell();
  // Author shown in « À propos » (same details as the user's other apps).
  const AUTHOR = {
    name: 'RANIRIAMANJAKA Antsa',
    email: 'antsa.raniriamanjaka@univ-antananarivo.mg',
    phone: '+261 33 43 838 82',
    whatsapp: 'https://wa.me/261334383882',
    github: 'https://github.com/raantss18',
  };
</script>

<div class="about">
  <div class="brand"><img src="/brand/icon.svg" alt="" width="56" height="56" /><Wordmark height={44} /></div>
  <p>Madalean {app.m.version}</p>
  <p class="small">{t('about.host', { host: app.m.host_name })} · {app.m.local ? t('about.local') : t('about.remote', { name: app.m.device?.name ?? '' })}{app.m.demo ? ` · ${t('about.demo')}` : ''}</p>
  <p class="small">{t('about.what')}</p>
  <p class="small">{t('about.lean')}</p>
  {#if sh}
    <p class="small">{t('about.shell', { kind: sh.kind, v: sh.version ?? '' })}</p>
    {#if sh.changeServer}<button class="btn" onclick={() => sh.changeServer?.()}>{t('devices.changeServer')}</button>{/if}
  {/if}
  {#if !app.m.local}<button class="btn" onclick={async () => { try { await api.forgetSelf(); } catch { /* leave anyway */ } location.assign('/pair'); }}>{t('devices.forget')}</button>{/if}
  <h3>{t('about.author')}</h3>
  <p><strong>{AUTHOR.name}</strong></p>
  <ul class="contact">
    <li><Icon name="mail" size={14} /> <a href={'mailto:' + AUTHOR.email}>{AUTHOR.email}</a></li>
    <li><Icon name="phone" size={14} /> <a href={'tel:' + AUTHOR.phone.replace(/\s/g, '')}>{AUTHOR.phone}</a> · <a href={AUTHOR.whatsapp} target="_blank" rel="noopener noreferrer">WhatsApp</a></li>
    <li><Icon name="github" size={14} /> <a href={AUTHOR.github} target="_blank" rel="noopener noreferrer">{AUTHOR.github.replace(/^https:\/\//, '')}</a></li>
  </ul>
  <h3>{t('about.licences')}</h3>
  <p class="small">{t('about.licencesText')}</p>
</div>

<style>
  .brand { display: flex; align-items: center; gap: var(--s-3); flex-wrap: wrap; }
  .brand img { border-radius: 12px; }
  h3 { margin-top: var(--s-4); }
  .contact { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
  .contact li { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  @media (pointer: coarse) { .contact a { display: inline-flex; align-items: center; min-height: var(--touch); } .contact { gap: 0; } }
</style>
