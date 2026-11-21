// The single reactive store: server state (Model) + connection + streams. Every screen reads from here; every
// server event goes through `Sequencer` → `applyEvent`. Screens never keep their own copy of server data.
import { api, ApiError } from '../api/client';
import type { Dossier, Job, SeqEvent, ServerEvent } from '../api/types';
import { i18n } from '../i18n/index.svelte';
import { toast } from '../ui/toasts.svelte';
import { Connection, type ConnState } from './connection';
import { activeJobFor, applyEvent, emptyModel, lastJobFor, loadSnapshot, type Model } from './model';
import { Sequencer } from './sequencer';
import { StreamStore } from './streams';

type AssistantListener = (ev: { type: string; kind?: string; text: string; model?: string; finish?: string; error?: string }) => void;

class AppStore {
  m: Model = $state(emptyModel());
  conn = $state<{ state: ConnState; nextInMs: number; attempt: number; everOpen: boolean }>({
    state: 'closed', nextInMs: 0, attempt: 0, everOpen: false,
  });
  bootError = $state<'' | 'network' | 'unauthorized' | 'other'>('');
  /** Monotonic counter bumped on resync, so open screens can refetch. */
  epoch = $state(0);
  streams = new StreamStore();
  /** Model currently answering per job (from `job.info` data.model): feeds the « who receives what » indicator. */
  liveModel = $state<Record<string, string>>({});
  private seq: Sequencer;
  private connection: Connection | null = null;
  private assistantListeners = new Map<string, AssistantListener>();
  private assistantEarly = new Map<string, Parameters<AssistantListener>[0][]>();
  private resyncing: Promise<void> | null = null;
  /** Extension point for screens added later (research layer): handle plugin event types. */
  private extraHandlers = new Map<string, Set<(ev: SeqEvent) => void>>();

  constructor() {
    this.seq = new Sequencer({
      deliver: (ev) => this.deliver(ev),
      send: (msg) => this.connection?.send(msg),
      resync: () => void this.reload(),
    });
  }

  async boot(): Promise<void> {
    try {
      const s = await api.state();
      loadSnapshot(this.m, s);
      this.seq.reset(s.seq, s.boot);
      if (s.settings?.language) i18n.set(s.settings.language);
      this.bootError = '';
    } catch (e) {
      this.bootError = e instanceof ApiError ? (e.status === 401 ? 'unauthorized' : e.status === 0 ? 'network' : 'other') : 'other';
      if (this.bootError !== 'unauthorized') setTimeout(() => void this.boot(), 3000);
      return;
    }
    if (!this.connection) {
      this.connection = new Connection({
        onEvent: (ev) => this.onSocket(ev),
        onState: (state, info) => {
          this.conn.state = state;
          this.conn.nextInMs = info.nextInMs;
          this.conn.attempt = info.attempt;
          if (state === 'open') this.conn.everOpen = true;
        },
        onClose: () => this.seq.disconnected(),
        onUnauthorized: () => {
          if (!location.pathname.startsWith('/pair')) location.assign('/pair?reason=auth');
        },
      });
      this.connection.start();
    }
  }

  reconnect(): void {
    this.connection?.retryNow();
  }

  /** GET /state again (server restarted, or events lost). */
  reload(): Promise<void> {
    if (this.resyncing) return this.resyncing;
    this.resyncing = (async () => {
      try {
        const s = await api.state();
        loadSnapshot(this.m, s);
        this.seq.reset(s.seq, s.boot);
        this.epoch++;
      } catch {
        setTimeout(() => { this.resyncing = null; void this.reload(); }, 2000);
        return;
      }
      this.resyncing = null;
    })();
    return this.resyncing;
  }

  private onSocket(ev: ServerEvent): void {
    this.seq.receive(ev);
  }

