<script lang="ts">
  // « Problèmes ouverts » on Home (S-BK, D70): shown only while the attack is on (setting `attack_enabled`), one
  // sentence and today's numbers, a link to the screen. Asked when the browser is idle (D48), live by `attack.state`.
  import { app } from '../../lib/store/app.svelte';
  import { attack, type AttackStatus } from '../../lib/api/attack';
  import { headline, money, statusFromEvent } from '../../lib/attack';
  import { t, i18n } from '../../lib/i18n/index.svelte';
  import Icon from '../../components/Icon.svelte';
  import { say } from './say';

  let st = $state<AttackStatus | null>(null);
  const enabled = $derived(Boolean((app.m.settings as Record<string, unknown> | null)?.['attack_enabled']));
  $effect(() => {
    if (!enabled) { st = null; return; }
    const run = () => { attack.get().then((s) => { st = s; }).catch(() => { st = null; }); };
    if ('requestIdleCallback' in window) { const id = requestIdleCallback(run, { timeout: 2500 }); return () => cancelIdleCallback(id); }
    const id = setTimeout(run, 400);
    return () => clearTimeout(id);
  });
  $effect(() => app.on('attack.state', (ev) => { const s = statusFromEvent(ev as unknown as Record<string, unknown>); if (s && enabled) st = s; }));
  const show = $derived(Boolean(enabled && st && st.state !== 'off'));
</script>

{#if show && st}
  <section class="atkcard" aria-labelledby="ac-h">
    <div class="row">
      <h2 id="ac-h"><Icon name="conjecture" size={18} />{t('attack.title')}</h2>
      <span class="spacer"></span>
      <a class="btn small" href="/attaque">{t('attack.card.open')}<Icon name="chevronRight" size={14} /></a>
    </div>
    <p>{say(headline(st, i18n.lang))}</p>
    <p class="small muted">{t('attack.spend')} : {t('attack.spendOf', { usd: money(st.today.usd, i18n.lang), cap: money(st.today.cap, i18n.lang) })}
      · {st.today.taken} {t('attack.count.taken')} · {st.today.proofs} {t('attack.count.proofs')} · {st.today.released} {t('attack.count.released')}</p>
  </section>
{/if}

<style>
  .atkcard { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-3) var(--s-4); display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-2); min-width: 0; }
  h2 { margin: 0; font-size: var(--fs-md); display: inline-flex; align-items: center; gap: 8px; }
  .row { gap: var(--s-2); flex-wrap: wrap; }
  p { margin: 0; }
</style>
