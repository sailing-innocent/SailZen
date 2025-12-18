import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { nodePolyfills } from 'vite-plugin-node-polyfills';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    nodePolyfills({
      // Whether to polyfill `node:` protocol imports.
      protocolImports: true,
      // Use globals to avoid import resolution issues
      globals: {
        process: true,
      },
    }),
  ],
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
    alias: {
      // Fix for vite-plugin-node-polyfills shim imports - map to process package
      'vite-plugin-node-polyfills/shims/process': 'process',
    },
  },
  server: {
    port: 4000,
    open: true,
    strictPort: false,
  },
  build: {
    outDir: 'build',
    sourcemap: true,
    rollupOptions: {
      output: {
        entryFileNames: 'static/js/index.bundle.js',
        chunkFileNames: 'static/js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) {
            return 'static/css/[name]-[hash][extname]';
          }
          return 'static/[ext]/[name]-[hash][extname]';
        },
      },
    },
  },
  publicDir: 'public',
  base: '/',
});
