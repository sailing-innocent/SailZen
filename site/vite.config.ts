import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from "@tailwindcss/vite"
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
  base: './',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, 'src'),
      '@lib': resolve(import.meta.dirname, 'src/lib'),
      '@components': resolve(import.meta.dirname, 'src/components'),
      '@pages': resolve(import.meta.dirname, 'src/pages'),
      '@shaders': resolve(import.meta.dirname, 'src/shaders'),
      '@hooks': resolve(import.meta.dirname, 'src/hooks'),
    },
  },
  define: {
    'process.env.SERVER_URL': JSON.stringify(env.SERVER_URL),
    // 可选 Bearer Token（对应后端 SAILZEN_API_TOKEN 鉴权），未设置时为空串不加头
    'process.env.VITE_SAILZEN_API_TOKEN': JSON.stringify(env.VITE_SAILZEN_API_TOKEN ?? ''),
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'bundle.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
}})