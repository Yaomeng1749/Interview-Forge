import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/api/guards.ts', 'src/lib/examState.ts', 'src/i18n/i18n.tsx'],
      thresholds: { lines: 80, functions: 80, statements: 80, branches: 80 }
    }
  }
})
