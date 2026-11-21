<script lang="ts">
  // Untrusted Markdown + maths → sanitised HTML (see lib/md.ts).
  import { renderMarkdown, renderInline } from '../lib/md';
  let { src = '', inline = false, cls = '' }: { src?: string; inline?: boolean; cls?: string } = $props();
  const html = $derived(inline ? renderInline(src) : renderMarkdown(src));
</script>

{#if inline}<span class="md {cls}">{@html html}</span>{:else}<div class="md {cls}">{@html html}</div>{/if}
