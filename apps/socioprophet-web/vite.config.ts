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
      },
      // Prophet Studio → platform services (nginx proxies these same prefixes in prod). Dev targets are
      // overridable via env so `vite dev` can point at port-forwarded services.
      '/svc/hellgraph': { target: process.env.VITE_HELLGRAPH ?? 'http://localhost:8090', changeOrigin: true, rewrite: (p) => p.replace(/^\/svc\/hellgraph/, '') },
      '/svc/reason': { target: process.env.VITE_REASON ?? 'http://localhost:8081', changeOrigin: true, rewrite: (p) => p.replace(/^\/svc\/reason/, '') },
      '/svc/er': { target: process.env.VITE_ER ?? 'http://localhost:8082', changeOrigin: true, rewrite: (p) => p.replace(/^\/svc\/er/, '') },
      '/svc/studio': { target: process.env.VITE_STUDIO ?? 'http://localhost:8083', changeOrigin: true, rewrite: (p) => p.replace(/^\/svc\/studio/, '') },
    }
  }
})
