import { describe, it, expect } from 'vitest';
import { keyboardOpen, scrollNeeded, KB_RATIO } from '../../src/lib/ui/keyboard';

describe('on-screen keyboard detection', () => {
  it('is open only while typing and when the page lost a keyboard-sized height', () => {
    expect(keyboardOpen(800, 420, true)).toBe(true);
    expect(keyboardOpen(800, 420, false)).toBe(false); // e.g. a split-screen resize
    expect(keyboardOpen(800, 790, true)).toBe(false); // address bar hiding, not a keyboard
    expect(keyboardOpen(800, Math.floor(800 * KB_RATIO) + 1, true)).toBe(false);
    expect(keyboardOpen(0, 300, true)).toBe(false);
  });
  it('scrolls the caret just above the keyboard, or back below the top bar', () => {
    expect(scrollNeeded({ top: 500, bottom: 520 }, 56, 420)).toBe(124);
    expect(scrollNeeded({ top: 200, bottom: 220 }, 56, 420)).toBe(0);
    expect(scrollNeeded({ top: 40, bottom: 60 }, 56, 420)).toBe(-40);
  });
});
