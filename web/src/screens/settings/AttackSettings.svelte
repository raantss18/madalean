<script lang="ts">
  // Réglages › Problèmes ouverts (S-BK, D70; docs/ATTACK.md): the kinds of problems, the daily budget, how many at once,
  // the highest difficulty of open problems, public notes for the site's team (off by default). Saved at once through
  // PATCH /api/attack/settings; the values are read from the general settings (`attack_*`), with the contract's defaults.
  import { app } from '../../lib/store/app.svelte';
  import { attack, ATTACK_KINDS, type AttackKind, type AttackSettings } from '../../lib/api/attack';
  import { t } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';

  const DEFAULTS: Required<Omit<AttackSettings, 'attack_enabled'>> = {
    attack_kinds: [...ATTACK_KINDS], attack_usd_per_day: 5, attack_parallel: 2, attack_max_difficulty_open: 40, attack_post_notes: false,
  };
  const raw = $derived((app.m.settings ?? {}) as Record<string, unknown>);
  const s = $derived({
    attack_kinds: (Array.isArray(raw['attack_kinds']) ? raw['attack_kinds'] : DEFAULTS.attack_kinds) as AttackKind[],
    attack_usd_per_day: Number(raw['attack_usd_per_day'] ?? DEFAULTS.attack_usd_per_day),
    attack_parallel: Number(raw['attack_parallel'] ?? DEFAULTS.attack_parallel),
    attack_max_difficulty_open: Number(raw['attack_max_difficulty_open'] ?? DEFAULTS.attack_max_difficulty_open),
    attack_post_notes: Boolean(raw['attack_post_notes'] ?? DEFAULTS.attack_post_notes),
  });

  async function save(patch: AttackSettings) {
    const set = app.m.settings as Record<string, unknown> | null;
    const before: Record<string, unknown> = {};
    if (set) for (const [k, v] of Object.entries(patch)) { before[k] = set[k]; set[k] = v; }   // optimistic
    try {
      const r = await attack.settings(patch);
      if (set && r && typeof r === 'object') for (const [k, v] of Object.entries(r)) if (k.startsWith('attack_')) set[k] = v;
      toast('ok', t('settings.saved'));
    } catch (e) {
      if (set) for (const [k, v] of Object.entries(before)) set[k] = v;
      toast('error', errorText(e));
    }
  }
  function toggleKind(k: AttackKind, on: boolean, el: HTMLInputElement) {
    const next = on ? [...new Set([...s.attack_kinds, k])] : s.attack_kinds.filter((x) => x !== k);
    if (!next.length) { el.checked = true; toast('error', t('attack.set.oneKind')); return; }
    void save({ attack_kinds: ATTACK_KINDS.filter((x) => next.includes(x)) });
  }
  function num(k: 'attack_usd_per_day' | 'attack_parallel' | 'attack_max_difficulty_open', min: number, max: number, e: Event, step = 1) {
    const el = e.currentTarget as HTMLInputElement;
    const v = Number(el.value);
    if (!Number.isFinite(v) || v < min || v > max) { toast('error', t('settings.range', { min, max })); el.value = String(s[k]); return; }
    void save({ [k]: step < 1 ? Math.round(v * 100) / 100 : Math.round(v) });
  }
</script>

<p class="hint">{t('attack.set.lead')} <a href="/attaque">{t('attack.set.openScreen')}<Icon name="chevronRight" size={14} /></a></p>

<section class="panel" aria-labelledby="as-kinds">
  <fieldset>
    <legend id="as-kinds"><h3>{t('attack.set.kinds')}</h3></legend>
    {#each ATTACK_KINDS as k (k)}
      <label class="kind">
        <input type="checkbox" checked={s.attack_kinds.includes(k)} onchange={(e) => toggleKind(k, e.currentTarget.checked, e.currentTarget)} />
        <span><strong>{t(`attack.kind.${k}`)}</strong><span class="small muted"> — {t(`attack.set.kind.${k}`)}</span></span>
      </label>
    {/each}
  </fieldset>
</section>

<section class="panel">
  <div class="grid">
    <div class="field">
      <label for="as-usd">{t('attack.set.budget')}</label>
      <div class="money"><span aria-hidden="true">$</span><input id="as-usd" class="input" type="number" inputmode="decimal" min="0" max="100" step="0.5" value={s.attack_usd_per_day} onchange={(e) => num('attack_usd_per_day', 0, 100, e, 0.01)} aria-describedby="as-usd-h" /></div>
      <p class="xs muted" id="as-usd-h">{t('attack.set.budgetHint')}</p>
    </div>
    <div class="field">
      <label for="as-par">{t('attack.set.parallel')}</label>
      <input id="as-par" class="input" type="number" inputmode="numeric" min="1" max="8" step="1" value={s.attack_parallel} onchange={(e) => num('attack_parallel', 1, 8, e)} aria-describedby="as-par-h" />
      <p class="xs muted" id="as-par-h">{t('attack.set.parallelHint')}</p>
    </div>
    <div class="field">
      <label for="as-diff">{t('attack.set.maxDiff')}</label>
      <input id="as-diff" class="input" type="number" inputmode="numeric" min="0" max="100" step="5" value={s.attack_max_difficulty_open} onchange={(e) => num('attack_max_difficulty_open', 0, 100, e)} aria-describedby="as-diff-h" />
      <p class="xs muted" id="as-diff-h">{t('attack.set.maxDiffHint')}</p>
    </div>
  </div>
</section>

<section class="panel" aria-labelledby="as-notes">
  <h3 id="as-notes" class="sr-only">{t('attack.set.notes')}</h3>
  <label class="switch"><input type="checkbox" checked={s.attack_post_notes} onchange={(e) => save({ attack_post_notes: e.currentTarget.checked })} aria-describedby="as-notes-h" /><span>{t('attack.set.notes')}</span></label>
  <p class="hint" id="as-notes-h">{t('attack.set.notesHint')}</p>
</section>

<style>
  fieldset { border: 0; margin: 0; padding: 0; display: grid; gap: var(--s-2); }
  legend { padding: 0; margin-bottom: var(--s-2); }
  legend h3 { margin: 0; }
  .kind { display: flex; gap: 10px; align-items: flex-start; min-height: var(--touch); padding: 6px 0; cursor: pointer; }
  .kind input { margin-top: 4px; flex: none; width: 18px; height: 18px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: var(--s-4); }
  .money { display: flex; align-items: center; gap: 6px; }
  .hint a :global(.ico) { vertical-align: -2px; }
  p.xs { margin: 4px 0 0; }
</style>
