import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      // dashboard-bff (VDT / causal-valuation endpoints). Kept separate from the
      // gateway on /api so the two can run independently in local dev.
      '/bff': {
        target: process.env.VITE_BFF_TARGET ?? 'http://localhost:8077',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/bff/, '')
      }
    }
  }
})
