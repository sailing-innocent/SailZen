import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/pipelines': 'http://localhost:8000',
      '/runs': 'http://localhost:8000',
      '/sse': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
