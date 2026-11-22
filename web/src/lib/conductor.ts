// S-AN (D46): small helpers shared by the places that show the conductor's corrections (Calcul cells, article
// suggestions, the cap question outside a job).

/** « 0,12 $ » / « $0.12 »; a few tenths of a cent are shown as « < 0,01 $ » rather than a misleading « 0,00 $ ». */
export function usdText(n: number, lang: string): string {
  const tiny = n > 0 && n < 0.005;
  const v = (tiny ? 0.01 : n).toFixed(2);
  const s = lang === 'fr' ? v.replace('.', ',') + ' $' : '$' + v;
  return tiny ? '< ' + s : s;
}

/** What a correction cost, as shown next to it: free models say so instead of « 0,00 $ ». */
export function costText(usd: number | undefined, lang: string, free: string): string {
  return usd && usd > 0 ? usdText(usd, lang) : free;
}
