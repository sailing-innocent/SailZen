import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { nodePolyfills } from 'vite-plugin-node-polyfills';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    nodePolyfills({
      // Only include necessary polyfills
      include: ['events', 'buffer', 'util', 'stream', 'path'],
      // Don't use shims for process - define it globally instead
      globals: {
        process: false,  // Disable process shim
        Buffer: true,
      },
    }),
  ],
  define: {
    // Define process globally to avoid shim issues
    'process.env': {},
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'development'),
    'process.browser': true,
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
  },
  // Optimize dependencies to handle CommonJS/ESM compatibility
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-redux',
      '@reduxjs/toolkit',
      'redux-logger',
      'antd',
      'lodash',
      'dayjs',
      'mermaid',
      '@saili/common-all',
    ],
    // Exclude server-only packages that have Node.js dependencies
    exclude: ['@saili/common-server'],
    // Force re-optimization when workspace dependencies change
    force: true,
    esbuildOptions: {
      keepNames: true,
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
    // Ensure CSS is extracted to a single file
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        // Fixed output names for vscode_plugin integration
        entryFileNames: 'static/js/index.bundle.js',
        chunkFileNames: 'static/js/[name]-[hash].js',
        // Use fixed CSS name: index.styles.css (required by vscode_plugin)
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) {
            return 'static/css/index.styles.css';
          }
          return 'static/[ext]/[name]-[hash][extname]';
        },
      },
    },
  },
  publicDir: 'public',
  base: './',  // Use relative paths for VSCode webview compatibility
});
