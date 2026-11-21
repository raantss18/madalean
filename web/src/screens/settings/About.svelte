<script lang="ts">
  import { app } from '../../lib/store/app.svelte';
  import { api, shell } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import Icon from '../../components/Icon.svelte';
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
  .about img { border-radius: 14px; }
  .word { font-family: var(--font-serif); font-size: 1.3rem; }
  h3 { margin-top: var(--s-4); }
  .contact { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
  .contact li { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
</style>
