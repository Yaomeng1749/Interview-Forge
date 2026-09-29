import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 20_000,
  fullyParallel: true,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: { command: 'npm run dev -- --port 4173', url: 'http://127.0.0.1:4173', reuseExistingServer: true },
})