  private deliver(ev: SeqEvent): void {
    const e = ev as unknown as Record<string, unknown> & { type: string };
    switch (e.type) {
      case 'job.token':
        this.streams.token(e['job_id'] as string, e['stage'] as string, e['attempt'] as number,
          (e['kind'] as 'text') ?? 'text', (e['text'] as string) ?? '');
        return;
      case 'job.info': {
        const data = (e['data'] as Record<string, unknown>) ?? {};
        if (typeof data['model'] === 'string') this.liveModel[e['job_id'] as string] = data['model'] as string;
      }
        this.streams.info(e['job_id'] as string, e['stage'] as string, (e['text'] as string) ?? '',
          (e['data'] as Record<string, unknown>) ?? {});
        return;
      case 'toast':
        toast((e['level'] as 'info') ?? 'info', (e['text'] as string) ?? '');
        return;
      case 'assistant.token':
      case 'assistant.done':
      case 'assistant.error': {
        const rid = e['request_id'] as string;
        const fn = this.assistantListeners.get(rid);
        if (!fn) {
          // The answer can overtake the HTTP 202 that tells us its id: keep it briefly for listenAssistant().
          const buf = this.assistantEarly.get(rid) ?? [];
          buf.push(e as never);
          this.assistantEarly.set(rid, buf);
          setTimeout(() => this.assistantEarly.delete(rid), 60_000);
          return;
        }
        fn(e as never);
        if (e.type !== 'assistant.token') this.assistantListeners.delete(rid);
        return;
      }
      case 'settings.updated': {
        applyEvent(this.m, ev);
        const lang = this.m.settings?.language;
        if (lang && lang !== i18n.lang) i18n.set(lang);
        return;
      }
    }
    if (!applyEvent(this.m, ev)) {
      for (const fn of this.extraHandlers.get(e.type) ?? []) fn(ev);
    }
  }

  /** Research screens (later session) can listen to their own event types. */
  on(type: string, fn: (ev: SeqEvent) => void): () => void {
    let set = this.extraHandlers.get(type);
    if (!set) this.extraHandlers.set(type, (set = new Set()));
    set.add(fn);
    return () => set!.delete(fn);
  }

  listenAssistant(requestId: string, fn: AssistantListener): () => void {
    this.assistantListeners.set(requestId, fn);
    const early = this.assistantEarly.get(requestId);
    if (early) {
      this.assistantEarly.delete(requestId);
      for (const ev of early) {
        fn(ev);
        if (ev.type !== 'assistant.token') this.assistantListeners.delete(requestId);
      }
    }
    return () => this.assistantListeners.delete(requestId);
  }

  /** Fetches the full dossier (cached; kept fresh by `dossier.updated`). */
  async ensureDossier(id: string, force = false): Promise<Dossier | null> {
    if (!force && this.m.full[id]) return this.m.full[id]!;
    const r = await api.dossier(id);
    this.m.full[id] = r.dossier;
    if (r.job) this.m.jobs[r.job.id] = r.job;
    if (r.job && !this.streams.has(r.job.id)) {
      try {
        const j = await api.job(r.job.id);
        this.streams.seed(j.job.id, j.job.attempts.map((a) => ({ stage: a.stage, attempt: a.index, text: a.raw ?? '' })));
      } catch { /* not important */ }
    }
    return r.dossier;
  }

  activeJob(dossierId: string): Job | undefined {
    return activeJobFor(this.m, dossierId);
  }

  lastJob(dossierId: string): Job | undefined {
    return lastJobFor(this.m, dossierId);
  }

  get activeJobs(): Job[] {
    return Object.values(this.m.jobs)
      .filter((j) => j.state === 'queued' || j.state === 'running')
      .sort((a, b) => a.created - b.created);
  }

  get remote(): boolean {
    return !this.m.local;
  }

  hostOnly(key: string): boolean {
    return this.m.hostOnly.includes(key);
  }

  /** For tests and the perf page: the sequencer counters. */
  get seqStats() {
    return { ...this.seq.stats, last: this.seq.last, boot: this.seq.boot };
  }
}

export const app = new AppStore();
if (typeof window !== 'undefined') (window as unknown as { __madalean: AppStore }).__madalean = app;
