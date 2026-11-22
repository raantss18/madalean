// S-AK (docs/UI.md §14): Enter / Shift+Enter rules, outside-click test, autosave controller.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { enterIntent, newlineIndent, tabIndent } from '../../src/lib/ui/enter';
import { isOutside } from '../../src/lib/ui/dismiss';
import { Autosave, retryDelay, isConflictError } from '../../src/lib/ui/autosave.svelte';
import { ApiError } from '../../src/lib/api/client';

const key = (k: Partial<KeyboardEvent>) => ({ key: 'Enter', shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, isComposing: false, ...k }) as KeyboardEvent;

describe('enterIntent', () => {
  it('Enter sends, Shift+Enter is a new line, Ctrl/Cmd+Enter sends', () => {
    expect(enterIntent(key({}))).toBe('submit');
    expect(enterIntent(key({ shiftKey: true }))).toBe('newline');
    expect(enterIntent(key({ ctrlKey: true }))).toBe('submit');
    expect(enterIntent(key({ metaKey: true }))).toBe('submit');
  });
  it('never while an IME composes, never for other keys or Alt+Enter', () => {
    expect(enterIntent(key({ isComposing: true }))).toBe('none');
    expect(enterIntent({ ...key({}), keyCode: 229 })).toBe('none');
    expect(enterIntent(key({ key: 'a' }))).toBe('none');
    expect(enterIntent(key({ altKey: true }))).toBe('none');
  });
});

describe('code cell editing', () => {
  it('Shift+Enter keeps the indentation and adds a level after « : »', () => {
    const src = 'for i in range(3):';
    const e = newlineIndent(src, src.length, src.length);
    expect(e.text).toBe('for i in range(3):\n    ');
    expect(e.start).toBe(e.text.length);
    const src2 = 'def f(x):\n    y = x';
    const e2 = newlineIndent(src2, src2.length, src2.length);
    expect(e2.text).toBe('def f(x):\n    y = x\n    ');
  });
  it('replaces a selection by the new line', () => {
    expect(newlineIndent('abcdef', 2, 4).text).toBe('ab\nef');
  });
  it('Tab inserts 4 spaces at the caret, indents and dedents selected lines', () => {
    expect(tabIndent('x', 0, 0, false)).toEqual({ text: '    x', start: 4, end: 4 });
    const two = 'a = 1\nb = 2';
    const ind = tabIndent(two, 0, two.length, false);
    expect(ind.text).toBe('    a = 1\n    b = 2');
    const back = tabIndent(ind.text, 0, ind.text.length, true);
    expect(back.text).toBe(two);
    expect(tabIndent('  y', 3, 3, true).text).toBe('y');
  });
});

describe('isOutside', () => {
  const node = (children: unknown[] = []) => ({ contains: (x: unknown) => x === nodeSelf || children.includes(x) }) as unknown as Node;
  const inner = {} as Node;
  let nodeSelf: unknown;
  it('inside the panel or on its button is not outside; elsewhere is', () => {
    const panel = node([inner]);
    nodeSelf = panel;
    const btn = { contains: (x: unknown) => x === btnChild } as unknown as Node;
    const btnChild = {} as Node;
    expect(isOutside(inner, panel, btn)).toBe(false);
    expect(isOutside(panel, panel, btn)).toBe(false);
    expect(isOutside(btnChild, panel, btn)).toBe(false);
    expect(isOutside({} as Node, panel, btn)).toBe(true);
    expect(isOutside(null, panel, btn)).toBe(false);
  });
});

describe('Autosave', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('debounces: one save after the last change', async () => {
    const save = vi.fn(async () => {});
    const a = new Autosave(save, { delay: 500 });
    a.touch(); a.touch();
    expect(a.status).toBe('dirty');
    await vi.advanceTimersByTimeAsync(400);
    a.touch();
    await vi.advanceTimersByTimeAsync(499);
    expect(save).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(save).toHaveBeenCalledTimes(1);
    expect(a.status).toBe('saved');
    a.destroy();
  });

  it('flush saves at once; nothing pending → no call', async () => {
    const save = vi.fn(async () => {});
    const a = new Autosave(save);
    expect(await a.flush()).toBe(true);
    expect(save).not.toHaveBeenCalled();
    a.touch();
    expect(await a.flush()).toBe(true);
    expect(save).toHaveBeenCalledTimes(1);
    a.destroy();
  });

  it('a change during a save is saved again afterwards', async () => {
    let release: () => void = () => {};
    const save = vi.fn(() => new Promise<void>((r) => { release = r; }));
    const a = new Autosave(save, { delay: 100 });
    a.touch();
    const p = a.flush();
    expect(a.status).toBe('saving');
    a.touch();
    release();
    await p;
    expect(a.status).toBe('dirty');
    await vi.advanceTimersByTimeAsync(100);
    release();
    await vi.advanceTimersByTimeAsync(0);
    expect(save).toHaveBeenCalledTimes(2);
    expect(a.status).toBe('saved');
    a.destroy();
  });

  it('retries with backoff after a failure, then succeeds', async () => {
    let fail = 2;
    const save = vi.fn(async () => { if (fail-- > 0) throw new Error('network'); });
    const a = new Autosave(save, { delay: 10 });
    a.touch();
    await vi.advanceTimersByTimeAsync(10);
    expect(a.status).toBe('error');
    await vi.advanceTimersByTimeAsync(retryDelay(1));
    expect(a.status).toBe('error');
    await vi.advanceTimersByTimeAsync(retryDelay(2));
    expect(a.status).toBe('saved');
    expect(save).toHaveBeenCalledTimes(3);
    a.destroy();
  });

  it('a 409 is a conflict: the text is kept, no retry', async () => {
    const onConflict = vi.fn();
    const save = vi.fn(async () => { throw new ApiError(409, 'conflict', {}); });
    const a = new Autosave(save, { delay: 10, onConflict });
    a.touch();
    await vi.advanceTimersByTimeAsync(10);
    expect(a.status).toBe('conflict');
    expect(onConflict).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(save).toHaveBeenCalledTimes(1);
    a.resolved();
    expect(a.status).toBe('saved');
    a.destroy();
  });

  it('backoff is capped at 30 s; conflicts are recognised', () => {
    expect(retryDelay(1)).toBe(2000);
    expect(retryDelay(3)).toBe(8000);
    expect(retryDelay(10)).toBe(30000);
    expect(isConflictError(new ApiError(409, 'x', {}))).toBe(true);
    expect(isConflictError(new ApiError(500, 'x', {}))).toBe(false);
  });
});
