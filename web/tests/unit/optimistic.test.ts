import { describe, it, expect } from 'vitest';
import { optimistic, setWithUndo } from '../../src/lib/store/optimistic';

describe('optimistic updates', () => {
  it('keeps the change on success', async () => {
    const s: Record<string, string> = { mode: 'auto' };
    const r = await optimistic(() => setWithUndo(s, 'mode', 'local'), async () => 'ok');
    expect(r.ok).toBe(true);
    expect(s['mode']).toBe('local');
  });
  it('rolls back on failure (and removes keys that did not exist)', async () => {
    const s: Record<string, string> = { mode: 'auto' };
    let seen: unknown = null;
    const r = await optimistic(() => {
      const a = setWithUndo(s, 'mode', 'local');
      const b = setWithUndo(s, 'extra', 'x');
      return () => { b(); a(); };
    }, async () => { throw new Error('403'); }, { onError: (e) => (seen = e) });
    expect(r.ok).toBe(false);
    expect(s).toEqual({ mode: 'auto' });
    expect((seen as Error).message).toBe('403');
  });
});
