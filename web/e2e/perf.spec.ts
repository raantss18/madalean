// Measurements reported in docs/UI.md. Run: npm run perf
import { test, expect } from '@playwright/test';
import { writeFileSync, mkdirSync } from 'node:fs';
import { open } from './util';

const results: Record<string, unknown> = {};
test.afterAll(() => {
  mkdirSync('test-results', { recursive: true });
  writeFileSync('test-results/perf.json', JSON.stringify(results, null, 2));
  console.log('PERF', JSON.stringify(results, null, 2));
});

function stats(frames: number[]) {
  const s = [...frames].sort((a, b) => a - b);
  const pct = (p: number) => s[Math.min(s.length - 1, Math.floor(p * s.length))]!;
  return { frames: s.length, p50: +pct(0.5).toFixed(1), p95: +pct(0.95).toFixed(1), p99: +pct(0.99).toFixed(1), max: +s[s.length - 1]!.toFixed(1),
    over50ms: s.filter((x) => x > 50).length };
}

test('time to interactive on a throttled mobile profile (4× CPU, fast 3G)', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 });
  await page.addInitScript(() => localStorage.setItem('madalean.tour', '1'));
  for (const cache of ['cold', 'warm'] as const) {
    if (cache === 'cold') await cdp.send('Network.clearBrowserCache');
    const t0 = Date.now();
    await page.goto(process.env['MADALEAN_URL'] + '/', { waitUntil: 'commit' });
    await expect(page.getByRole('heading', { level: 1, name: 'Que voulez-vous prouver ?' })).toBeVisible({ timeout: 30_000 });
    // Interactive = the statement editor accepts input.
    await page.getByRole('textbox', { name: 'Énoncé' }).first().click();
    await page.keyboard.type('x');
    const tti = Date.now() - t0;
    const nav = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming; return { dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd) }; });
    const bytes = await page.evaluate(() => performance.getEntriesByType('resource').filter((r) => /\.js$/.test(r.name)).reduce((n, r) => n + ((r as PerformanceResourceTiming).transferSize || 0), 0));
    results[`tti_mobile_${cache}`] = { ms: tti, ...nav, js_transfer_bytes: bytes };
  }
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
});

test('10 000-line stream: frame times while streaming, typing stays responsive, scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/__perf', { mode: 'research' });
  await page.waitForFunction(() => Boolean((window as unknown as { __perf?: unknown }).__perf));
  // Type while streaming: measure input latency of each keystroke.
  const streaming = page.evaluate(() => (window as unknown as { __perf: { stream: (n: number, k: number) => Promise<{ frames: number[]; ms: number }> } }).__perf.stream(10000, 40));
  const input = page.getByLabel('Type while streaming');
  await input.click();
  const lat: number[] = [];
  for (let i = 0; i < 20; i++) {
    const t = Date.now();
    await page.keyboard.type('a');
    await expect(input).toHaveValue('a'.repeat(i + 1));
    lat.push(Date.now() - t);
    await page.waitForTimeout(50);
  }
  const r = await streaming;
  results['stream_10k'] = { duration_ms: Math.round(r.ms), ...stats(r.frames.slice(1)), keystroke_ms_p50: lat.sort((a, b) => a - b)[10], keystroke_ms_max: Math.max(...lat) };
  // Scroll through the 10 000 lines and record frames.
  const scroll = await page.evaluate(async () => {
    const box = document.querySelector('[role=log]') as HTMLElement;
    const frames: number[] = [];
    let last = performance.now();
    box.scrollTop = 0;
    await new Promise((r) => requestAnimationFrame(r));
    const total = box.scrollHeight;
    return await new Promise<{ frames: number[]; height: number }>((resolve) => {
      const step = () => {
        const t = performance.now(); frames.push(t - last); last = t;
        box.scrollTop += 600;
        if (box.scrollTop + box.clientHeight >= total - 2) resolve({ frames, height: total });
        else requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  });
  results['scroll_10k'] = { scroll_height_px: scroll.height, ...stats(scroll.frames.slice(1)) };
  const lines = await page.evaluate(() => (document.querySelector('[role=log]')!.textContent ?? '').split('\n').length);
  expect(lines).toBeGreaterThanOrEqual(10000);
});
