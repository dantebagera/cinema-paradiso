import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5000',
    browserName: 'chromium',
    headless: true,
    viewport: { width: 1600, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  webServer: {
    command: '.venv\\Scripts\\python.exe app.py',
    url: 'http://127.0.0.1:5000/api/library/status',
    reuseExistingServer: true,
    timeout: 60_000
  }
});
