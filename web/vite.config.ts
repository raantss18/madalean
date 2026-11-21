import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';
import { cpSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Plugin } from 'vite';

// The manual's images (docs/manual/img, docs/SITE.md §2) are served at /help/img/ — one source, copied at build.
const MANUAL_IMG = fileURLToPath(new URL('../docs/manual/img', import.meta.url));
function manualImages(): Plugin {
  let outDir = '';
  return {
    name: 'madalean-manual-images',
    configResolved(c) { outDir = c.build.outDir; },
    configureServer(server) {
      server.middlewares.use('/help/img/', (req, res, next) => {
        const f = join(MANUAL_IMG, decodeURIComponent((req.url ?? '').split('?')[0]!.replace(/^\/+/, '')));
        if (!f.startsWith(MANUAL_IMG) || !existsSync(f)) return next();
        res.setHeader('Content-Type', 'image/png');
        res.end(readFileSync(f));
      });
    },
    closeBundle() {
      if (!existsSync(MANUAL_IMG)) return;
      mkdirSync(join(outDir, 'help', 'img'), { recursive: true });
      cpSync(MANUAL_IMG, join(outDir, 'help', 'img'), { recursive: true });
    },
  };
}

// Dev: `MADALEAN_DEV_API=http://127.0.0.1:11760 npm run dev` proxies /api to a `madalean serve --demo` instance.
const api = process.env.MADALEAN_DEV_API ?? 'http://127.0.0.1:11600';

export default defineConfig({
  plugins: [svelte(), manualImages()],
  base: '/',
  build: {
    outDir: fileURLToPath(new URL('../madalean/static', import.meta.url)),
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: false,
    assetsInlineLimit: 0,          // strict CSP: no data: fonts/images
    chunkSizeWarningLimit: 700,
  },
  server: { fs: { allow: ['..'] }, proxy: { '/api': { target: api, ws: true, changeOrigin: false } } },
  test: { include: ['tests/unit/**/*.test.ts'], environment: 'node' },
});
