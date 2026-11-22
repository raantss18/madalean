#!/usr/bin/env node
// Screen open time on a phone (TODO B16, S-AP, docs/PERFORMANCE.md « Interface sur téléphone (S-AP) »).
//
//   node scripts/dev/phone_perf.mjs [--static DIR] [--runs 3] [--port 12900] [--json out.json] [--screens home,calcul]
//                                   [--parts screens,ws,burst,replay]
//
// Starts a `madalean serve --demo` (temporary config / cache / home directories, ports 12900–12999, never the live
// server) serving a PRODUCTION build of the web UI (DIR, or a fresh `vite build` + compression into a temp dir),
// then, in headless Chromium with phone emulation (360×780, DPR 3, touch, mobile UA), CPU throttled 4× and a slow
// network (150 ms RTT, 1.6 Mbit/s down, 750 kbit/s up), opens each screen by its URL, cold (empty cache) and warm
// (reload, cache kept), and records:
//   - fcp: first contentful paint (ms after navigation start);
//   - useful: first frame where the screen's own content is on screen (a selector per screen, below);
//   - interactive: useful paint, then the end of the last long task (> 50 ms) before 1 s without any;
//   - complete: the last part shown after the first paint is in (formulas rendered by KaTeX, code fields turned into
//     CodeMirror); equal to `useful` when nothing comes later;
//   - jsCritical / cssCritical: bytes transferred (compressed, as on the wire) before the useful paint;
//   - js / css: all bytes transferred and number of files once complete (includes idle prefetches, if any);
// and, on Home, the WebSocket frames received while idle (30 s), and during a demo job watched from its dossier
// screen the main-thread time (CDP Performance.getMetrics TaskDuration / ScriptDuration), style recalcs and layouts;
// and the same for a replay burst (300 `job.updated` for 20 running jobs, one task each, as after a reconnection).
// Medians of --runs runs. Needs web/node_modules (Playwright + Chromium) and the checkout's .venv.
import { spawn, execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const require = createRequire(join(ROOT, 'web', 'package.json'));
const { chromium } = require('@playwright/test');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : '1']);
  return acc;
}, []));
const RUNS = Number(args.runs ?? 3);
const ONLY = args.screens ? new Set(String(args.screens).split(',')) : null;

const PHONE = {
  viewport: { width: 360, height: 780 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true, locale: 'fr-FR',
  userAgent: 'Mozilla/5.0 (Linux; Android 13; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36',
};
const NETWORK = { offline: false, latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 };

function portFree(p) {
  return new Promise((res) => {
    const s = net.createServer();
    s.once('error', () => res(false));
    s.listen(p, '127.0.0.1', () => s.close(() => res(true)));
  });
}
async function pickPorts() {
  const start = Number(args.port ?? 12900 + Math.floor(Math.random() * 40) * 2);
  for (let p = start; p < 12999; p += 2) if (await portFree(p) && await portFree(p + 1)) return [p, p + 1];
  throw new Error('no free port pair in 12900–12999');
}

async function startServer(staticDir) {
  const dir = mkdtempSync(join(process.env.TMPDIR ?? tmpdir(), 'madalean-phoneperf-'));
  const [port, remote] = await pickPorts();
  const child = spawn(join(ROOT, 'bin', 'madalean'), ['serve', '--demo', '--port', String(port), '--remote-port', String(remote),
    '--config-dir', join(dir, 'config'), '--cache-dir', join(dir, 'cache'), '--static', staticDir],
  { stdio: ['ignore', 'ignore', 'ignore'], env: { ...process.env, MADALEAN_HOME: join(dir, 'home') } });
  const url = `http://127.0.0.1:${port}`;
  const t0 = Date.now();
  for (;;) {
    try { if ((await fetch(`${url}/api/hello`)).ok) break; } catch { /* not yet */ }
    if (Date.now() - t0 > 40_000) { child.kill(); throw new Error('demo server did not start'); }
    await new Promise((r) => setTimeout(r, 250));
  }
  return { url, stop: () => { child.kill('SIGTERM'); setTimeout(() => rmSync(dir, { recursive: true, force: true }), 1500); } };
}

function buildStatic() {
  const out = mkdtempSync(join(process.env.TMPDIR ?? tmpdir(), 'madalean-phoneperf-static-'));
  execFileSync('npx', ['vite', 'build', '--outDir', out, '--emptyOutDir'], { cwd: join(ROOT, 'web'), stdio: 'ignore' });
  execFileSync('node', ['scripts/compress.mjs', out], { cwd: join(ROOT, 'web'), stdio: 'ignore' });
  return out;
}

// Runs in the page before any script: long tasks, and the first frame where `window.__ready()` (set below) is true.
function probe() {
  const w = window;
  w.__lt = [];
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) w.__lt.push([e.startTime, e.startTime + e.duration]); })
      .observe({ type: 'longtask', buffered: true });
  } catch { /* unsupported */ }
  w.__useful = 0;
  w.__complete = 0;          // last frame where a part shown after the first paint (formula, code editor) arrived
  w.__pend = 0;
  const check = () => {
    try {
      if (!w.__useful && w.__readySel && document.querySelector(w.__readySel)) {
        requestAnimationFrame(() => { w.__useful ||= performance.now(); });
      }
      const pend = document.querySelectorAll('.math-pending').length
        + [...document.querySelectorAll('main .code-editor')].filter((e) => !e.querySelector('.cm-content')).length;
      if (w.__pend > 0 && pend === 0) requestAnimationFrame(() => { w.__complete = performance.now(); });
      w.__pend = pend;
    } catch { /* bad selector */ }
  };
  new MutationObserver(check).observe(document, { childList: true, subtree: true, characterData: true });
}

