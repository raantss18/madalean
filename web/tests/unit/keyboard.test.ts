import { describe, it, expect } from 'vitest';
import { keyboardOpen, keyboardInset, scrollNeeded, KB_RATIO } from '../../src/lib/ui/keyboard';

describe('on-screen keyboard detection', () => {
  it('is open only while typing and when the page lost a keyboard-sized height', () => {
    expect(keyboardOpen(800, 420, true)).toBe(true);
    expect(keyboardOpen(800, 420, false)).toBe(false); // e.g. a split-screen resize
    expect(keyboardOpen(800, 790, true)).toBe(false); // address bar hiding, not a keyboard
    expect(keyboardOpen(800, Math.floor(800 * KB_RATIO) + 1, true)).toBe(false);
    expect(keyboardOpen(0, 300, true)).toBe(false);
  });
  it('stays open while the page is still short after the focus moved to a menu, closes when the keyboard goes', () => {
    expect(keyboardOpen(800, 420, false, true)).toBe(true); // menu opened over the keyboard: no bottom bar, no gap
    expect(keyboardOpen(800, 800, false, true)).toBe(false); // keyboard gone
    expect(keyboardOpen(800, 420, false, false)).toBe(false); // never opened by typing
  });
  it('measures a keyboard drawn over the page (visual viewport only)', () => {
    expect(keyboardInset(800, 420, 0)).toBe(380);
    expect(keyboardInset(800, 420, 100)).toBe(280); // page panned up
    expect(keyboardInset(420, 420, 0)).toBe(0); // the page itself was resized
    expect(keyboardInset(420, 430, 0)).toBe(0);
  });
  it('scrolls the caret just above the keyboard, or back below the top bar', () => {
    expect(scrollNeeded({ top: 500, bottom: 520 }, 56, 420)).toBe(124);
    expect(scrollNeeded({ top: 200, bottom: 220 }, 56, 420)).toBe(0);
    expect(scrollNeeded({ top: 40, bottom: 60 }, 56, 420)).toBe(-40);
  });
});
