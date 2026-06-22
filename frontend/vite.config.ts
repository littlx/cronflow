import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // 后端 API 端口在 8123 (避开 OrbStack 占用的 8000)
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8123',
        changeOrigin: true,
      },
      '/metrics': {
        target: process.env.VITE_API_URL || 'http://localhost:8123',
        changeOrigin: true,
      },
      '/socket.io': {
        target: process.env.VITE_API_URL || 'http://localhost:8123',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
