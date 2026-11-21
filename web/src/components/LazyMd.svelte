<script lang="ts">
  // Markdown + maths without putting KaTeX on the critical path: plain text first, rendered once the chunk is in.
  import type { Component } from 'svelte';
  let { src = '', inline = false, cls = '' }: { src?: string; inline?: boolean; cls?: string } = $props();
  let Md = $state<Component<{ src?: string; inline?: boolean; cls?: string }> | null>(null);
  let promise: Promise<unknown> | null = null;
  $effect(() => {
    if (Md || promise) return;
    const load = () => { promise ??= import('./Md.svelte').then((m) => { Md = m.default; }); };
    // Load when idle (or at once if the text contains maths and is being shown).
    if (/\$|\\\(|\\\[/.test(src)) load();
    else if ('requestIdleCallback' in window) requestIdleCallback(load, { timeout: 2000 }); else setTimeout(load, 300);
  });
</script>

{#if Md}<Md {src} {inline} {cls} />{:else if inline}<span class="md {cls}">{src}</span>{:else}<div class="md {cls}"><p>{src}</p></div>{/if}
