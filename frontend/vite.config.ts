import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 개발 중에는 /api를 로컬 FastAPI로 넘긴다. 배포에서는 FastAPI가 dist를 직접 내보낸다.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