async function api(url, method, path, body) {
  const r = await fetch(url + '/api' + path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${method} ${path}: ${r.status}`);
  return r.json();
}

async function screensFor(url) {
  const dossiers = (await api(url, 'GET', '/dossiers')).dossiers;
  const proved = dossiers.find((d) => d.status === 'proved' && !d.parent_id).id;
  const projects = (await api(url, 'GET', '/projects')).projects;
  let calculProject = projects[0].id;
  for (const p of projects) if ((await api(url, 'GET', `/calcul/${p.id}/docs/calcul`)).cells.length) { calculProject = p.id; break; }
  const research = projects.find((p) => /Recherche/.test(p.title))?.id ?? projects[0].id;
  const examples = projects.find((p) => /Exemples/.test(p.title))?.id ?? projects[0].id;
  const notes = (await api(url, 'GET', `/notes?project=${examples}`)).notes;
  const note = (notes.find((n) => /Parité/.test(n.title)) ?? notes[0]).id;
  return [
    { name: 'home', path: '/', project: '', ready: 'main h1' },
    // the proof's code on screen (CodeMirror, or the plain text field shown until it has loaded)
    { name: 'dossier', path: `/d/${proved}/preuve`, project: '', ready: 'main .code-editor' },
    { name: 'calcul', path: '/calcul', project: calculProject, ready: 'li.cell .output' },
    { name: 'article', path: '/article', project: research, ready: '.cm-editor .cm-content' },
    { name: 'notes', path: `/notes/${note}`, project: examples, ready: 'main .code-editor' },
    { name: 'settings', path: '/reglages', project: '', ready: 'main h1' },
  ].filter((s) => !ONLY || ONLY.has(s.name));
}

async function measure(page, cdp) {
  await page.waitForFunction(() => window.__useful > 0, null, { timeout: 60_000 });
  // Interactive: 1 s (wall clock, throttled page) without any long task after the useful paint.
  let quietSince = Date.now();
  let lastCount = -1;
  for (;;) {
    const n = await page.evaluate(() => window.__lt.length);
    if (n !== lastCount) { lastCount = n; quietSince = Date.now(); }
    if (Date.now() - quietSince >= 1000) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  const lastEnd = await page.evaluate(() => window.__lt.reduce((m, [, e]) => Math.max(m, e), 0));
  // Complete: every formula rendered by KaTeX and every code field turned into CodeMirror (the parts that may load
  // after the first paint); bytes are counted at that point, so they include everything the screen loads.
  await page.waitForFunction(() => !document.querySelector('.math-pending')
    && [...document.querySelectorAll('main .code-editor')].every((e) => e.querySelector('.cm-content')), null, { timeout: 30_000 }).catch(() => {});
  await new Promise((r) => setTimeout(r, 300));
  return page.evaluate((lastEnd) => {
    const fcp = performance.getEntriesByName('first-contentful-paint')[0]?.startTime ?? 0;
    const useful = window.__useful;
    const res = performance.getEntriesByType('resource');
    const sum = (re, before = Infinity) => res.filter((r) => re.test(new URL(r.name).pathname) && r.responseEnd <= before)
      .reduce((a, r) => [a[0] + (r.transferSize || 0), a[1] + 1], [0, 0]);
    const [js, jsFiles] = sum(/\.m?js$/);
    const [css, cssFiles] = sum(/\.css$/);
    const [jsCritical] = sum(/\.m?js$/, useful);         // what had to arrive before the first useful paint
    const [cssCritical] = sum(/\.css$/, useful);
    const longTasksMs = window.__lt.reduce((a, [s, e]) => a + (e - s), 0);
    return { fcp: Math.round(fcp), useful: Math.round(useful), interactive: Math.round(Math.max(useful, lastEnd)),
      complete: Math.round(Math.max(useful, window.__complete)), jsCritical, cssCritical, js, jsFiles, css, cssFiles, longTasksMs: Math.round(longTasksMs) };
  }, lastEnd);
}

async function newPhonePage(browser, s) {
  const ctx = await browser.newContext(PHONE);
  await ctx.addInitScript(probe);
  await ctx.addInitScript(([sel, project]) => {
    window.__readySel = sel;
    try {
      localStorage.setItem('madalean.tour', '1');
      localStorage.setItem('madalean.density', 'research');
      if (project) localStorage.setItem('madalean.project', project);
    } catch { /* ignore */ }
  }, [s.ready, s.project]);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', NETWORK);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  return { ctx, page, cdp };
}

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
function med(rows) {
  const out = {};
  for (const k of Object.keys(rows[0])) out[k] = median(rows.map((r) => r[k]));
  return out;
}

async function screenRuns(browser, url, s) {
  const cold = [], warm = [];
  for (let i = 0; i < RUNS; i++) {
    const { ctx, page, cdp } = await newPhonePage(browser, s);
    await cdp.send('Network.clearBrowserCache');
    await page.goto(url + s.path, { waitUntil: 'commit' });
    cold.push(await measure(page, cdp));
    await page.reload({ waitUntil: 'commit' });
    warm.push(await measure(page, cdp));
    await ctx.close();
  }
  return { cold: med(cold), warm: med(warm) };
}

async function wsIdle(browser, url) {
  const { ctx, page, cdp } = await newPhonePage(browser, { ready: 'main h1', project: '' });
  await page.goto(url + '/', { waitUntil: 'commit' });
  await page.waitForFunction(() => window.__useful > 0, null, { timeout: 60_000 });
  await new Promise((r) => setTimeout(r, 3000));
  let frames = 0, bytes = 0;
  const types = {};
  cdp.on('Network.webSocketFrameReceived', (e) => {
    frames++; bytes += e.response.payloadData.length;
    try { const t = JSON.parse(e.response.payloadData).type; types[t] = (types[t] ?? 0) + 1; } catch { /* binary */ }
  });
  await new Promise((r) => setTimeout(r, 30_000));
  await ctx.close();
  return { seconds: 30, frames, per_min: Math.round((frames / 30) * 60), bytes, types };
}

async function idleJobs(url, ms = 90_000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (!(await api(url, 'GET', '/jobs')).active.length) return;
    await new Promise((r) => setTimeout(r, 500));
  }
}

// A demo job (statement → proof → explanation, scripted models streaming tokens) watched from its dossier screen:
// the page is loaded and quiet first, then the job starts and the main thread is measured for 12 s.
async function jobBurst(browser, url) {
  await idleJobs(url);
  const d = (await api(url, 'POST', '/dossiers', { problem: 'Montrer que la somme de deux entiers pairs est paire.' })).dossier;
  await idleJobs(url);
  const { ctx, page, cdp } = await newPhonePage(browser, { ready: 'main .code-editor', project: '' });
  let frames = 0;
  const types = {};
  cdp.on('Network.webSocketFrameReceived', (e) => {
    frames++;
    try { const t = JSON.parse(e.response.payloadData).type; types[t] = (types[t] ?? 0) + 1; } catch { /* binary */ }
  });
  await page.goto(`${url}/d/${d.id}/preuve`, { waitUntil: 'commit' });
  await measure(page, cdp);
  await new Promise((r) => setTimeout(r, 5000));
  await cdp.send('Performance.enable');
  const metrics = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
  const m0 = await metrics();
  const f0 = frames;
  for (const k of Object.keys(types)) delete types[k];
  await api(url, 'POST', `/dossiers/${d.id}/run`, { plan: [{ stage: 'proof', force: true }, 'explanation'] });
  await new Promise((r) => setTimeout(r, 12_000));
  const m1 = await metrics();
  const batches = await page.evaluate(() => window.__madalean?.batchStats ?? null);
  await ctx.close();
  try { await api(url, 'POST', `/dossiers/${d.id}/stop`, {}); } catch { /* finished */ }
  return { seconds: 12, ws_frames: frames - f0, types: { ...types }, batches, task_ms: Math.round((m1.TaskDuration - m0.TaskDuration) * 1000),
    script_ms: Math.round((m1.ScriptDuration - m0.ScriptDuration) * 1000), style_recalcs: m1.RecalcStyleCount - m0.RecalcStyleCount,
    layouts: m1.LayoutCount - m0.LayoutCount };
}

// A burst as after a reconnection (the server replays what was missed) or with many jobs running: 300 `job.updated`
// events for 20 running jobs, each delivered as its own task (like socket messages) a few ms apart, into the app's
// socket handler, on Home (the dossier list, the status button). Measured until the page is quiet again.
async function replayBurst(browser, url) {
  const { ctx, page, cdp } = await newPhonePage(browser, { ready: 'main h1', project: '' });
  await page.goto(`${url}/`, { waitUntil: 'commit' });
  await measure(page, cdp);
  await new Promise((r) => setTimeout(r, 5000));
  await cdp.send('Performance.enable');
  const metrics = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
  const m0 = await metrics();
  const wall = await page.evaluate(() => new Promise((resolve) => {
    const app = window.__madalean;
    const tpl = Object.values(app.m.jobs)[0] ?? { plan: [{ stage: 'proof' }], mode: 'auto', strategy: 'auto', user: true, started: null,
      attempts: [], done_stages: [], summary: {}, error: '' };
    const dossiers = Object.keys(app.m.dossiers).slice(0, 20);
    let seq = app.seqStats.last;
    const evs = [];
    for (let i = 0; i < 300; i++) {
      const k = i % dossiers.length;
      const job = { ...JSON.parse(JSON.stringify(tpl)), id: `burst-${k}`, dossier_id: dossiers[k], state: 'running', stage: i % 2 ? 'proof' : 'statement',
        created: 1e10 + k, ended: null, waiting: '' };
      evs.push({ type: 'job.updated', seq: ++seq, job });
    }
    const ch = new MessageChannel();
    const t0 = performance.now();
    let i = 0;
    ch.port1.onmessage = () => {
      app.onSocket(evs[i++]);
      if (i < evs.length) ch.port2.postMessage(0);
      else requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now() - t0)));
    };
    ch.port2.postMessage(0);
  }));
  await new Promise((r) => setTimeout(r, 1500));
  const m1 = await metrics();
  const batches = await page.evaluate(() => window.__madalean?.batchStats ?? null);
  await ctx.close();
  return { events: 300, wall_ms: Math.round(wall), task_ms: Math.round((m1.TaskDuration - m0.TaskDuration) * 1000),
    script_ms: Math.round((m1.ScriptDuration - m0.ScriptDuration) * 1000), style_recalcs: m1.RecalcStyleCount - m0.RecalcStyleCount,
    layouts: m1.LayoutCount - m0.LayoutCount, batches };
}

const staticDir = args.static ? resolve(String(args.static)) : buildStatic();
if (!existsSync(join(staticDir, 'index.html'))) throw new Error(`no index.html in ${staticDir}`);
const server = await startServer(staticDir);
const browser = await chromium.launch();
const out = { static: staticDir, runs: RUNS, network: NETWORK, cpu_throttle: 4, screens: {} };
const PARTS = new Set(String(args.parts ?? (ONLY ? 'screens' : 'screens,ws,burst,replay')).split(','));
try {
  if (PARTS.has('screens')) {
    for (const s of await screensFor(server.url)) {
      out.screens[s.name] = await screenRuns(browser, server.url, s);
      console.error(s.name, JSON.stringify(out.screens[s.name]));
    }
  }
  if (PARTS.has('ws')) {
    out.ws_idle = await wsIdle(browser, server.url);
    console.error('ws_idle', JSON.stringify(out.ws_idle));
  }
  if (PARTS.has('burst')) {
    const runs = [];
    for (let i = 0; i < RUNS; i++) runs.push(await jobBurst(browser, server.url));
    const num = (k) => median(runs.map((r) => r[k]));
    out.job_burst = { runs: RUNS, seconds: 12, ws_frames: num('ws_frames'), task_ms: num('task_ms'), script_ms: num('script_ms'),
      style_recalcs: num('style_recalcs'), layouts: num('layouts'), types: runs[0].types, batches: runs[0].batches };
    console.error('job_burst', JSON.stringify(out.job_burst));
  }
  if (PARTS.has('replay')) {
    const runs = [];
    for (let i = 0; i < RUNS; i++) runs.push(await replayBurst(browser, server.url));
    const num = (k) => median(runs.map((r) => r[k]));
    out.replay_burst = { runs: RUNS, events: 300, wall_ms: num('wall_ms'), task_ms: num('task_ms'), script_ms: num('script_ms'),
      style_recalcs: num('style_recalcs'), layouts: num('layouts'), batches: runs[0].batches };
    console.error('replay_burst', JSON.stringify(out.replay_burst));
  }
} finally {
  await browser.close();
  server.stop();
}
const text = JSON.stringify(out, null, 2);
if (args.json) writeFileSync(String(args.json), text + '\n');
console.log(text);
