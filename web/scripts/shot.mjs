// Dev helper: node scripts/shot.mjs <url> <out.png> [width] [height] [dark]
import { chromium } from '@playwright/test';
const [url, out, w = '1440', h = '900', scheme = 'light'] = process.argv.slice(2);
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: +w, height: +h }, colorScheme: scheme });
const logs = [];
p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push(`${m.type()}: ${m.text()}`); });
p.on('pageerror', (e) => logs.push(`pageerror: ${e.message}`));
await p.goto(url, { waitUntil: 'networkidle' });
await p.waitForTimeout(800);
await p.screenshot({ path: out, fullPage: false });
const sw = await p.evaluate(() => document.documentElement.scrollWidth);
console.log('scrollWidth', sw, 'viewport', w);
console.log(logs.join('\n'));
await b.close();
