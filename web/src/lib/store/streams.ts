// Streamed model output (job.token) kept OUTSIDE the reactive state: thousands of tokens per minute must not
// re-render the app. Views subscribe and are notified at most once per animation frame.
import type { TokenKind } from '../api/types';

export interface StreamPart {
  stage: string;
  attempt: number;
  kind: TokenKind;
  text: string;
  /** Number of '\n' in text (for size estimates). */
  lines: number;
}

export class JobStream {
  parts: StreamPart[] = [];
  rev = 0;
  chars = 0;
  info: { stage: string; text: string; t: number }[] = [];
  /** Model currently answering (from job.info data.model), "" when unknown. */
  model = '';

  append(stage: string, attempt: number, kind: TokenKind, text: string): void {
    const last = this.parts[this.parts.length - 1];
    if (last && last.stage === stage && last.attempt === attempt && last.kind === kind) {
      last.text += text;
      last.lines += countNl(text);
    } else {
      this.parts.push({ stage, attempt, kind, text, lines: countNl(text) });
    }
    this.chars += text.length;
    this.rev++;
  }

  /** `job.info` with data.event = restart/switch: another model starts, the partial text of that step is dropped. */
  dropPartial(stage: string): void {
    while (this.parts.length) {
      const last = this.parts[this.parts.length - 1]!;
      if (last.stage !== stage) break;
      this.chars -= last.text.length;
      this.parts.pop();
    }
    this.rev++;
  }

  /** Parts of the most recent (stage, attempt). */
  latest(): StreamPart[] {
    const last = this.parts[this.parts.length - 1];
    if (!last) return [];
    return this.parts.filter((p) => p.stage === last.stage && p.attempt === last.attempt);
  }
}

function countNl(s: string): number {
  let n = 0;
  for (let i = s.indexOf('\n'); i !== -1; i = s.indexOf('\n', i + 1)) n++;
  return n;
}

type Listener = () => void;

export class StreamStore {
  private streams = new Map<string, JobStream>();
  private listeners = new Map<string, Set<Listener>>();
  private dirty = new Set<string>();
  private scheduled = false;
  /** Keep at most this many jobs' output in memory. */
  max = 40;
  private raf: (cb: () => void) => void;

  constructor(raf?: (cb: () => void) => void) {
    this.raf = raf ?? ((cb) => (typeof requestAnimationFrame !== 'undefined' ? requestAnimationFrame(() => cb()) : setTimeout(cb, 16)));
  }

  get(jobId: string): JobStream {
    let s = this.streams.get(jobId);
    if (!s) {
      s = new JobStream();
      this.streams.set(jobId, s);
      if (this.streams.size > this.max) {
        const oldest = this.streams.keys().next().value as string;
        if (oldest !== jobId && !this.listeners.get(oldest)?.size) this.streams.delete(oldest);
      }
    }
    return s;
  }

  has(jobId: string): boolean {
    return this.streams.has(jobId);
  }

  token(jobId: string, stage: string, attempt: number, kind: TokenKind, text: string): void {
    this.get(jobId).append(stage, attempt, kind, text);
    this.mark(jobId);
  }

  info(jobId: string, stage: string, text: string, data: Record<string, unknown>): void {
    const s = this.get(jobId);
    const ev = data?.['event'];
    if (ev === 'restart') s.dropPartial(stage);
    if (typeof data?.['model'] === 'string') s.model = data['model'] as string;
    s.info.push({ stage, text, t: Date.now() });
    s.rev++;
    this.mark(jobId);
  }

  /** Seeds a stream from saved attempts (page opened while a job runs). */
  seed(jobId: string, parts: { stage: string; attempt: number; text: string; kind?: string }[]): void {
    const s = this.get(jobId);
    if (s.parts.length) return;
    for (const p of parts) if (p.text) s.append(p.stage, p.attempt, (p.kind as TokenKind) ?? 'text', p.text);
    this.mark(jobId);
  }

  subscribe(jobId: string, fn: Listener): () => void {
    let set = this.listeners.get(jobId);
    if (!set) this.listeners.set(jobId, (set = new Set()));
    set.add(fn);
    return () => set!.delete(fn);
  }

  private mark(jobId: string): void {
    this.dirty.add(jobId);
    if (this.scheduled) return;
    this.scheduled = true;
    this.raf(() => {
      this.scheduled = false;
      this.flush();
    });
  }

  /** Notifies the views of what changed now (the socket batch already runs inside a frame, S-AP). */
  flush(): void {
    if (!this.dirty.size) return;
    const ids = [...this.dirty];
    this.dirty.clear();
    for (const id of ids) for (const fn of this.listeners.get(id) ?? []) fn();
  }
}
