// The small plot of an exploration's data: pure geometry (unit-tested), drawn as inline SVG by ExplorePlot.svelte.
// Values arrive as strings (large integers, "p/q" fractions); anything else is not a point.

export interface PlotPoint { x: number; y: number; cx: number; cy: number }
export interface Plot {
  points: PlotPoint[]; log: boolean; width: number; height: number;
  xmin: number; xmax: number; ymin: number; ymax: number; path: string;
}


/** log10 of a non-negative decimal integer string of any length. */
function log10OfDigits(digits: string): number {
  const d = digits.replace(/^0+/, '');
  if (!d) return -Infinity;
  const head = Number(d.slice(0, 15));
  return Math.log10(head) + (d.length - Math.min(d.length, 15));
}

/** A cell as a number and its log10 (kept apart: 200-digit integers overflow a float, their logarithm does not). */
export function parseCell(v: unknown): { value: number; log: number } | null {
  if (typeof v === 'number') return Number.isFinite(v) ? { value: v, log: v > 0 ? Math.log10(v) : NaN } : null;
  if (typeof v !== 'string') return null;
  const m = /^\s*(-?)(\d+)(?:\/(\d+))?\s*$/.exec(v);
  if (!m) return null;
  const neg = m[1] === '-';
  const ln = log10OfDigits(m[2]!);
  const ld = m[3] ? log10OfDigits(m[3]) : 0;
  if (ld === -Infinity) return null;
  if (ln === -Infinity) return { value: 0, log: NaN };
  const lg = ln - ld;
  const value = lg > 300 ? Infinity : Number(m[2]) / (m[3] ? Number(m[3]) : 1);
  return { value: neg ? -value : value, log: neg ? NaN : lg };
}

/** Log scale when every value is positive and they span more than three orders of magnitude (or overflow a float). */
export function useLog(cells: { value: number; log: number }[]): boolean {
  if (!cells.length || cells.some((c) => !(c.value > 0))) return false;
  const logs = cells.map((c) => c.log);
  return Math.max(...logs) - Math.min(...logs) > 3 || cells.some((c) => !Number.isFinite(c.value));
}

/** Geometry of the plot of column `col` against column `xcol` (row order when the x cells are not numbers). */
export function buildPlot(rows: unknown[][], col: number, xcol = 0, width = 320, height = 160, pad = 12): Plot | null {
  const raw: { x: number; c: { value: number; log: number } }[] = [];
  rows.forEach((r, i) => {
    const c = parseCell(r[col]);
    if (!c) return;
    const x = xcol === col ? null : parseCell(r[xcol]);
    raw.push({ x: x && Number.isFinite(x.value) ? x.value : i, c });
  });
  if (raw.length < 2) return null;
  const log = useLog(raw.map((p) => p.c));
  if (!log && raw.some((p) => !Number.isFinite(p.c.value))) return null;
  const ys = raw.map((p) => (log ? p.c.log : p.c.value));
  const xs = raw.map((p) => p.x);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const sx = (x: number) => pad + (xmax === xmin ? 0.5 : (x - xmin) / (xmax - xmin)) * (width - 2 * pad);
  const sy = (y: number) => height - pad - (ymax === ymin ? 0.5 : (y - ymin) / (ymax - ymin)) * (height - 2 * pad);
  const points = raw.map((p, i) => ({ x: p.x, y: ys[i]!, cx: Math.round(sx(p.x) * 100) / 100, cy: Math.round(sy(ys[i]!) * 100) / 100 }));
  const sorted = [...points].sort((a, b) => a.x - b.x);
  const path = sorted.map((p, i) => `${i ? 'L' : 'M'}${p.cx} ${p.cy}`).join(' ');
  return { points, log, width, height, xmin, xmax, ymin, ymax, path };
}

/** A short spelling of a (possibly huge) cell for the text alternative. */
export function shortValue(v: unknown): string {
  const s = String(v ?? '');
  if (/^-?\d{13,}$/.test(s)) {
    const neg = s.startsWith('-');
    const d = neg ? s.slice(1) : s;
    return `${neg ? '-' : ''}${d[0]}.${d.slice(1, 3)}e${d.length - 1}`;
  }
  return s.length > 24 ? s.slice(0, 21) + '…' : s;
}

