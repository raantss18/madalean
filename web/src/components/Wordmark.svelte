<script lang="ts">
  // The Madalean wordmark (navy script, orange ∃ and swoosh; white script on dark themes). Both files are generated
  // by scripts/build_brand.py; only the one matching the active theme is displayed (the other is display:none, so
  // it is out of the accessibility tree too).
  let { height = 32, alt = 'Madalean' }: { height?: number; alt?: string } = $props();
  const width = $derived(Math.round((height * 1726) / 508));
</script>

<span class="wordmark" style:height={`${height}px`}>
  <img class="wm-light" src="/brand/wordmark.svg" {alt} {width} {height} />
  <img class="wm-dark" src="/brand/wordmark-dark.svg" {alt} {width} {height} />
</span>

<style>
  .wordmark { display: inline-flex; align-items: center; line-height: 0; }
  .wordmark img { display: block; max-width: 100%; height: auto; }
  .wm-dark { display: none !important; }
  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme='light'])) .wm-light { display: none !important; }
    :global(:root:not([data-theme='light'])) .wm-dark { display: block !important; }
  }
  :global(:root[data-theme='dark']) .wm-light { display: none !important; }
  :global(:root[data-theme='dark']) .wm-dark { display: block !important; }
</style>
