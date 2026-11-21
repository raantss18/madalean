import { describe, it, expect } from 'vitest';
import { Sequencer } from '../../src/lib/store/sequencer';
import type { SeqEvent } from '../../src/lib/api/types';

function harness() {
  const delivered: number[] = [];
  const sent: Record<string, unknown>[] = [];
  const resyncs: string[] = [];
  const s = new Sequencer({ deliver: (e) => delivered.push(e.seq), send: (m) => sent.push(m), resync: (r) => resyncs.push(r) });
  return { s, delivered, sent, resyncs };
}
const ev = (seq: number): SeqEvent => ({ type: 'toast', seq, ts: 0, level: 'info', key: '', params: {}, text: '' }) as SeqEvent;

describe('Sequencer (seq / resume / resync)', () => {
  it('delivers in order and drops duplicates', () => {
    const h = harness();
    h.s.reset(10, 1);
    for (const n of [11, 12, 12, 11, 13]) h.s.receive(ev(n));
    expect(h.delivered).toEqual([11, 12, 13]);
    expect(h.s.stats.duplicates).toBe(2);
  });
  it('on hello with the same boot and a higher seq, asks to resume from the last seen seq', () => {
    const h = harness();
    h.s.reset(5, 42);
    h.s.receive({ type: 'hello', seq: 9, boot: 42, version: '', local: true });
    expect(h.sent).toEqual([{ type: 'resume', seq: 5, boot: 42 }]);
    for (const n of [6, 7, 8, 9]) h.s.receive(ev(n));
    expect(h.delivered).toEqual([6, 7, 8, 9]);
  });
  it('a gap buffers later events, asks resume once, then flushes in order when filled', () => {
    const h = harness();
    h.s.reset(1, 1);
    h.s.receive(ev(4));
    h.s.receive(ev(5));
    expect(h.delivered).toEqual([]);
    expect(h.sent).toEqual([{ type: 'resume', seq: 1, boot: 1 }]);
    h.s.receive(ev(2));
    h.s.receive(ev(3));
    expect(h.delivered).toEqual([2, 3, 4, 5]);
    expect(h.s.last).toBe(5);
  });
  it('a different boot (server restarted) forces a resync; events newer than the snapshot are kept', () => {
    const h = harness();
    h.s.reset(100, 1);
    h.s.receive({ type: 'hello', seq: 3, boot: 2, version: '', local: true });
    expect(h.resyncs).toEqual(['boot']);
    h.s.receive(ev(4));
    h.s.receive(ev(5));
    expect(h.delivered).toEqual([]);
    h.s.reset(4, 2);           // GET /state answered at seq 4
    expect(h.delivered).toEqual([5]);
  });
  it('a server resync order triggers a reload exactly once', () => {
    const h = harness();
    h.s.reset(10, 1);
    h.s.receive({ type: 'resync', seq: 50, boot: 1 });
    h.s.receive({ type: 'resync', seq: 50, boot: 1 });
    expect(h.resyncs).toEqual(['server']);
  });
  it('first hello before any snapshot asks for a full load', () => {
    const h = harness();
    h.s.receive({ type: 'hello', seq: 3, boot: 9, version: '', local: true });
    expect(h.resyncs).toEqual(['boot']);
  });
  it('too many buffered events → resync instead of unbounded memory', () => {
    const h = harness();
    h.s.reset(0, 1);
    for (let n = 2; n < 5005; n++) h.s.receive(ev(n));
    expect(h.resyncs).toEqual(['gap']);
  });
});
