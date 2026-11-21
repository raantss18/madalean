// WebSocket connection with automatic reconnection. Knows nothing about the app: it hands raw events to `onEvent`.
import type { ServerEvent } from '../api/types';

export type ConnState = 'connecting' | 'open' | 'reconnecting' | 'offline' | 'closed';

export interface ConnectionOpts {
  url?: string;
  onEvent(ev: ServerEvent): void;
  onState(s: ConnState, info: { attempt: number; nextInMs: number }): void;
  onOpen?(): void;
  onClose?(): void;
  onUnauthorized(): void;
  /** For tests. */
  WebSocketImpl?: typeof WebSocket;
}

const BACKOFF = [300, 1000, 2000, 4000, 8000, 15000];

export class Connection {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private ping: ReturnType<typeof setInterval> | null = null;
  private stopped = false;
  state: ConnState = 'closed';

  constructor(private o: ConnectionOpts) {}

  start(): void {
    this.stopped = false;
    if (typeof window !== 'undefined') {
      window.addEventListener('online', this.onOnline);
      window.addEventListener('offline', this.onOffline);
      document.addEventListener('visibilitychange', this.onVisible);
    }
    this.open();
  }

  stop(): void {
    this.stopped = true;
    this.clearTimers();
    this.ws?.close(1000);
    this.ws = null;
    if (typeof window !== 'undefined') {
      window.removeEventListener('online', this.onOnline);
      window.removeEventListener('offline', this.onOffline);
      document.removeEventListener('visibilitychange', this.onVisible);
    }
    this.set('closed', 0);
  }

  send(msg: Record<string, unknown>): boolean {
    if (this.ws?.readyState === 1) {
      this.ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }

  /** Reconnect now (button « Reconnecter »). */
  retryNow(): void {
    if (this.state === 'open' || this.state === 'connecting') return;
    this.clearTimers();
    this.attempt = 0;
    this.open();
  }

  private url(): string {
    if (this.o.url) return this.o.url;
    const p = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${p}//${location.host}/api/ws`;
  }

  private open(): void {
    if (this.stopped) return;
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      this.set('offline', 0);
      return;
    }
    this.set(this.attempt === 0 ? 'connecting' : 'reconnecting', 0);
    const Impl = this.o.WebSocketImpl ?? WebSocket;
    let ws: WebSocket;
    try {
      ws = new Impl(this.url());
    } catch {
      this.schedule();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      this.attempt = 0;
      this.set('open', 0);
      this.o.onOpen?.();
      this.ping = setInterval(() => this.send({ type: 'ping', t: Date.now() }), 25_000);
    };
    ws.onmessage = (m: MessageEvent) => {
      let ev: ServerEvent;
      try { ev = JSON.parse(String(m.data)) as ServerEvent; } catch { return; }
      this.o.onEvent(ev);
    };
    ws.onclose = (c: CloseEvent) => {
      if (this.ws !== ws) return;
      this.ws = null;
      if (this.ping) clearInterval(this.ping);
      this.ping = null;
      this.o.onClose?.();
      if (c.code === 4401 || c.code === 1008) {
        this.o.onUnauthorized();
        return;
      }
      if (!this.stopped) this.schedule();
    };
    ws.onerror = () => { /* onclose follows */ };
  }

  private schedule(): void {
    const base = BACKOFF[Math.min(this.attempt, BACKOFF.length - 1)] ?? 15000;
    const delay = Math.round(base * (0.8 + Math.random() * 0.4));
    this.attempt++;
    this.set('reconnecting', delay);
    this.timer = setTimeout(() => this.open(), delay);
  }

  private set(s: ConnState, nextInMs: number): void {
    this.state = s;
    this.o.onState(s, { attempt: this.attempt, nextInMs });
  }

  private clearTimers(): void {
    if (this.timer) clearTimeout(this.timer);
    if (this.ping) clearInterval(this.ping);
    this.timer = null;
    this.ping = null;
  }

  private onOnline = () => this.retryNow();
  private onOffline = () => {
    this.ws?.close();
    this.clearTimers();
    this.set('offline', 0);
  };
  private onVisible = () => {
    if (document.visibilityState === 'visible' && this.state !== 'open') this.retryNow();
  };
}
