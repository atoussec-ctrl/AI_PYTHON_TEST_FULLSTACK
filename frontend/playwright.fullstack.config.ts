import { defineConfig, devices } from '@playwright/test'
import { mkdirSync, rmSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const backendRoot = path.resolve(frontendRoot, '../backend')
const runtimeRoot = path.resolve(frontendRoot, '.cache/fullstack-e2e')
// This directory contains only disposable state owned by this Playwright
// configuration. A file-backed database gives concurrent Flask requests
// independent SQLite connections; the in-memory unit-test database cannot.
// Playwright loads this config again inside its worker. The marker is inherited
// by that worker and prevents it from deleting the database while Flask has it
// open; a new top-level test run has no marker and starts from a clean slate.
const runtimeMarker = 'MINDSIGHT_FULLSTACK_RUNTIME'
if (process.env[runtimeMarker] !== runtimeRoot) {
  rmSync(runtimeRoot, { recursive: true, force: true })
  mkdirSync(runtimeRoot, { recursive: true })
  process.env[runtimeMarker] = runtimeRoot
}
const testDatabasePath = path.join(runtimeRoot, 'app.db').replaceAll('\\', '/')
const testUploadDir = path.join(runtimeRoot, 'uploads')
const backendPython =
  process.env.PLAYWRIGHT_BACKEND_PYTHON ??
  (process.platform === 'win32'
    ? '.\\.venv\\Scripts\\python.exe'
    : './.venv/bin/python')

export default defineConfig({
  testDir: './e2e-fullstack',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:3003',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${backendPython} run.py`,
      cwd: backendRoot,
      url: 'http://127.0.0.1:5001/api/v1/health',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        APP_ENV: 'testing',
        TEST_DATABASE_URL: `sqlite:///${testDatabasePath}`,
        TEST_UPLOAD_DIR: testUploadDir,
        HOST: '127.0.0.1',
        PORT: '5001',
        FLASK_DEBUG: '0',
      },
    },
    {
      command: 'pnpm dev --host 127.0.0.1 --port 3003',
      cwd: frontendRoot,
      url: 'http://127.0.0.1:3003',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        VITE_API_BASE_URL: '/api/v1',
        VITE_API_PROXY_TARGET: 'http://127.0.0.1:5001',
      },
    },
  ],
  projects: [
    {
      name: 'chromium-fullstack',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
