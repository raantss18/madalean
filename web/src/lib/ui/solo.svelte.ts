// Parts of a dossier open in their own window (« Séparer », D66). The windows of one browser tell each other with a
// BroadcastChannel: the main window knows which parts are away, « Remettre » closes the separate window. The data
// itself is kept in sync by the WebSocket, like any two devices.
import type { Part } from '../flow';

export const away = $state<Record<string, boolean>>({});
const key = (id: string, part: string) => `${id}/${part}`;
type Msg = { type: 'open' | 'closed' | 'close' | 'who'; key?: string };

let chan: BroadcastChannel | null = null;
let own = '';
function channel(): BroadcastChannel | null {
  if (chan || typeof BroadcastChannel === 'undefined') return chan;
  chan = new BroadcastChannel('madalean.solo');
  chan.onmessage = (e: MessageEvent<Msg>) => {
    const m = e.data;
    if (m.type === 'open' && m.key) away[m.key] = true;
    else if (m.type === 'closed' && m.key) delete away[m.key];
    else if (m.type === 'who' && own) chan?.postMessage({ type: 'open', key: own });
    else if (m.type === 'close' && m.key === own && own) window.close();
  };
  return chan;
}

export function isAway(id: string, part: string): boolean {
  return Boolean(away[key(id, part)]);
}

/** Main window: asks which parts are already open elsewhere. */
export function watchSolo(): void {
  channel()?.postMessage({ type: 'who' });
}

/** Separate window: announces itself until it closes. */
export function announceSolo(id: string, part: string): () => void {
  const c = channel();
  own = key(id, part);
  c?.postMessage({ type: 'open', key: own });
  const bye = () => { if (own) c?.postMessage({ type: 'closed', key: own }); };
  window.addEventListener('pagehide', bye);
  return () => { window.removeEventListener('pagehide', bye); bye(); own = ''; };
}

/** Opens a part in its own window; false when the browser blocked it. */
export function separate(id: string, part: Part): boolean {
  channel();
  const w = window.open(`/d/${encodeURIComponent(id)}/${part}?solo=1`, `madalean-${id}-${part}`, 'popup,width=820,height=900');
  if (!w) return false;
  away[key(id, part)] = true;
  return true;
}

export function putBack(id: string, part: string): void {
  channel()?.postMessage({ type: 'close', key: key(id, part) });
  delete away[key(id, part)];
}
