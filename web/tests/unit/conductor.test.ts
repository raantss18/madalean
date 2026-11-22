// S-AN (D46): the cost shown next to a conductor's correction (Calcul cell history, article suggestion).
import { describe, expect, it } from 'vitest';
import { costText, usdText } from '../../src/lib/conductor';

describe('conductor cost text', () => {
  it('formats dollars per language and never shows a misleading zero', () => {
    expect(usdText(0.12, 'fr')).toBe('0,12 $');
    expect(usdText(0.12, 'en')).toBe('$0.12');
    expect(usdText(0.0008, 'fr')).toBe('< 0,01 $');
    expect(usdText(0.0008, 'en')).toBe('< $0.01');
    expect(usdText(0, 'en')).toBe('$0.00');
  });
  it('says « free » for a free model', () => {
    expect(costText(0, 'fr', 'gratuit')).toBe('gratuit');
    expect(costText(undefined, 'en', 'free')).toBe('free');
    expect(costText(0.004, 'fr', 'gratuit')).toBe('< 0,01 $');
    expect(costText(0.5, 'en', 'free')).toBe('$0.50');
  });
});
