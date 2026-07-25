import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const rootEnvDir = path.resolve(__dirname, '..')

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // The repository intentionally has one root .env. Loading only the VITE_
  // namespace here keeps backend secrets out of the browser configuration.
  const env = loadEnv(mode, rootEnvDir, 'VITE_')

  return {
    envDir: rootEnvDir,
    // VITE_BASE_URL is set by the deploy workflow for GitHub Pages.
    base: process.env.VITE_BASE_URL ?? env.VITE_BASE_URL ?? '/',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3002,
      strictPort: true,
      watch: {
        ignored: [
          '**/dist/**',
          '**/storybook-static/**',
          '**/coverage/**',
          '**/test-results/**',
        ],
      },
      proxy: {
        '/api': {
          target:
            process.env.VITE_API_PROXY_TARGET ??
            env.VITE_API_PROXY_TARGET ??
            'http://localhost:5000',
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: true,
      include: ['src/**/*.test.{ts,tsx}'],
      exclude: ['node_modules', 'dist', 'e2e'],
      // Keep CI and developer machines responsive while the jsdom suites run.
      // Vitest otherwise consumes all available worker parallelism by default.
      maxWorkers: 4,
      coverage: {
        provider: 'v8',
        reporter: ['text', 'text-summary'],
        include: ['src/**/*.{ts,tsx}'],
        exclude: [
          'src/**/*.test.{ts,tsx}',
          'src/test/**',
          'src/**/*.stories.tsx',
          // main.tsx is the composition root; behavior is exercised through App.
          'src/main.tsx',
          // types.ts contains only TypeScript type declarations — no executable code to cover
          'src/shared/api/types.ts',
          'src/shared/api/schema.d.ts',
        ],
        // These thresholds cover every executable production module. The old
        // 90%+ gate omitted App, hooks and UI components, producing a much less
        // meaningful number over only a curated subset of the application.
        thresholds: {
          lines: 84,
          functions: 80,
          branches: 80,
          statements: 82,
        },
      },
    },
  }
})
