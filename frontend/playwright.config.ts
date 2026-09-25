import { defineConfig } from '@playwright/test'

const API_PORT = 8100
const WEB_PORT = 5273

// Values used only by the end-to-end run against a throwaway local database.
export const E2E = {
  adminEmail: 'admin@clinic.test',
  adminPassword: 'e2e admin passphrase',
  baseURL: `http://localhost:${WEB_PORT}`,
}

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: { baseURL: E2E.baseURL, trace: 'retain-on-failure' },
  webServer: [
    {
      command: `uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://localhost:${API_PORT}/api/v1/health`,
      reuseExistingServer: !process.env.CI,
      env: {
        ENV: 'dev',
        JWT_SECRET: 'e2e-secret-e2e-secret-e2e-secret-1234',
        // Deterministic AI stand-in (no network); a symptom containing 'simulate-ai-outage'
        // makes it behave as if the AI were down.
        LLM_PROVIDER: 'fake',
      },
    },
    {
      command: `npm run dev -- --port ${WEB_PORT} --strictPort`,
      url: E2E.baseURL,
      reuseExistingServer: !process.env.CI,
      env: { API_PROXY_TARGET: `http://localhost:${API_PORT}` },
    },
  ],
})
