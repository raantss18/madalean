import { describe, expect, it } from 'vitest';
import { guessKind } from '../../src/lib/calcul/detect';

describe('calcul: code or request (S-AB)', () => {
  it('recognises requests in French and English', () => {
    for (const t of ['la série de Fourier de x² sur [0,2pi]', 'trace sin(x)/x sur [-10,10]', 'factorise x^4+4 sur Z[i]',
      'graphe de Petersen et son nombre chromatique', 'what is the integral of x^2?', 'combien de premiers < 100', 'plot sin(x) on [0, pi]'])
      expect(guessKind(t), t).toBe('ask');
  });
  it('recognises Sage / Python code', () => {
    for (const t of ['factor(x^4+4)', 'integral(x^2, x, 0, 1)', 'f(x) = x^2\nplot(f, (x, 0, 1))', '2+2', 'G = graphs.PetersenGraph()',
      'print("la valeur de x")', 'x^2 + 1', 'for k in range(3):\n    print(k)', ''])
      expect(guessKind(t), t).toBe('code');
  });
});
