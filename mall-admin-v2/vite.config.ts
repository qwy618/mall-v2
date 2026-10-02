import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 骨架说明：
// 1. '@' 指向 src，避免 ../../ 这种相对路径地狱
// 2. /api 前缀代理到后端 8080，并去掉 /api —— 这样前端写 /api/brand/list，
//    实际打到 http://localhost:8080/brand/list，开发期不需要后端配 CORS
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    open: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // 后台 WebSocket：把 /ws 升级请求转发到 admin 后端 8080（ws:true 透传 upgrade）
      '/ws': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
