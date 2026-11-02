import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The built page ships inside the Python package, which serves it.
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../src/plan_review/static', emptyOutDir: true },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'] },
})
