<script lang="ts">
  // Measurement page (used by e2e/perf.spec.ts): streams a synthetic 10 000-line answer through the real
  // StreamStore + StreamView and records frame times while streaming and while scrolling.
  import { app } from '../lib/store/app.svelte';
  import StreamView from '../components/StreamView.svelte';
  let { params: _p }: { params: Record<string, string> } = $props();
  const JOB = '__perf';
  let done = $state(false);
  let typed = $state('');

  function line(i: number): string {
    return `  have h${i} : ∀ x ∈ Finset.range ${i}, f x ≤ g x := by intro x hx; simp [Finset.mem_range] at hx; nlinarith [sq_nonneg (x - ${i})]\n`;
  }
  async function stream(lines: number, perTick: number): Promise<{ frames: number[]; ms: number }> {
    done = false;
    const frames: number[] = [];
    let last = performance.now();
    let running = true;
    const tick = (t: number) => { frames.push(t - last); last = t; if (running) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    const t0 = performance.now();
    let i = 0;
    // Server coalesces tokens every 100 ms; we push faster (every 16 ms) to stress the client.
    await new Promise<void>((resolve) => {
      const iv = setInterval(() => {
        let chunk = '';
        for (let k = 0; k < perTick && i < lines; k++, i++) chunk += line(i);
        app.streams.token(JOB, 'proof', 0, 'text', chunk);
        if (i >= lines) { clearInterval(iv); resolve(); }
      }, 16);
    });
    await new Promise((r) => setTimeout(r, 300));
    running = false;
    done = true;
    return { frames, ms: performance.now() - t0 };
  }
  (window as unknown as { __perf: unknown }).__perf = { stream };
</script>

<h1>Perf</h1>
<p>Synthetic stream. <span data-testid="perf-done">{done ? 'done' : 'idle'}</span></p>
<label for="perf-in">Type while streaming</label>
<input id="perf-in" class="input" bind:value={typed} />
<StreamView jobId={JOB} stage="proof" attempt={0} maxHeight="60vh" label="perf stream" />
