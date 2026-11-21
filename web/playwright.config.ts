import { defineConfig, devices } from '@playwright/test';

// All e2e tests run against ONE `madalean serve --demo` started by e2e/global-setup.ts on free ports with a
// temporary config dir (never ~/.config/madalean, never 11500/11501), stopped by global-teardown.ts.
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: [['list']],
  use: { headless: true, trace: 'off', screenshot: 'only-on-failure', locale: 'fr-FR' },
  projects: [
    { name: 'e2e', testIgnore: /perf\.spec|screens\.spec/, use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'screens', testMatch: /screens\.spec/, use: { ...devices['Desktop Chrome'] } },
    { name: 'perf', testMatch: /perf\.spec/, use: { ...devices['Desktop Chrome'] } },
  ],
});
