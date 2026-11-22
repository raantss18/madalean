// Bursts of WebSocket events applied once per animation frame (S-AP, docs/PERFORMANCE.md « Interface sur
// téléphone »). Each socket message is its own task: applied one by one, every `job.updated` / `dossier.updated`
// would recompute and re-render whatever reads it, many times per frame on a slow phone. The batcher keeps the
// events in arrival order and hands them over together in the next frame (or after `maxWaitMs` when frames do not
// come: hidden tab), so the store applies them in one synchronous run and Svelte renders once.

export type Schedule = (cb: () => void) => void;

/** requestAnimationFrame, with a timer as a fallback (a hidden tab gets no frames). The first to fire wins. */
export function frameOrTimeout(maxWaitMs = 100): Schedule {
  return (cb) => {
    let done = false;
    const run = () => { if (done) return; done = true; cb(); };
    if (typeof requestAnimationFrame !== 'undefined') requestAnimationFrame(run);
    setTimeout(run, maxWaitMs);
  };
}

export class FrameBatcher<T> {
  private queue: T[] = [];
  private scheduled = false;
  /** For tests and the perf page: batches flushed, items delivered, largest batch. */
  stats = { batches: 0, items: 0, largest: 0 };

  constructor(private handle: (items: T[]) => void, private schedule: Schedule = frameOrTimeout()) {}

  push(item: T): void {
    this.queue.push(item);
    if (this.scheduled) return;
    this.scheduled = true;
    this.schedule(() => this.flush());
  }

  /** Delivers what is waiting now (also used before something that must see every event, e.g. a resync). */
  flush(): void {
    this.scheduled = false;
    if (!this.queue.length) return;
    const items = this.queue;
    this.queue = [];
    this.stats.batches++;
    this.stats.items += items.length;
    this.stats.largest = Math.max(this.stats.largest, items.length);
    this.handle(items);
  }

  get pending(): number {
    return this.queue.length;
  }
}
