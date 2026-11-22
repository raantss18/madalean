// Autosave of one editable thing (session S-AK, docs/UI.md §14.5): debounced after the last change, flushed on blur,
// before an in-app navigation, when the page is hidden or closed, and when the editor goes away; failures retried
// with backoff; a conflict (409: changed on another device) keeps the user's text and stops retrying.
//
//   const as = new Autosave(async () => { await api.patchDossier(id, { title }); });
//   oninput → as.touch()    onblur → as.flush()    onDestroy → as.destroy()   <SaveState state={as} />
import { ApiError } from '../api/client';
import { beforeNavigate } from '../router.svelte';

export type SaveStatus = 'saved' | 'dirty' | 'saving' | 'error' | 'conflict';

export interface AutosaveOptions {
  /** ms of idle before saving (default 1000). */
  delay?: number;
  /** Is this error a conflict (no retry)? Default: ApiError with status 409 / kind 'conflict'. */
  isConflict?: (e: unknown) => boolean;
  /** Called after a conflict, e.g. to show a merge view. */
  onConflict?: (e: unknown) => void;
}

const live = new Set<Autosave>();

export function isConflictError(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 409 || e.kind === 'conflict');
}

/** Backoff of the n-th retry (1-based): 2, 4, 8, 16, 30, 30… s. */
export function retryDelay(n: number): number {
  return Math.min(30_000, 1000 * 2 ** Math.max(1, n));
}

export class Autosave {
  status = $state<SaveStatus>('saved');
  /** The last error (SaveState shows it in plain words through errorText). */
  lastError = $state<unknown>(null);
  private timer: ReturnType<typeof setTimeout> | null = null;
  private retries = 0;
  private running: Promise<boolean> | null = null;
  private again = false;
  private readonly delay: number;
  private readonly unhook: () => void;

  constructor(private readonly save: () => Promise<unknown>, private readonly opts: AutosaveOptions = {}) {
    this.delay = opts.delay ?? 1000;
    live.add(this);
    this.unhook = beforeNavigate(() => { void this.flush(); });
  }

  get pending(): boolean { return this.status === 'dirty' || this.status === 'saving' || this.status === 'error'; }

  /** Something changed: save after `delay` ms of quiet. */
  touch(): void {
    if (this.status === 'saving') { this.again = true; return; }
    if (this.status !== 'conflict') this.status = 'dirty';
    this.schedule(this.delay);
  }

  private schedule(ms: number): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => { this.timer = null; void this.flush(); }, ms);
  }

  /** Save now if anything is pending. Resolves true when everything is saved. */
  flush(): Promise<boolean> {
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    if (this.running) { return this.running; }
    if (this.status !== 'dirty' && this.status !== 'error') return Promise.resolve(this.status === 'saved');
    this.running = this.run().finally(() => { this.running = null; });
    return this.running;
  }

  private async run(): Promise<boolean> {
    this.status = 'saving';
    this.again = false;
    try {
      await this.save();
      this.retries = 0;
      this.lastError = null;
      if (this.again) { this.again = false; this.status = 'dirty'; this.schedule(this.delay); return false; }
      this.status = 'saved';
      return true;
    } catch (e) {
      const conflict = (this.opts.isConflict ?? isConflictError)(e);
      this.lastError = e;
      if (conflict) {
        this.status = 'conflict';
        this.opts.onConflict?.(e);
        return false;
      }
      this.status = 'error';
      this.retries += 1;
      this.schedule(retryDelay(this.retries));
      return false;
    }
  }

  /** The conflict was resolved (text reloaded or merged): back to normal. */
  resolved(): void { this.status = 'saved'; this.lastError = null; this.retries = 0; }

  /** The editor goes away: save what is pending, stop listening. */
  destroy(): void {
    void this.flush().finally(() => live.delete(this));
    this.unhook();
    if (this.status === 'saved' || this.status === 'conflict') live.delete(this);
  }
}

/** Save everything pending (page hidden / closed). */
export function flushAll(): void {
  for (const a of [...live]) void a.flush();
}

export function anyUnsaved(): boolean {
  return [...live].some((a) => a.status === 'error' || a.status === 'conflict' || a.status === 'saving' || a.status === 'dirty');
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', flushAll);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flushAll(); });
  window.addEventListener('beforeunload', (e) => {
    flushAll();
    // Only warn when a save really failed: pending saves were just sent.
    if ([...live].some((a) => a.status === 'error' || a.status === 'conflict')) { e.preventDefault(); e.returnValue = ''; }
  });
}
