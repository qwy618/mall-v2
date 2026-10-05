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
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8081',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
      // 智能助手（mall-ai-agent，FastAPI :8090）：前端统一走 /ai/**，避免与 portal 的 /api 抢前缀。
      // 助手自身路径是 /api/chat/stream，故 rewrite 把 /ai 补回 /api。
      // 走代理而非直连，是为了开发/生产同一套相对路径，也免去跨域。
      '/ai': {
        target: 'http://localhost:8090',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/ai/, '/api'),
      },
    },
  },
})
