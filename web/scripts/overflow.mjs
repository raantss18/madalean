import { chromium } from '@playwright/test';
const [url, w = '360', h = '780'] = process.argv.slice(2);
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: +w, height: +h } });
await p.addInitScript(() => localStorage.setItem('madalean.tour', '1'));
await p.goto(url, { waitUntil: 'networkidle' });
await p.waitForTimeout(600);
const r = await p.evaluate(() => {
  const W = innerWidth; const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const rc = el.getBoundingClientRect();
    if (rc.right > W + 1 && rc.width > 0) out.push(`${el.tagName}.${[...el.classList].join('.')} right=${Math.round(rc.right)} w=${Math.round(rc.width)}`);
  }
  return out.slice(0, 25);
});
console.log(r.join('\n'));
await b.close();
