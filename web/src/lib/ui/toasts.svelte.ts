// Toasts: transient messages, with at most one action (often « Annuler » = undo).
export type ToastLevel = 'info' | 'ok' | 'warn' | 'error';
export interface Toast {
  id: number;
  level: ToastLevel;
  text: string;
  action?: { label: string; run: () => void | Promise<void> };
  timeout: number;
}

let next = 1;
export const toasts = $state<{ list: Toast[] }>({ list: [] });
const timers = new Map<number, ReturnType<typeof setTimeout>>();

export function toast(level: ToastLevel, text: string, opts: { action?: Toast['action']; timeout?: number } = {}): number {
  const id = next++;
  // Undo toasts stay longer (WCAG 2.2.1: enough time); errors stay until dismissed when they carry an action.
  const timeout = opts.timeout ?? (opts.action ? 10_000 : level === 'error' ? 9_000 : 5_000);
  toasts.list.push({ id, level, text, action: opts.action, timeout });
  if (toasts.list.length > 4) dismiss(toasts.list[0]!.id);
  if (timeout > 0) timers.set(id, setTimeout(() => dismiss(id), timeout));
  return id;
}

export function dismiss(id: number): void {
  const i = toasts.list.findIndex((t) => t.id === id);
  if (i >= 0) toasts.list.splice(i, 1);
  const tm = timers.get(id);
  if (tm) clearTimeout(tm);
  timers.delete(id);
}

/** Pause auto-dismiss while hovered/focused (WCAG 2.2.1). */
export function hold(id: number): void {
  const tm = timers.get(id);
  if (tm) clearTimeout(tm);
  timers.delete(id);
}
export function release(id: number): void {
  if (timers.has(id)) return;
  timers.set(id, setTimeout(() => dismiss(id), 4000));
}
