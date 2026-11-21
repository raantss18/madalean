<script lang="ts">
  // Live model output of one job. Never janky:
  // - tokens live outside Svelte state (StreamStore) and are painted at most once per animation frame;
  // - text is split into fixed 200-line blocks; finished blocks never re-render and use `content-visibility:auto`
  //   (the browser skips layout/paint of off-screen blocks — virtualisation that keeps line wrapping);
  // - the view sticks to the bottom only when the reader is already there (no jump while reading above);
  // - reasoning (« thinking ») is collapsed by default.
  import { onDestroy } from 'svelte';
  import { app } from '../lib/store/app.svelte';
  import { t, tk } from '../lib/i18n/index.svelte';
  import type { StreamPart } from '../lib/store/streams';

  let { jobId, stage = '', attempt = null, maxHeight = '420px', label = '' }: { jobId: string; stage?: string; attempt?: number | null; maxHeight?: string; label?: string } = $props();

  const BLOCK = 200;
  interface Section { kind: string; stage: string; attempt: number; blocks: string[]; tail: string; chars: number; frozen: number }
  let sections = $state<Section[]>([]);
  let showThinking = $state(false);
  let box: HTMLDivElement | undefined = $state();
  let stick = true;
  let rev = -1;
  const totalLines = $derived(sections.reduce((n, s) => n + s.blocks.length * BLOCK + (s.tail ? s.tail.split('\n').length : 0), 0));

  function rebuild(parts: StreamPart[]) {
    const wanted = parts.filter((p) => (!stage || p.stage === stage) && (attempt === null || p.attempt === attempt));
    const next: Section[] = [];
    for (let i = 0; i < wanted.length; i++) {
      const p = wanted[i]!;
      const old = sections[i];
      // Reuse frozen blocks: only the tail of the last section changes while streaming.
      if (old && old.kind === p.kind && old.stage === p.stage && old.attempt === p.attempt && old.chars === p.text.length) { next.push(old); continue; }
      // Only the text after the frozen blocks is split again (O(new text) per frame, not O(total)).
      const same = old && old.kind === p.kind && old.stage === p.stage && old.attempt === p.attempt && p.text.length >= old.chars;
      const blocks = same ? old.blocks.slice() : [];
      let offset = same ? old.frozen : 0;
      const lines = p.text.slice(offset).split('\n');
      let k = 0;
      while (lines.length - k > BLOCK) {
        const chunk = lines.slice(k, k + BLOCK).join('\n') + '\n';
        blocks.push(chunk);
        offset += chunk.length;
        k += BLOCK;
      }
      next.push({ kind: p.kind, stage: p.stage, attempt: p.attempt, blocks, tail: lines.slice(k).join('\n'), chars: p.text.length, frozen: offset });
    }
    sections = next;
  }

  function paint() {
    const s = app.streams.get(jobId);
    if (s.rev === rev) return;
    rev = s.rev;
    if (box) stick = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    rebuild(s.parts);
    if (stick) requestAnimationFrame(() => { if (box) box.scrollTop = box.scrollHeight; });
  }

  let unsub: (() => void) | null = null;
  $effect(() => {
    const id = jobId;
    void stage; void attempt;
    rev = -1;
    sections = [];
    unsub?.();
    unsub = app.streams.subscribe(id, paint);
    paint();
    return () => { unsub?.(); unsub = null; };
  });
  onDestroy(() => unsub?.());
  const hasThinking = $derived(sections.some((s) => s.kind === 'thinking'));
</script>

<div class="stream">
  {#if hasThinking}
    <button class="btn small quiet" aria-expanded={showThinking} onclick={() => (showThinking = !showThinking)}>{showThinking ? t('stream.hideThinking') : t('stream.showThinking')}</button>
  {/if}
  <!-- svelte-ignore a11y_no_noninteractive_tabindex (a scrollable region must be reachable by keyboard, WCAG 2.1.1) -->
  <div class="box" bind:this={box} style:max-height={maxHeight} role="log" aria-label={label || t('stream.label')} aria-live="off" tabindex="0">
    {#if sections.length === 0}
      <p class="wait muted small">{t('stream.waiting')}</p>
    {/if}
    {#each sections as s, i (i)}
      {#if s.kind !== 'thinking' || showThinking}
        <div class="sec {s.kind}">
          {#if s.kind !== 'text'}<span class="tag xs">{tk(`stream.kind.${s.kind}`, s.kind)}</span>{/if}
          {#each s.blocks as b, j (j)}<pre class="blk frozen">{b}</pre>{/each}
          <pre class="blk">{s.tail}</pre>
        </div>
      {/if}
    {/each}
  </div>
  <p class="sr-only" aria-live="polite">{totalLines > 0 && totalLines % 50 === 0 ? t('stream.progress', { n: totalLines }) : ''}</p>
</div>

<style>
  .box { overflow: auto; overflow-anchor: none; background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); contain: content; }
  .blk { margin: 0; font: 0.8125rem/1.55 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text); }
  .blk.frozen { content-visibility: auto; contain-intrinsic-size: auto 310px; }
  .sec + .sec { margin-top: var(--s-2); padding-top: var(--s-2); border-top: 1px dashed var(--line); }
  .sec.thinking .blk { color: var(--text-2); font-style: italic; }
  .sec.tool_call .blk, .sec.tool_result .blk { color: var(--text-2); }
  .tag { display: inline-block; margin-bottom: 2px; color: var(--text-3); font-weight: 650; }
  .wait { margin: var(--s-2) 0; }
</style>
