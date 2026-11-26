import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['frontend'],
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure(proxy) {
          // Vite logs the incoming URL when forwarding fails.
          proxy.on('error', (_error, request) => {
            if (request.url) request.url = request.url.split('?', 1)[0]
          })
        },
      },
    },
  },
})
