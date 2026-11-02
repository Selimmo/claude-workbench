import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The built page ships inside the Python package, which serves it.
export default defineConfig({
  plugins: [react()],
  // ELK alone is ~1.5 MB; it is served locally and loaded lazily, so the warning is noise.
  build: { outDir: '../src/plan_review/static', emptyOutDir: true, chunkSizeWarningLimit: 2000 },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'] },
})
