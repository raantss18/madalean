<script lang="ts">
  // Status of a plan node: icon + words (never colour alone).
  import Icon from '../../components/Icon.svelte';
  import { tk } from '../../lib/i18n/index.svelte';
  import { UI_ICON } from '../../lib/plan/layout';
  let { ui, obvious = false, small = false }: { ui: string; obvious?: boolean; small?: boolean } = $props();
</script>

<span class="pst ui-{ui}" class:small><Icon name={UI_ICON[ui] ?? 'info'} size={small ? 12 : 14} />{tk(`plan.ui.${ui}`, ui)}{#if obvious && ui === 'proved'}<span class="ob"> · {tk('plan.obviousTag', 'obvious')}</span>{/if}</span>

<style>
  .pst { display: inline-flex; align-items: center; gap: 4px; font-size: var(--fs-xs); font-weight: 700; color: var(--text-2); white-space: nowrap; }
  .pst.small { font-size: 0.75rem; }
  .ob { font-weight: 600; }
  .ui-proved { color: var(--proved); }
  .ui-failed { color: var(--failed); }
  .ui-running, .ui-hole, .ui-conditional { color: var(--running); }
  .ui-to_validate { color: var(--accent); }
  .ui-abandoned, .ui-alternative { color: var(--text-3); }
</style>
