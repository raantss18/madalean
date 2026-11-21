<script lang="ts">
  import { encode } from 'uqr';
  let { text, label, size = 200 }: { text: string; label: string; size?: number } = $props();
  const qr = $derived(encode(text, { ecc: 'M', border: 2 }));
  const path = $derived.by(() => {
    let d = '';
    qr.data.forEach((row, y) => row.forEach((on, x) => { if (on) d += `M${x} ${y}h1v1h-1z`; }));
    return d;
  });
</script>

<svg width={size} height={size} viewBox="0 0 {qr.size} {qr.size}" role="img" aria-label={label} shape-rendering="crispEdges" class="qr">
  <rect width={qr.size} height={qr.size} fill="#fff" />
  <path d={path} fill="#000" />
</svg>

<style>.qr { border-radius: 6px; display: block; }</style>
