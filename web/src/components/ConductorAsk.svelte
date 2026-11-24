<script lang="ts">
  // S-AN (D46): « Plafond atteint : continuer avec Claude (+0,50 $) ? » for a request outside a dossier job — the
  // automatic correction of a Calcul cell or of an article compilation. One question at a time, wherever the user
  // is; closing the dialog answers « Continuer sans Claude » (the request then goes on with the free models).
  import type { ConductorAsk } from '../lib/api/types';
  import { api } from '../lib/api/client';
  import { app } from '../lib/store/app.svelte';
  import { t, i18n } from '../lib/i18n/index.svelte';
  import { usdText } from '../lib/conductor';
  import { toast } from '../lib/ui/toasts.svelte';
  import Dialog from './Dialog.svelte';

  let asks = $state<ConductorAsk[]>([]);
  let open = $state(false);
  let sending = $state(false);
  const cur = $derived(asks[0] ?? null);
  const usd = (n: number) => usdText(n, i18n.base);
  let shown = '';                                  // the question on screen (closing the dialog answers it)
  $effect(() => { open = !!cur; shown = cur?.id ?? ''; });
  $effect(() => app.on('conductor.ask', (ev) => {
    const a = ev as unknown as ConductorAsk;
    asks = a.done ? asks.filter((x) => x.id !== a.id) : [...asks.filter((x) => x.id !== a.id), a];
  }));
  $effect(() => {                                   // a question asked before this page was open
    api.conductorAsks().then((r) => { for (const a of r.asks) if (!asks.some((x) => x.id === a.id)) asks = [...asks, a]; })
      .catch(() => { /* older server */ });
  });

  async function reply(approve: boolean) {
    const a = cur;
    if (!a || sending) return;
    sending = true;
    shown = '';
    asks = asks.filter((x) => x.id !== a.id);
    try { await api.answerConductorAsk(a.id, approve); }
    catch { if (approve) toast('error', t('conductor.askTitle')); }
    finally { sending = false; }
  }
</script>

{#if cur}
  <Dialog bind:open title={t('conductor.askTitle')} onclose={() => { if (shown && shown === cur?.id && !sending) void reply(false); }}>
    <p>{t(cur.kind === 'article' ? 'conductor.askArticle' : 'conductor.askCalcul')}</p>
    <p>{t('conductor.askBody', { spent: usd(cur.spent), cap: usd(cur.cap), step: usd(cur.step) })}</p>
    {#snippet actions()}
      <button class="btn" disabled={sending} onclick={() => reply(false)}>{t('conductor.askNo')}</button>
      <button class="btn primary" disabled={sending} onclick={() => reply(true)}>{t('conductor.askYes', { step: usd(cur?.step ?? 0.5) })}</button>
    {/snippet}
  </Dialog>
{/if}
