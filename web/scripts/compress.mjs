// Writes .br and .gz next to every compressible file of the build (aiohttp's FileResponse serves them when the
// browser accepts them). Usage: node scripts/compress.mjs <dir>
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { brotliCompressSync, gzipSync, constants } from 'node:zlib';
const dir = process.argv[2];
let n = 0, raw = 0, br = 0;
const walk = (d) => { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) walk(p); else handle(p); } };
function handle(p) {
  if (!/\.(js|css|html|svg|json|txt|map)$/.test(p)) return;
  const buf = readFileSync(p);
  if (buf.length < 1024) return;
  const b = brotliCompressSync(buf, { params: { [constants.BROTLI_PARAM_QUALITY]: 11 } });
  writeFileSync(p + '.br', b);
  writeFileSync(p + '.gz', gzipSync(buf, { level: 9 }));
  n++; raw += buf.length; br += b.length;
}
walk(dir);
console.log(`compressed ${n} files: ${(raw / 1024).toFixed(0)} kB → ${(br / 1024).toFixed(0)} kB (brotli)`);
