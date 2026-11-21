// Sequencing of WebSocket events (docs/API.md §4): exactly-once, in-order delivery across reconnects.
// - every sequenced event has `seq` (+1 per event, shared by all clients);
// - duplicates (seq <= last) are dropped; a gap triggers a `resume`, later events wait in a buffer;
// - after (re)connecting, `hello` → `resume {seq, boot}`; a different `boot` or a `resync` → full reload.
import type { SeqEvent, ServerEvent } from '../api/types';

export interface SequencerHooks {
  deliver(ev: SeqEvent): void;
  send(msg: Record<string, unknown>): void;
  /** Reload GET /state; must call `reset(seq, boot)` when done. */
  resync(reason: 'boot' | 'server' | 'gap'): void;
}

export class Sequencer {
  last = 0;
  boot = 0;
  /** Out-of-order events waiting for a gap to be filled. */
  private pending = new Map<number, SeqEvent>();
  private waitingResync = false;
  private resumeAskedFor = -1;
  stats = { delivered: 0, duplicates: 0, gaps: 0, resyncs: 0 };

  constructor(private hooks: SequencerHooks) {}

  /** After loading GET /state. */
  reset(seq: number, boot: number): void {
    this.last = seq;
    this.boot = boot;
    this.waitingResync = false;
    this.resumeAskedFor = -1;
    // Keep buffered events newer than the snapshot, drop the rest.
    for (const s of [...this.pending.keys()]) if (s <= seq) this.pending.delete(s);
    this.flush();
  }

  /** Called for every message from the socket. */
  receive(ev: ServerEvent): void {
    const t = (ev as { type: string }).type;
    if (t === 'hello') {
      const h = ev as { seq: number; boot: number };
      if (this.boot && h.boot !== this.boot) return this.askResync('boot');
      if (!this.boot) return this.askResync('boot');
      if (h.seq > this.last) this.askResume();
      return;
    }
    if (t === 'resync') return this.askResync('server');
    if (t === 'pong') return;
    const se = ev as SeqEvent;
    if (typeof se.seq !== 'number') return;
    if (this.waitingResync) {
      // Keep everything: after a server restart seq starts again from a lower number; reset() sorts it out.
      if (this.pending.size < 5000) this.pending.set(se.seq, se);
      return;
    }
    if (se.seq <= this.last) {
      this.stats.duplicates++;
      return;
    }
    if (se.seq === this.last + 1) {
      this.deliverOne(se);
      this.flush();
      return;
    }
    // Gap: buffer and ask the server for what we missed (once per gap start).
    this.pending.set(se.seq, se);
    this.stats.gaps++;
    if (this.pending.size > 5000) return this.askResync('gap');
    this.askResume();
  }

  /** The socket (re)opened: nothing to do until `hello`. The socket closed: forget the pending resume. */
  disconnected(): void {
    this.resumeAskedFor = -1;
  }

  private askResume(): void {
    if (this.resumeAskedFor === this.last) return;
    this.resumeAskedFor = this.last;
    this.hooks.send({ type: 'resume', seq: this.last, boot: this.boot });
  }

  private askResync(reason: 'boot' | 'server' | 'gap'): void {
    if (this.waitingResync) return;
    this.waitingResync = true;
    this.stats.resyncs++;
    this.hooks.resync(reason);
  }

  private deliverOne(ev: SeqEvent): void {
    this.last = ev.seq;
    this.stats.delivered++;
    this.hooks.deliver(ev);
  }

  private flush(): void {
    let next = this.pending.get(this.last + 1);
    while (next) {
      this.pending.delete(next.seq);
      this.deliverOne(next);
      next = this.pending.get(this.last + 1);
    }
    if (this.pending.size === 0) this.resumeAskedFor = -1;
  }
}
