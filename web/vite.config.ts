import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';

// Dev: `MADALEAN_DEV_API=http://127.0.0.1:11760 npm run dev` proxies /api to a `madalean serve --demo` instance.
const api = process.env.MADALEAN_DEV_API ?? 'http://127.0.0.1:11600';

export default defineConfig({
  plugins: [svelte()],
  base: '/',
  build: {
    outDir: fileURLToPath(new URL('../madalean/static', import.meta.url)),
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: false,
    assetsInlineLimit: 0,          // strict CSP: no data: fonts/images
    chunkSizeWarningLimit: 700,
  },
  server: { proxy: { '/api': { target: api, ws: true, changeOrigin: false } } },
  test: { include: ['tests/unit/**/*.test.ts'], environment: 'node' },
});
